"""Shared pytest fixtures: fresh SQLite in-memory DB seeded with the 25 foods + 25 exercises + admin."""

from __future__ import annotations

import os

os.environ.setdefault("AI_PROVIDER", "fake")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "AdminPass123")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import session_factory, set_engine
from app.core.seed import seed_all
from app.main import app
from app.models import Base
from app.routers.ai import reset_circuit_breaker
from app.services.ai.providers import get_fake_provider, set_override_provider


@pytest.fixture()
def client(tmp_path):
    get_settings.cache_clear()
    s = get_settings()
    s.ai_provider = "fake"
    s.ai_rate_limit_per_hour = 10
    s.ai_circuit_fails = 3
    s.ai_circuit_open_seconds = 60
    reset_circuit_breaker()
    fake = get_fake_provider()
    fake.reset()
    set_override_provider(fake)

    db_file = tmp_path / "test.db"
    eng = set_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=eng)
    with session_factory()() as db:
        seed_all(db)

    with TestClient(app) as c:
        yield c

    set_override_provider(None)


def register_and_setup_user(
    client: TestClient,
    email: str = "raka@example.com",
    password: str = "RakaStrong123",
    *,
    ai_cloud: bool = False,
    profile_overrides: dict | None = None,
    pref_overrides: dict | None = None,
) -> dict:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    uid = r.json()["user_id"]
    c = client.post("/api/v1/consent", json={"consent_version": "1.0", "data_processing": True, "ai_cloud": ai_cloud})
    assert c.status_code == 201, c.text

    prof = {
        "age_years": 22,
        "sex": "male",
        "weight_kg": 70.0,
        "height_cm": 170,
        "activity_level": "light",
        "goal": "maintain",
        "protein_g_per_kg": 1.6,
        "screening": {
            "pregnant_or_breastfeeding": False,
            "eating_disorder_history": False,
            "kidney_disease": False,
            "serious_injury": False,
            "other_medical_condition": False,
        },
        **(profile_overrides or {}),
    }
    pref = {
        "daily_budget_idr": 45000,
        "workout_days": [0, 2, 4],
        "session_minutes": 60,
        "experience_level": "beginner",
        "equipment_access": "gym_full",
        "excluded_food_ids": [],
        "allergies": [],
        "excluded_exercise_ids": [],
        "region": "default",
        **(pref_overrides or {}),
    }
    p = client.put("/api/v1/profile", json={"profile": prof, "preferences": pref})
    return {"user_id": uid, "profile_response": p}

