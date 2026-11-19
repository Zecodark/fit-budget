"""Export model DDL and catalog seed; run from apps/api using its Python environment.

Does not connect to Supabase or export user data. Output is for an empty database.
"""

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.config import get_settings
from app.core.seed import seed_all
from app.models import Base, Food


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    return "'" + str(value).replace("'", "''") + "'"


def main():
    output = Path(__file__).resolve().parents[1] / "supabase"
    output.mkdir(exist_ok=True)
    dialect = postgresql.dialect()
    ddl = ["-- Generated from SQLAlchemy models. Apply only to an empty FitBudget database.",
           "SET search_path TO public;"]
    for table in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(table).compile(dialect=dialect)) + ";")
        for index in sorted(table.indexes, key=lambda item: item.name):
            ddl.append(str(CreateIndex(index).compile(dialect=dialect)) + ";")
        ddl.append(f'ALTER TABLE public."{table.name}" ENABLE ROW LEVEL SECURITY;')
        ddl.append(f'REVOKE ALL ON TABLE public."{table.name}" FROM anon, authenticated, PUBLIC;')
    (output / "schema.sql").write_text("\n\n".join(ddl) + "\n", encoding="utf-8")

    # Seed into a disposable in-memory database to evaluate Python model defaults.
    settings = get_settings()
    settings.admin_email = ""
    settings.admin_password = ""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        food_codes = {food.id: food.code for food in session.scalars(select(Food))}
        statements = ["-- Catalog only; no admin accounts or user data.", "SET search_path TO public;"]
        for name in ("system_state", "foods", "exercises", "food_aliases", "food_prices"):
            table = Base.metadata.tables[name]
            for row in session.execute(select(table)).mappings():
                values = [
                    f"(SELECT id FROM public.foods WHERE code = {literal(food_codes[value])})"
                    if key == "food_id" else literal(value)
                    for key, value in row.items()
                ]
                columns = ", ".join(f'"{key}"' for key in row)
                statements.append(
                    f'INSERT INTO public."{name}" ({columns}) VALUES ({", ".join(values)}) ON CONFLICT DO NOTHING;'
                )
    (output / "seed.sql").write_text("\n".join(statements) + "\n", encoding="utf-8")
    print(f"Exported {len(Base.metadata.tables)} tables and catalog SQL to {output}")


if __name__ == "__main__":
    main()
