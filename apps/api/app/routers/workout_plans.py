"""Workout plan & session endpoints (PRD §5.6)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_consent
from app.core.errors import AppError
from app.models import User, WorkoutPlan, WorkoutSession, WorkoutSessionExercise
from app.schemas import (
    GenerateWorkoutPlanRequest,
    PatchWorkoutPlanRequest,
    PatchWorkoutSessionRequest,
    SwapExerciseRequest,
)
from app.services.workout.service import (
    confirm_workout_plan,
    generate_and_save_workout_plan,
    reschedule_workout_sessions,
    serialize_workout_plan,
    swap_session_exercise,
)

router = APIRouter(tags=["workout_plans"])


def _owned_plan(db: Session, plan_id: str, user_id: str) -> WorkoutPlan:
    p = db.get(WorkoutPlan, plan_id)
    if not p or p.user_id != user_id:
        raise AppError("NOT_FOUND")
    return p


def _owned_session(db: Session, session_id: str, user_id: str) -> WorkoutSession:
    s = db.get(WorkoutSession, session_id)
    if not s or not s.plan or s.plan.user_id != user_id:
        raise AppError("NOT_FOUND")
    return s


@router.post("/workout-plans/generate")
def generate_workout_endpoint(
    body: GenerateWorkoutPlanRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    return generate_and_save_workout_plan(
        db,
        user_id=user.id,
        week_start=body.week_start,
        equipment_access=body.equipment_access,
    )


@router.get("/workout-plans")
def list_workout_plans(
    week_start: date | None = None,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(WorkoutPlan).where(WorkoutPlan.user_id == user.id).order_by(desc(WorkoutPlan.created_at))
    if week_start:
        stmt = stmt.where(WorkoutPlan.week_start == week_start)
    rows = db.scalars(stmt).all()
    return {"items": [serialize_workout_plan(db, r) for r in rows], "total": len(rows)}


@router.get("/workout-plans/{plan_id}")
def get_workout_plan(plan_id: str, user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    p = _owned_plan(db, plan_id, user.id)
    return serialize_workout_plan(db, p)


@router.patch("/workout-plans/{plan_id}")
def patch_workout_plan(
    plan_id: str,
    body: PatchWorkoutPlanRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    p = _owned_plan(db, plan_id, user.id)
    moves = [{"session_id": m.session_id, "new_date": m.new_date} for m in body.moves]
    return reschedule_workout_sessions(db, plan=p, base_version=body.base_version, moves=moves, source="user")


@router.post("/workout-plans/{plan_id}/confirm")
def confirm_workout_endpoint(
    plan_id: str,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    p = _owned_plan(db, plan_id, user.id)
    return confirm_workout_plan(db, p)


@router.patch("/workout-sessions/{session_id}")
def patch_workout_session(
    session_id: str,
    body: PatchWorkoutSessionRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    s = _owned_session(db, session_id, user.id)
    s.status = body.status
    s.completed_at = datetime.now(UTC) if body.status == "completed" else None
    s.plan.version += 1
    db.flush()
    db.refresh(s.plan)
    return serialize_workout_plan(db, s.plan)


@router.patch("/workout-sessions/{session_id}/exercises/{item_id}")
def patch_session_exercise(
    session_id: str,
    item_id: str,
    body: SwapExerciseRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    s = _owned_session(db, session_id, user.id)
    item = db.get(WorkoutSessionExercise, item_id)
    if not item or item.session_id != s.id:
        raise AppError("NOT_FOUND")
    return swap_session_exercise(db, user_id=user.id, session=s, item=item, new_exercise_id=body.exercise_id)

