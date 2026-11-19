"""Profile, preferences, and nutrition endpoints (PRD §5.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import current_user, require_consent
from app.core.errors import AppError, validation_error
from app.models import NutritionTarget, Preferences, Profile, User, new_id
from app.schemas import (
    NutritionEstimateRequest,
    PreferencesInput,
    ProfileInput,
    PutProfileRequest,
)
from app.services.nutrition.engine import (
    FORMULA_VERSION,
    SCREENING_KEYS,
    estimate_nutrition,
    evaluate_safety,
)

router = APIRouter(tags=["profile", "nutrition"])


def _extract_profile_and_prefs(
    body: PutProfileRequest,
    existing_prof: Profile | None,
    existing_pref: Preferences | None,
    partial: bool,
) -> tuple[ProfileInput, PreferencesInput]:
    if body.profile and body.preferences and not partial:
        return body.profile, body.preferences

    def _p(field: str, default: Any = None) -> Any:
        if body.profile and getattr(body.profile, field, None) is not None:
            return getattr(body.profile, field)
        if getattr(body, field, None) is not None:
            return getattr(body, field)
        if existing_prof is not None and hasattr(existing_prof, field):
            return getattr(existing_prof, field)
        return default

    def _pr(field: str, default: Any = None) -> Any:
        if body.preferences and getattr(body.preferences, field, None) is not None:
            return getattr(body.preferences, field)
        if getattr(body, field, None) is not None:
            return getattr(body, field)
        if existing_pref is not None and hasattr(existing_pref, field):
            return getattr(existing_pref, field)
        return default

    scr_raw: dict[str, bool] = {}
    if existing_prof and existing_prof.screening_json:
        scr_raw.update(existing_prof.screening_json)
    if body.profile and body.profile.screening:
        scr_raw.update(body.profile.screening.model_dump())
    if body.screening:
        scr_raw.update(body.screening.model_dump())

    try:
        prof_in = ProfileInput(
            age_years=_p("age_years"),
            sex=_p("sex"),
            weight_kg=_p("weight_kg"),
            height_cm=_p("height_cm"),
            activity_level=_p("activity_level"),
            goal=_p("goal"),
            protein_g_per_kg=_p("protein_g_per_kg", Decimal("1.6")),
            screening=scr_raw,
        )
        pref_in = PreferencesInput(
            daily_budget_idr=_pr("daily_budget_idr", 45000),
            workout_days=_pr("workout_days", [0, 2, 4]),
            session_minutes=_pr("session_minutes", 60),
            experience_level=_pr("experience_level", "beginner"),
            equipment_access=_pr("equipment_access", "gym_full"),
            excluded_food_ids=_pr("excluded_food_ids", []),
            allergies=_pr("allergies", []),
            excluded_exercise_ids=_pr("excluded_exercise_ids", []),
            region=_pr("region", "default"),
        )
    except Exception as exc:
        raise validation_error(str(exc)) from exc
    return prof_in, pref_in


def maybe_record_nutrition_target(db: Session, user_id: str, prof: Profile) -> NutritionTarget:
    inputs = {
        "sex": prof.sex,
        "age_years": int(prof.age_years),
        "weight_kg": float(prof.weight_kg),
        "height_cm": int(prof.height_cm),
        "activity_level": prof.activity_level,
        "goal": prof.goal,
        "protein_g_per_kg": float(prof.protein_g_per_kg),
    }
    latest = db.scalar(
        select(NutritionTarget)
        .where(NutritionTarget.user_id == user_id)
        .order_by(desc(NutritionTarget.created_at), desc(NutritionTarget.id))
        .limit(1)
    )
    if latest and latest.inputs_json == inputs:
        return latest

    calc = estimate_nutrition(
        sex=prof.sex,
        age_years=prof.age_years,
        weight_kg=prof.weight_kg,
        height_cm=prof.height_cm,
        activity_level=prof.activity_level,
        goal=prof.goal,
        protein_g_per_kg=prof.protein_g_per_kg,
    )
    row = NutritionTarget(
        id=new_id(),
        user_id=user_id,
        inputs_json=inputs,
        ree_kcal=Decimal(str(calc["ree_kcal"])),
        tdee_kcal=Decimal(str(calc["tdee_kcal"])),
        energy_target_kcal=int(calc["energy_target_kcal"]),
        protein_target_g=int(calc["protein_target_g"]),
        warnings_json=calc["warnings"],
        result_json=calc,
        formula_version=FORMULA_VERSION,
    )
    db.add(row)
    db.flush()
    return row


def _serialize_profile_bundle(prof: Profile, pref: Preferences, nt: NutritionTarget | None) -> dict[str, Any]:
    allowed, bmi, safety_warnings, _ = evaluate_safety(
        weight_kg=prof.weight_kg,
        height_cm=prof.height_cm,
        goal=prof.goal,
        screening=prof.screening_json,
    )
    warnings = list(safety_warnings)
    if nt and nt.warnings_json:
        seen = {w["code"] for w in warnings}
        for w in nt.warnings_json:
            if w["code"] not in seen:
                warnings.append(w)

    scr = {k: bool((prof.screening_json or {}).get(k, False)) for k in SCREENING_KEYS}
    return {
        "profile": {
            "age_years": prof.age_years,
            "sex": prof.sex,
            "weight_kg": float(prof.weight_kg),
            "height_cm": prof.height_cm,
            "activity_level": prof.activity_level,
            "goal": prof.goal,
            "protein_g_per_kg": float(prof.protein_g_per_kg),
            "screening": scr,
            "updated_at": prof.updated_at.isoformat(),
        },
        "preferences": {
            "daily_budget_idr": pref.daily_budget_idr,
            "workout_days": pref.workout_days,
            "session_minutes": pref.session_minutes,
            "experience_level": pref.experience_level,
            "equipment_access": pref.equipment_access,
            "excluded_food_ids": pref.excluded_food_ids or [],
            "allergies": pref.allergies or [],
            "excluded_exercise_ids": pref.excluded_exercise_ids or [],
            "region": pref.region,
        },
        "bmi": float(bmi),
        "plan_generation_allowed": allowed,
        "warnings": warnings,
    }


@router.get("/profile")
def get_profile(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    prof = db.get(Profile, user.id)
    pref = db.get(Preferences, user.id)
    if not prof or not pref:
        raise AppError("NOT_FOUND", "Profil belum dibuat.")
    nt = db.scalar(
        select(NutritionTarget).where(NutritionTarget.user_id == user.id).order_by(desc(NutritionTarget.created_at)).limit(1)
    )
    return _serialize_profile_bundle(prof, pref, nt)


def _save_profile(body: PutProfileRequest, user: User, db: Session, partial: bool) -> dict:
    prof = db.get(Profile, user.id)
    pref = db.get(Preferences, user.id)
    if partial and (not prof or not pref):
        raise AppError("NOT_FOUND", "Profil belum dibuat.")

    prof_in, pref_in = _extract_profile_and_prefs(body, prof, pref, partial)
    scr_dict = prof_in.screening.model_dump()
    _, _, _, goal_not_allowed = evaluate_safety(
        weight_kg=prof_in.weight_kg,
        height_cm=prof_in.height_cm,
        goal=prof_in.goal,
        screening=scr_dict,
    )
    if goal_not_allowed:
        raise AppError(
            "GOAL_NOT_ALLOWED",
            "Tujuan penurunan berat badan tidak diizinkan untuk BMI di bawah 18,5.",
        )

    now = datetime.now(UTC)
    if not prof:
        prof = Profile(
            user_id=user.id,
            age_years=prof_in.age_years,
            sex=prof_in.sex,
            weight_kg=prof_in.weight_kg,
            height_cm=prof_in.height_cm,
            activity_level=prof_in.activity_level,
            goal=prof_in.goal,
            protein_g_per_kg=prof_in.protein_g_per_kg,
            screening_json=scr_dict,
            updated_at=now,
        )
        db.add(prof)
    else:
        prof.age_years = prof_in.age_years
        prof.sex = prof_in.sex
        prof.weight_kg = prof_in.weight_kg
        prof.height_cm = prof_in.height_cm
        prof.activity_level = prof_in.activity_level
        prof.goal = prof_in.goal
        prof.protein_g_per_kg = prof_in.protein_g_per_kg
        prof.screening_json = scr_dict
        prof.updated_at = now

    if not pref:
        pref = Preferences(
            user_id=user.id,
            daily_budget_idr=pref_in.daily_budget_idr,
            workout_days=pref_in.workout_days,
            session_minutes=pref_in.session_minutes,
            experience_level=pref_in.experience_level,
            equipment_access=pref_in.equipment_access,
            excluded_food_ids=pref_in.excluded_food_ids,
            allergies=pref_in.allergies,
            excluded_exercise_ids=pref_in.excluded_exercise_ids,
            region=pref_in.region,
            updated_at=now,
        )
        db.add(pref)
    else:
        pref.daily_budget_idr = pref_in.daily_budget_idr
        pref.workout_days = pref_in.workout_days
        pref.session_minutes = pref_in.session_minutes
        pref.experience_level = pref_in.experience_level
        pref.equipment_access = pref_in.equipment_access
        pref.excluded_food_ids = pref_in.excluded_food_ids
        pref.allergies = pref_in.allergies
        pref.excluded_exercise_ids = pref_in.excluded_exercise_ids
        pref.region = pref_in.region
        pref.updated_at = now

    db.flush()
    nt = maybe_record_nutrition_target(db, user.id, prof)
    return _serialize_profile_bundle(prof, pref, nt)


@router.put("/profile")
def put_profile(body: PutProfileRequest, user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    return _save_profile(body, user, db, partial=False)


@router.patch("/profile")
def patch_profile(body: PutProfileRequest, user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    return _save_profile(body, user, db, partial=True)


@router.post("/nutrition/estimate")
def post_nutrition_estimate(body: NutritionEstimateRequest, _user: User = Depends(current_user)) -> dict:
    _, _, _, goal_not_allowed = evaluate_safety(
        weight_kg=body.weight_kg, height_cm=body.height_cm, goal=body.goal, screening=None
    )
    if goal_not_allowed:
        raise AppError("GOAL_NOT_ALLOWED", "Tujuan penurunan berat badan tidak diizinkan untuk BMI di bawah 18,5.")
    return estimate_nutrition(
        sex=body.sex,
        age_years=body.age_years,
        weight_kg=body.weight_kg,
        height_cm=body.height_cm,
        activity_level=body.activity_level,
        goal=body.goal,
        protein_g_per_kg=body.protein_g_per_kg,
    )


def _serialize_target(t: NutritionTarget) -> dict[str, Any]:
    res = dict(t.result_json or {})
    if not res:
        res = {
            "ree_kcal": float(t.ree_kcal),
            "activity_factor": 1.375,
            "tdee_kcal": float(t.tdee_kcal),
            "goal_adjustment_pct": 0,
            "energy_target_kcal": t.energy_target_kcal,
            "protein_g_per_kg": t.inputs_json.get("protein_g_per_kg", 1.6),
            "protein_target_g": t.protein_target_g,
            "assumptions": ["Persamaan Mifflin–St Jeor untuk orang dewasa sehat (estimasi)"],
            "sources": ["[5]", "[6]"],
            "warnings": t.warnings_json or [],
            "formula_version": t.formula_version,
            "calculated_at": t.created_at.isoformat(),
        }
    return {**res, "id": t.id, "inputs": t.inputs_json, "created_at": t.created_at.isoformat()}


@router.get("/nutrition/target")
def get_nutrition_target(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    t = db.scalar(
        select(NutritionTarget)
        .where(NutritionTarget.user_id == user.id)
        .order_by(desc(NutritionTarget.created_at), desc(NutritionTarget.id))
        .limit(1)
    )
    if not t:
        raise AppError("NOT_FOUND", "Target nutrisi belum dihitung. Simpan profil terlebih dahulu.")
    return _serialize_target(t)


@router.get("/nutrition/target/history")
def get_nutrition_target_history(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(
        select(NutritionTarget)
        .where(NutritionTarget.user_id == user.id)
        .order_by(desc(NutritionTarget.created_at), desc(NutritionTarget.id))
    ).all()
    return {"items": [_serialize_target(r) for r in rows], "total": len(rows)}

