"""Read-only connection/schema check: python -m app.core.check_db."""

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import get_engine
from app.models import Base


def main() -> int:
    if not get_settings().database_url.startswith("postgresql+psycopg://"):
        print("DATABASE_URL belum menunjuk ke PostgreSQL. Isi .env terlebih dahulu.")
        return 1
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            missing = set(Base.metadata.tables) - set(inspect(conn).get_table_names())
            if missing:
                print("Koneksi OK, tabel belum lengkap: " + ", ".join(sorted(missing)))
                return 1
            counts = {
                name: conn.scalar(text(f'SELECT count(*) FROM "{name}"'))
                for name in ("foods", "food_prices", "exercises")
            }
        print(f"Koneksi PostgreSQL OK; {len(Base.metadata.tables)} tabel tersedia; katalog: {counts}")
        return 0
    except (SQLAlchemyError, ValueError):
        # Do not print exception messages: connection errors can contain secrets.
        print("Koneksi gagal. Periksa DATABASE_URL, password, SSL, dan akses jaringan.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
