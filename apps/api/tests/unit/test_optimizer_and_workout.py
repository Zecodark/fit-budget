"""Optimizer &Workout engine unit + property tests (PRD §11.2 O1–O9, §11.3 W1–W7)."""

from __future__ import annotations

import csv
import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.optimizer.checker import FoodSpec, check_day, item_metrics
from app.services.optimizer.model import _solve_stage1, _solve_stage2, solve_week_plan
from app.services.workout.engine import ExerciseSpec, generate_workout_plan

SEED_DIR = Path(__file__).resolve().parents[4] / "data" / "seeds"


def _seed_foods() -> list[FoodSpec]:
    out: list[FoodSpec] = []
    with (SEED_DIR / "foods.csv").open("r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append(
                FoodSpec(
                    id=r["code"],
                    code=r["code"],
                    name=r["name"],
                    food_group=r["food_group"],
                    slots=r["slots"],
                    edible_pct=int(r["edible_pct"]),
                    kcal_100g=Decimal(r["kcal_100g"]),
                    protein_100g=Decimal(r["protein_100g"]),
                    step_g=int(r["step_g"]),
                    min_g=int(r["min_g"]),
                    max_g=int(r["max_g"]),
                    max_days_wk=int(r["max_days_wk"]),
                    price_id="price_" + r["code"],
                    package_g=int(r["package_g"]),
                    price_idr=int(r["price_idr"]),
                    recorded_at="2026-11-01",
                )
            )
    return out


def _seed_exercises() -> list[ExerciseSpec]:
    out: list[ExerciseSpec] = []
    with (SEED_DIR / "exercises.csv").open("r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append(
                ExerciseSpec(
                    id=r["code"],
                    code=r["code"],
                    name=r["name"],
                    pattern=r["pattern"],
                    muscle_group=r["muscle_group"],
                    equipment=r["equipment"],
                    difficulty=int(r["difficulty"]),
                    rank=int(r["rank"]),
                    sets=int(r["sets"]),
                    reps_min=int(r["reps_min"]),
                    reps_max=int(r["reps_max"]),
                    unit=r["unit"],
                    rest_s=int(r["rest_s"]),
                    instructions=r["instructions"],
                    contraindication_notes="Hentikan bila nyeri tajam.",
                )
            )
    return out


def test_o1_feasible_g1_45000():
    foods = _seed_foods()
    by_id = {f.id: f for f in foods}
    res = solve_week_plan(
        foods=foods,
        start_date=date(2026, 11, 9),
        budget_idr=45000,
        target_energy_kcal=2279,
        target_protein_g=112,
    )
    assert res["result_status"] == "FEASIBLE"
    days_used: dict[str, int] = {}
    for d in res["days"]:
        assert d["day_status"] == "FEASIBLE"
        assert d["unmet_constraints"] == []
        t = d["totals"]
        assert t["cost_idr"] <= 45000
        assert Decimal("0.95") * 2279 <= Decimal(str(t["energy_kcal"])) <= Decimal("1.05") * 2279
        assert Decimal("0.95") * 112 <= Decimal(str(t["protein_g"])) <= Decimal("1.30") * 112
        assert t["vegetable_g"] >= 150

        day_foods: dict[str, int] = {}
        recalc_cost = 0
        recalc_e = Decimal(0)
        recalc_p = Decimal(0)
        for sl in d["slots"]:
            for it in sl["items"]:
                fid = it["food_id"]
                g = it["grams"]
                day_foods[fid] = day_foods.get(fid, 0) + g
                c, e, p = item_metrics(by_id[fid], g)
                assert c == it["cost_idr"]
                assert float(e) == it["energy_kcal"]
                assert float(p) == it["protein_g"]
                recalc_cost += c
                recalc_e += by_id[fid].kcal_100g * Decimal(g) / Decimal(100)
                recalc_p += by_id[fid].protein_100g * Decimal(g) / Decimal(100)
        assert len(day_foods) >= 6
        for fid, g in day_foods.items():
            assert g <= by_id[fid].max_g
            days_used[fid] = days_used.get(fid, 0) + 1
        assert recalc_cost == t["cost_idr"]
        assert float(recalc_e.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) == t["energy_kcal"]
        assert float(recalc_p.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) == t["protein_g"]
    for fid, cnt in days_used.items():
        assert cnt <= by_id[fid].max_days_wk


def test_o2_and_o3_infeasible_and_boundary():
    foods = _seed_foods()
    r_low = solve_week_plan(
        foods=foods, start_date=date(2026, 11, 9), budget_idr=10000, target_energy_kcal=2279, target_protein_g=112
    )
    assert r_low["result_status"] == "INFEASIBLE"
    m = r_low["minimum_budget_required_idr"]
    assert m is not None and m > 10000
    for d in r_low["days"]:
        assert d["totals"]["cost_idr"] <= 10000

    r_below = solve_week_plan(
        foods=foods, start_date=date(2026, 11, 9), budget_idr=m - 500, target_energy_kcal=2279, target_protein_g=112
    )
    assert r_below["result_status"] != "FEASIBLE"
    r_at = solve_week_plan(
        foods=foods, start_date=date(2026, 11, 9), budget_idr=m, target_energy_kcal=2279, target_protein_g=112
    )
    assert r_at["result_status"] == "FEASIBLE"


def test_o4_determinism():
    foods = _seed_foods()
    r1 = solve_week_plan(
        foods=foods, start_date=date(2026, 11, 9), budget_idr=45000, target_energy_kcal=2279, target_protein_g=112
    )
    r2 = solve_week_plan(
        foods=foods, start_date=date(2026, 11, 9), budget_idr=45000, target_energy_kcal=2279, target_protein_g=112
    )
    assert r1 == r2


def test_o7_excluded_food_and_o8_shopping():
    foods = [f for f in _seed_foods() if f.code not in ("TELU", "LELE")]
    by_id = {f.id: f for f in foods}
    res = solve_week_plan(
        foods=foods, start_date=date(2026, 11, 9), budget_idr=45000, target_energy_kcal=2279, target_protein_g=112
    )
    for d in res["days"]:
        for sl in d["slots"]:
            for it in sl["items"]:
                assert it["food_id"] not in ("TELU", "LELE")

    for sh in res["shopping_list"]:
        f = by_id[sh["food_id"]]
        expected_purchase = math.ceil(sh["total_edible_g"] * 100 / f.edible_pct)
        expected_pkg = math.ceil(expected_purchase / f.package_g)
        assert sh["packages"] == expected_pkg
        assert sh["est_cost_idr"] == expected_pkg * f.price_idr


@settings(max_examples=12, deadline=None)
@given(
    b1=st.integers(min_value=10_000, max_value=120_000),
    delta=st.integers(min_value=1_000, max_value=80_000),
    excl_indices=st.lists(st.integers(min_value=0, max_value=24), max_size=5, unique=True),
)
def test_o6_property_day1_monotonic_and_checker_sound(b1: int, delta: int, excl_indices: list[int]):
    all_foods = _seed_foods()
    excl = {all_foods[i].id for i in excl_indices}
    foods = [f for f in all_foods if f.id not in excl]
    by_id = {f.id: f for f in foods}
    rank = {"INFEASIBLE": 0, "PARTIAL": 1, "FEASIBLE": 2}

    def _day1_status(budget: int) -> str:
        items = _solve_stage1(foods, 2279, 112, budget, set(), 1.5)
        if items is not None:
            chk = check_day(
                day_date="2026-11-09",
                items=items,
                foods_by_id=by_id,
                target_energy_kcal=2279,
                target_protein_g=112,
                budget_idr=budget,
            )
            assert chk["day_status"] == "FEASIBLE"
            assert chk["unmet_constraints"] == []
            return "FEASIBLE"
        items2 = _solve_stage2(foods, 2279, 112, budget, 1.5)
        if items2 is not None:
            chk2 = check_day(
                day_date="2026-11-09",
                items=items2,
                foods_by_id=by_id,
                target_energy_kcal=2279,
                target_protein_g=112,
                budget_idr=budget,
            )
            assert chk2["totals"]["cost_idr"] <= budget
            return "PARTIAL"
        return "INFEASIBLE"

    s1 = _day1_status(b1)
    s2 = _day1_status(min(200_000, b1 + delta))
    assert rank[s2] >= rank[s1]


def test_w1_w2_w3_w6_workout_engine():
    ex = _seed_exercises()
    # W1: [0,2,4], 60m, gym_full -> 3 sessions Mon/Wed/Fri, ISO parity templates, no consecutive
    w1_even = generate_workout_plan(
        exercises=ex,
        workout_days=[0, 2, 4],
        session_minutes=60,
        experience_level="beginner",
        equipment_access="gym_full",
        excluded_exercise_ids=set(),
        week_start=date(2026, 11, 9),  # ISO week 46 (even)
    )
    assert [s["date"] for s in w1_even["sessions"]] == ["2026-11-09", "2026-11-11", "2026-11-13"]
    assert [s["template_code"] for s in w1_even["sessions"]] == ["FB-A", "FB-B", "FB-A"]

    w1_odd = generate_workout_plan(
        exercises=ex,
        workout_days=[0, 2, 4],
        session_minutes=60,
        experience_level="beginner",
        equipment_access="gym_full",
        excluded_exercise_ids=set(),
        week_start=date(2026, 11, 2),  # ISO week 45 (odd)
    )
    assert [s["template_code"] for s in w1_odd["sessions"]] == ["FB-B", "FB-A", "FB-B"]

    # W2: [0,1,2] -> k reduced to 2 (Mon & Wed) + SESSIONS_REDUCED
    w2 = generate_workout_plan(
        exercises=ex,
        workout_days=[0, 1, 2],
        session_minutes=60,
        experience_level="beginner",
        equipment_access="gym_full",
        excluded_exercise_ids=set(),
        week_start=date(2026, 11, 9),
    )
    assert [s["date"] for s in w2["sessions"]] == ["2026-11-09", "2026-11-11"]
    assert any(w["code"] == "SESSIONS_REDUCED" for w in w2["warnings"])

    # W3: bodyweight_only -> all bodyweight; vertical_pull falls back to EX16 + PATTERN_FALLBACK
    w3 = generate_workout_plan(
        exercises=ex,
        workout_days=[0, 2, 4],
        session_minutes=60,
        experience_level="beginner",
        equipment_access="bodyweight_only",
        excluded_exercise_ids=set(),
        week_start=date(2026, 11, 9),
    )
    ex_by_id = {e.id: e for e in ex}
    assert any(w["code"] == "PATTERN_FALLBACK" for w in w3["warnings"])
    for s in w3["sessions"]:
        for item in s["exercises"]:
            assert ex_by_id[item["exercise_id"]].equipment == "bodyweight"
        if s["template_code"] == "FB-B":
            assert any(item["exercise_id"] == "EX16" for item in s["exercises"])

    # W6: session_minutes = 30 -> N >= 3 and (estimated_minutes <= 30 or SESSION_TOO_LONG)
    w6 = generate_workout_plan(
        exercises=ex,
        workout_days=[0, 3],
        session_minutes=30,
        experience_level="beginner",
        equipment_access="gym_full",
        excluded_exercise_ids=set(),
        week_start=date(2026, 11, 9),
    )
    for s in w6["sessions"]:
        assert len(s["exercises"]) >= 3
        assert s["estimated_minutes"] <= 30 or any(w["code"] == "SESSION_TOO_LONG" for w in w6["warnings"])

