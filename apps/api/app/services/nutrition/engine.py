"""Pure deterministic nutrition & health-screening functions (PRD §3.1–3.3). No I/O."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

FORMULA_VERSION = "nutrition-1.0.0"

ACTIVITY_FACTORS: dict[str, Decimal] = {
    "sedentary": Decimal("1.2"),
    "light": Decimal("1.375"),
    "moderate": Decimal("1.55"),
    "active": Decimal("1.725"),
}

GOAL_ADJUSTMENTS: dict[str, Decimal] = {
    "maintain": Decimal("0"),
    "build_strength": Decimal("0.10"),
    "lose_weight": Decimal("-0.10"),
}

ENERGY_FLOORS: dict[str, Decimal] = {
    "female": Decimal("1200"),
    "male": Decimal("1500"),
}

SCREENING_KEYS = (
    "pregnant_or_breastfeeding",
    "eating_disorder_history",
    "kidney_disease",
    "serious_injury",
    "other_medical_condition",
)


def round_half_up_int(val: Decimal | float | int) -> int:
    d = val if isinstance(val, Decimal) else Decimal(str(val))
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_half_up_1(val: Decimal | float | int) -> Decimal:
    d = val if isinstance(val, Decimal) else Decimal(str(val))
    return d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def compute_bmi(weight_kg: Decimal | float, height_cm: int) -> Decimal:
    w = Decimal(str(weight_kg))
    h_m = Decimal(str(height_cm)) / Decimal("100")
    return round_half_up_1(w / (h_m * h_m))


def compute_protein(
    weight_kg: Decimal | float,
    protein_g_per_kg: Decimal | float,
    energy_target_kcal: int,
) -> tuple[int, list[dict[str, str]]]:
    w = Decimal(str(weight_kg))
    r = Decimal(str(protein_g_per_kg))
    raw = round_half_up_int(w * r)
    max_from_energy = Decimal(energy_target_kcal) * Decimal("0.35") / Decimal("4")
    warnings: list[dict[str, str]] = []
    if Decimal(raw) * Decimal("4") > Decimal(energy_target_kcal) * Decimal("0.35"):
        raw = round_half_up_int(max_from_energy)
        warnings.append(
            {
                "code": "PROTEIN_CAPPED",
                "message": "Target protein dibatasi maksimal 35% dari target energi harian.",
            }
        )
    return raw, warnings


def estimate_nutrition(
    *,
    sex: str,
    age_years: int,
    weight_kg: Decimal | float,
    height_cm: int,
    activity_level: str,
    goal: str,
    protein_g_per_kg: Decimal | float = Decimal("1.6"),
    calculated_at: datetime | None = None,
) -> dict[str, Any]:
    w = Decimal(str(weight_kg))
    h = Decimal(str(height_cm))
    a = Decimal(age_years)
    s = Decimal("5") if sex == "male" else Decimal("-161")

    ree_raw = Decimal("10") * w + Decimal("6.25") * h - Decimal("5") * a + s
    ree = round_half_up_1(ree_raw)
    factor = ACTIVITY_FACTORS[activity_level]
    tdee_raw = ree_raw * factor
    tdee = round_half_up_1(tdee_raw)

    adj = GOAL_ADJUSTMENTS[goal]
    adjusted = tdee_raw * (Decimal("1") + adj)
    floor = ENERGY_FLOORS[sex]
    warnings: list[dict[str, str]] = []

    best = max(adjusted, ree_raw, floor)
    if best > adjusted:
        warnings.append(
            {
                "code": "ENERGY_FLOOR_APPLIED",
                "message": "Target energi dinaikkan ke batas aman minimum (REE / lantai kalori).",
            }
        )
    energy_target = round_half_up_int(best)

    ratio = round_half_up_1(protein_g_per_kg)
    protein_target, p_warn = compute_protein(w, ratio, energy_target)
    warnings.extend(p_warn)

    ts = (calculated_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    return {
        "ree_kcal": float(ree),
        "activity_factor": float(factor),
        "tdee_kcal": float(tdee),
        "goal_adjustment_pct": int(adj * 100),
        "energy_target_kcal": energy_target,
        "protein_g_per_kg": float(ratio),
        "protein_target_g": protein_target,
        "assumptions": [
            "Persamaan Mifflin–St Jeor untuk orang dewasa sehat (estimasi)",
            f"Faktor aktivitas {factor} ({activity_level})",
            f"Penyesuaian tujuan {int(adj * 100)}% ({goal})",
        ],
        "sources": ["[5]", "[6]"],
        "warnings": warnings,
        "formula_version": FORMULA_VERSION,
        "calculated_at": ts,
    }


def evaluate_safety(
    *,
    weight_kg: Decimal | float,
    height_cm: int,
    goal: str,
    screening: dict[str, bool] | None,
) -> tuple[bool, Decimal, list[dict[str, str]], bool]:
    """Returns (plan_generation_allowed, bmi, warnings, goal_not_allowed)."""
    bmi = compute_bmi(weight_kg, height_cm)
    scr = {k: bool((screening or {}).get(k, False)) for k in SCREENING_KEYS}
    goal_not_allowed = bmi < Decimal("18.5") and goal == "lose_weight"
    warnings: list[dict[str, str]] = []
    any_flag = any(scr.values())
    allowed = True
    if any_flag or bmi < Decimal("16.0"):
        allowed = False
        warnings.append(
            {
                "code": "PROFESSIONAL_CONSULT_REQUIRED",
                "message": "Kondisi Anda memerlukan konsultasi tenaga kesehatan profesional; rencana otomatis dinonaktifkan.",
            }
        )
    return allowed, bmi, warnings, goal_not_allowed

