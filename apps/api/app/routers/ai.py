"""AI chat, status, session management, history, and proposal endpoints (PRD §6.3–6.8)."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, desc, func, select
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
    extract_numbers,
    has_banned_output,
    matches_safety_keyword,
)
from app.services.ai.prompts import (
    SAFETY_RESPONSE_TEXT,
    SYSTEM_PROMPT,
    VALID_INTENTS,
    LLMResponse,
    explain_greeting,
    explain_meal_plan,
    explain_nutrition,
    explain_prices,
    explain_progress,
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

_GREETING_FALLBACK_RE = re.compile(
    r"^(?:hai+|halo+|hello+|hi+|hey+|p+|pagi|selamat\s+(?:pagi|siang|sore|malam)|assalamu'?alaikum|makasih|terima\s+kasih|thanks?)$",
    re.IGNORECASE,
)


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


def _fallback_template(intent: str | None, ctx: dict[str, Any], user_msg: str) -> tuple[str, str]:
    low = (user_msg or "").strip().lower()
    if intent == "general_chat" or _GREETING_FALLBACK_RE.match(low.strip("!?., ")):
        return "general_chat", explain_greeting(ctx)
    if intent == "explain_workout" or (not intent and any(k in low for k in ("latihan", "gym", "workout", "sesi"))):
        return "explain_workout", explain_workout(ctx)
    if intent == "explain_progress" or (not intent and any(k in low for k in ("progres", "progress", "catatan", "riwayat", "tracker"))):
        return "explain_progress", explain_progress(ctx)
    if intent == "explain_nutrition" or (not intent and any(k in low for k in ("kalori", "protein", "tdee", "ree", "nutrisi"))):
        return "explain_nutrition", explain_nutrition(ctx)
    if intent == "price_question" or (not intent and "harga" in low):
        return "price_question", explain_prices(ctx, user_msg)
    return intent or "explain_plan", explain_meal_plan(ctx)


def _normalize_llm_payload(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return raw
    explanation = raw.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        for alt_key in ("response", "message", "reply", "answer", "text", "content"):
            val = raw.get(alt_key)
            if isinstance(val, str) and val.strip():
                explanation = val.strip()
                break
    if not isinstance(explanation, str) or not explanation.strip():
        return raw  # let Pydantic fail so invalid_output is recorded

    raw_intent = raw.get("intent")
    intent = raw_intent if isinstance(raw_intent, str) and raw_intent in VALID_INTENTS else "general_chat"

    raw_changes = raw.get("proposed_changes")
    changes: list[dict[str, Any]] = []
    if isinstance(raw_changes, list):
        for ch in raw_changes[:1]:
            if isinstance(ch, dict) and ch.get("type") in ("change_budget", "exclude_food", "reschedule_workout"):
                p = ch.get("params") if isinstance(ch.get("params"), dict) else {}
                clean_p = {k: v for k, v in p.items() if v is not None and v != ""}
                changes.append({"type": ch["type"], "params": clean_p})

    def _str_list(v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x) for x in v if x is not None and str(x).strip()]

    return {
        "intent": intent,
        "explanation": explanation.strip()[:2500],
        "proposed_changes": changes,
        "references": _str_list(raw.get("references")),
        "warnings": _str_list(raw.get("warnings")),
        "missing_params": _str_list(raw.get("missing_params")),
    }


def _context_fingerprint(ctx: dict[str, Any]) -> str:
    mp = ctx.get("meal_plan") or {}
    wp = ctx.get("workout_plan") or {}
    prog = ctx.get("recent_progress") or {}
    pref = ctx.get("preferences") or {}
    sig = {
        "mp_v": mp.get("version", 0),
        "mp_s": mp.get("status"),
        "wp_v": wp.get("version", 0),
        "wp_s": wp.get("status"),
        "eq": pref.get("equipment_access"),
        "b": (ctx.get("targets") or {}).get("daily_budget_idr"),
        "fl": len(prog.get("food_logs_by_day") or []),
        "wl": len(prog.get("workout_logs") or []),
        "wt": (prog.get("weight_trend") or {}).get("logs_count", 0),
    }
    return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:16]


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

    # Step 6: build whitelisted, multi-segment user context
    ctx = build_context(db, user.id)
    ctx_fp = _context_fingerprint(ctx)
    norm_msg = " ".join(user_text.lower().split())
    cache_key = hashlib.sha256(f"v2:{user.id}:{ctx_fp}:{norm_msg}".encode()).hexdigest()

    # Step 5: cache lookup for pure factual explanation repeats (only if no prior history context makes it follow-up)
    hist_rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id, ChatMessage.conversation_id == conv_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(s.ai_max_history_messages)
    ).all()
    hist_msgs = [{"role": r.role, "content": r.content} for r in reversed(hist_rows)]

    cached = db.get(AICache, cache_key) if len(hist_msgs) == 0 else None
    if cached and (cached.response_json or {}).get("explanation_source") == "llm":
        payload = cached.response_json
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=payload["content"],
            intent=payload["intent"],
            meta_json=payload.get("meta", {"explanation_source": "llm", "references": payload.get("references", [])}),
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

    # Omit facts_numbers from LLM prompt payload to save tokens and reduce noise
    llm_ctx = {k: v for k, v in ctx.items() if k != "facts_numbers"}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "KONTEKS_JSON:\n" + json.dumps(llm_ctx, ensure_ascii=False)},
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
        fb_intent, fallback_text = _fallback_template(None, ctx, user_text)
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent=fb_intent,
            status="invalid_output",
            latency_ms=0,
            tokens_in=None,
            tokens_out=None,
            request_id=req_id,
        )
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=fallback_text,
            intent=fb_intent,
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
                "intent": fb_intent,
                "explanation_source": "template",
                "references": [],
                "warnings": [],
            },
            "proposal": None,
            "missing_params": [],
            "candidates": [],
        }

    # Step 8: normalize & validate Pydantic schema
    try:
        normalized = _normalize_llm_payload(res.parsed)
        llm_out = LLMResponse.model_validate(normalized)
    except Exception:
        fb_intent, fallback_text = _fallback_template(None, ctx, user_text)
        _log_interaction(
            db,
            user_id=user.id,
            provider=provider.name,
            model=provider.model,
            intent=fb_intent,
            status="invalid_output",
            latency_ms=res.latency_ms,
            tokens_in=res.tokens_in,
            tokens_out=res.tokens_out,
            request_id=req_id,
        )
        db.add(ChatMessage(id=new_id(), user_id=user.id, conversation_id=conv_id, role="user", content=user_text))
        asst = ChatMessage(
            id=new_id(),
            user_id=user.id,
            conversation_id=conv_id,
            role="assistant",
            content=fallback_text,
            intent=fb_intent,
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
                "intent": fb_intent,
                "explanation_source": "template",
                "references": [],
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
    extra_facts: list[float] = list(extract_numbers(user_text))
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
        intent, explanation = _fallback_template(intent, ctx, user_text)
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

    if (
        len(hist_msgs) == 0
        and proposal_obj is None
        and interaction_status == "ok"
        and explanation_source == "llm"
        and intent in ("explain_plan", "explain_nutrition", "explain_workout", "explain_progress", "price_question")
    ):
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


@router.get("/conversations")
def list_conversations(
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    msgs = db.scalars(
        select(ChatMessage).where(ChatMessage.user_id == user.id).order_by(ChatMessage.created_at)
    ).all()
    sessions: dict[str, dict[str, Any]] = {}
    for m in msgs:
        s = sessions.get(m.conversation_id)
        if not s:
            s = {
                "conversation_id": m.conversation_id,
                "title": m.content[:60] if m.role == "user" else "Sesi Percakapan",
                "first_user_set": m.role == "user",
                "message_count": 0,
                "last_message_at": m.created_at.isoformat(),
                "last_preview": m.content[:90],
            }
            sessions[m.conversation_id] = s
        elif not s["first_user_set"] and m.role == "user":
            s["title"] = m.content[:60]
            s["first_user_set"] = True
        s["message_count"] += 1
        s["last_message_at"] = m.created_at.isoformat()
        s["last_preview"] = m.content[:90]

    items = [
        {k: v for k, v in s.items() if k != "first_user_set"}
        for s in sorted(sessions.values(), key=lambda x: x["last_message_at"], reverse=True)
    ]
    return {"items": items, "total": len(items)}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        delete(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.conversation_id == conversation_id)
    )
    db.flush()
    return Response(status_code=204)


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
