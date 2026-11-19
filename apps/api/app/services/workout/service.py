"""Workout plan DB orchestration: generate, reschedule, status update, swap exercise, confirm (PRD §3.6, §5.6)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_catalog_version
from app.core.errors import AppError, validation_error
from app.models import (
    Exercise,
    PlanChangeLog,
    Preferences,
    WorkoutPlan,
    WorkoutSession,
    WorkoutSessionExercise,
    new_id,
)
from app.services.optimizer.service import require_user_can_generate
from app.services.workout.engine import ExerciseSpec, generate_workout_plan, recovery_ok
from app.services.workout.templates import DIFFICULTY_LEVEL, ENGINE_VERSION, EQUIPMENT_ALLOWED


def load_exercise_specs(db: Session) -> list[ExerciseSpec]:
    rows = db.scalars(select(Exercise).where(Exercise.is_active.is_(True)).order_by(Exercise.rank, Exercise.code)).all()
    return [
        ExerciseSpec(
            id=r.id,
            code=r.code,
            name=r.name,
            pattern=r.pattern,
            muscle_group=r.muscle_group,
            equipment=r.equipment,
            difficulty=int(r.difficulty),
            rank=int(r.rank),
            sets=int(r.sets),
            reps_min=int(r.reps_min),
            reps_max=int(r.reps_max),
            unit=r.unit,
            rest_s=int(r.rest_s),
            instructions=r.instructions,
            contraindication_notes=r.contraindication_notes,
        )
        for r in rows
    ]


def serialize_workout_plan(db: Session, plan: WorkoutPlan) -> dict[str, Any]:
    ex_map = {e.id: e for e in db.scalars(select(Exercise)).all()}
    sessions_out: list[dict[str, Any]] = []
    for s in sorted(plan.sessions, key=lambda x: x.date):
        ex_out = []
        for item in sorted(s.exercises, key=lambda x: x.position):
            ex = ex_map.get(item.exercise_id)
            ex_out.append(
                {
                    "id": item.id,
                    "position": item.position,
                    "exercise_id": item.exercise_id,
                    "name": ex.name if ex else "Latihan",
                    "pattern": ex.pattern if ex else "",
                    "sets": item.sets,
                    "reps_min": item.reps_min,
                    "reps_max": item.reps_max,
                    "unit": item.unit,
                    "rest_s": item.rest_s,
                    "instructions": ex.instructions if ex else "",
                    "contraindication_notes": ex.contraindication_notes if ex else "",
                    "alternatives": item.alternatives_json or [],
                }
            )
        sessions_out.append(
            {
                "id": s.id,
                "date": s.date.isoformat(),
                "template_code": s.template_code,
                "status": s.status,
                "estimated_minutes": s.estimated_minutes,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "exercises": ex_out,
            }
        )
    return {
        "id": plan.id,
        "week_start": plan.week_start.isoformat(),
        "status": plan.status,
        "version": plan.version,
        "sessions": sessions_out,
        "warnings": plan.warnings_json or [],
        "engine_version": plan.engine_version,
        "catalog_version": plan.catalog_version,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


def generate_and_save_workout_plan(
    db: Session,
    *,
    user_id: str,
    week_start: date,
) -> dict[str, Any]:
    if week_start.weekday() != 0:
        raise validation_error("week_start harus hari Senin.", field="week_start")
    _, pref, _ = require_user_can_generate(db, user_id)
    specs = load_exercise_specs(db)
    gen = generate_workout_plan(
        exercises=specs,
        workout_days=list(pref.workout_days or [0, 2, 4]),
        session_minutes=int(pref.session_minutes or 60),
        experience_level=pref.experience_level or "beginner",
        equipment_access=pref.equipment_access or "gym_full",
        excluded_exercise_ids=set(pref.excluded_exercise_ids or []),
        week_start=week_start,
    )

    cat_ver = get_catalog_version(db)
    plan = WorkoutPlan(
        id=new_id(),
        user_id=user_id,
        week_start=week_start,
        status="draft",
        version=1,
        warnings_json=gen["warnings"],
        params_json={
            "workout_days": pref.workout_days,
            "session_minutes": pref.session_minutes,
            "experience_level": pref.experience_level,
            "equipment_access": pref.equipment_access,
            "excluded_exercise_ids": pref.excluded_exercise_ids,
        },
        engine_version=ENGINE_VERSION,
        catalog_version=cat_ver,
    )
    db.add(plan)
    db.flush()

    for s in gen["sessions"]:
        sess = WorkoutSession(
            id=new_id(),
            plan_id=plan.id,
            date=date.fromisoformat(s["date"]),
            template_code=s["template_code"],
            status="planned",
            estimated_minutes=int(s["estimated_minutes"]),
        )
        db.add(sess)
        db.flush()
        for ex in s["exercises"]:
            db.add(
                WorkoutSessionExercise(
                    id=new_id(),
                    session_id=sess.id,
                    position=int(ex["position"]),
                    exercise_id=ex["exercise_id"],
                    sets=int(ex["sets"]),
                    reps_min=int(ex["reps_min"]),
                    reps_max=int(ex["reps_max"]),
                    unit=ex["unit"],
                    rest_s=int(ex["rest_s"]),
                    alternatives_json=ex["alternatives"],
                )
            )
    db.add(
        PlanChangeLog(
            user_id=user_id,
            plan_type="workout",
            plan_id=plan.id,
            from_version=None,
            to_version=1,
            source="user",
            diff_json={"action": "generate", "week_start": week_start.isoformat()},
        )
    )
    db.flush()
    db.refresh(plan)
    return serialize_workout_plan(db, plan)


def reschedule_workout_sessions(
    db: Session,
    *,
    plan: WorkoutPlan,
    base_version: int,
    moves: list[dict[str, Any]],  # [{session_id, new_date}]
    source: str = "user",
) -> dict[str, Any]:
    if plan.version != base_version:
        raise AppError("PLAN_VERSION_CONFLICT")
    week_end = plan.week_start + timedelta(days=6)
    sess_by_id = {s.id: s for s in plan.sessions}

    # Apply moves to a virtual map first to detect conflicts
    target_dates: dict[str, date] = {s.id: s.date for s in plan.sessions}
    for m in moves:
        sid = m["session_id"]
        nd_raw = m["new_date"]
        nd = nd_raw if isinstance(nd_raw, date) else date.fromisoformat(str(nd_raw))
        if sid not in sess_by_id:
            raise AppError("NOT_FOUND", "Sesi latihan tidak ditemukan.")
        if nd < plan.week_start or nd > week_end:
            raise validation_error("Tanggal baru harus berada pada minggu rencana yang sama.", field="new_date")
        target_dates[sid] = nd

    seen_dates: set[date] = set()
    for d in target_dates.values():
        if d in seen_dates:
            raise AppError("SESSION_CONFLICT", "Sudah ada sesi lain pada tanggal tersebut.")
        seen_dates.add(d)

    for sid, nd in target_dates.items():
        sess_by_id[sid].date = nd

    ordered = sorted(plan.sessions, key=lambda s: s.date)
    wds = tuple((s.date - plan.week_start).days for s in ordered)
    tmpls = [s.template_code for s in ordered]
    warnings = [w for w in (plan.warnings_json or []) if w.get("code") != "RECOVERY_WARNING"]
    if not recovery_ok(wds, tmpls):
        warnings.append(
            {
                "code": "RECOVERY_WARNING",
                "message": "Jadwal baru memiliki sesi tanpa jeda pemulihan ideal; perhatikan istirahat.",
            }
        )

    old_v = plan.version
    plan.version = old_v + 1
    plan.warnings_json = warnings
    db.add(
        PlanChangeLog(
            user_id=plan.user_id,
            plan_type="workout",
            plan_id=plan.id,
            from_version=old_v,
            to_version=plan.version,
            source=source,
            diff_json={
                "moves": [
                    {
                        "session_id": m["session_id"],
                        "new_date": m["new_date"].isoformat()
                        if isinstance(m["new_date"], date)
                        else str(m["new_date"]),
                    }
                    for m in moves
                ]
            },
        )
    )
    db.flush()
    db.refresh(plan)
    return serialize_workout_plan(db, plan)


def swap_session_exercise(
    db: Session,
    *,
    user_id: str,
    session: WorkoutSession,
    item: WorkoutSessionExercise,
    new_exercise_id: str,
) -> dict[str, Any]:
    pref = db.get(Preferences, user_id)
    allowed_eq = EQUIPMENT_ALLOWED.get(pref.equipment_access if pref else "gym_full", {"bodyweight", "dumbbell", "gym"})
    max_diff = DIFFICULTY_LEVEL.get(pref.experience_level if pref else "beginner", 1)

    cur_ex = db.get(Exercise, item.exercise_id)
    new_ex = db.get(Exercise, new_exercise_id)
    if not new_ex or not new_ex.is_active:
        raise validation_error("Latihan pengganti tidak ditemukan.", field="exercise_id")
    if cur_ex and new_ex.pattern != cur_ex.pattern:
        raise validation_error(
            "Latihan pengganti harus memiliki pola gerak (pattern) yang sama.",
            field="exercise_id",
            issue="pattern_mismatch",
        )
    if new_ex.equipment not in allowed_eq or new_ex.difficulty > max_diff:
        raise validation_error(
            "Latihan pengganti tidak sesuai akses alat atau tingkat pengalaman Anda.",
            field="exercise_id",
            issue="equipment_or_difficulty_mismatch",
        )

    item.exercise_id = new_ex.id
    item.sets = int(new_ex.sets)
    item.reps_min = int(new_ex.reps_min)
    item.reps_max = int(new_ex.reps_max)
    item.unit = new_ex.unit
    item.rest_s = int(new_ex.rest_s)

    plan = session.plan
    plan.version += 1
    db.flush()
    db.refresh(plan)
    return serialize_workout_plan(db, plan)


def confirm_workout_plan(db: Session, plan: WorkoutPlan) -> dict[str, Any]:
    prev = db.scalars(
        select(WorkoutPlan).where(
            WorkoutPlan.user_id == plan.user_id,
            WorkoutPlan.week_start == plan.week_start,
            WorkoutPlan.status == "confirmed",
        )
    ).all()
    for p in prev:
        if p.id != plan.id:
            p.status = "archived"
    plan.status = "confirmed"
    plan.updated_at = datetime.now(UTC)
    db.flush()
    db.refresh(plan)
    return serialize_workout_plan(db, plan)

