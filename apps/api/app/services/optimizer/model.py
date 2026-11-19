"""7-day meal plan optimizer using OR-Tools CP-SAT integer arithmetic (PRD §3.5)."""

from __future__ import annotations

import math
import time
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ortools.sat.python import cp_model

from app.core.errors import AppError
from app.services.optimizer.checker import (
    ALL_SLOTS,
    ENGINE_VERSION,
    SLOT_CHAR_TO_NAME,
    SLOT_SHARE_BOUNDS,
    FoodSpec,
    check_day,
)
from app.services.optimizer.shopping import build_shopping_list

REPEAT_PENALTY_IDR = 500


class _DayModel:
    def __init__(self, foods: list[FoodSpec]) -> None:
        self.model = cp_model.CpModel()
        self.foods = foods
        self.x: dict[tuple[int, str], cp_model.IntVar] = {}
        self.u: dict[tuple[int, str], cp_model.IntVar] = {}
        self.y: dict[int, cp_model.IntVar] = {}

        for idx, f in enumerate(foods):
            self.y[idx] = self.model.new_bool_var(f"y_{idx}")
            slot_vars: list[cp_model.IntVar] = []
            slot_units: list[cp_model.IntVar] = []
            for ch in f.slots:
                sname = SLOT_CHAR_TO_NAME.get(ch)
                if not sname:
                    continue
                xv = self.model.new_int_var(0, f.max_units, f"x_{idx}_{sname}")
                uv = self.model.new_bool_var(f"u_{idx}_{sname}")
                self.model.add(xv <= f.max_units * uv)
                self.model.add(xv >= f.min_units * uv)
                self.model.add(self.y[idx] >= uv)
                self.x[(idx, sname)] = xv
                self.u[(idx, sname)] = uv
                slot_vars.append(uv)
                slot_units.append(xv)
            if slot_vars:
                self.model.add(self.y[idx] <= sum(slot_vars))
                # C6: total daily grams per food <= max_g
                self.model.add(sum(slot_units) <= f.max_units)
            else:
                self.model.add(self.y[idx] == 0)

    def total_cost_expr(self):
        return sum(self.foods[i].cost_per_unit_idr * xv for (i, _), xv in self.x.items())

    def total_energy_u100_expr(self):
        return sum(self.foods[i].energy_u100 * xv for (i, _), xv in self.x.items())

    def total_protein_u100_expr(self):
        return sum(self.foods[i].protein_u100 * xv for (i, _), xv in self.x.items())

    def slot_energy_u100_expr(self, slot: str):
        terms = [self.foods[i].energy_u100 * xv for (i, s), xv in self.x.items() if s == slot]
        return sum(terms) if terms else 0

    def veg_grams_expr(self):
        terms = [self.foods[i].step_g * xv for (i, _), xv in self.x.items() if self.foods[i].food_group == "vegetable"]
        return sum(terms) if terms else 0

    def add_c8_composition(self) -> None:
        for ms in ("lunch", "dinner"):
            carbs = [
                uv for (i, s), uv in self.u.items() if s == ms and self.foods[i].food_group == "carb"
            ]
            prots = [
                uv
                for (i, s), uv in self.u.items()
                if s == ms and self.foods[i].food_group in ("protein_animal", "protein_plant")
            ]
            if carbs:
                self.model.add(sum(carbs) >= 1)
            else:
                self.model.add(0 >= 1)
            if prots:
                self.model.add(sum(prots) >= 1)
            else:
                self.model.add(0 >= 1)

    def extract_items(self, solver: cp_model.CpSolver) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for (i, slot), xv in self.x.items():
            u = solver.value(xv)
            if u > 0:
                f = self.foods[i]
                out.append({"slot": slot, "food_id": f.id, "grams": int(u * f.step_g)})
        return out


def _make_solver(time_limit_s: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    # Deterministic time limit (work units) so CP-SAT never varies by CPU load (NFR-10, O4, O5)
    solver.parameters.max_deterministic_time = 0.25
    solver.parameters.max_time_in_seconds = max(0.5, float(time_limit_s))
    return solver


def _solved(status: int) -> bool:
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def _solve_stage1(
    foods: list[FoodSpec],
    target_energy_kcal: int,
    target_protein_g: int,
    budget_idr: int | None,
    yesterday_food_ids: set[str],
    time_limit_s: float,
) -> list[dict[str, Any]] | None:
    if not foods:
        return None
    dm = _DayModel(foods)
    cost = dm.total_cost_expr()
    energy = dm.total_energy_u100_expr()
    protein = dm.total_protein_u100_expr()

    if budget_idr is not None:
        dm.model.add(cost <= budget_idr)  # C1

    E100 = target_energy_kcal * 100
    P100 = target_protein_g * 100
    # C2: 0.95*E* <= energy <= 1.05*E*
    e_lo = math.ceil(95 * E100 / 100)
    e_hi = (105 * E100) // 100
    dm.model.add(energy >= e_lo)
    dm.model.add(energy <= e_hi)
    # C3: 0.95*P* <= protein <= 1.30*P*
    p_lo = math.ceil(95 * P100 / 100)
    p_hi = (130 * P100) // 100
    dm.model.add(protein >= p_lo)
    dm.model.add(protein <= p_hi)
    # C4: veg >= 150 g
    dm.model.add(dm.veg_grams_expr() >= 150)
    # C5: >= 6 distinct foods
    dm.model.add(sum(dm.y.values()) >= 6)
    # C7: slot energy share bounds
    for slot, (lo, hi) in SLOT_SHARE_BOUNDS.items():
        se = dm.slot_energy_u100_expr(slot)
        dm.model.add(100 * se >= lo * energy)
        dm.model.add(100 * se <= hi * energy)
    # C8: lunch & dinner composition
    dm.add_c8_composition()

    penalty_terms = [
        REPEAT_PENALTY_IDR * dm.y[i]
        for i, f in enumerate(foods)
        if f.id in yesterday_food_ids and f.food_group not in ("carb", "fat")
    ]
    dm.model.minimize(cost + (sum(penalty_terms) if penalty_terms else 0))

    solver = _make_solver(time_limit_s)
    st = solver.solve(dm.model)
    if not _solved(st):
        return None
    return dm.extract_items(solver)


def _solve_stage2(
    foods: list[FoodSpec],
    target_energy_kcal: int,
    target_protein_g: int,
    budget_idr: int,
    time_limit_s: float,
) -> list[dict[str, Any]] | None:
    if not foods:
        return None
    dm = _DayModel(foods)
    cost = dm.total_cost_expr()
    energy = dm.total_energy_u100_expr()
    protein = dm.total_protein_u100_expr()

    dm.model.add(cost <= budget_idr)
    E100 = target_energy_kcal * 100
    P100 = target_protein_g * 100
    dm.model.add(energy >= math.ceil(85 * E100 / 100))
    dm.model.add(energy <= (110 * E100) // 100)
    dm.model.add(protein >= math.ceil(75 * P100 / 100))
    dm.model.add(protein <= (130 * P100) // 100)
    dm.model.add(dm.veg_grams_expr() >= 100)
    dm.model.add(sum(dm.y.values()) >= 4)
    dm.add_c8_composition()

    # Lexicographic objective (PRD §3.5.3): (1) min protein shortfall, (2) min energy shortfall, (3) min cost
    p_target_strict = math.ceil(95 * P100 / 100)
    e_target_strict = math.ceil(95 * E100 / 100)
    sp = dm.model.new_int_var(0, p_target_strict, "shortfall_p")
    se = dm.model.new_int_var(0, e_target_strict, "shortfall_e")
    dm.model.add(sp >= p_target_strict - protein)
    dm.model.add(se >= e_target_strict - energy)

    per_pass = max(0.5, time_limit_s / 3)
    dm.model.minimize(sp)
    s1 = _make_solver(per_pass)
    st1 = s1.solve(dm.model)
    if not _solved(st1):
        return None
    best_sp = int(s1.value(sp))
    dm.model.add(sp <= best_sp)

    dm.model.minimize(se)
    s2 = _make_solver(per_pass)
    st2 = s2.solve(dm.model)
    if not _solved(st2):
        return dm.extract_items(s1)
    best_se = int(s2.value(se))
    dm.model.add(se <= best_se)

    dm.model.minimize(cost)
    s3 = _make_solver(per_pass)
    st3 = s3.solve(dm.model)
    return dm.extract_items(s3 if _solved(st3) else s2)


def _solve_stage3_best_effort(
    foods: list[FoodSpec],
    target_energy_kcal: int,
    target_protein_g: int,
    budget_idr: int,
    time_limit_s: float,
) -> list[dict[str, Any]]:
    if not foods:
        return []
    dm = _DayModel(foods)
    cost = dm.total_cost_expr()
    energy = dm.total_energy_u100_expr()
    protein = dm.total_protein_u100_expr()

    dm.model.add(cost <= budget_idr)
    E100 = target_energy_kcal * 100
    P100 = target_protein_g * 100
    dm.model.add(energy <= (105 * E100) // 100)
    dm.model.add(protein <= (130 * P100) // 100)

    # Maximize energy_u100/E* + protein_u100/P*  <=> maximize P* * energy_u100 + E* * protein_u100
    dm.model.maximize(target_protein_g * energy + target_energy_kcal * protein)
    solver = _make_solver(time_limit_s)
    st = solver.solve(dm.model)
    if not _solved(st):
        return []
    return dm.extract_items(solver)


def compute_minimum_budget_idr(
    foods: list[FoodSpec],
    target_energy_kcal: int,
    target_protein_g: int,
    time_limit_s: float = 1.0,
) -> int:
    """Stage 1 without C1, minimize cost, rounded up to Rp 500 (PRD §3.5.3)."""
    items = _solve_stage1(foods, target_energy_kcal, target_protein_g, None, set(), time_limit_s)
    if not items:
        return 50_000
    by_id = {f.id: f for f in foods}
    raw_cost = sum((it["grams"] // by_id[it["food_id"]].step_g) * by_id[it["food_id"]].cost_per_unit_idr for it in items)
    return int(math.ceil(raw_cost / 500.0) * 500)


def format_day_response(
    day_date: str,
    checked: dict[str, Any],
    item_id_map: dict[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    slots_out: list[dict[str, Any]] = []
    for sname in ALL_SLOTS:
        slot_items = []
        for it in checked["items"]:
            if it["slot"] == sname:
                iid = it.get("id") or (item_id_map or {}).get((sname, it["food_id"]), "")
                slot_items.append(
                    {
                        "id": iid,
                        "food_id": it["food_id"],
                        "food_name": it["food_name"],
                        "grams": it["grams"],
                        "price_id": it["price_id"],
                        "cost_idr": it["cost_idr"],
                        "energy_kcal": it["energy_kcal"],
                        "protein_g": it["protein_g"],
                    }
                )
        slots_out.append({"slot": sname, "items": slot_items})
    return {
        "date": day_date,
        "day_status": checked["day_status"],
        "slots": slots_out,
        "totals": checked["totals"],
        "unmet_constraints": checked["unmet_constraints"],
    }


def compute_week_summary(days: list[dict[str, Any]]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    statuses = [d["day_status"] for d in days]
    if "INFEASIBLE" in statuses:
        week_status = "INFEASIBLE"
    elif "PARTIAL" in statuses:
        week_status = "PARTIAL"
    else:
        week_status = "FEASIBLE"

    total_cost = sum(int(d["totals"]["cost_idr"]) for d in days)
    n = max(1, len(days))
    avg_e = float(
        (sum(Decimal(str(d["totals"]["energy_kcal"])) for d in days) / Decimal(n)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    )
    avg_p = float(
        (sum(Decimal(str(d["totals"]["protein_g"])) for d in days) / Decimal(n)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    )
    all_unmet: list[dict[str, Any]] = []
    for d in days:
        all_unmet.extend(d.get("unmet_constraints", []))
    return week_status, {"cost_idr": total_cost, "avg_energy_kcal": avg_e, "avg_protein_g": avg_p}, all_unmet


def solve_week_plan(
    *,
    foods: list[FoodSpec],
    start_date: date,
    budget_idr: int,
    target_energy_kcal: int,
    target_protein_g: int,
    time_limit_per_day_s: float = 10.0,
    hard_limit_s: float = 15.0,
) -> dict[str, Any]:
    t0 = time.monotonic()
    foods_by_id = {f.id: f for f in foods}
    used_days: dict[str, int] = {f.id: 0 for f in foods}
    yesterday_ids: set[str] = set()
    warnings: list[dict[str, str]] = []
    days_out: list[dict[str, Any]] = []
    repeat_relaxed = False

    for day_offset in range(7):
        if time.monotonic() - t0 > hard_limit_s:
            raise AppError("OPTIMIZER_TIMEOUT")
        d_str = (start_date + timedelta(days=day_offset)).isoformat()
        avail = [f for f in foods if used_days[f.id] < f.max_days_wk]

        items = _solve_stage1(avail, target_energy_kcal, target_protein_g, budget_idr, yesterday_ids, time_limit_per_day_s)
        expected = "FEASIBLE"
        if items is None and len(avail) < len(foods):
            # Retry without weekly repeat cap (PRD §3.5.2)
            items = _solve_stage1(foods, target_energy_kcal, target_protein_g, budget_idr, yesterday_ids, time_limit_per_day_s)
            if items is not None:
                repeat_relaxed = True

        if items is None:
            items = _solve_stage2(avail, target_energy_kcal, target_protein_g, budget_idr, time_limit_per_day_s)
            if items is None and len(avail) < len(foods):
                items = _solve_stage2(foods, target_energy_kcal, target_protein_g, budget_idr, time_limit_per_day_s)
                if items is not None:
                    repeat_relaxed = True
            expected = "PARTIAL"

        if items is None:
            items = _solve_stage3_best_effort(foods, target_energy_kcal, target_protein_g, budget_idr, time_limit_per_day_s)
            expected = "INFEASIBLE"

        checked = check_day(
            day_date=d_str,
            items=items,
            foods_by_id=foods_by_id,
            target_energy_kcal=target_energy_kcal,
            target_protein_g=target_protein_g,
            budget_idr=budget_idr,
        )
        # Solver verification guardrail (PRD §3.5.4 #1)
        if expected == "FEASIBLE" and checked["day_status"] != "FEASIBLE":
            raise AppError("INTERNAL_ERROR", "Hasil solver gagal diverifikasi oleh constraint checker.")
        if checked["totals"]["cost_idr"] > budget_idr:
            raise AppError("INTERNAL_ERROR", "Hasil solver melebihi batas budget.")

        today_ids = {it["food_id"] for it in checked["items"]}
        for fid in today_ids:
            used_days[fid] = used_days.get(fid, 0) + 1
        yesterday_ids = today_ids

        days_out.append(format_day_response(d_str, checked))

    if repeat_relaxed:
        warnings.append(
            {
                "code": "FOOD_REPEAT_LIMIT_RELAXED",
                "message": "Batas pengulangan mingguan beberapa bahan dilonggarkan agar target harian tercapai.",
            }
        )

    week_status, week_totals, all_unmet = compute_week_summary(days_out)
    shopping = build_shopping_list(days_out, foods_by_id)

    min_budget: int | None = None
    if week_status == "INFEASIBLE":
        min_budget = max(budget_idr + 500, compute_minimum_budget_idr(foods, target_energy_kcal, target_protein_g))

    return {
        "result_status": week_status,
        "start_date": start_date.isoformat(),
        "budget_limit_idr": budget_idr,
        "targets": {"energy_kcal": target_energy_kcal, "protein_g": target_protein_g},
        "days": days_out,
        "week_totals": week_totals,
        "shopping_list": shopping,
        "unmet_constraints": all_unmet,
        "warnings": warnings,
        "minimum_budget_required_idr": min_budget,
        "engine_version": ENGINE_VERSION,
    }
