"""Food, workout, weight log endpoints and 7-day dashboard (PRD §5.7)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import as_utc, require_consent
from app.core.errors import AppError, validation_error
from app.models import (
    Exercise,
    Food,
    FoodLog,
    FoodPrice,
    MealPlan,
    NutritionTarget,
    Preferences,
    Profile,
    User,
    WeightLog,
    WorkoutLog,
    WorkoutPlan,
    WorkoutSession,
    new_id,
)
from app.routers.profile import maybe_record_nutrition_target
from app.schemas import (
    FoodLogCreateRequest,
    FoodLogPatchRequest,
    WeightLogRequest,
    WorkoutLogCreateRequest,
    WorkoutLogPatchRequest,
)
from app.services.dashboard.aggregates import build_dashboard
from app.services.nutrition.engine import evaluate_safety, round_half_up_1

router = APIRouter(tags=["logs", "dashboard"])


def _compute_food_snapshot(
    db: Session, food: Food, grams: int, actual_price_idr: int | None
) -> tuple[Decimal, Decimal, int, str | None, bool]:
    e_kcal = round_half_up_1(Decimal(str(food.kcal_100g)) * Decimal(grams) / Decimal(100))
    p_g = round_half_up_1(Decimal(str(food.protein_100g)) * Decimal(grams) / Decimal(100))
    lp = db.scalar(
        select(FoodPrice)
        .where(FoodPrice.food_id == food.id)
        .order_by(desc(FoodPrice.recorded_at), desc(FoodPrice.created_at))
        .limit(1)
    )
    if actual_price_idr is not None:
        return e_kcal, p_g, int(actual_price_idr), (lp.id if lp else None), True
    if lp:
        num = int(lp.price_idr) * grams * 100
        den = int(lp.package_g) * int(food.edible_pct)
        cost = (num + den - 1) // den
        return e_kcal, p_g, cost, lp.id, False
    return e_kcal, p_g, 0, None, False


def _serialize_food_log(fl: FoodLog, food_name: str) -> dict:
    return {
        "id": fl.id,
        "date": fl.date.isoformat(),
        "meal_slot": fl.meal_slot,
        "food_id": fl.food_id,
        "food_name": food_name,
        "grams": fl.grams,
        "energy_kcal": float(fl.energy_kcal),
        "protein_g": float(fl.protein_g),
        "cost_idr": fl.cost_idr,
        "price_id": fl.price_id,
        "cost_is_actual": fl.cost_is_actual,
        "created_at": fl.created_at.isoformat(),
    }


def _day_food_totals(db: Session, user_id: str, d: date) -> dict:
    rows = db.scalars(select(FoodLog).where(FoodLog.user_id == user_id, FoodLog.date == d)).all()
    e = sum((Decimal(str(r.energy_kcal)) for r in rows), Decimal(0)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    p = sum((Decimal(str(r.protein_g)) for r in rows), Decimal(0)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    c = sum(int(r.cost_idr) for r in rows)
    return {"energy_kcal": float(e), "protein_g": float(p), "cost_idr": c}


@router.post("/logs/food", status_code=201)
def create_food_log(
    body: FoodLogCreateRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    food = db.get(Food, body.food_id)
    if not food:
        raise validation_error("Bahan pangan tidak ditemukan.", field="food_id")
    e_kcal, p_g, cost, pid, is_act = _compute_food_snapshot(db, food, body.grams, body.actual_price_idr)
    fl = FoodLog(
        id=new_id(),
        user_id=user.id,
        date=body.date,
        meal_slot=body.meal_slot,
        food_id=food.id,
        grams=body.grams,
        energy_kcal=e_kcal,
        protein_g=p_g,
        cost_idr=cost,
        price_id=pid,
        cost_is_actual=is_act,
    )
    db.add(fl)
    db.flush()
    return {
        "item": _serialize_food_log(fl, food.name),
        "day_totals": _day_food_totals(db, user.id, body.date),
    }


@router.get("/logs/food")
def list_food_logs(
    date: date | None = None,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(FoodLog).where(FoodLog.user_id == user.id).order_by(FoodLog.date, FoodLog.created_at)
    if date:
        stmt = stmt.where(FoodLog.date == date)
    rows = db.scalars(stmt).all()
    foods_map = {f.id: f.name for f in db.scalars(select(Food)).all()}
    totals = _day_food_totals(db, user.id, date) if date else {"energy_kcal": 0.0, "protein_g": 0.0, "cost_idr": 0}
    return {
        "items": [_serialize_food_log(r, foods_map.get(r.food_id, "Pangan")) for r in rows],
        "total": len(rows),
        "day_totals": totals,
    }


@router.patch("/logs/food/{log_id}")
def patch_food_log(
    log_id: str,
    body: FoodLogPatchRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    fl = db.get(FoodLog, log_id)
    if not fl or fl.user_id != user.id:
        raise AppError("NOT_FOUND")
    food = db.get(Food, fl.food_id)
    if body.meal_slot is not None:
        fl.meal_slot = body.meal_slot
    grams = body.grams if body.grams is not None else fl.grams
    act_price = body.actual_price_idr if body.actual_price_idr is not None else (fl.cost_idr if fl.cost_is_actual else None)
    e_kcal, p_g, cost, pid, is_act = _compute_food_snapshot(db, food, grams, act_price)
    fl.grams = grams
    fl.energy_kcal = e_kcal
    fl.protein_g = p_g
    fl.cost_idr = cost
    fl.price_id = pid
    fl.cost_is_actual = is_act
    db.flush()
    return {
        "item": _serialize_food_log(fl, food.name if food else "Pangan"),
        "day_totals": _day_food_totals(db, user.id, fl.date),
    }


@router.delete("/logs/food/{log_id}", status_code=204)
def delete_food_log(
    log_id: str,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> Response:
    fl = db.get(FoodLog, log_id)
    if not fl or fl.user_id != user.id:
        raise AppError("NOT_FOUND")
    db.delete(fl)
    db.flush()
    return Response(status_code=204)


def _serialize_workout_log(wl: WorkoutLog, ex_name: str, progression_hint: str | None = None) -> dict:
    return {
        "id": wl.id,
        "date": wl.date.isoformat(),
        "session_id": wl.session_id,
        "exercise_id": wl.exercise_id,
        "exercise_name": ex_name,
        "sets": wl.sets_json,
        "effort_rating": wl.effort_rating,
        "progression_suggestion": progression_hint,
        "completed_at": wl.completed_at.isoformat(),
    }


@router.post("/logs/workout", status_code=201)
def create_workout_log(
    body: WorkoutLogCreateRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    ex = db.get(Exercise, body.exercise_id)
    if not ex:
        raise validation_error("Latihan tidak ditemukan.", field="exercise_id")
    if body.session_id:
        sess = db.get(WorkoutSession, body.session_id)
        if not sess or not sess.plan or sess.plan.user_id != user.id:
            raise AppError("NOT_FOUND")
    sets_clean = [s.model_dump(exclude_none=True) for s in body.sets]
    wl = WorkoutLog(
        id=new_id(),
        user_id=user.id,
        date=body.date,
        session_id=body.session_id,
        exercise_id=ex.id,
        sets_json=sets_clean,
        effort_rating=body.effort_rating,
    )
    db.add(wl)
    db.flush()
    hint: str | None = None
    if (
        body.effort_rating is not None
        and body.effort_rating <= 8
        and ex.unit == "reps"
        and all((s.get("reps") or 0) >= ex.reps_max for s in sets_clean)
    ):
        hint = "Semua set mencapai batas atas repetisi dengan usaha terkendali — coba tambah beban kecil pada sesi berikutnya."
    return _serialize_workout_log(wl, ex.name, hint)


@router.get("/logs/workout")
def list_workout_logs(
    date: date | None = None,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(WorkoutLog).where(WorkoutLog.user_id == user.id).order_by(WorkoutLog.date, WorkoutLog.created_at)
    if date:
        stmt = stmt.where(WorkoutLog.date == date)
    rows = db.scalars(stmt).all()
    ex_map = {e.id: e.name for e in db.scalars(select(Exercise)).all()}
    return {
        "items": [_serialize_workout_log(r, ex_map.get(r.exercise_id, "Latihan")) for r in rows],
        "total": len(rows),
    }


@router.patch("/logs/workout/{log_id}")
def patch_workout_log(
    log_id: str,
    body: WorkoutLogPatchRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    wl = db.get(WorkoutLog, log_id)
    if not wl or wl.user_id != user.id:
        raise AppError("NOT_FOUND")
    if body.sets is not None:
        wl.sets_json = [s.model_dump(exclude_none=True) for s in body.sets]
    if body.effort_rating is not None:
        wl.effort_rating = body.effort_rating
    ex = db.get(Exercise, wl.exercise_id)
    db.flush()
    return _serialize_workout_log(wl, ex.name if ex else "Latihan")


@router.delete("/logs/workout/{log_id}", status_code=204)
def delete_workout_log(
    log_id: str,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> Response:
    wl = db.get(WorkoutLog, log_id)
    if not wl or wl.user_id != user.id:
        raise AppError("NOT_FOUND")
    db.delete(wl)
    db.flush()
    return Response(status_code=204)


@router.post("/logs/weight", status_code=201)
def create_or_update_weight_log(
    body: WeightLogRequest,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    w = body.weight_kg.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    existing = db.scalar(select(WeightLog).where(WeightLog.user_id == user.id, WeightLog.date == body.date))
    if existing:
        existing.weight_kg = w
        row = existing
    else:
        row = WeightLog(id=new_id(), user_id=user.id, date=body.date, weight_kg=w)
        db.add(row)
    db.flush()

    if body.apply_to_profile:
        prof = db.get(Profile, user.id)
        if prof:
            _, _, _, goal_not_allowed = evaluate_safety(
                weight_kg=w, height_cm=prof.height_cm, goal=prof.goal, screening=prof.screening_json
            )
            if goal_not_allowed:
                raise AppError(
                    "GOAL_NOT_ALLOWED",
                    "Tujuan penurunan berat badan tidak diizinkan untuk BMI di bawah 18,5.",
                )
            prof.weight_kg = w
            prof.updated_at = datetime.now(UTC)
            db.flush()
            maybe_record_nutrition_target(db, user.id, prof)

    return {"id": row.id, "date": row.date.isoformat(), "weight_kg": float(row.weight_kg)}


@router.get("/logs/weight")
def list_weight_logs(
    from_date: date | None = None,
    to_date: date | None = None,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(WeightLog).where(WeightLog.user_id == user.id).order_by(WeightLog.date)
    if from_date:
        stmt = stmt.where(WeightLog.date >= from_date)
    if to_date:
        stmt = stmt.where(WeightLog.date <= to_date)
    rows = db.scalars(stmt).all()
    return {
        "items": [{"id": r.id, "date": r.date.isoformat(), "weight_kg": float(r.weight_kg)} for r in rows],
        "total": len(rows),
    }


@router.get("/dashboard")
def get_dashboard(
    week_start: date | None = None,
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> dict:
    today = date.today()
    ws = week_start or (today - timedelta(days=today.weekday()))
    if ws.weekday() != 0:
        ws = ws - timedelta(days=ws.weekday())
    we = ws + timedelta(days=6)

    prof = db.get(Profile, user.id)
    pref = db.get(Preferences, user.id)
    nt = db.scalar(
        select(NutritionTarget).where(NutritionTarget.user_id == user.id).order_by(desc(NutritionTarget.created_at)).limit(1)
    )
    target_e = int(nt.energy_target_kcal) if nt else 2000
    target_p = int(nt.protein_target_g) if nt else 100
    budget = int(pref.daily_budget_idr) if pref else 45000

    # Latest prices for repricing confirmed meal plan (PLAN_OVER_BUDGET_AFTER_PRICE_CHANGE, PRD §3.7)
    foods_map = {f.id: f for f in db.scalars(select(Food)).all()}
    all_prices = db.scalars(
        select(FoodPrice).order_by(desc(FoodPrice.recorded_at), desc(FoodPrice.created_at), desc(FoodPrice.id))
    ).all()
    latest_price_by_food: dict[str, FoodPrice] = {}
    for p in all_prices:
        if p.food_id not in latest_price_by_food:
            latest_price_by_food[p.food_id] = p

    mp = db.scalar(
        select(MealPlan)
        .where(MealPlan.user_id == user.id, MealPlan.status == "confirmed")
        .order_by(desc(MealPlan.confirmed_at), desc(MealPlan.created_at))
        .limit(1)
    )
    planned_by_date: dict[str, dict] = {}
    if mp:
        for it in mp.items:
            if ws <= it.date <= we:
                d_str = it.date.isoformat()
                b = planned_by_date.setdefault(
                    d_str, {"energy_kcal": Decimal(0), "protein_g": Decimal(0), "cost_idr": 0, "repriced_cost_idr": 0}
                )
                b["energy_kcal"] += Decimal(str(it.energy_kcal))
                b["protein_g"] += Decimal(str(it.protein_g))
                b["cost_idr"] += int(it.cost_idr)
                f = foods_map.get(it.food_id)
                lp = latest_price_by_food.get(it.food_id)
                if f and lp:
                    step_cost = (int(lp.price_idr) * int(f.step_g) * 100 + int(lp.package_g) * int(f.edible_pct) - 1) // (
                        int(lp.package_g) * int(f.edible_pct)
                    )
                    units = int(it.grams) // max(1, int(f.step_g))
                    b["repriced_cost_idr"] += units * step_cost
                else:
                    b["repriced_cost_idr"] += int(it.cost_idr)

    flogs = db.scalars(
        select(FoodLog).where(FoodLog.user_id == user.id, FoodLog.date >= ws, FoodLog.date <= we)
    ).all()
    actual_by_date: dict[str, dict] = {}
    for fl in flogs:
        d_str = fl.date.isoformat()
        b = actual_by_date.setdefault(
            d_str, {"energy_kcal": Decimal(0), "protein_g": Decimal(0), "cost_idr": 0, "has_logs": True}
        )
        b["energy_kcal"] += Decimal(str(fl.energy_kcal))
        b["protein_g"] += Decimal(str(fl.protein_g))
        b["cost_idr"] += int(fl.cost_idr)

    wp = db.scalar(
        select(WorkoutPlan)
        .where(
            WorkoutPlan.user_id == user.id,
            WorkoutPlan.week_start == ws,
            WorkoutPlan.status.in_(("confirmed", "draft")),
        )
        .order_by(desc(WorkoutPlan.status == "confirmed"), desc(WorkoutPlan.created_at))
        .limit(1)
    )
    ws_list = [{"date": s.date.isoformat(), "status": s.status} for s in wp.sessions] if wp else []

    stale_days: int | None = None
    if prof and prof.updated_at:
        stale_days = (datetime.now(UTC) - as_utc(prof.updated_at)).days

    return build_dashboard(
        week_start=ws,
        target_energy_kcal=target_e,
        target_protein_g=target_p,
        daily_budget_idr=budget,
        planned_by_date=planned_by_date,
        actual_food_by_date=actual_by_date,
        workout_sessions=ws_list,
        profile_updated_days_ago=stale_days,
    )

