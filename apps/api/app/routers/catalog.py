"""Catalog & price read endpoints (PRD §5.4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import current_user
from app.models import Exercise, Food, FoodPrice, User

router = APIRouter(tags=["catalog"])


def _latest_prices(db: Session, region: str = "default") -> dict[str, FoodPrice]:
    rows = db.scalars(
        select(FoodPrice)
        .where(FoodPrice.region == region)
        .order_by(desc(FoodPrice.recorded_at), desc(FoodPrice.created_at), desc(FoodPrice.id))
    ).all()
    out: dict[str, FoodPrice] = {}
    for r in rows:
        if r.food_id not in out:
            out[r.food_id] = r
    return out


def serialize_food(f: Food, p: FoodPrice | None) -> dict:
    return {
        "id": f.id,
        "code": f.code,
        "name": f.name,
        "food_group": f.food_group,
        "slots": f.slots,
        "edible_pct": f.edible_pct,
        "kcal_100g": float(f.kcal_100g),
        "protein_100g": float(f.protein_100g),
        "fat_100g": float(f.fat_100g) if f.fat_100g is not None else None,
        "carb_100g": float(f.carb_100g) if f.carb_100g is not None else None,
        "step_g": f.step_g,
        "min_g": f.min_g,
        "max_g": f.max_g,
        "max_days_wk": f.max_days_wk,
        "source_id": f.source_id,
        "verified": f.verified,
        "is_active": f.is_active,
        "latest_price": (
            {
                "price_id": p.id,
                "region": p.region,
                "package_g": p.package_g,
                "price_idr": p.price_idr,
                "source": p.source,
                "recorded_at": p.recorded_at.isoformat(),
            }
            if p
            else None
        ),
    }


def serialize_exercise(e: Exercise) -> dict:
    return {
        "id": e.id,
        "code": e.code,
        "name": e.name,
        "pattern": e.pattern,
        "muscle_group": e.muscle_group,
        "equipment": e.equipment,
        "difficulty": e.difficulty,
        "rank": e.rank,
        "sets": e.sets,
        "reps_min": e.reps_min,
        "reps_max": e.reps_max,
        "unit": e.unit,
        "rest_s": e.rest_s,
        "instructions": e.instructions,
        "contraindication_notes": e.contraindication_notes,
        "is_active": e.is_active,
    }


@router.get("/foods")
def list_foods(
    query: str = "",
    group: str = "",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Food).where(Food.is_active.is_(True)).order_by(Food.name)
    if group:
        stmt = stmt.where(Food.food_group == group)
    all_rows = db.scalars(stmt).all()
    if query:
        q = query.strip().lower()
        all_rows = [f for f in all_rows if q in f.name.lower() or q in f.code.lower()]
    total = len(all_rows)
    sliced = all_rows[offset : offset + limit]
    lp = _latest_prices(db, "default")
    return {"items": [serialize_food(f, lp.get(f.id)) for f in sliced], "total": total}


@router.get("/prices")
def list_prices(
    region: str = "default",
    food_id: str = "",
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    foods = {f.id: f for f in db.scalars(select(Food).where(Food.is_active.is_(True))).all()}
    lp = _latest_prices(db, region or "default")
    items = []
    for fid, p in lp.items():
        if food_id and fid != food_id:
            continue
        f = foods.get(fid)
        if not f:
            continue
        items.append(
            {
                "price_id": p.id,
                "food_id": fid,
                "food_code": f.code,
                "food_name": f.name,
                "region": p.region,
                "package_g": p.package_g,
                "price_idr": p.price_idr,
                "source": p.source,
                "recorded_at": p.recorded_at.isoformat(),
            }
        )
    items.sort(key=lambda x: x["food_name"])
    return {"items": items, "total": len(items)}


@router.get("/exercises")
def list_exercises(
    pattern: str = "",
    equipment: str = "",
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Exercise).where(Exercise.is_active.is_(True)).order_by(Exercise.rank, Exercise.code)
    if pattern:
        stmt = stmt.where(Exercise.pattern == pattern)
    if equipment:
        stmt = stmt.where(Exercise.equipment == equipment)
    rows = db.scalars(stmt).all()
    return {"items": [serialize_exercise(e) for e in rows], "total": len(rows)}

