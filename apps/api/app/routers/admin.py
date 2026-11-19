"""Admin catalog CRUD, price append, all-or-nothing CSV import, and audit log (PRD §5.8)."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import bump_catalog_version, get_catalog_version, require_admin
from app.core.errors import AppError, validation_error
from app.models import AdminAuditLog, Exercise, Food, FoodPrice, User, new_id
from app.routers.catalog import _latest_prices, serialize_exercise, serialize_food
from app.schemas import (
    AdminExerciseCreateRequest,
    AdminExercisePatchRequest,
    AdminFoodCreateRequest,
    AdminFoodPatchRequest,
    AdminPriceCreateRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _record_audit(
    db: Session,
    *,
    admin_id: str,
    action: str,
    entity: str,
    entity_id: str | None,
    before: dict | None,
    after: dict | None,
    reason: str,
) -> None:
    db.add(
        AdminAuditLog(
            id=new_id(),
            admin_id=admin_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before_json=before,
            after_json=after,
            reason=reason,
        )
    )


def _validate_price_fields(package_g: int, price_idr: int, recorded_at: date, today: date | None = None) -> list[str]:
    t = today or date.today()
    issues: list[str] = []
    if package_g < 1 or package_g > 25_000:
        issues.append("package_g_out_of_range")
    if price_idr <= 0:
        issues.append("price_idr_non_positive")
    if package_g > 0:
        price_per_kg = price_idr * 1000 / package_g
        if price_per_kg < 1_000 or price_per_kg > 500_000:
            issues.append("price_per_kg_out_of_range")
    if recorded_at > t:
        issues.append("recorded_at_in_future")
    if recorded_at < (t - timedelta(days=90)):
        issues.append("recorded_at_too_old")
    return issues


@router.get("/foods")
def admin_list_foods(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Food).order_by(Food.code)).all()
    lp = _latest_prices(db, "default")
    return {
        "items": [serialize_food(f, lp.get(f.id)) for f in rows],
        "total": len(rows),
        "catalog_version": get_catalog_version(db),
    }


@router.post("/foods", status_code=201)
def admin_create_food(
    body: AdminFoodCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    code = body.code.strip().upper()
    if db.scalar(select(Food).where(Food.code == code)):
        raise validation_error("Kode pangan sudah digunakan.", field="code")
    if set(body.slots) - {"B", "L", "D", "S"}:
        raise validation_error("Slots hanya boleh berisi huruf B, L, D, S.", field="slots")
    f = Food(
        id=new_id(),
        code=code,
        name=body.name.strip(),
        food_group=body.food_group,
        slots=body.slots,
        edible_pct=body.edible_pct,
        kcal_100g=body.kcal_100g,
        protein_100g=body.protein_100g,
        fat_100g=body.fat_100g,
        carb_100g=body.carb_100g,
        step_g=body.step_g,
        min_g=body.min_g,
        max_g=body.max_g,
        max_days_wk=body.max_days_wk,
        source_id=body.source_id,
        verified=body.verified,
        is_active=body.is_active,
    )
    db.add(f)
    db.flush()
    after = serialize_food(f, None)
    _record_audit(db, admin_id=admin.id, action="create", entity="food", entity_id=f.id, before=None, after=after, reason=body.reason)
    bump_catalog_version(db)
    return after


@router.patch("/foods/{food_id}")
def admin_patch_food(
    food_id: str,
    body: AdminFoodPatchRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    f = db.get(Food, food_id)
    if not f:
        raise AppError("NOT_FOUND")
    before = serialize_food(f, None)
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    if "slots" in data and data["slots"] and (set(data["slots"]) - {"B", "L", "D", "S"}):
        raise validation_error("Slots hanya boleh berisi huruf B, L, D, S.", field="slots")
    for k, v in data.items():
        if v is not None:
            setattr(f, k, v)
    db.flush()
    after = serialize_food(f, None)
    _record_audit(
        db, admin_id=admin.id, action="update", entity="food", entity_id=f.id, before=before, after=after, reason=reason
    )
    bump_catalog_version(db)
    return after


@router.get("/exercises")
def admin_list_exercises(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Exercise).order_by(Exercise.code)).all()
    return {
        "items": [serialize_exercise(e) for e in rows],
        "total": len(rows),
        "catalog_version": get_catalog_version(db),
    }


@router.post("/exercises", status_code=201)
def admin_create_exercise(
    body: AdminExerciseCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    code = body.code.strip().upper()
    if db.scalar(select(Exercise).where(Exercise.code == code)):
        raise validation_error("Kode latihan sudah digunakan.", field="code")
    e = Exercise(
        id=new_id(),
        code=code,
        name=body.name.strip(),
        pattern=body.pattern,
        muscle_group=body.muscle_group.strip(),
        equipment=body.equipment,
        difficulty=body.difficulty,
        rank=body.rank,
        sets=body.sets,
        reps_min=body.reps_min,
        reps_max=body.reps_max,
        unit=body.unit,
        rest_s=body.rest_s,
        instructions=body.instructions,
        contraindication_notes=body.contraindication_notes,
        is_active=body.is_active,
    )
    db.add(e)
    db.flush()
    after = serialize_exercise(e)
    _record_audit(
        db, admin_id=admin.id, action="create", entity="exercise", entity_id=e.id, before=None, after=after, reason=body.reason
    )
    bump_catalog_version(db)
    return after


@router.patch("/exercises/{exercise_id}")
def admin_patch_exercise(
    exercise_id: str,
    body: AdminExercisePatchRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    e = db.get(Exercise, exercise_id)
    if not e:
        raise AppError("NOT_FOUND")
    before = serialize_exercise(e)
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    for k, v in data.items():
        if v is not None:
            setattr(e, k, v)
    db.flush()
    after = serialize_exercise(e)
    _record_audit(
        db, admin_id=admin.id, action="update", entity="exercise", entity_id=e.id, before=before, after=after, reason=reason
    )
    bump_catalog_version(db)
    return after


@router.post("/prices", status_code=201)
def admin_create_price(
    body: AdminPriceCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    food: Food | None = None
    if body.food_id:
        food = db.get(Food, body.food_id)
    elif body.food_code:
        food = db.scalar(select(Food).where(Food.code == body.food_code.strip().upper()))
    if not food:
        raise validation_error("Bahan pangan tidak ditemukan.", field="food_id")

    issues = _validate_price_fields(body.package_g, body.price_idr, body.recorded_at)
    if issues:
        raise validation_error(f"Data harga tidak valid ({', '.join(issues)}).", field="price_idr", issue=issues[0])

    dup = db.scalar(
        select(FoodPrice).where(
            FoodPrice.food_id == food.id,
            FoodPrice.region == body.region,
            FoodPrice.recorded_at == body.recorded_at,
        )
    )
    if dup:
        raise validation_error("Harga untuk bahan, wilayah, dan tanggal tersebut sudah tercatat.", field="recorded_at")

    p = FoodPrice(
        id=new_id(),
        food_id=food.id,
        region=body.region,
        package_g=body.package_g,
        price_idr=body.price_idr,
        recorded_at=body.recorded_at,
        source=body.source.strip(),
        created_by=admin.id,
    )
    db.add(p)
    db.flush()
    after = {
        "price_id": p.id,
        "food_id": food.id,
        "food_code": food.code,
        "region": p.region,
        "package_g": p.package_g,
        "price_idr": p.price_idr,
        "source": p.source,
        "recorded_at": p.recorded_at.isoformat(),
    }
    _record_audit(
        db, admin_id=admin.id, action="create_price", entity="food_price", entity_id=p.id, before=None, after=after, reason=body.reason
    )
    ver = bump_catalog_version(db)
    return {**after, "catalog_version": ver}


@router.post("/prices/import")
async def admin_import_prices(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=False),
    confirm_large_changes: bool = Query(default=False),
    reason: str = Query(default="Impor CSV harga"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except Exception as exc:
        raise validation_error("Berkas CSV harus berformat UTF-8.", field="file") from exc

    reader = csv.DictReader(io.StringIO(text))
    required_cols = {"food_code", "region", "package_g", "price_idr", "source", "recorded_at"}
    if not reader.fieldnames or not required_cols.issubset({c.strip() for c in reader.fieldnames if c}):
        raise validation_error(
            "Header CSV wajib memuat: food_code,region,package_g,price_idr,source,recorded_at.",
            field="file",
        )

    foods_by_code = {f.code.upper(): f for f in db.scalars(select(Food)).all()}
    latest = _latest_prices(db, "default")

    valid_rows: list[dict] = []
    error_rows: list[dict] = []
    warnings: list[dict] = []
    seen_keys: set[tuple[str, str, date]] = set()
    today = date.today()

    for idx, row in enumerate(reader, start=2):  # row 1 is header
        code = (row.get("food_code") or "").strip().upper()
        region = (row.get("region") or "default").strip() or "default"
        source = (row.get("source") or "").strip()
        food = foods_by_code.get(code)
        if not food:
            error_rows.append({"row": idx, "field": "food_code", "issue": "unknown_food_code"})
            continue
        try:
            pkg = int((row.get("package_g") or "").strip())
        except Exception:
            error_rows.append({"row": idx, "field": "package_g", "issue": "invalid_integer"})
            continue
        try:
            price = int((row.get("price_idr") or "").strip())
        except Exception:
            error_rows.append({"row": idx, "field": "price_idr", "issue": "invalid_integer"})
            continue
        try:
            rec_date = date.fromisoformat((row.get("recorded_at") or "").strip())
        except Exception:
            error_rows.append({"row": idx, "field": "recorded_at", "issue": "invalid_date"})
            continue
        if not source:
            error_rows.append({"row": idx, "field": "source", "issue": "required"})
            continue

        field_issues = _validate_price_fields(pkg, price, rec_date, today)
        if field_issues:
            for iss in field_issues:
                fld = "recorded_at" if "recorded_at" in iss else ("package_g" if "package" in iss else "price_idr")
                error_rows.append({"row": idx, "field": fld, "issue": iss})
            continue

        key = (food.id, region, rec_date)
        existing_db = db.scalar(
            select(FoodPrice).where(
                FoodPrice.food_id == food.id,
                FoodPrice.region == region,
                FoodPrice.recorded_at == rec_date,
            )
        )
        if key in seen_keys or existing_db:
            error_rows.append({"row": idx, "field": "recorded_at", "issue": "duplicate_food_region_date"})
            continue
        seen_keys.add(key)

        prev = latest.get(food.id)
        if prev and prev.package_g > 0:
            old_pkg_price = prev.price_idr * 1000 / prev.package_g
            new_pkg_price = price * 1000 / pkg
            if old_pkg_price > 0 and abs(new_pkg_price - old_pkg_price) / old_pkg_price > 0.50:
                pct = round((new_pkg_price - old_pkg_price) * 100 / old_pkg_price, 1)
                warnings.append(
                    {
                        "row": idx,
                        "food_code": code,
                        "code": "LARGE_PRICE_CHANGE",
                        "change_pct": pct,
                        "message": f"Perubahan harga {code} sebesar {pct}% melebihi 50%.",
                    }
                )

        valid_rows.append(
            {
                "food_id": food.id,
                "food_code": code,
                "region": region,
                "package_g": pkg,
                "price_idr": price,
                "source": source,
                "recorded_at": rec_date,
            }
        )

    if error_rows:
        raise AppError(
            "VALIDATION_ERROR",
            "Terdapat baris CSV yang tidak valid; tidak ada perubahan yang diterapkan.",
            details={"valid_rows": len(valid_rows), "error_rows": error_rows, "warnings": warnings, "applied": False},
            status=422,
        )

    if warnings and not dry_run and not confirm_large_changes:
        raise AppError(
            "VALIDATION_ERROR",
            "Terdapat perubahan harga > 50%; konfirmasi dengan confirm_large_changes=true diperlukan.",
            details={"valid_rows": len(valid_rows), "error_rows": [], "warnings": warnings, "applied": False},
            status=422,
        )

    applied = False
    if not dry_run and valid_rows:
        for vr in valid_rows:
            db.add(
                FoodPrice(
                    id=new_id(),
                    food_id=vr["food_id"],
                    region=vr["region"],
                    package_g=vr["package_g"],
                    price_idr=vr["price_idr"],
                    recorded_at=vr["recorded_at"],
                    source=vr["source"],
                    created_by=admin.id,
                )
            )
        _record_audit(
            db,
            admin_id=admin.id,
            action="import_prices",
            entity="food_price",
            entity_id=None,
            before=None,
            after={"count": len(valid_rows), "codes": [v["food_code"] for v in valid_rows]},
            reason=reason,
        )
        bump_catalog_version(db)
        applied = True

    return {
        "valid_rows": len(valid_rows),
        "error_rows": error_rows,
        "warnings": warnings,
        "applied": applied,
        "catalog_version": get_catalog_version(db),
    }


@router.get("/audit")
def admin_list_audit(
    entity: str = "",
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AdminAuditLog).order_by(desc(AdminAuditLog.created_at)).limit(limit)
    if entity:
        stmt = stmt.where(AdminAuditLog.entity == entity)
    rows = db.scalars(stmt).all()
    return {
        "items": [
            {
                "id": r.id,
                "admin_id": r.admin_id,
                "action": r.action,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "before": r.before_json,
                "after": r.after_json,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": len(rows),
    }

