"""Shared meal-plan DB orchestration: FoodSpec loading, generating & persisting drafts, manual edits, confirm."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_catalog_version
from app.core.errors import AppError, validation_error
from app.models import (
    Food,
    FoodPrice,
    MealPlan,
    MealPlanItem,
    NutritionTarget,
    PlanChangeLog,
    Preferences,
    Profile,
    new_id,
)
from app.services.nutrition.engine import evaluate_safety
from app.services.optimizer.checker import (
    ALL_SLOTS,
    ENGINE_VERSION,
    FoodSpec,
    check_day,
    item_metrics,
)
from app.services.optimizer.model import (
    compute_week_summary,
    format_day_response,
    solve_week_plan,
)
from app.services.optimizer.shopping import build_shopping_list


def load_food_specs(
    db: Session,
    *,
    region: str = "default",
    excluded_ids: set[str] | None = None,
    fixed_price_ids: dict[str, str] | None = None,
) -> list[FoodSpec]:
    excl = excluded_ids or set()
    foods = db.scalars(select(Food).where(Food.is_active.is_(True)).order_by(Food.code)).all()
    if fixed_price_ids:
        prices_by_id = {
            p.id: p for p in db.scalars(select(FoodPrice).where(FoodPrice.id.in_(list(fixed_price_ids.values())))).all()
        }
    else:
        prices_by_id = {}

    all_prices = db.scalars(
        select(FoodPrice)
        .where(FoodPrice.region == region)
        .order_by(desc(FoodPrice.recorded_at), desc(FoodPrice.created_at), desc(FoodPrice.id))
    ).all()
    latest_by_food: dict[str, FoodPrice] = {}
    for p in all_prices:
        if p.food_id not in latest_by_food:
            latest_by_food[p.food_id] = p

    specs: list[FoodSpec] = []
    for f in foods:
        if f.id in excl:
            continue
        p: FoodPrice | None = None
        if fixed_price_ids and f.id in fixed_price_ids:
            p = prices_by_id.get(fixed_price_ids[f.id])
        if p is None:
            p = latest_by_food.get(f.id)
        if p is None:
            continue
        specs.append(
            FoodSpec(
                id=f.id,
                code=f.code,
                name=f.name,
                food_group=f.food_group,
                slots=f.slots,
                edible_pct=int(f.edible_pct),
                kcal_100g=Decimal(str(f.kcal_100g)),
                protein_100g=Decimal(str(f.protein_100g)),
                step_g=int(f.step_g),
                min_g=int(f.min_g),
                max_g=int(f.max_g),
                max_days_wk=int(f.max_days_wk),
                price_id=p.id,
                package_g=int(p.package_g),
                price_idr=int(p.price_idr),
                recorded_at=p.recorded_at.isoformat(),
            )
        )
    return specs


def require_user_can_generate(db: Session, user_id: str) -> tuple[Profile, Preferences, NutritionTarget]:
    prof = db.get(Profile, user_id)
    pref = db.get(Preferences, user_id)
    if not prof or not pref:
        raise validation_error("Profil belum lengkap. Lengkapi profil terlebih dahulu.", field="profile")
    allowed, _, _, _ = evaluate_safety(
        weight_kg=prof.weight_kg, height_cm=prof.height_cm, goal=prof.goal, screening=prof.screening_json
    )
    if not allowed:
        raise AppError("PROFESSIONAL_CONSULT_REQUIRED")
    nt = db.scalar(
        select(NutritionTarget).where(NutritionTarget.user_id == user_id).order_by(desc(NutritionTarget.created_at)).limit(1)
    )
    if not nt:
        raise validation_error("Target nutrisi belum tersedia.")
    return prof, pref, nt


def serialize_meal_plan(db: Session, plan: MealPlan) -> dict[str, Any]:
    foods_map = {f.id: f for f in db.scalars(select(Food)).all()}
    price_ids = {it.price_id for it in plan.items}
    prices_map = (
        {p.id: p for p in db.scalars(select(FoodPrice).where(FoodPrice.id.in_(price_ids))).all()} if price_ids else {}
    )
    specs_by_id: dict[str, FoodSpec] = {}
    for fid, f in foods_map.items():
        # Match the price used in plan items if present, else latest
        p = next((prices_map[it.price_id] for it in plan.items if it.food_id == fid and it.price_id in prices_map), None)
        if not p:
            p = db.scalar(
                select(FoodPrice).where(FoodPrice.food_id == fid).order_by(desc(FoodPrice.recorded_at)).limit(1)
            )
        if p:
            specs_by_id[fid] = FoodSpec(
                id=f.id,
                code=f.code,
                name=f.name,
                food_group=f.food_group,
                slots=f.slots,
                edible_pct=int(f.edible_pct),
                kcal_100g=Decimal(str(f.kcal_100g)),
                protein_100g=Decimal(str(f.protein_100g)),
                step_g=int(f.step_g),
                min_g=int(f.min_g),
                max_g=int(f.max_g),
                max_days_wk=int(f.max_days_wk),
                price_id=p.id,
                package_g=int(p.package_g),
                price_idr=int(p.price_idr),
                recorded_at=p.recorded_at.isoformat(),
            )

    from datetime import timedelta

    days_out: list[dict[str, Any]] = []
    for offset in range(7):
        d = plan.start_date + timedelta(days=offset)
        d_str = d.isoformat()
        day_items = [
            {"id": it.id, "slot": it.meal_slot, "food_id": it.food_id, "grams": int(it.grams)}
            for it in plan.items
            if it.date == d
        ]
        checked = check_day(
            day_date=d_str,
            items=day_items,
            foods_by_id=specs_by_id,
            target_energy_kcal=plan.target_energy_kcal,
            target_protein_g=plan.target_protein_g,
            budget_idr=plan.budget_limit_idr,
        )
        days_out.append(format_day_response(d_str, checked))

    _, week_totals, _ = compute_week_summary(days_out)
    shopping = build_shopping_list(days_out, specs_by_id)
    return {
        "id": plan.id,
        "group_id": plan.group_id,
        "version": plan.version,
        "parent_id": plan.parent_id,
        "status": plan.status,
        "result_status": plan.result_status,
        "start_date": plan.start_date.isoformat(),
        "budget_limit_idr": plan.budget_limit_idr,
        "targets": {"energy_kcal": plan.target_energy_kcal, "protein_g": plan.target_protein_g},
        "days": days_out,
        "week_totals": week_totals,
        "shopping_list": shopping,
        "unmet_constraints": plan.unmet_json or [],
        "warnings": plan.warnings_json or [],
        "generation_params": plan.generation_params_json or {},
        "engine_version": plan.engine_version,
        "catalog_version": plan.catalog_version,
        "created_at": plan.created_at.isoformat(),
        "confirmed_at": plan.confirmed_at.isoformat() if plan.confirmed_at else None,
    }


def generate_and_save_meal_plan(
    db: Session,
    *,
    user_id: str,
    start_date: date,
    daily_budget_idr: int | None = None,
    excluded_food_ids: list[str] | None = None,
    fixed_price_ids: dict[str, str] | None = None,
    source: str = "user",
    dry_run: bool = False,
) -> dict[str, Any]:
    _, pref, nt = require_user_can_generate(db, user_id)
    budget = int(daily_budget_idr if daily_budget_idr is not None else pref.daily_budget_idr)
    if budget < 10_000 or budget > 500_000:
        raise validation_error(
            "Budget harian harus antara 10000 dan 500000 rupiah.",
            field="daily_budget_idr",
            issue="out_of_range",
            min=10000,
            max=500000,
        )
    excl_list = (
        list(excluded_food_ids)
        if excluded_food_ids is not None
        else list(set((pref.excluded_food_ids or []) + (pref.allergies or [])))
    )
    if len(excl_list) > 15:
        raise validation_error("Maksimum 15 pangan dapat dikecualikan.", field="excluded_food_ids")

    specs = load_food_specs(
        db, region=pref.region or "default", excluded_ids=set(excl_list), fixed_price_ids=fixed_price_ids
    )
    s = get_settings()
    solved = solve_week_plan(
        foods=specs,
        start_date=start_date,
        budget_idr=budget,
        target_energy_kcal=int(nt.energy_target_kcal),
        target_protein_g=int(nt.protein_target_g),
        time_limit_per_day_s=s.optimizer_time_limit_seconds_per_day,
        hard_limit_s=s.optimizer_hard_limit_seconds,
    )

    if solved["result_status"] == "INFEASIBLE":
        best_effort = {
            **solved,
            "is_best_effort": True,
        }
        suggestions = [
            f"Naikkan budget harian minimal ke Rp {solved['minimum_budget_required_idr']:,}.".replace(",", "."),
            "Kurangi daftar pangan yang dikecualikan (terutama sumber protein nabati/hewani ekonomis seperti tempe, tahu, telur).",
            "Sesuaikan rasio protein/kg pada halaman Nutrisi ke 1,4 g/kg bila sesuai kebutuhan.",
        ]
        if dry_run:
            return {
                "result_status": "INFEASIBLE",
                "minimum_budget_required_idr": solved["minimum_budget_required_idr"],
                "week_totals": solved["week_totals"],
                "unmet_constraints": solved["unmet_constraints"],
                "best_effort": best_effort,
                "suggestions": suggestions,
            }
        raise AppError(
            "NO_FEASIBLE_PLAN",
            "Tidak ditemukan menu 7 hari yang memenuhi target gizi dalam batas budget ini.",
            details={
                "unmet_constraints": solved["unmet_constraints"],
                "best_effort": best_effort,
                "minimum_budget_required_idr": solved["minimum_budget_required_idr"],
                "suggestions": suggestions,
            },
        )

    if dry_run:
        return solved

    cat_ver = get_catalog_version(db)
    price_map = {sp.id: sp.price_id for sp in specs}
    gen_params = {
        "start_date": start_date.isoformat(),
        "daily_budget_idr": budget,
        "excluded_food_ids": sorted(excl_list),
        "target_energy_kcal": int(nt.energy_target_kcal),
        "target_protein_g": int(nt.protein_target_g),
        "price_ids": price_map,
        "catalog_version": cat_ver,
        "engine_version": ENGINE_VERSION,
    }
    plan = MealPlan(
        id=new_id(),
        group_id=new_id(),
        version=1,
        parent_id=None,
        user_id=user_id,
        status="draft",
        result_status=solved["result_status"],
        start_date=start_date,
        budget_limit_idr=budget,
        target_energy_kcal=int(nt.energy_target_kcal),
        target_protein_g=int(nt.protein_target_g),
        generation_params_json=gen_params,
        unmet_json=solved["unmet_constraints"],
        warnings_json=solved["warnings"],
        day_status_json={d["date"]: d["day_status"] for d in solved["days"]},
        engine_version=ENGINE_VERSION,
        catalog_version=cat_ver,
    )
    db.add(plan)
    db.flush()

    for d in solved["days"]:
        d_date = date.fromisoformat(d["date"])
        for sl in d["slots"]:
            for it in sl["items"]:
                db.add(
                    MealPlanItem(
                        id=new_id(),
                        meal_plan_id=plan.id,
                        date=d_date,
                        meal_slot=sl["slot"],
                        food_id=it["food_id"],
                        grams=int(it["grams"]),
                        price_id=it["price_id"],
                        cost_idr=int(it["cost_idr"]),
                        energy_kcal=Decimal(str(it["energy_kcal"])),
                        protein_g=Decimal(str(it["protein_g"])),
                    )
                )
    db.add(
        PlanChangeLog(
            user_id=user_id,
            plan_type="meal",
            plan_id=plan.id,
            from_version=None,
            to_version=1,
            source=source,
            diff_json={"action": "generate", "budget_limit_idr": budget},
        )
    )
    db.flush()
    db.refresh(plan)
    return serialize_meal_plan(db, plan)


def apply_meal_plan_operations(
    db: Session,
    *,
    plan: MealPlan,
    base_version: int,
    operations: list[dict[str, Any]],
    source: str = "user",
) -> dict[str, Any]:
    if plan.version != base_version:
        raise AppError("PLAN_VERSION_CONFLICT")
    if plan.status == "archived":
        raise AppError("CONFLICT", "Rencana yang sudah diarsipkan tidak dapat diubah.")

    # Max version in group so new version never collides with uq_meal_plans_group_version
    max_v = db.scalar(
        select(MealPlan.version)
        .where(MealPlan.group_id == plan.group_id)
        .order_by(desc(MealPlan.version))
        .limit(1)
    )
    next_version = int(max_v or plan.version) + 1

    working: list[dict[str, Any]] = [
        {
            "orig_id": it.id,
            "date": it.date,
            "meal_slot": it.meal_slot,
            "food_id": it.food_id,
            "grams": int(it.grams),
            "price_id": it.price_id,
        }
        for it in plan.items
    ]

    for op in operations:
        kind = op.get("op")
        if kind == "set_grams":
            iid = op.get("item_id")
            g = int(op.get("grams") or 0)
            if g <= 0 or g > 2000:
                raise validation_error("Gram harus antara 1 dan 2000.", field="grams")
            target = next((w for w in working if w["orig_id"] == iid), None)
            if not target:
                raise AppError("NOT_FOUND", "Item rencana tidak ditemukan.")
            target["grams"] = g
        elif kind == "remove_item":
            iid = op.get("item_id")
            before = len(working)
            working = [w for w in working if w["orig_id"] != iid]
            if len(working) == before:
                raise AppError("NOT_FOUND", "Item rencana tidak ditemukan.")
        elif kind == "add_item":
            d_raw = op.get("date")
            d_val = d_raw if isinstance(d_raw, date) else date.fromisoformat(str(d_raw))
            slot = op.get("slot")
            fid = op.get("food_id")
            g = int(op.get("grams") or 0)
            if slot not in ALL_SLOTS:
                raise validation_error("Slot makan tidak valid.", field="slot")
            if g <= 0 or g > 2000:
                raise validation_error("Gram harus antara 1 dan 2000.", field="grams")
            food = db.get(Food, fid)
            if not food or not food.is_active:
                raise validation_error("Bahan pangan tidak ditemukan.", field="food_id")
            p = db.scalar(
                select(FoodPrice).where(FoodPrice.food_id == fid).order_by(desc(FoodPrice.recorded_at)).limit(1)
            )
            if not p:
                raise validation_error("Harga bahan belum tersedia.", field="food_id")
            working.append(
                {
                    "orig_id": new_id(),
                    "date": d_val,
                    "meal_slot": slot,
                    "food_id": fid,
                    "grams": g,
                    "price_id": p.id,
                }
            )
        else:
            raise validation_error("Operasi tidak dikenal.", field="op")

    # Build specs for all foods in working set
    fixed_prices = {w["food_id"]: w["price_id"] for w in working}
    specs = load_food_specs(db, fixed_price_ids=fixed_prices)
    specs_by_id = {sp.id: sp for sp in specs}

    from datetime import timedelta

    days_checked: list[dict[str, Any]] = []
    for offset in range(7):
        d_val = plan.start_date + timedelta(days=offset)
        d_str = d_val.isoformat()
        d_items = [
            {"slot": w["meal_slot"], "food_id": w["food_id"], "grams": w["grams"]}
            for w in working
            if w["date"] == d_val
        ]
        c = check_day(
            day_date=d_str,
            items=d_items,
            foods_by_id=specs_by_id,
            target_energy_kcal=plan.target_energy_kcal,
            target_protein_g=plan.target_protein_g,
            budget_idr=plan.budget_limit_idr,
        )
        days_checked.append(format_day_response(d_str, c))

    week_status, _, all_unmet = compute_week_summary(days_checked)

    # Archive previous draft when cloning from a draft so only the latest draft stays active
    if plan.status == "draft":
        plan.status = "archived"

    new_plan = MealPlan(
        id=new_id(),
        group_id=plan.group_id,
        version=next_version,
        parent_id=plan.id,
        user_id=plan.user_id,
        status="draft",
        result_status=week_status,
        start_date=plan.start_date,
        budget_limit_idr=plan.budget_limit_idr,
        target_energy_kcal=plan.target_energy_kcal,
        target_protein_g=plan.target_protein_g,
        generation_params_json=plan.generation_params_json,
        unmet_json=all_unmet,
        warnings_json=plan.warnings_json,
        day_status_json={d["date"]: d["day_status"] for d in days_checked},
        engine_version=plan.engine_version,
        catalog_version=get_catalog_version(db),
    )
    db.add(new_plan)
    db.flush()

    for w in working:
        sp = specs_by_id[w["food_id"]]
        cost, e_kcal, p_g = item_metrics(sp, w["grams"])
        db.add(
            MealPlanItem(
                id=new_id(),
                meal_plan_id=new_plan.id,
                date=w["date"],
                meal_slot=w["meal_slot"],
                food_id=w["food_id"],
                grams=w["grams"],
                price_id=w["price_id"],
                cost_idr=cost,
                energy_kcal=e_kcal,
                protein_g=p_g,
            )
        )
    db.add(
        PlanChangeLog(
            user_id=plan.user_id,
            plan_type="meal",
            plan_id=new_plan.id,
            from_version=plan.version,
            to_version=next_version,
            source=source,
            diff_json={"operations": operations},
        )
    )
    db.flush()
    db.refresh(new_plan)
    return serialize_meal_plan(db, new_plan)


def confirm_meal_plan(db: Session, plan: MealPlan, base_version: int) -> dict[str, Any]:
    if plan.version != base_version:
        raise AppError("PLAN_VERSION_CONFLICT")
    if plan.result_status == "INFEASIBLE":
        raise AppError(
            "NO_FEASIBLE_PLAN",
            "Rencana dengan status INFEASIBLE tidak dapat dikonfirmasi.",
            details={"unmet_constraints": plan.unmet_json or []},
        )
    # Archive any previously confirmed plans in the same group (max 1 confirmed per group_id, PRD §3.5.6)
    prev_confirmed = db.scalars(
        select(MealPlan).where(MealPlan.group_id == plan.group_id, MealPlan.status == "confirmed")
    ).all()
    for p in prev_confirmed:
        if p.id != plan.id:
            p.status = "archived"
    plan.status = "confirmed"
    plan.confirmed_at = datetime.now(UTC)
    db.flush()
    db.refresh(plan)
    return serialize_meal_plan(db, plan)
