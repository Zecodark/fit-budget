from app.core.config import Settings


def test_supabase_uri_uses_installed_driver_and_preserves_encoded_password():
    uri = "postgresql://postgres.example:pass%25%40word@pooler.supabase.com:5432/postgres?sslmode=require"
    settings = Settings(_env_file=None, database_url=uri)
    assert settings.database_url == uri.replace("postgresql://", "postgresql+psycopg://", 1)


def test_sqlite_still_supported():
    assert Settings(_env_file=None, database_url="sqlite:///:memory:").database_url == "sqlite:///:memory:"
