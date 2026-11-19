"""SQLAlchemy models (PRD §4.2). Portable types only (no Postgres-specific features)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


UUID = String(36)
TS = DateTime(timezone=True)


def _user_fk() -> Any:
    return ForeignKey("users.id", ondelete="CASCADE")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="user")
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_failed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    __table_args__ = (CheckConstraint("role IN ('user','admin')", name="ck_users_role"),)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False, index=True)
    consent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    data_processing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ai_cloud: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), primary_key=True)
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(6), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_level: Mapped[str] = mapped_column(String(10), nullable=False)
    goal: Mapped[str] = mapped_column(String(20), nullable=False)
    protein_g_per_kg: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False, default=Decimal("1.6"))
    screening_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("sex IN ('male','female')", name="ck_profiles_sex"),
        CheckConstraint("activity_level IN ('sedentary','light','moderate','active')", name="ck_profiles_activity"),
        CheckConstraint("goal IN ('maintain','build_strength','lose_weight')", name="ck_profiles_goal"),
    )


class Preferences(Base):
    __tablename__ = "preferences"
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), primary_key=True)
    daily_budget_idr: Mapped[int] = mapped_column(Integer, nullable=False)
    workout_days: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    session_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    experience_level: Mapped[str] = mapped_column(String(15), nullable=False)
    equipment_access: Mapped[str] = mapped_column(String(20), nullable=False)
    excluded_food_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    allergies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    excluded_exercise_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    region: Mapped[str] = mapped_column(String(40), nullable=False, default="default")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)


class NutritionTarget(Base):
    __tablename__ = "nutrition_targets"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False, index=True)
    inputs_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    ree_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    tdee_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    energy_target_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_target_g: Mapped[int] = mapped_column(Integer, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    formula_version: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)


class Food(Base):
    __tablename__ = "foods"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    food_group: Mapped[str] = mapped_column(String(20), nullable=False)
    slots: Mapped[str] = mapped_column(String(4), nullable=False)
    edible_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    kcal_100g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    protein_100g: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    fat_100g: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    carb_100g: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    step_g: Mapped[int] = mapped_column(Integer, nullable=False)
    min_g: Mapped[int] = mapped_column(Integer, nullable=False)
    max_g: Mapped[int] = mapped_column(Integer, nullable=False)
    max_days_wk: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "food_group IN ('carb','protein_animal','protein_plant','vegetable','fruit','dairy','fat')",
            name="ck_foods_group",
        ),
        CheckConstraint("edible_pct BETWEEN 1 AND 100", name="ck_foods_edible"),
    )


class FoodAlias(Base):
    __tablename__ = "food_aliases"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    food_id: Mapped[str] = mapped_column(UUID, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)


class FoodPrice(Base):
    """Append-only: never update or delete rows."""

    __tablename__ = "food_prices"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    food_id: Mapped[str] = mapped_column(UUID, ForeignKey("foods.id"), nullable=False)
    region: Mapped[str] = mapped_column(String(40), nullable=False)
    package_g: Mapped[int] = mapped_column(Integer, nullable=False)
    price_idr: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str | None] = mapped_column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("package_g > 0", name="ck_prices_package"),
        CheckConstraint("price_idr > 0", name="ck_prices_price"),
        Index("ix_food_prices_lookup", "food_id", "region", "recorded_at"),
    )


class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    pattern: Mapped[str] = mapped_column(String(20), nullable=False)
    muscle_group: Mapped[str] = mapped_column(String(40), nullable=False)
    equipment: Mapped[str] = mapped_column(String(12), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_min: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_max: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    rest_s: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contraindication_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "pattern IN ('squat','hinge','lunge','horizontal_push','horizontal_pull','vertical_push',"
            "'vertical_pull','core','carry')",
            name="ck_ex_pattern",
        ),
        CheckConstraint("equipment IN ('bodyweight','dumbbell','gym')", name="ck_ex_equipment"),
        CheckConstraint("difficulty BETWEEN 1 AND 2", name="ck_ex_difficulty"),
        CheckConstraint("unit IN ('reps','seconds')", name="ck_ex_unit"),
    )


class MealPlan(Base):
    __tablename__ = "meal_plans"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(UUID, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(UUID, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    result_status: Mapped[str] = mapped_column(String(12), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    budget_limit_idr: Mapped[int] = mapped_column(Integer, nullable=False)
    target_energy_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_protein_g: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    unmet_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    day_status_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    engine_version: Mapped[str] = mapped_column(String(30), nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    items: Mapped[list[MealPlanItem]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )
    __table_args__ = (
        UniqueConstraint("group_id", "version", name="uq_meal_plans_group_version"),
        CheckConstraint("status IN ('draft','confirmed','archived')", name="ck_mp_status"),
        CheckConstraint("result_status IN ('FEASIBLE','PARTIAL','INFEASIBLE')", name="ck_mp_result"),
    )


class MealPlanItem(Base):
    __tablename__ = "meal_plan_items"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    meal_plan_id: Mapped[str] = mapped_column(UUID, ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_slot: Mapped[str] = mapped_column(String(10), nullable=False)
    food_id: Mapped[str] = mapped_column(UUID, ForeignKey("foods.id"), nullable=False)
    grams: Mapped[int] = mapped_column(Integer, nullable=False)
    price_id: Mapped[str] = mapped_column(UUID, ForeignKey("food_prices.id"), nullable=False)
    cost_idr: Mapped[int] = mapped_column(Integer, nullable=False)
    energy_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    plan: Mapped[MealPlan] = relationship(back_populates="items")
    __table_args__ = (CheckConstraint("meal_slot IN ('breakfast','lunch','dinner','snack')", name="ck_mpi_slot"),)


class WorkoutPlan(Base):
    __tablename__ = "workout_plans"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    engine_version: Mapped[str] = mapped_column(String(30), nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)
    sessions: Mapped[list[WorkoutSession]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True, order_by="WorkoutSession.date"
    )
    __table_args__ = (CheckConstraint("status IN ('draft','confirmed','archived')", name="ck_wp_status"),)


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(UUID, ForeignKey("workout_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    template_code: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="planned")
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    plan: Mapped[WorkoutPlan] = relationship(back_populates="sessions")
    exercises: Mapped[list[WorkoutSessionExercise]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkoutSessionExercise.position",
    )
    __table_args__ = (CheckConstraint("status IN ('planned','completed','skipped')", name="ck_ws_status"),)


class WorkoutSessionExercise(Base):
    __tablename__ = "workout_session_exercises"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    exercise_id: Mapped[str] = mapped_column(UUID, ForeignKey("exercises.id"), nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_min: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_max: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    rest_s: Mapped[int] = mapped_column(Integer, nullable=False)
    alternatives_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    session: Mapped[WorkoutSession] = relationship(back_populates="exercises")


class PlanChangeLog(Base):
    __tablename__ = "plan_change_log"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(String(10), nullable=False)
    plan_id: Mapped[str] = mapped_column(UUID, nullable=False)
    from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(15), nullable=False)
    diff_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("plan_type IN ('meal','workout')", name="ck_pcl_type"),
        CheckConstraint("source IN ('user','ai_proposal','system')", name="ck_pcl_source"),
    )


class FoodLog(Base):
    __tablename__ = "food_logs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_slot: Mapped[str] = mapped_column(String(10), nullable=False)
    food_id: Mapped[str] = mapped_column(UUID, ForeignKey("foods.id"), nullable=False)
    grams: Mapped[int] = mapped_column(Integer, nullable=False)
    energy_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    cost_idr: Mapped[int] = mapped_column(Integer, nullable=False)
    price_id: Mapped[str | None] = mapped_column(UUID, ForeignKey("food_prices.id"), nullable=True)
    cost_is_actual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (CheckConstraint("grams > 0", name="ck_fl_grams"), Index("ix_food_logs_user_date", "user_id", "date"))


class WorkoutLog(Base):
    __tablename__ = "workout_logs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        UUID, ForeignKey("workout_sessions.id", ondelete="SET NULL"), nullable=True
    )
    exercise_id: Mapped[str] = mapped_column(UUID, ForeignKey("exercises.id"), nullable=False)
    sets_json: Mapped[list] = mapped_column(JSON, nullable=False)
    effort_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("effort_rating IS NULL OR effort_rating BETWEEN 1 AND 10", name="ck_wl_effort"),
        Index("ix_workout_logs_user_date", "user_id", "date"),
    )


class WeightLog(Base):
    __tablename__ = "weight_logs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_weight_user_date"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False)
    conversation_id: Mapped[str] = mapped_column(UUID, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_chat_role"),
        Index("ix_chat_user_conv", "user_id", "conversation_id", "created_at"),
    )


class AIProposal(Base):
    __tablename__ = "ai_proposals"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(UUID, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    preview_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    base_plan_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    base_plan_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    base_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    __table_args__ = (
        CheckConstraint("type IN ('change_budget','exclude_food','reschedule_workout')", name="ck_prop_type"),
        CheckConstraint("status IN ('pending','confirmed','rejected','expired','failed')", name="ck_prop_status"),
    )


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "status IN ('ok','timeout','error','rate_limited','invalid_output','fallback_template','safety','cache')",
            name="ck_aii_status",
        ),
        Index("ix_ai_interactions_user_created", "user_id", "created_at"),
    )


class AICache(Base):
    __tablename__ = "ai_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID, _user_fk(), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    admin_id: Mapped[str | None] = mapped_column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    entity: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, nullable=False)


class SystemState(Base):
    __tablename__ = "system_state"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)

