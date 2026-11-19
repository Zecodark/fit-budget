"""Consent, data export, and account deletion endpoints (PRD §5.2, FR-03)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import CONSENT_TEXT, CONSENT_VERSION, current_user, latest_consent
from app.core.errors import AppError, validation_error
from app.core.security import clear_session_cookie, verify_password
from app.models import (
    AIProposal,
    ChatMessage,
    Consent,
    FoodLog,
    MealPlan,
    NutritionTarget,
    Preferences,
    Profile,
    User,
    WeightLog,
    WorkoutLog,
    WorkoutPlan,
    new_id,
)
from app.schemas import ConsentRequest, DeleteAccountRequest

router = APIRouter(tags=["account"])


@router.get("/consent")
def get_consent(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    c = latest_consent(db, user.id)
    return {
        "consent_version": CONSENT_VERSION,
        "text": CONSENT_TEXT,
        "current": (
            {
                "consent_version": c.consent_version,
                "data_processing": c.data_processing,
                "ai_cloud": c.ai_cloud,
                "created_at": c.created_at.isoformat(),
            }
            if c
            else None
        ),
    }


@router.post("/consent", status_code=201)
def post_consent(body: ConsentRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not body.data_processing:
        raise validation_error(
            "Persetujuan pemrosesan data dasar wajib dicentang untuk menggunakan aplikasi.",
            field="data_processing",
        )
    if body.consent_version != CONSENT_VERSION:
        raise validation_error("Versi consent tidak sesuai.", field="consent_version")
    c = Consent(
        id=new_id(),
        user_id=user.id,
        consent_version=CONSENT_VERSION,
        data_processing=body.data_processing,
        ai_cloud=bool(body.ai_cloud),
    )
    db.add(c)
    db.flush()
    return {
        "id": c.id,
        "consent_version": c.consent_version,
        "data_processing": c.data_processing,
        "ai_cloud": c.ai_cloud,
        "created_at": c.created_at.isoformat(),
    }


@router.get("/account/export")
def export_account(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prof = db.get(Profile, user.id)
    pref = db.get(Preferences, user.id)
    consents = db.scalars(select(Consent).where(Consent.user_id == user.id)).all()
    targets = db.scalars(select(NutritionTarget).where(NutritionTarget.user_id == user.id)).all()
    meal_plans = db.scalars(select(MealPlan).where(MealPlan.user_id == user.id)).all()
    workout_plans = db.scalars(select(WorkoutPlan).where(WorkoutPlan.user_id == user.id)).all()
    food_logs = db.scalars(select(FoodLog).where(FoodLog.user_id == user.id)).all()
    workout_logs = db.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user.id)).all()
    weight_logs = db.scalars(select(WeightLog).where(WeightLog.user_id == user.id)).all()
    chats = db.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id)).all()
    proposals = db.scalars(select(AIProposal).where(AIProposal.user_id == user.id)).all()

    return {
        "user": {"id": user.id, "email": user.email, "role": user.role, "created_at": user.created_at.isoformat()},
        "consents": [
            {
                "id": c.id,
                "consent_version": c.consent_version,
                "data_processing": c.data_processing,
                "ai_cloud": c.ai_cloud,
                "created_at": c.created_at.isoformat(),
            }
            for c in consents
        ],
        "profile": (
            {
                "age_years": prof.age_years,
                "sex": prof.sex,
                "weight_kg": float(prof.weight_kg),
                "height_cm": prof.height_cm,
                "activity_level": prof.activity_level,
                "goal": prof.goal,
                "protein_g_per_kg": float(prof.protein_g_per_kg),
                "screening": prof.screening_json,
                "updated_at": prof.updated_at.isoformat(),
            }
            if prof
            else None
        ),
        "preferences": (
            {
                "daily_budget_idr": pref.daily_budget_idr,
                "workout_days": pref.workout_days,
                "session_minutes": pref.session_minutes,
                "experience_level": pref.experience_level,
                "equipment_access": pref.equipment_access,
                "excluded_food_ids": pref.excluded_food_ids,
                "allergies": pref.allergies,
                "excluded_exercise_ids": pref.excluded_exercise_ids,
                "region": pref.region,
            }
            if pref
            else None
        ),
        "nutrition_targets": [
            {
                "id": t.id,
                "ree_kcal": float(t.ree_kcal),
                "tdee_kcal": float(t.tdee_kcal),
                "energy_target_kcal": t.energy_target_kcal,
                "protein_target_g": t.protein_target_g,
                "formula_version": t.formula_version,
                "created_at": t.created_at.isoformat(),
            }
            for t in targets
        ],
        "meal_plans": [
            {
                "id": mp.id,
                "group_id": mp.group_id,
                "version": mp.version,
                "status": mp.status,
                "result_status": mp.result_status,
                "start_date": mp.start_date.isoformat(),
                "budget_limit_idr": mp.budget_limit_idr,
                "created_at": mp.created_at.isoformat(),
            }
            for mp in meal_plans
        ],
        "workout_plans": [
            {
                "id": wp.id,
                "week_start": wp.week_start.isoformat(),
                "status": wp.status,
                "version": wp.version,
                "created_at": wp.created_at.isoformat(),
            }
            for wp in workout_plans
        ],
        "food_logs": [
            {
                "id": fl.id,
                "date": fl.date.isoformat(),
                "meal_slot": fl.meal_slot,
                "food_id": fl.food_id,
                "grams": fl.grams,
                "energy_kcal": float(fl.energy_kcal),
                "protein_g": float(fl.protein_g),
                "cost_idr": fl.cost_idr,
            }
            for fl in food_logs
        ],
        "workout_logs": [
            {
                "id": wl.id,
                "date": wl.date.isoformat(),
                "exercise_id": wl.exercise_id,
                "sets": wl.sets_json,
                "effort_rating": wl.effort_rating,
            }
            for wl in workout_logs
        ],
        "weight_logs": [{"id": w.id, "date": w.date.isoformat(), "weight_kg": float(w.weight_kg)} for w in weight_logs],
        "chat_messages": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "intent": m.intent,
                "created_at": m.created_at.isoformat(),
            }
            for m in chats
        ],
        "ai_proposals": [
            {"id": p.id, "type": p.type, "params": p.params_json, "status": p.status, "created_at": p.created_at.isoformat()}
            for p in proposals
        ],
    }


@router.delete("/account", status_code=204)
def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(body.password, user.password_hash):
        raise AppError("UNAUTHORIZED", "Kata sandi salah.")
    db.delete(user)
    db.flush()
    clear_session_cookie(response)
    response.status_code = 204
    return response
