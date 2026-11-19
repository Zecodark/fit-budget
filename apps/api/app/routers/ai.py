"""AI chat, status, history, and proposal endpoints (PRD §6.3–6.8)."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import latest_consent, require_consent
from app.core.errors import AppError
from app.core.logging import get_logger
from app.models import AICache, AIInteraction, AIProposal, ChatMessage, User, new_id
from app.schemas import ChatRequest, ConfirmVersionRequest
from app.services.ai.context import build_context
from app.services.ai.guardrails import (
    check_number_whitelist,
    has_banned_output,
    matches_safety_keyword,
)
from app.services.ai.prompts import (
    SAFETY_RESPONSE_TEXT,
    SYSTEM_PROMPT,
    LLMResponse,
    explain_meal_plan,
    explain_nutrition,
    explain_prices,
    explain_workout,
)
from app.services.ai.proposals import (
    confirm_proposal,
    resolve_and_create_proposal,
    serialize_proposal,
)
from app.services.ai.providers import (
    AIInvalidOutput,
    AITimeout,
    AIUnavailable,
    resolve_provider,
)

router = APIRouter(prefix="/ai", tags=["ai"])
log = get_logger("ai")

_consecutive_fails: int = 0
_circuit_open_until: float = 0.0


def reset_circuit_breaker() -> None:
    global _consecutive_fails, _circuit_open_until
    _consecutive_fails = 0
    _circuit_open_until = 0.0


def _record_failure() -> None:
    global _consecutive_fails, _circuit_open_until
    s = get_settings()
    _consecutive_fails += 1
    if _consecutive_fails >= s.ai_circuit_fails:
        _circuit_open_until = time.monotonic() + s.ai_circuit_open_seconds


def _record_success() -> None:
    global _consecutive_fails
    _consecutive_fails = 0


def _fallback_template(intent: str, ctx: dict[str, Any], user_msg: str) -> str:
    if intent == "explain_workout":
        return explain_workout(ctx)
    if intent == "explain_nutrition":
        return explain_nutrition(ctx)
    if intent == "price_question":
        return explain_prices(ctx, user_msg)
    return explain_meal_plan(ctx)


def _log_interaction(
    db: Session,
    *,
    user_id: str,
    provider: str,
    model: str,
    intent: str | None,
    status: str,
    latency_ms: int,
    tokens_in: int | None,
    tokens_out: int | None,
    request_id: str,
) -> None:
    db.add(
        AIInteraction(
            id=new_id(),
            user_id=user_id,
            provider=provider,
            model=model,
            intent=intent,
            status=status,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            request_id=request_id,
        )
    )
    db.flush()
    log.info(
        "ai_interaction",
        request_id=request_id,
        provider=provider,
        model=model,
        intent=intent,
        status=status,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


@router.get("/status")
def get_ai_status(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    provider = resolve_provider()
    if provider is None or (s.ai_provider or "none").lower() == "none":
        return {"available": False, "provider": "none", "degraded_reason": "AI_PROVIDER=none"}
    if time.monotonic() < _circuit_open_until:
        return {"available": False, "provider": provider.name, "degraded_reason": "circuit_open"}
    if provider.name == "gemini":
        c = latest_consent(db, user.id)
        if not c or not c.ai_cloud:
            return {"available": False, "provider": "gemini", "degraded_reason": "ai_cloud_consent_required"}
        if not s.gemini_api_key:
            return {"available": False, "provider": "gemini", "degraded_reason": "missing_api_key"}
    return {"available": True, "provider": provider.name, "degraded_reason": None}


@router.post("/chat")
async def post_chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    s = get_settings()
    req_id = getattr(request.state, "request_id", "") or ""
    provider = resolve_provider()

    # Step 1: check AI_PROVIDER != none and cloud consent
    if provider is None or (s.ai_provider or "none").lower() == "none":
        raise AppError("AI_UNAVAILABLE")
    if provider.name == "gemini":
        c = latest_consent(db, user.id)
        if not c or not c.ai_cloud:
            raise AppError("AI_CONSENT_REQUIRED")

    # Step 2: rate limit per hour from ai_interactions
    since = datetime.now(UTC) - timedelta(hours=1)
    used_hour = db.scalar(
        select(func.count(AIInteraction.id)).where(
            AIInteraction.user_id == user.id,
            AIInteraction.created_at >= since,
        )
    )
    if (used_hour or 0) >= s.ai_rate_limit_per_hour:
        raise AppError("AI_RATE_LIMIT")

    # Step 3: circuit breaker
    if time.monotonic() < _circuit_open_until:
        raise AppError("AI_UNAVAILABLE", "Asisten AI sementara dinonaktifkan karena gangguan penyedia.")

    conv_id = body.conversation_id or new_id()
    user_text = body.message.strip()

    # Step 4: safety keyword guard (pre-LLM — MUST NOT call provider, PRD §6.6 #3, A11)
    if matches_safety_keyword(user_text):
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=SAFETY_RESPONSE_TEXT,
            intent="safety_redirect",
            meta_json={"explanation_source": "safety", "references": []},
        )
        db.add(asst)
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent="safety_redirect",
            status="safety",
            latency_ms=0,
            tokens_in=0,
            tokens_out=0,
            request_id=req_id,
        )
        return {
            "conversation_id": conv_id,
            "message": {
                "id": asst.id,
                "role": "assistant",
                "content": SAFETY_RESPONSE_TEXT,
                "intent": "safety_redirect",
                "explanation_source": "safety",
                "references": [],
                "warnings": [],
            },
            "proposal": None,
            "missing_params": [],
            "candidates": [],
        }

    # Step 6: build whitelisted context
    ctx = build_context(db, user.id)
    mp_v = (ctx.get("meal_plan") or {}).get("version", 0)
    wp_v = (ctx.get("workout_plan") or {}).get("version", 0)
    norm_msg = " ".join(user_text.lower().split())
    cache_key = hashlib.sha256(f"{user.id}:{mp_v}:{wp_v}:{norm_msg}".encode()).hexdigest()

    # Step 5: cache lookup for pure explanation repeats
    cached = db.get(AICache, cache_key)
    if cached:
        payload = cached.response_json
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=payload["content"],
            intent=payload["intent"],
            meta_json=payload.get("meta", {}),
        )
        db.add(asst)
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent=payload["intent"],
            status="cache",
            latency_ms=0,
            tokens_in=0,
            tokens_out=0,
            request_id=req_id,
        )
        return {
            "conversation_id": conv_id,
            "message": {
                "id": asst.id,
                "role": "assistant",
                "content": payload["content"],
                "intent": payload["intent"],
                "explanation_source": payload.get("explanation_source", "llm"),
                "references": payload.get("references", []),
                "warnings": payload.get("warnings", []),
            },
            "proposal": None,
            "missing_params": [],
            "candidates": [],
        }

    # History (<= AI_MAX_HISTORY_MESSAGES)
    hist_rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id, ChatMessage.conversation_id == conv_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(s.ai_max_history_messages)
    ).all()
    hist_msgs = [{"role": r.role, "content": r.content} for r in reversed(hist_rows)]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "KONTEKS_JSON:\n" + json.dumps(ctx, ensure_ascii=False)},
        *hist_msgs,
        {"role": "user", "content": user_text},
    ]
    schema = LLMResponse.model_json_schema()

    # Step 7: call provider
    try:
        res = await provider.chat(messages, schema, s.ai_timeout_seconds)
        _record_success()
    except AITimeout as exc:
        _record_failure()
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent=None,
            status="timeout",
            latency_ms=int(s.ai_timeout_seconds * 1000),
            tokens_in=None,
            tokens_out=None,
            request_id=req_id,
        )
        db.commit()
        raise AppError("AI_UNAVAILABLE", "Asisten AI melebihi batas waktu.") from exc
    except AIUnavailable as exc:
        _record_failure()
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent=None,
            status="error",
            latency_ms=0,
            tokens_in=None,
            tokens_out=None,
            request_id=req_id,
        )
        db.commit()
        raise AppError("AI_UNAVAILABLE") from exc
    except AIInvalidOutput:
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent="explain_plan",
            status="invalid_output",
            latency_ms=0,
            tokens_in=None,
            tokens_out=None,
            request_id=req_id,
        )
        fallback_text = explain_meal_plan(ctx)
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=fallback_text,
            intent="explain_plan",
            meta_json={"explanation_source": "template"},
        )
        db.add(asst)
        db.flush()
        return {
            "conversation_id": conv_id,
            "message": {
                "id": asst.id,
                "role": "assistant",
                "content": fallback_text,
                "intent": "explain_plan",
                "explanation_source": "template",
                "references": ["meal_plan", "targets"],
                "warnings": [],
            },
            "proposal": None,
            "missing_params": [],
            "candidates": [],
        }

    # Step 8: validate Pydantic schema
    try:
        llm_out = LLMResponse.model_validate(res.parsed)
    except Exception:
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent="explain_plan",
            status="invalid_output",
            latency_ms=res.latency_ms,
            tokens_in=res.tokens_in,
            tokens_out=res.tokens_out,
            request_id=req_id,
        )
        fallback_text = explain_meal_plan(ctx)
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=fallback_text,
            intent="explain_plan",
            meta_json={"explanation_source": "template"},
        )
        db.add(asst)
        db.flush()
        return {
            "conversation_id": conv_id,
            "message": {
                "id": asst.id,
                "role": "assistant",
                "content": fallback_text,
                "intent": "explain_plan",
                "explanation_source": "template",
                "references": ["meal_plan", "targets"],
                "warnings": [],
            },
            "proposal": None,
            "missing_params": [],
            "candidates": [],
        }

    valid_refs = [r for r in llm_out.references if r in ctx and ctx.get(r) is not None]
    explanation = llm_out.explanation
    intent: str = llm_out.intent
    explanation_source = "llm"
    interaction_status = "ok"
    missing_params = list(llm_out.missing_params)
    candidates: list[str] = []
    proposal_obj: AIProposal | None = None

    # Resolve proposal parameters first (may add proposal numbers to whitelist or downgrade to clarification_needed)
    extra_facts: list[float] = []
    if llm_out.proposed_changes:
        pc = llm_out.proposed_changes[0]
        if pc.type == "change_budget" and isinstance(pc.params.get("daily_budget_idr"), int):
            extra_facts.append(float(pc.params["daily_budget_idr"]))
        proposal_obj, miss, cands, clar_msg = resolve_and_create_proposal(
            db, user_id=user.id, conversation_id=conv_id, prop_type=pc.type, params=pc.params
        )
        if proposal_obj is None:
            intent = "clarification_needed"
            missing_params = miss
            candidates = cands
            if clar_msg:
                explanation = clar_msg
                explanation_source = "template"

    # Content ban & Number whitelist guardrails (PRD §6.6 #1 & #2)
    if has_banned_output(explanation):
        explanation = SAFETY_RESPONSE_TEXT
        intent = "safety_redirect"
        explanation_source = "safety"
        interaction_status = "fallback_template"
    elif explanation_source == "llm" and not check_number_whitelist(
        explanation, list(ctx["facts_numbers"]) + extra_facts
    ):
        explanation = _fallback_template(intent, ctx, user_text)
        explanation_source = "template"
        interaction_status = "fallback_template"

    db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
    asst = ChatMessage(
        id=new_id(),
        user_id=user.id,
        conversation_id=conv_id,
        role="assistant",
        content=explanation,
        intent=intent,
        meta_json={"explanation_source": explanation_source, "references": valid_refs},
    )
    db.add(asst)
    _log_interaction(
        db,
        user_id=user.id,
        provider=provider.name,
        model=provider.model,
        intent=intent,
        status=interaction_status,
        latency_ms=res.latency_ms,
        tokens_in=res.tokens_in,
        tokens_out=res.tokens_out,
        request_id=req_id,
    )

    if proposal_obj is None and intent in ("explain_plan", "explain_nutrition", "explain_workout", "price_question"):
        if not db.get(AICache, cache_key):
            db.add(
                AICache(
                    key=cache_key,
                    user_id=user.id,
                    response_json={
                        "content": explanation,
                        "intent": intent,
                        "explanation_source": explanation_source,
                        "references": valid_refs,
                        "warnings": llm_out.warnings,
                    },
                )
            )
    db.flush()

    return {
        "conversation_id": conv_id,
        "message": {
            "id": asst.id,
            "role": "assistant",
            "content": explanation,
            "intent": intent,
            "explanation_source": explanation_source,
            "references": valid_refs,
            "warnings": llm_out.warnings,
        },
        "proposal": serialize_proposal(proposal_obj) if proposal_obj else None,
        "missing_params": missing_params,
        "candidates": candidates,
    }


@router.get("/history")
def get_chat_history(
    conversation_id: str = "",
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(ChatMessage).where(ChatMessage.user_id == user.id).order_by(ChatMessage.created_at)
    if conversation_id:
        stmt = stmt.where(ChatMessage.conversation_id == conversation_id)
    msgs = db.scalars(stmt).all()
    p_stmt = select(AIProposal).where(AIProposal.user_id == user.id).order_by(desc(AIProposal.created_at))
    if conversation_id:
        p_stmt = p_stmt.where(AIProposal.conversation_id == conversation_id)
    props = db.scalars(p_stmt).all()
    return {
        "items": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "intent": m.intent,
                "explanation_source": (m.meta_json or {}).get("explanation_source", "llm"),
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
        "proposals": [serialize_proposal(p) for p in props],
        "total": len(msgs),
    }


@router.post("/proposals/{proposal_id}/confirm")
def confirm_proposal_endpoint(
    proposal_id: str,
    body: ConfirmVersionRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    return confirm_proposal(db, user_id=user.id, proposal_id=proposal_id, base_version=body.base_version)


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal_endpoint(
    proposal_id: str,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    prop = db.get(AIProposal, proposal_id)
    if not prop or prop.user_id != user.id:
        raise AppError("NOT_FOUND")
    if prop.status != "pending":
        raise AppError("CONFLICT", "Usulan sudah diproses sebelumnya.")
    prop.status = "rejected"
    prop.resolved_at = datetime.now(UTC)
    db.flush()
    return {"proposal": serialize_proposal(prop)}

