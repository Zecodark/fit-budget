"""Shared data structures, unit math, and independent constraint checker (PRD §3.5.1, §3.5.4)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.services.nutrition.engine import round_half_up_1, round_half_up_int

ENGINE_VERSION = "mealopt-1.0.0"

SLOT_CHAR_TO_NAME = {"B": "breakfast", "L": "lunch", "D": "dinner", "S": "snack"}
SLOT_NAME_TO_CHAR = {v: k for k, v in SLOT_CHAR_TO_NAME.items()}
ALL_SLOTS = ("breakfast", "lunch", "dinner", "snack")

# Stage 1 slot energy share bounds (inclusive, scaled by 100 of total daily energy)
SLOT_SHARE_BOUNDS: dict[str, tuple[int, int]] = {
    "breakfast": (15, 30),
    "lunch": (25, 40),
    "dinner": (25, 40),
    "snack": (0, 15),
}


@dataclass(frozen=True)
class FoodSpec:
    id: str
    code: str
    name: str
    food_group: str
    slots: str  # subset of 'BLDS'
    edible_pct: int
    kcal_100g: Decimal
    protein_100g: Decimal
    step_g: int
    min_g: int
    max_g: int
    max_days_wk: int
    price_id: str
    package_g: int
    price_idr: int
    recorded_at: str

    @property
    def cost_per_unit_idr(self) -> int:
        # ceil(price_idr * step_g * 100 / (package_g * edible_pct))
        num = self.price_idr * self.step_g * 100
        den = self.package_g * self.edible_pct
        return (num + den - 1) // den

    @property
    def energy_u100(self) -> int:
        # round(kcal_100g * step_g)
        return round_half_up_int(self.kcal_100g * Decimal(self.step_g))

    @property
    def protein_u100(self) -> int:
        # round(protein_100g * step_g)
        return round_half_up_int(self.protein_100g * Decimal(self.step_g))

    @property
    def min_units(self) -> int:
        return math.ceil(self.min_g / self.step_g)

    @property
    def max_units(self) -> int:
        return self.max_g // self.step_g


def item_metrics(food: FoodSpec, grams: int) -> tuple[int, Decimal, Decimal]:
    """Return (cost_idr, energy_kcal (1 dec), protein_g (1 dec)) from grams using unit arithmetic when aligned."""
    if grams % food.step_g == 0:
        units = grams // food.step_g
        cost = units * food.cost_per_unit_idr
        energy = round_half_up_1(Decimal(units * food.energy_u100) / Decimal(100))
        protein = round_half_up_1(Decimal(units * food.protein_u100) / Decimal(100))
        return cost, energy, protein
    # Non-step manual edit fallback: exact ceiling cost & Decimal macros
    num = food.price_idr * grams * 100
    den = food.package_g * food.edible_pct
    cost = (num + den - 1) // den
    energy = round_half_up_1(food.kcal_100g * Decimal(grams) / Decimal(100))
    protein = round_half_up_1(food.protein_100g * Decimal(grams) / Decimal(100))
    return cost, energy, protein


def check_day(
    *,
    day_date: str,
    items: list[dict[str, Any]],  # [{slot, food_id, grams}]
    foods_by_id: dict[str, FoodSpec],
    target_energy_kcal: int,
    target_protein_g: int,
    budget_idr: int,
) -> dict[str, Any]:
    """Independent Decimal verifier. Classifies FEASIBLE / PARTIAL / INFEASIBLE and reports unmet constraints."""
    total_cost = 0
    total_energy_u100 = Decimal(0)
    total_protein_u100 = Decimal(0)
    veg_g = 0
    grams_per_food: dict[str, int] = {}
    slot_energy_u100: dict[str, Decimal] = {s: Decimal(0) for s in ALL_SLOTS}
    slot_groups: dict[str, set[str]] = {s: set() for s in ALL_SLOTS}

    enriched: list[dict[str, Any]] = []
    for it in items:
        g = int(it["grams"])
        if g <= 0:
            continue
        f = foods_by_id[it["food_id"]]
        slot = it["slot"]
        cost, e_kcal, p_g = item_metrics(f, g)
        e_u100 = Decimal(g) * f.kcal_100g
        p_u100 = Decimal(g) * f.protein_100g
        total_cost += cost
        total_energy_u100 += e_u100
        total_protein_u100 += p_u100
        slot_energy_u100[slot] += e_u100
        slot_groups[slot].add(f.food_group)
        grams_per_food[f.id] = grams_per_food.get(f.id, 0) + g
        if f.food_group == "vegetable":
            veg_g += g
        enriched.append(
            {
                **it,
                "food_name": f.name,
                "price_id": f.price_id,
                "cost_idr": cost,
                "energy_kcal": float(e_kcal),
                "protein_g": float(p_g),
            }
        )

    total_energy = round_half_up_1(total_energy_u100 / Decimal(100))
    total_protein = round_half_up_1(total_protein_u100 / Decimal(100))
    distinct_foods = len(grams_per_food)

    E = Decimal(target_energy_kcal)
    P = Decimal(target_protein_g)
    e_val = total_energy_u100 / Decimal(100)
    p_val = total_protein_u100 / Decimal(100)

    def _u(code: str, req: float | int, act: float | int, unit: str) -> dict[str, Any]:
        return {"code": code, "day": day_date, "required": req, "actual": act, "unit": unit}

    strict_unmet: list[dict[str, Any]] = []
    if total_cost > budget_idr:
        strict_unmet.append(_u("BUDGET_EXCEEDED", budget_idr, total_cost, "idr"))
    e_min_s = (Decimal("0.95") * E).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    e_max_s = (Decimal("1.05") * E).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if e_val < Decimal("0.95") * E:
        strict_unmet.append(_u("ENERGY_BELOW_TARGET", float(e_min_s), float(total_energy), "kcal"))
    if e_val > Decimal("1.05") * E:
        strict_unmet.append(_u("ENERGY_ABOVE_TARGET", float(e_max_s), float(total_energy), "kcal"))
    p_min_s = (Decimal("0.95") * P).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    p_max_s = (Decimal("1.30") * P).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if p_val < Decimal("0.95") * P:
        strict_unmet.append(_u("PROTEIN_BELOW_TARGET", float(p_min_s), float(total_protein), "g"))
    if p_val > Decimal("1.30") * P:
        strict_unmet.append(_u("PROTEIN_ABOVE_LIMIT", float(p_max_s), float(total_protein), "g"))
    if veg_g < 150:
        strict_unmet.append(_u("VEGETABLE_BELOW_MIN", 150, veg_g, "g"))
    if distinct_foods < 6:
        strict_unmet.append(_u("VARIETY_BELOW_MIN", 6, distinct_foods, "foods"))
    if total_energy_u100 > 0:
        for slot, (lo, hi) in SLOT_SHARE_BOUNDS.items():
            se = slot_energy_u100[slot]
            if se * 100 < Decimal(lo) * total_energy_u100 or se * 100 > Decimal(hi) * total_energy_u100:
                pct = float((se * 100 / total_energy_u100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
                strict_unmet.append(_u("SLOT_SHARE_VIOLATION", lo, pct, "pct"))
                break
    else:
        strict_unmet.append(_u("SLOT_SHARE_VIOLATION", 15, 0, "pct"))

    for main_slot in ("lunch", "dinner"):
        grps = slot_groups[main_slot]
        if "carb" not in grps or not (grps & {"protein_animal", "protein_plant"}):
            strict_unmet.append(_u("MEAL_COMPOSITION_INVALID", 1, 0, main_slot))
            break

    max_g_exceeded = any(g > foods_by_id[fid].max_g for fid, g in grams_per_food.items())

    if not strict_unmet and not max_g_exceeded:
        status = "FEASIBLE"
    else:
        # Check Stage 2 (RELAXED) feasibility
        relaxed_ok = (
            total_cost <= budget_idr
            and not max_g_exceeded
            and Decimal("0.85") * E <= e_val <= Decimal("1.10") * E
            and Decimal("0.75") * P <= p_val <= Decimal("1.30") * P
            and veg_g >= 100
            and distinct_foods >= 4
            and all(
                "carb" in slot_groups[ms] and bool(slot_groups[ms] & {"protein_animal", "protein_plant"})
                for ms in ("lunch", "dinner")
            )
        )
        status = "PARTIAL" if relaxed_ok else "INFEASIBLE"

    return {
        "day_status": status,
        "items": enriched,
        "totals": {
            "cost_idr": total_cost,
            "energy_kcal": float(total_energy),
            "protein_g": float(total_protein),
            "vegetable_g": veg_g,
        },
        "unmet_constraints": strict_unmet,
    }

