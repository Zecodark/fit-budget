"""Application configuration (env-driven, see /.env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    app_env: str = "dev"
    tz: str = "Asia/Jakarta"
    database_url: str = "sqlite:///./fitbudget.db"
    secret_key: str = "dev-secret-key-change-me-please-32chars!!"
    session_ttl_minutes: int = 720
    cookie_secure: bool = False
    admin_email: str = "admin@example.com"
    admin_password: str = "ganti-saya-segera1"
    default_region: str = "default"

    ai_provider: str = "ollama"  # ollama | gemini | fake | none
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen3:4b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    ai_timeout_seconds: float = 30
    ai_rate_limit_per_hour: int = 10
    ai_max_history_messages: int = 6
    ai_max_output_tokens: int = 600
    ai_circuit_fails: int = 3
    ai_circuit_open_seconds: int = 60

    optimizer_time_limit_seconds_per_day: float = 10
    optimizer_hard_limit_seconds: float = 15

    max_body_bytes: int = 1_000_000
    max_csv_bytes: int = 2_000_000
    allowed_origins: str = ""  # comma-separated extra origins accepted for mutations
    seed_dir: str = ""  # default: <repo>/data/seeds
    auto_bootstrap: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

