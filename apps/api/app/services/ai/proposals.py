"""AI proposal validation, parameter resolution, deterministic preview, and confirmation (PRD §6.5)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import as_utc
from app.core.errors import AppError
from app.models import (
    AIProposal,
    Food,
    FoodAlias,
    MealPlan,
    Preferences,
    WorkoutPlan,
    new_id,
)
from app.services.optimizer.service import generate_and_save_meal_plan
from app.services.workout.engine import recovery_ok
from app.services.workout.service import reschedule_workout_sessions

PROPOSAL_TTL_MINUTES = 30


def _active_meal_plan(db: Session, user_id: str) -> MealPlan | None:
    return db.scalar(
        select(MealPlan)
        .where(MealPlan.user_id == user_id, MealPlan.status.in_(("confirmed", "draft")))
        .order_by(desc(MealPlan.status == "confirmed"), desc(MealPlan.created_at))
        .limit(1)
    )


def _active_workout_plan(db: Session, user_id: str) -> WorkoutPlan | None:
    return db.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == user_id, WorkoutPlan.status.in_(("confirmed", "draft")))
        .order_by(desc(WorkoutPlan.status == "confirmed"), desc(WorkoutPlan.created_at))
        .limit(1)
    )


def match_food_by_name(db: Session, raw_name: str) -> tuple[Food | None, list[str]]:
    q = (raw_name or "").strip().lower()
    if not q:
        return None, []
    foods = db.scalars(select(Food).where(Food.is_active.is_(True))).all()
    aliases = db.scalars(select(FoodAlias)).all()
    by_id = {f.id: f for f in foods}

    for f in foods:
        if f.code.lower() == q or f.name.lower() == q:
            return f, [f.name]
    for al in aliases:
        if al.alias.lower() == q and al.food_id in by_id:
            f = by_id[al.food_id]
            return f, [f.name]

    substr_hits: dict[str, Food] = {}
    for f in foods:
        if q in f.name.lower() or f.name.lower() in q:
            substr_hits[f.id] = f
    for al in aliases:
        if q in al.alias.lower() and al.food_id in by_id:
            substr_hits[al.food_id] = by_id[al.food_id]

    if len(substr_hits) == 1:
        only = next(iter(substr_hits.values()))
        return only, [only.name]
    if len(substr_hits) > 1:
        return None, sorted(f.name for f in substr_hits.values())
    return None, []


def resolve_and_create_proposal(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    prop_type: str,
    params: dict[str, Any],
) -> tuple[AIProposal | None, list[str], list[str], str | None]:
    """Returns (proposal, missing_params, candidates, clarification_message)."""
    pref = db.get(Preferences, user_id)
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=PROPOSAL_TTL_MINUTES)

    if prop_type == "change_budget":
        raw_b = params.get("daily_budget_idr")
        try:
            budget = int(raw_b)
        except Exception:
            return None, ["daily_budget_idr"], [], "Sebutkan nominal budget harian dalam rupiah (10.000–500.000)."
        if budget < 10_000 or budget > 500_000:
            return (
                None,
                ["daily_budget_idr"],
                [],
                "Budget harian harus antara Rp10.000 dan Rp500.000. Sebutkan nominal dalam rentang tersebut.",
            )
        mp = _active_meal_plan(db, user_id)
        start_d = mp.start_date if mp else date.today()
        dry = generate_and_save_meal_plan(
            db, user_id=user_id, start_date=start_d, daily_budget_idr=budget, dry_run=True
        )
        preview = {
            "daily_budget_idr": budget,
            "result_status": dry["result_status"],
            "week_cost_idr": dry["week_totals"]["cost_idr"],
            "unmet_count": len(dry.get("unmet_constraints") or []),
            "minimum_budget_required_idr": dry.get("minimum_budget_required_idr"),
        }
        prop = AIProposal(
            id=new_id(),
            user_id=user_id,
            conversation_id=conversation_id,
            type="change_budget",
            params_json={"daily_budget_idr": budget},
            preview_json=preview,
            base_plan_type="meal" if mp else None,
            base_plan_id=mp.id if mp else None,
            base_version=mp.version if mp else 0,
            status="pending",
            expires_at=expires,
        )
        db.add(prop)
        db.flush()
        return prop, [], [], None

    if prop_type == "exclude_food":
        raw_name = str(params.get("food_name") or "").strip()
        if not raw_name:
            return None, ["food_name"], [], "Sebutkan nama bahan pangan yang ingin dikecualikan."
        matched, candidates = match_food_by_name(db, raw_name)
        if not matched:
            msg = (
                f"Nama pangan '{raw_name}' ambigu ({', '.join(candidates)}). Pilih salah satu dengan lebih spesifik."
                if candidates
                else f"Bahan '{raw_name}' tidak ditemukan di katalog. Sebutkan nama bahan lain dari katalog."
            )
            return None, ["food_name"], candidates, msg
        mp = _active_meal_plan(db, user_id)
        start_d = mp.start_date if mp else date.today()
        cur_excl = list(set((pref.excluded_food_ids if pref else []) or []) | {matched.id})
        dry = generate_and_save_meal_plan(
            db, user_id=user_id, start_date=start_d, excluded_food_ids=cur_excl, dry_run=True
        )
        preview = {
            "food_id": matched.id,
            "food_name": matched.name,
            "result_status": dry["result_status"],
            "week_cost_idr": dry["week_totals"]["cost_idr"],
            "unmet_count": len(dry.get("unmet_constraints") or []),
        }
        prop = AIProposal(
            id=new_id(),
            user_id=user_id,
            conversation_id=conversation_id,
            type="exclude_food",
            params_json={"food_id": matched.id, "food_name": matched.name},
            preview_json=preview,
            base_plan_type="meal" if mp else None,
            base_plan_id=mp.id if mp else None,
            base_version=mp.version if mp else 0,
            status="pending",
            expires_at=expires,
        )
        db.add(prop)
        db.flush()
        return prop, [], [], None

    if prop_type == "reschedule_workout":
        from_s = str(params.get("from_date") or "").strip()
        to_s = str(params.get("to_date") or "").strip()
        try:
            from_d = date.fromisoformat(from_s)
            to_d = date.fromisoformat(to_s)
        except Exception:
            return None, ["from_date", "to_date"], [], "Sebutkan tanggal sesi asal dan tujuan (YYYY-MM-DD)."
        wp = _active_workout_plan(db, user_id)
        if not wp:
            return None, ["workout_plan"], [], "Anda belum memiliki jadwal latihan aktif."
        sess = next((s for s in wp.sessions if s.date == from_d), None)
        if not sess:
            return None, ["from_date"], [], f"Tidak ada sesi latihan pada tanggal {from_s}."
        conflict = any(s.date == to_d and s.id != sess.id for s in wp.sessions)
        sim_dates = sorted(to_d if s.id == sess.id else s.date for s in wp.sessions)
        wds = tuple((d - wp.week_start).days for d in sim_dates)
        tmpls = [s.template_code for s in sorted(wp.sessions, key=lambda x: to_d if x.id == sess.id else x.date)]
        rec_warn = not recovery_ok(wds, tmpls)
        preview = {
            "session_id": sess.id,
            "from_date": from_s,
            "to_date": to_s,
            "conflict": conflict,
            "recovery_warning": rec_warn,
        }
        prop = AIProposal(
            id=new_id(),
            user_id=user_id,
            conversation_id=conversation_id,
            type="reschedule_workout",
            params_json={"session_id": sess.id, "from_date": from_s, "to_date": to_s},
            preview_json=preview,
            base_plan_type="workout",
            base_plan_id=wp.id,
            base_version=wp.version,
            status="pending",
            expires_at=expires,
        )
        db.add(prop)
        db.flush()
        return prop, [], [], None

    return None, [], [], None


def serialize_proposal(p: AIProposal) -> dict[str, Any]:
    return {
        "id": p.id,
        "conversation_id": p.conversation_id,
        "type": p.type,
        "params": p.params_json,
        "preview": p.preview_json,
        "base_plan_type": p.base_plan_type,
        "base_plan_id": p.base_plan_id,
        "base_version": p.base_version,
        "status": p.status,
        "expires_at": as_utc(p.expires_at).isoformat(),
        "created_at": as_utc(p.created_at).isoformat(),
        "resolved_at": as_utc(p.resolved_at).isoformat() if p.resolved_at else None,
    }


def confirm_proposal(db: Session, *, user_id: str, proposal_id: str, base_version: int) -> dict[str, Any]:
    prop = db.get(AIProposal, proposal_id)
    if not prop or prop.user_id != user_id:
        raise AppError("NOT_FOUND")
    if prop.status != "pending":
        raise AppError("CONFLICT", "Usulan sudah diproses sebelumnya.")
    now = datetime.now(UTC)
    if as_utc(prop.expires_at) <= now:
        prop.status = "expired"
        prop.resolved_at = now
        db.flush()
        raise AppError("PROPOSAL_EXPIRED")

    # Verify current plan version matches both base_version from request and proposal snapshot (PRD §6.5, A5)
    if prop.base_plan_type == "meal":
        cur_mp = db.get(MealPlan, prop.base_plan_id) if prop.base_plan_id else _active_meal_plan(db, user_id)
        cur_ver = cur_mp.version if cur_mp else 0
        if base_version != cur_ver or (prop.base_version is not None and prop.base_version != cur_ver):
            raise AppError("PLAN_VERSION_CONFLICT")
    elif prop.base_plan_type == "workout":
        cur_wp = db.get(WorkoutPlan, prop.base_plan_id) if prop.base_plan_id else _active_workout_plan(db, user_id)
        cur_ver = cur_wp.version if cur_wp else 0
        if base_version != cur_ver or (prop.base_version is not None and prop.base_version != cur_ver):
            raise AppError("PLAN_VERSION_CONFLICT")

    pref = db.get(Preferences, user_id)
    try:
        if prop.type == "change_budget":
            new_b = int(prop.params_json["daily_budget_idr"])
            if pref:
                pref.daily_budget_idr = new_b
            mp = _active_meal_plan(db, user_id)
            start_d = mp.start_date if mp else date.today()
            result = generate_and_save_meal_plan(
                db, user_id=user_id, start_date=start_d, daily_budget_idr=new_b, source="ai_proposal"
            )
            prop.status = "confirmed"
            prop.resolved_at = now
            db.flush()
            return {"proposal": serialize_proposal(prop), "meal_plan": result}

        if prop.type == "exclude_food":
            fid = prop.params_json["food_id"]
            if pref:
                excl = list(pref.excluded_food_ids or [])
                if fid not in excl:
                    excl.append(fid)
                pref.excluded_food_ids = excl
            mp = _active_meal_plan(db, user_id)
            start_d = mp.start_date if mp else date.today()
            result = generate_and_save_meal_plan(
                db,
                user_id=user_id,
                start_date=start_d,
                excluded_food_ids=list(pref.excluded_food_ids) if pref else [fid],
                source="ai_proposal",
            )
            prop.status = "confirmed"
            prop.resolved_at = now
            db.flush()
            return {"proposal": serialize_proposal(prop), "meal_plan": result}

        if prop.type == "reschedule_workout":
            wp = db.get(WorkoutPlan, prop.base_plan_id) if prop.base_plan_id else _active_workout_plan(db, user_id)
            if not wp:
                raise AppError("NOT_FOUND")
            result = reschedule_workout_sessions(
                db,
                plan=wp,
                base_version=base_version,
                moves=[{"session_id": prop.params_json["session_id"], "new_date": prop.params_json["to_date"]}],
                source="ai_proposal",
            )
            prop.status = "confirmed"
            prop.resolved_at = now
            db.flush()
            return {"proposal": serialize_proposal(prop), "workout_plan": result}
    except AppError as exc:
        if exc.code == "NO_FEASIBLE_PLAN":
            prop.status = "failed"
            prop.resolved_at = now
            db.flush()
        raise

    raise AppError("VALIDATION_ERROR", "Tipe usulan tidak dikenal.")

