"""Strict Pydantic request schemas (extra="forbid" per PRD §2.5, NFR-01, S3)."""

from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthCredentials(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ConsentRequest(StrictModel):
    consent_version: str = "1.0"
    data_processing: bool
    ai_cloud: bool = False


class DeleteAccountRequest(StrictModel):
    password: str = Field(min_length=1, max_length=128)


class ScreeningInput(StrictModel):
    pregnant_or_breastfeeding: bool = False
    eating_disorder_history: bool = False
    kidney_disease: bool = False
    serious_injury: bool = False
    other_medical_condition: bool = False


class ProfileInput(StrictModel):
    age_years: int = Field(ge=18, le=80)
    sex: Literal["male", "female"]
    weight_kg: Decimal = Field(ge=Decimal("30.0"), le=Decimal("250.0"))
    height_cm: int = Field(ge=120, le=230)
    activity_level: Literal["sedentary", "light", "moderate", "active"]
    goal: Literal["maintain", "build_strength", "lose_weight"]
    protein_g_per_kg: Decimal = Field(default=Decimal("1.6"), ge=Decimal("1.4"), le=Decimal("2.0"))
    screening: ScreeningInput = Field(default_factory=ScreeningInput)

    @field_validator("protein_g_per_kg")
    @classmethod
    def _step_01(cls, v: Decimal) -> Decimal:
        scaled = v * Decimal(10)
        if scaled != int(scaled):
            raise ValueError("Rasio protein harus dalam kelipatan 0,1 antara 1,4 dan 2,0.")
        return v.quantize(Decimal("0.1"))


class PreferencesInput(StrictModel):
    daily_budget_idr: int = Field(ge=10_000, le=500_000)
    workout_days: list[int]
    session_minutes: Literal[30, 45, 60, 75, 90]
    experience_level: Literal["beginner", "intermediate"]
    equipment_access: Literal["bodyweight_only", "home_dumbbell", "gym_full"]
    excluded_food_ids: list[str] = Field(default_factory=list, max_length=15)
    allergies: list[str] = Field(default_factory=list, max_length=15)
    excluded_exercise_ids: list[str] = Field(default_factory=list, max_length=15)
    region: str = "default"

    @field_validator("workout_days")
    @classmethod
    def _validate_days(cls, v: list[int]) -> list[int]:
        if len(v) < 2 or len(v) > 6:
            raise ValueError("Hari latihan harus berisi 2 hingga 6 hari.")
        if len(set(v)) != len(v):
            raise ValueError("Hari latihan tidak boleh memiliki duplikat.")
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("Hari latihan harus bernilai 0 (Senin) sampai 6 (Minggu).")
        return sorted(v)


class PutProfileRequest(StrictModel):
    profile: ProfileInput | None = None
    preferences: PreferencesInput | None = None
    # Also support flat payload for convenience
    age_years: int | None = Field(default=None, ge=18, le=80)
    sex: Literal["male", "female"] | None = None
    weight_kg: Decimal | None = Field(default=None, ge=Decimal("30.0"), le=Decimal("250.0"))
    height_cm: int | None = Field(default=None, ge=120, le=230)
    activity_level: Literal["sedentary", "light", "moderate", "active"] | None = None
    goal: Literal["maintain", "build_strength", "lose_weight"] | None = None
    protein_g_per_kg: Decimal | None = Field(default=None, ge=Decimal("1.4"), le=Decimal("2.0"))
    screening: ScreeningInput | None = None
    daily_budget_idr: int | None = Field(default=None, ge=10_000, le=500_000)
    workout_days: list[int] | None = None
    session_minutes: Literal[30, 45, 60, 75, 90] | None = None
    experience_level: Literal["beginner", "intermediate"] | None = None
    equipment_access: Literal["bodyweight_only", "home_dumbbell", "gym_full"] | None = None
    excluded_food_ids: list[str] | None = Field(default=None, max_length=15)
    allergies: list[str] | None = Field(default=None, max_length=15)
    excluded_exercise_ids: list[str] | None = Field(default=None, max_length=15)
    region: str | None = None


class NutritionEstimateRequest(StrictModel):
    sex: Literal["male", "female"]
    age_years: int = Field(ge=18, le=80)
    weight_kg: Decimal = Field(ge=Decimal("30.0"), le=Decimal("250.0"))
    height_cm: int = Field(ge=120, le=230)
    activity_level: Literal["sedentary", "light", "moderate", "active"]
    goal: Literal["maintain", "build_strength", "lose_weight"]
    protein_g_per_kg: Decimal = Field(default=Decimal("1.6"), ge=Decimal("1.4"), le=Decimal("2.0"))


class GenerateMealPlanRequest(StrictModel):
    start_date: DateType
    daily_budget_idr: int | None = Field(default=None, ge=10_000, le=500_000)
    excluded_food_ids: list[str] | None = Field(default=None, max_length=15)


class MealPlanOperation(StrictModel):
    op: Literal["set_grams", "remove_item", "add_item"]
    item_id: str | None = None
    grams: int | None = None
    date: DateType | None = None
    slot: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    food_id: str | None = None


class PatchMealPlanRequest(StrictModel):
    base_version: int = Field(ge=1)
    operations: list[MealPlanOperation] = Field(min_length=1)


class ConfirmVersionRequest(StrictModel):
    base_version: int = Field(ge=0)


class GenerateWorkoutPlanRequest(StrictModel):
    week_start: DateType
    equipment_access: Literal["bodyweight_only", "home_dumbbell", "gym_full"] | None = None


class SessionMove(StrictModel):
    session_id: str
    new_date: DateType


class PatchWorkoutPlanRequest(StrictModel):
    base_version: int = Field(ge=1)
    moves: list[SessionMove] = Field(min_length=1)


class PatchWorkoutSessionRequest(StrictModel):
    status: Literal["planned", "completed", "skipped"]


class SwapExerciseRequest(StrictModel):
    exercise_id: str


class FoodLogCreateRequest(StrictModel):
    date: DateType
    meal_slot: Literal["breakfast", "lunch", "dinner", "snack"]
    food_id: str
    grams: int = Field(gt=0, le=3000)
    actual_price_idr: int | None = Field(default=None, ge=0, le=1_000_000)


class FoodLogPatchRequest(StrictModel):
    meal_slot: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    grams: int | None = Field(default=None, gt=0, le=3000)
    actual_price_idr: int | None = Field(default=None, ge=0, le=1_000_000)


class WorkoutSetEntry(StrictModel):
    reps: int | None = Field(default=None, ge=1, le=100)
    weight_kg: float | None = Field(default=None, ge=0, le=500)
    seconds: int | None = Field(default=None, ge=1, le=600)

    @field_validator("seconds")
    @classmethod
    def _check_mode(cls, v, info):
        reps = info.data.get("reps")
        if v is None and reps is None:
            raise ValueError("Set harus memiliki reps atau seconds.")
        return v


class WorkoutLogCreateRequest(StrictModel):
    date: DateType
    session_id: str | None = None
    exercise_id: str
    sets: list[WorkoutSetEntry] = Field(min_length=1, max_length=10)
    effort_rating: int | None = Field(default=None, ge=1, le=10)


class WorkoutLogPatchRequest(StrictModel):
    sets: list[WorkoutSetEntry] | None = Field(default=None, min_length=1, max_length=10)
    effort_rating: int | None = Field(default=None, ge=1, le=10)


class WeightLogRequest(StrictModel):
    date: DateType
    weight_kg: Decimal = Field(ge=Decimal("30.0"), le=Decimal("250.0"))
    apply_to_profile: bool = False


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


class AdminFoodCreateRequest(StrictModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=120)
    food_group: Literal["carb", "protein_animal", "protein_plant", "vegetable", "fruit", "dairy", "fat"]
    slots: str = Field(min_length=1, max_length=4)
    edible_pct: int = Field(ge=1, le=100)
    kcal_100g: Decimal = Field(ge=0, le=1000)
    protein_100g: Decimal = Field(ge=0, le=100)
    fat_100g: Decimal | None = Field(default=None, ge=0, le=100)
    carb_100g: Decimal | None = Field(default=None, ge=0, le=100)
    step_g: int = Field(ge=1, le=500)
    min_g: int = Field(ge=1, le=1000)
    max_g: int = Field(ge=1, le=2000)
    max_days_wk: int = Field(ge=1, le=7)
    source_id: str | None = None
    verified: bool = False
    is_active: bool = True
    reason: str = Field(min_length=3, max_length=500)


class AdminFoodPatchRequest(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    food_group: Literal["carb", "protein_animal", "protein_plant", "vegetable", "fruit", "dairy", "fat"] | None = None
    slots: str | None = Field(default=None, min_length=1, max_length=4)
    edible_pct: int | None = Field(default=None, ge=1, le=100)
    kcal_100g: Decimal | None = Field(default=None, ge=0, le=1000)
    protein_100g: Decimal | None = Field(default=None, ge=0, le=100)
    fat_100g: Decimal | None = Field(default=None, ge=0, le=100)
    carb_100g: Decimal | None = Field(default=None, ge=0, le=100)
    step_g: int | None = Field(default=None, ge=1, le=500)
    min_g: int | None = Field(default=None, ge=1, le=1000)
    max_g: int | None = Field(default=None, ge=1, le=2000)
    max_days_wk: int | None = Field(default=None, ge=1, le=7)
    source_id: str | None = None
    verified: bool | None = None
    is_active: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class AdminExerciseCreateRequest(StrictModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=120)
    pattern: Literal[
        "squat",
        "hinge",
        "lunge",
        "horizontal_push",
        "horizontal_pull",
        "vertical_push",
        "vertical_pull",
        "core",
        "carry",
    ]
    muscle_group: str = Field(min_length=2, max_length=40)
    equipment: Literal["bodyweight", "dumbbell", "gym"]
    difficulty: int = Field(ge=1, le=2)
    rank: int = Field(ge=1, le=200)
    sets: int = Field(ge=1, le=10)
    reps_min: int = Field(ge=1, le=600)
    reps_max: int = Field(ge=1, le=600)
    unit: Literal["reps", "seconds"]
    rest_s: int = Field(ge=10, le=300)
    instructions: str = ""
    contraindication_notes: str = "Hentikan bila nyeri tajam; bukan pengganti saran tenaga kesehatan."
    is_active: bool = True
    reason: str = Field(min_length=3, max_length=500)


class AdminExercisePatchRequest(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    pattern: (
        Literal[
            "squat",
            "hinge",
            "lunge",
            "horizontal_push",
            "horizontal_pull",
            "vertical_push",
            "vertical_pull",
            "core",
            "carry",
        ]
        | None
    ) = None
    muscle_group: str | None = Field(default=None, min_length=2, max_length=40)
    equipment: Literal["bodyweight", "dumbbell", "gym"] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=2)
    rank: int | None = Field(default=None, ge=1, le=200)
    sets: int | None = Field(default=None, ge=1, le=10)
    reps_min: int | None = Field(default=None, ge=1, le=600)
    reps_max: int | None = Field(default=None, ge=1, le=600)
    unit: Literal["reps", "seconds"] | None = None
    rest_s: int | None = Field(default=None, ge=10, le=300)
    instructions: str | None = None
    contraindication_notes: str | None = None
    is_active: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class AdminPriceCreateRequest(StrictModel):
    food_id: str | None = None
    food_code: str | None = None
    region: str = "default"
    package_g: int = Field(ge=1, le=25_000)
    price_idr: int = Field(gt=0, le=10_000_000)
    source: str = Field(min_length=2, max_length=200)
    recorded_at: DateType
    reason: str = Field(default="Penambahan harga manual", min_length=3, max_length=500)


def dump_clean(obj: BaseModel) -> dict[str, Any]:
    return obj.model_dump(exclude_unset=True)
