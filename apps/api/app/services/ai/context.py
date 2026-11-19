"""Whitelisted, anonymized LLM context builder (PRD §6.4).

Forbidden in context: name, email, internal UUIDs, exact age/weight/height, DOB, >max history.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    Exercise,
    Food,
    FoodPrice,
    MealPlan,
    NutritionTarget,
    Preferences,
    Profile,
    WorkoutPlan,
)


def _latest_prices_by_food(db: Session, region: str = "default") -> dict[str, tuple[Food, FoodPrice]]:
    foods = {f.id: f for f in db.scalars(select(Food).where(Food.is_active.is_(True))).all()}
    prices = db.scalars(
        select(FoodPrice).where(FoodPrice.region == region).order_by(desc(FoodPrice.recorded_at), desc(FoodPrice.created_at))
    ).all()
    out: dict[str, tuple[Food, FoodPrice]] = {}
    for p in prices:
        if p.food_id in foods and p.food_id not in out:
            out[p.food_id] = (foods[p.food_id], p)
    return out


def build_context(db: Session, user_id: str, today: date | None = None) -> dict[str, Any]:
    today_d = today or date.today()
    prof = db.get(Profile, user_id)
    pref = db.get(Preferences, user_id)
    nt = db.scalar(
        select(NutritionTarget).where(NutritionTarget.user_id == user_id).order_by(desc(NutritionTarget.created_at)).limit(1)
    )

    energy_t = int(nt.energy_target_kcal) if nt else 2000
    protein_t = int(nt.protein_target_g) if nt else 100
    budget = int(pref.daily_budget_idr) if pref else 45000
    goal = prof.goal if prof else "maintain"

    facts: set[float] = {float(energy_t), float(protein_t), float(budget), float(budget * 7)}

    # Latest confirmed or draft meal plan
    mp = db.scalar(
        select(MealPlan)
        .where(MealPlan.user_id == user_id, MealPlan.status.in_(("confirmed", "draft")))
        .order_by(desc(MealPlan.status == "confirmed"), desc(MealPlan.created_at))
        .limit(1)
    )
    foods_map = {f.id: f for f in db.scalars(select(Food)).all()}
    mp_ctx: dict[str, Any] | None = None
    if mp:
        facts.add(float(mp.version))
        facts.add(float(mp.budget_limit_idr))
        by_day: dict[str, list[dict[str, Any]]] = {}
        for it in mp.items:
            d_s = it.date.isoformat()
            fname = foods_map[it.food_id].name if it.food_id in foods_map else "Pangan"
            by_day.setdefault(d_s, []).append(
                {
                    "food": fname,
                    "slot": it.meal_slot,
                    "grams": int(it.grams),
                    "cost_idr": int(it.cost_idr),
                    "energy_kcal": float(it.energy_kcal),
                    "protein_g": float(it.protein_g),
                }
            )
            facts.update([float(it.grams), float(it.cost_idr), float(it.energy_kcal), float(it.protein_g)])
        days_list = []
        week_cost = 0
        for d_s in sorted(by_day.keys()):
            d_items = by_day[d_s]
            c = sum(x["cost_idr"] for x in d_items)
            e = float(
                sum(Decimal(str(x["energy_kcal"])) for x in d_items).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            )
            p = float(
                sum(Decimal(str(x["protein_g"])) for x in d_items).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            )
            week_cost += c
            facts.update([float(c), e, p, float(abs(budget - c)), round(abs(energy_t - e), 1), round(abs(protein_t - p), 1)])
            days_list.append(
                {
                    "date": d_s,
                    "totals": {"cost_idr": c, "energy_kcal": e, "protein_g": p},
                    "items": [{"food": x["food"], "slot": x["slot"], "grams": x["grams"], "cost_idr": x["cost_idr"]} for x in d_items],
                }
            )
        facts.add(float(week_cost))
        mp_ctx = {
            "version": mp.version,
            "status": mp.status,
            "result_status": mp.result_status,
            "week_cost_idr": week_cost,
            "days": days_list,
            "unmet": mp.unmet_json or [],
        }

    wp = db.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == user_id, WorkoutPlan.status.in_(("confirmed", "draft")))
        .order_by(desc(WorkoutPlan.status == "confirmed"), desc(WorkoutPlan.created_at))
        .limit(1)
    )
    ex_map = {e.id: e for e in db.scalars(select(Exercise)).all()}
    wp_ctx: dict[str, Any] | None = None
    if wp:
        facts.add(float(wp.version))
        sessions = []
        for s in wp.sessions:
            facts.add(float(s.estimated_minutes))
            sessions.append(
                {
                    "date": s.date.isoformat(),
                    "template": s.template_code,
                    "status": s.status,
                    "exercises": [ex_map[se.exercise_id].name for se in s.exercises if se.exercise_id in ex_map],
                }
            )
        wp_ctx = {"week_start": wp.week_start.isoformat(), "version": wp.version, "sessions": sessions}

    latest_prices = _latest_prices_by_food(db, pref.region if pref else "default")
    prices_ctx = []
    for f, p in sorted(latest_prices.values(), key=lambda fp: fp[0].name):
        prices_ctx.append(
            {
                "food": f.name,
                "price_idr": int(p.price_idr),
                "package_g": int(p.package_g),
                "recorded_at": p.recorded_at.isoformat(),
            }
        )
        facts.update([float(p.price_idr), float(p.package_g)])

    return {
        "today": today_d.isoformat(),
        "targets": {
            "energy_kcal": energy_t,
            "protein_g": protein_t,
            "daily_budget_idr": budget,
            "goal": goal,
        },
        "meal_plan": mp_ctx,
        "workout_plan": wp_ctx,
        "prices": prices_ctx,
        "facts_numbers": sorted(facts),
    }

