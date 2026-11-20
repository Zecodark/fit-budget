"""Whitelisted, anonymized LLM context builder (PRD §6.4).

Forbidden in context: name, email, internal UUIDs, exact age/weight/height, DOB, >max history.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    Exercise,
    Food,
    FoodLog,
    FoodPrice,
    MealPlan,
    NutritionTarget,
    Preferences,
    Profile,
    WeightLog,
    WorkoutLog,
    WorkoutPlan,
)

DAY_NAMES_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
EQUIPMENT_LABELS_ID = {
    "gym_full": "Mode Gym (barbell, mesin, cable, dumbbell)",
    "bodyweight_only": "Mode Workout Tanpa Alat (bodyweight / rumahan)",
    "home_dumbbell": "Mode Workout Rumahan + Dumbbell",
}


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
    ree_kcal = float(nt.ree_kcal) if nt and nt.ree_kcal is not None else None
    tdee_kcal = float(nt.tdee_kcal) if nt and nt.tdee_kcal is not None else None
    budget = int(pref.daily_budget_idr) if pref else 45000
    goal = prof.goal if prof else "maintain"

    facts: set[float] = {
        100.0,
        float(energy_t),
        float(protein_t),
        float(budget),
        float(budget * 7),
    }
    if ree_kcal is not None:
        facts.add(ree_kcal)
    if tdee_kcal is not None:
        facts.add(tdee_kcal)

    foods_map = {f.id: f for f in db.scalars(select(Food)).all()}
    all_exercises = db.scalars(select(Exercise).where(Exercise.is_active.is_(True))).all()
    ex_map = {e.id: e for e in all_exercises}

    # Anonymized preferences & profile summary (no name, email, exact age/weight/height, UUIDs)
    excluded_food_names = [
        foods_map[fid].name for fid in (pref.excluded_food_ids or []) if fid in foods_map
    ] if pref else []
    workout_day_names = [
        DAY_NAMES_ID[d] for d in sorted(pref.workout_days or []) if 0 <= int(d) <= 6
    ] if pref else []
    eq_access = (pref.equipment_access if pref else None) or "gym_full"
    session_min = int(pref.session_minutes) if pref and pref.session_minutes else 60
    facts.add(float(session_min))
    if prof and prof.protein_g_per_kg is not None:
        facts.add(float(prof.protein_g_per_kg))

    preferences_ctx = {
        "activity_level": prof.activity_level if prof else "light",
        "goal": goal,
        "protein_g_per_kg": float(prof.protein_g_per_kg) if prof and prof.protein_g_per_kg is not None else 1.6,
        "daily_budget_idr": budget,
        "workout_days": workout_day_names,
        "session_minutes": session_min,
        "experience_level": (pref.experience_level if pref else None) or "beginner",
        "equipment_access": eq_access,
        "equipment_access_label": EQUIPMENT_LABELS_ID.get(eq_access, eq_access),
        "excluded_foods": excluded_food_names,
        "allergies": list(pref.allergies or []) if pref else [],
    }

    # Latest confirmed or draft meal plan
    mp = db.scalar(
        select(MealPlan)
        .where(MealPlan.user_id == user_id, MealPlan.status.in_(("confirmed", "draft")))
        .order_by(desc(MealPlan.status == "confirmed"), desc(MealPlan.created_at))
        .limit(1)
    )
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
        avg_daily = round(week_cost / len(days_list)) if days_list else 0
        facts.update([float(week_cost), float(avg_daily)])
        mp_ctx = {
            "version": mp.version,
            "status": mp.status,
            "result_status": mp.result_status,
            "start_date": mp.start_date.isoformat(),
            "week_cost_idr": week_cost,
            "avg_daily_cost_idr": avg_daily,
            "days": days_list,
            "unmet": mp.unmet_json or [],
        }

    # Latest confirmed or draft workout plan
    wp = db.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == user_id, WorkoutPlan.status.in_(("confirmed", "draft")))
        .order_by(desc(WorkoutPlan.status == "confirmed"), desc(WorkoutPlan.created_at))
        .limit(1)
    )
    wp_ctx: dict[str, Any] | None = None
    if wp:
        facts.add(float(wp.version))
        wp_eq = (wp.params_json or {}).get("equipment_access") or eq_access
        sessions = []
        for s in sorted(wp.sessions, key=lambda x: x.date):
            facts.add(float(s.estimated_minutes))
            ex_details = []
            for se in sorted(s.exercises, key=lambda x: x.position):
                ex = ex_map.get(se.exercise_id)
                if not ex:
                    continue
                facts.update([float(se.sets), float(se.reps_min), float(se.reps_max), float(se.rest_s)])
                cat = "gym" if ex.equipment == "gym" else ("workout" if ex.equipment == "bodyweight" else "dumbbell")
                ex_details.append(
                    {
                        "name": ex.name,
                        "category": cat,
                        "muscle_group": ex.muscle_group,
                        "sets": int(se.sets),
                        "reps_min": int(se.reps_min),
                        "reps_max": int(se.reps_max),
                        "unit": se.unit,
                        "rest_s": int(se.rest_s),
                    }
                )
            sessions.append(
                {
                    "date": s.date.isoformat(),
                    "day_name": DAY_NAMES_ID[s.date.weekday()],
                    "template": s.template_code,
                    "status": s.status,
                    "estimated_minutes": int(s.estimated_minutes),
                    "exercises": ex_details,
                }
            )
        wp_ctx = {
            "week_start": wp.week_start.isoformat(),
            "version": wp.version,
            "status": wp.status,
            "equipment_access": wp_eq,
            "equipment_access_label": EQUIPMENT_LABELS_ID.get(wp_eq, wp_eq),
            "sessions": sessions,
        }

    # Recent 7-day progress logs (Progres / Tracker segment)
    since_7d = today_d - timedelta(days=6)
    flogs = db.scalars(
        select(FoodLog)
        .where(FoodLog.user_id == user_id, FoodLog.date >= since_7d, FoodLog.date <= today_d)
        .order_by(FoodLog.date, FoodLog.created_at)
    ).all()
    food_logs_by_day: dict[str, dict[str, Any]] = {}
    for fl in flogs:
        ds = fl.date.isoformat()
        bucket = food_logs_by_day.setdefault(
            ds,
            {"date": ds, "energy_kcal": Decimal(0), "protein_g": Decimal(0), "cost_idr": 0, "items_count": 0, "foods": []},
        )
        bucket["energy_kcal"] += Decimal(str(fl.energy_kcal))
        bucket["protein_g"] += Decimal(str(fl.protein_g))
        bucket["cost_idr"] += int(fl.cost_idr)
        bucket["items_count"] += 1
        fname = foods_map[fl.food_id].name if fl.food_id in foods_map else "Pangan"
        if fname not in bucket["foods"] and len(bucket["foods"]) < 8:
            bucket["foods"].append(fname)
        facts.update([float(fl.grams), float(fl.energy_kcal), float(fl.protein_g), float(fl.cost_idr)])
    food_logs_summary = []
    for ds in sorted(food_logs_by_day.keys()):
        b = food_logs_by_day[ds]
        e_val = float(b["energy_kcal"].quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        p_val = float(b["protein_g"].quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        c_val = int(b["cost_idr"])
        facts.update([e_val, p_val, float(c_val), float(abs(budget - c_val)), round(abs(energy_t - e_val), 1), round(abs(protein_t - p_val), 1)])
        food_logs_summary.append(
            {
                "date": ds,
                "energy_kcal": e_val,
                "protein_g": p_val,
                "cost_idr": c_val,
                "items_count": b["items_count"],
                "foods": b["foods"],
            }
        )

    wlogs = db.scalars(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == user_id, WorkoutLog.date >= since_7d, WorkoutLog.date <= today_d)
        .order_by(desc(WorkoutLog.date), desc(WorkoutLog.created_at))
        .limit(20)
    ).all()
    workout_logs_summary = []
    for wl in reversed(wlogs):
        ex = ex_map.get(wl.exercise_id)
        eq = ex.equipment if ex else "gym"
        cat = "gym" if eq == "gym" else ("workout" if eq == "bodyweight" else "dumbbell")
        sets_list = wl.sets_json or []
        first_s = sets_list[0] if sets_list else {}
        for s_item in sets_list:
            for k in ("reps", "weight_kg", "seconds"):
                if s_item.get(k) is not None:
                    facts.add(float(s_item[k]))
        if first_s.get("seconds") is not None:
            summary = f"{len(sets_list)} set x {first_s['seconds']} detik"
        elif first_s.get("reps") is not None:
            w_val = first_s.get("weight_kg") or 0
            summary = f"{len(sets_list)} set x {first_s['reps']} rep" + (f" @ {w_val} kg" if w_val else " (bodyweight)")
        else:
            summary = f"{len(sets_list)} set"
        workout_logs_summary.append(
            {
                "date": wl.date.isoformat(),
                "exercise": ex.name if ex else "Latihan",
                "category": cat,
                "muscle_group": ex.muscle_group if ex else "",
                "sets_summary": summary,
                "effort_rating": wl.effort_rating,
            }
        )

    # Privacy-safe weight trend (no raw body weight exposed, only count, trend, and delta)
    wt_rows = db.scalars(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date)).all()
    weight_trend_ctx: dict[str, Any]
    if len(wt_rows) >= 2:
        delta = float((Decimal(str(wt_rows[-1].weight_kg)) - Decimal(str(wt_rows[0].weight_kg))).quantize(Decimal("0.1")))
        facts.add(abs(delta))
        trend = "turun" if delta < -0.1 else ("naik" if delta > 0.1 else "stabil")
        weight_trend_ctx = {
            "logs_count": len(wt_rows),
            "trend": trend,
            "delta_kg": delta,
            "last_logged_date": wt_rows[-1].date.isoformat(),
        }
    elif len(wt_rows) == 1:
        weight_trend_ctx = {
            "logs_count": 1,
            "trend": "baru_1_catatan",
            "delta_kg": 0.0,
            "last_logged_date": wt_rows[0].date.isoformat(),
        }
    else:
        weight_trend_ctx = {"logs_count": 0, "trend": "belum_ada_catatan", "delta_kg": None, "last_logged_date": None}

    recent_progress_ctx = {
        "window_days": 7,
        "food_logs_by_day": food_logs_summary,
        "workout_logs": workout_logs_summary,
        "weight_trend": weight_trend_ctx,
    }

    gym_only_cnt = sum(1 for e in all_exercises if e.equipment == "gym")
    workout_bw_cnt = sum(1 for e in all_exercises if e.equipment == "bodyweight")
    dumbbell_cnt = sum(1 for e in all_exercises if e.equipment == "dumbbell")
    facts.update([float(len(all_exercises)), float(gym_only_cnt), float(workout_bw_cnt), float(dumbbell_cnt), float(gym_only_cnt + dumbbell_cnt)])
    catalog_summary_ctx = {
        "total_exercises": len(all_exercises),
        "gym_only_count": gym_only_cnt,
        "workout_bodyweight_count": workout_bw_cnt,
        "dumbbell_count": dumbbell_cnt,
        "gym_including_dumbbell_count": gym_only_cnt + dumbbell_cnt,
    }

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
            "ree_kcal": ree_kcal,
            "tdee_kcal": tdee_kcal,
            "daily_budget_idr": budget,
            "goal": goal,
        },
        "preferences": preferences_ctx,
        "meal_plan": mp_ctx,
        "workout_plan": wp_ctx,
        "recent_progress": recent_progress_ctx,
        "exercise_catalog_summary": catalog_summary_ctx,
        "prices": prices_ctx,
        "facts_numbers": sorted(facts),
    }
