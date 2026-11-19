"""Meal plan endpoints (PRD §5.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_consent
from app.core.errors import AppError
from app.models import MealPlan, User
from app.schemas import (
    ConfirmVersionRequest,
    GenerateMealPlanRequest,
    PatchMealPlanRequest,
)
from app.services.ai.context import build_context
from app.services.ai.prompts import explain_meal_plan
from app.services.optimizer.service import (
    apply_meal_plan_operations,
    confirm_meal_plan,
    generate_and_save_meal_plan,
    serialize_meal_plan,
)

router = APIRouter(prefix="/meal-plans", tags=["meal_plans"])


def _owned_plan(db: Session, plan_id: str, user_id: str) -> MealPlan:
    plan = db.get(MealPlan, plan_id)
    if not plan or plan.user_id != user_id:
        raise AppError("NOT_FOUND")
    return plan


@router.post("/generate")
def generate_meal_plan_endpoint(
    body: GenerateMealPlanRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    return generate_and_save_meal_plan(
        db,
        user_id=user.id,
        start_date=body.start_date,
        daily_budget_idr=body.daily_budget_idr,
        excluded_food_ids=body.excluded_food_ids,
        source="user",
    )


@router.get("")
def list_meal_plans(
    status: str = "",
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(MealPlan).where(MealPlan.user_id == user.id).order_by(desc(MealPlan.created_at), desc(MealPlan.version))
    if status:
        stmt = stmt.where(MealPlan.status == status)
    rows = db.scalars(stmt).all()
    items = [
        {
            "id": p.id,
            "group_id": p.group_id,
            "version": p.version,
            "parent_id": p.parent_id,
            "status": p.status,
            "result_status": p.result_status,
            "start_date": p.start_date.isoformat(),
            "budget_limit_idr": p.budget_limit_idr,
            "target_energy_kcal": p.target_energy_kcal,
            "target_protein_g": p.target_protein_g,
            "engine_version": p.engine_version,
            "catalog_version": p.catalog_version,
            "created_at": p.created_at.isoformat(),
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
        }
        for p in rows
    ]
    return {"items": items, "total": len(items)}


@router.get("/{plan_id}")
def get_meal_plan(plan_id: str, user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    plan = _owned_plan(db, plan_id, user.id)
    return serialize_meal_plan(db, plan)


@router.patch("/{plan_id}")
def patch_meal_plan(
    plan_id: str,
    body: PatchMealPlanRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    plan = _owned_plan(db, plan_id, user.id)
    ops = [op.model_dump(exclude_none=True) for op in body.operations]
    return apply_meal_plan_operations(db, plan=plan, base_version=body.base_version, operations=ops, source="user")


@router.post("/{plan_id}/confirm")
def confirm_meal_plan_endpoint(
    plan_id: str,
    body: ConfirmVersionRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    plan = _owned_plan(db, plan_id, user.id)
    return confirm_meal_plan(db, plan, body.base_version)


@router.get("/{plan_id}/shopping-list")
def get_shopping_list(plan_id: str, user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    plan = _owned_plan(db, plan_id, user.id)
    data = serialize_meal_plan(db, plan)
    return {"plan_id": plan.id, "version": plan.version, "items": data["shopping_list"]}


@router.get("/{plan_id}/explanation")
def get_meal_plan_explanation(plan_id: str, user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    plan = _owned_plan(db, plan_id, user.id)
    ctx = build_context(db, user.id)
    return {
        "plan_id": plan.id,
        "version": plan.version,
        "explanation_source": "template",
        "explanation": explain_meal_plan(ctx),
    }

