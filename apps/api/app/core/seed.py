"""Idempotent database bootstrap and CSV seed importer (PRD §4.3–4.5)."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Exercise, Food, FoodAlias, FoodPrice, SystemState, User

DEFAULT_CONTRAINDICATION = "Hentikan bila nyeri tajam; bukan pengganti saran tenaga kesehatan."

DEFAULT_ALIASES: dict[str, list[str]] = {
    "BERAS": ["beras", "nasi", "beras putih"],
    "UBIJ": ["ubi", "ubi jalar"],
    "SING": ["singkong", "ketela"],
    "KENT": ["kentang"],
    "OAT": ["oat", "oatmeal", "oat gulung"],
    "ROTI": ["roti", "roti tawar"],
    "DADA": ["dada ayam", "ayam dada"],
    "PAHA": ["paha ayam", "ayam paha"],
    "TELU": ["telur", "telur ayam"],
    "LELE": ["lele", "ikan lele"],
    "TONG": ["tongkol", "ikan tongkol"],
    "TEMP": ["tempe"],
    "TAHU": ["tahu", "tahu putih"],
    "KHIJ": ["kacang hijau"],
    "KTAN": ["kacang tanah", "kacang"],
    "SUSU": ["susu", "susu uht"],
    "BAYA": ["bayam"],
    "KANG": ["kangkung"],
    "WORT": ["wortel"],
    "KOL": ["kol", "kubis"],
    "BUNC": ["buncis"],
    "TOMA": ["tomat"],
    "SAWI": ["sawi", "sawi hijau"],
    "PISA": ["pisang"],
    "MINY": ["minyak", "minyak goreng"],
}


def resolve_seed_dir() -> Path:
    s = get_settings()
    if s.seed_dir:
        return Path(s.seed_dir)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "data" / "seeds"
        if cand.exists():
            return cand
    return Path("data/seeds")


def seed_all(db: Session, seed_dir: Path | None = None) -> None:
    sdir = seed_dir or resolve_seed_dir()
    s = get_settings()

    if not db.get(SystemState, "catalog_version"):
        db.add(SystemState(key="catalog_version", value="1"))

    admin = db.scalar(select(User).where(User.role == "admin").limit(1))
    if not admin and s.admin_email and s.admin_password:
        email = s.admin_email.strip().lower()
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            existing.role = "admin"
            admin = existing
        else:
            admin = User(email=email, password_hash=hash_password(s.admin_password), role="admin")
            db.add(admin)
        db.flush()

    foods_csv = sdir / "foods.csv"
    prices_csv = sdir / "food_prices.csv"
    ex_csv = sdir / "exercises.csv"

    code_to_food: dict[str, Food] = {f.code: f for f in db.scalars(select(Food)).all()}
    if foods_csv.exists():
        with foods_csv.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                code = row["code"].strip()
                food = code_to_food.get(code)
                if not food:
                    food = Food(
                        code=code,
                        name=row["name"].strip(),
                        food_group=row["food_group"].strip(),
                        slots=row["slots"].strip(),
                        edible_pct=int(row["edible_pct"]),
                        kcal_100g=Decimal(row["kcal_100g"]),
                        protein_100g=Decimal(row["protein_100g"]),
                        fat_100g=Decimal(row["fat_100g"]) if row.get("fat_100g") else None,
                        carb_100g=Decimal(row["carb_100g"]) if row.get("carb_100g") else None,
                        step_g=int(row["step_g"]),
                        min_g=int(row["min_g"]),
                        max_g=int(row["max_g"]),
                        max_days_wk=int(row["max_days_wk"]),
                        source_id="USDA-FDC-seed",
                        verified=False,
                        is_active=True,
                    )
                    db.add(food)
                    db.flush()
                    code_to_food[code] = food
                    for alias in DEFAULT_ALIASES.get(code, []):
                        db.add(FoodAlias(food_id=food.id, alias=alias))

    if prices_csv.exists():
        with prices_csv.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                food = code_to_food.get(row["food_code"].strip())
                if not food:
                    continue
                rec = date.fromisoformat(row["recorded_at"].strip())
                region = row["region"].strip()
                exists = db.scalar(
                    select(FoodPrice).where(
                        FoodPrice.food_id == food.id,
                        FoodPrice.region == region,
                        FoodPrice.recorded_at == rec,
                    )
                )
                if not exists:
                    db.add(
                        FoodPrice(
                            food_id=food.id,
                            region=region,
                            package_g=int(row["package_g"]),
                            price_idr=int(row["price_idr"]),
                            recorded_at=rec,
                            source=row["source"].strip(),
                            created_by=admin.id if admin else None,
                        )
                    )

    if ex_csv.exists():
        existing_ex = {e.code for e in db.scalars(select(Exercise)).all()}
        with ex_csv.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                code = row["code"].strip()
                if code in existing_ex:
                    continue
                db.add(
                    Exercise(
                        code=code,
                        name=row["name"].strip(),
                        pattern=row["pattern"].strip(),
                        muscle_group=row["muscle_group"].strip(),
                        equipment=row["equipment"].strip(),
                        difficulty=int(row["difficulty"]),
                        rank=int(row["rank"]),
                        sets=int(row["sets"]),
                        reps_min=int(row["reps_min"]),
                        reps_max=int(row["reps_max"]),
                        unit=row["unit"].strip(),
                        rest_s=int(row["rest_s"]),
                        instructions=row.get("instructions", "").strip(),
                        contraindication_notes=DEFAULT_CONTRAINDICATION,
                        is_active=True,
                    )
                )
    db.commit()


if __name__ == "__main__":
    from app.core.db import get_engine, session_factory
    from app.models import Base

    Base.metadata.create_all(bind=get_engine())
    with session_factory()() as session:
        seed_all(session)

