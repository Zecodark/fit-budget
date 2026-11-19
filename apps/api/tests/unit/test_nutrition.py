"""Golden-value unit tests for nutrition & health screening (PRD §11.1: G1–G6, U7, U8)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import PreferencesInput, ProfileInput
from app.services.nutrition.engine import (
    compute_bmi,
    compute_protein,
    estimate_nutrition,
    evaluate_safety,
)


def test_g1_male_maintain():
    res = estimate_nutrition(
        sex="male", age_years=22, weight_kg=70, height_cm=170, activity_level="light", goal="maintain"
    )
    assert res["ree_kcal"] == 1657.5
    assert res["tdee_kcal"] == 2279.1
    assert res["energy_target_kcal"] == 2279
    assert res["protein_target_g"] == 112
    assert res["warnings"] == []


def test_g2_and_g2b_female():
    res = estimate_nutrition(
        sex="female", age_years=25, weight_kg=55, height_cm=160, activity_level="moderate", goal="maintain"
    )
    assert res["ree_kcal"] == 1264.0
    assert res["tdee_kcal"] == 1959.2
    assert res["energy_target_kcal"] == 1959
    assert res["protein_target_g"] == 88

    res_lose = estimate_nutrition(
        sex="female", age_years=25, weight_kg=55, height_cm=160, activity_level="moderate", goal="lose_weight"
    )
    assert res_lose["energy_target_kcal"] == 1763


def test_g3_energy_floor_applied():
    res = estimate_nutrition(
        sex="female", age_years=30, weight_kg=45, height_cm=150, activity_level="sedentary", goal="lose_weight"
    )
    assert res["ree_kcal"] == 1076.5
    assert res["tdee_kcal"] == 1291.8
    assert res["energy_target_kcal"] == 1200
    assert any(w["code"] == "ENERGY_FLOOR_APPLIED" for w in res["warnings"])


def test_g4_build_strength():
    res = estimate_nutrition(
        sex="male", age_years=22, weight_kg=70, height_cm=170, activity_level="light", goal="build_strength"
    )
    assert res["energy_target_kcal"] == 2507


def test_g5_protein_capped():
    p, warnings = compute_protein(weight_kg=100, protein_g_per_kg=Decimal("2.0"), energy_target_kcal=1700)
    assert p == 149
    assert any(w["code"] == "PROTEIN_CAPPED" for w in warnings)


def test_g6_bmi_and_safety():
    assert compute_bmi(45, 150) == Decimal("20.0")
    assert compute_bmi(50, 180) == Decimal("15.4")

    allowed_low, bmi_low, warns_low, _ = evaluate_safety(weight_kg=50, height_cm=180, goal="maintain", screening={})
    assert bmi_low == Decimal("15.4")
    assert allowed_low is False
    assert any(w["code"] == "PROFESSIONAL_CONSULT_REQUIRED" for w in warns_low)

    # BMI 17.5 (e.g. 50.6 kg at 170 cm -> 50.6 / 2.89 = 17.5) + lose_weight -> goal_not_allowed
    _, bmi_175, _, goal_blocked = evaluate_safety(weight_kg=Decimal("50.6"), height_cm=170, goal="lose_weight", screening={})
    assert bmi_175 == Decimal("17.5")
    assert goal_blocked is True


def test_u7_profile_input_validation():
    with pytest.raises(ValidationError):
        ProfileInput(age_years=17, sex="male", weight_kg=Decimal("70"), height_cm=170, activity_level="light", goal="maintain")
    with pytest.raises(ValidationError):
        ProfileInput(age_years=22, sex="male", weight_kg=Decimal("20"), height_cm=170, activity_level="light", goal="maintain")
    with pytest.raises(ValidationError):
        PreferencesInput(
            daily_budget_idr=5000,
            workout_days=[0, 2, 4],
            session_minutes=60,
            experience_level="beginner",
            equipment_access="gym_full",
        )
    with pytest.raises(ValidationError):
        PreferencesInput(
            daily_budget_idr=45000,
            workout_days=[0, 0, 2],
            session_minutes=60,
            experience_level="beginner",
            equipment_access="gym_full",
        )


def test_u8_screening_kidney_disease():
    allowed, _, warns, _ = evaluate_safety(
        weight_kg=70, height_cm=170, goal="maintain", screening={"kidney_disease": True}
    )
    assert allowed is False
    assert any(w["code"] == "PROFESSIONAL_CONSULT_REQUIRED" for w in warns)
