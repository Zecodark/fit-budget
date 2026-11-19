"""Integration & security tests (PRD §11.2 O5/O9, §11.3 W4/W5/W7, §11.4 D1–D3, §11.5 I1–I12 & S1–S7)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.db import session_factory
from app.models import (
    AIInteraction,
    AIProposal,
    ChatMessage,
    Consent,
    FoodLog,
    MealPlan,
    NutritionTarget,
    PlanChangeLog,
    Preferences,
    Profile,
    User,
    WeightLog,
    WorkoutLog,
    WorkoutPlan,
)
from app.services.optimizer.service import generate_and_save_meal_plan
from tests.conftest import register_and_setup_user


def _login(client, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_i12_health_and_request_id(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["db"] == "ok"
    assert "X-Request-ID" in r.headers


def test_s3_s4_auth_lockout_cookie_argon2_mass_assignment(client):
    # S3: extra fields / mass assignment on register or profile -> 400 VALIDATION_ERROR
    r_extra = client.post(
        "/api/v1/auth/register",
        json={"email": "hack@example.com", "password": "HackPassword1", "role": "admin"},
    )
    assert r_extra.status_code == 400
    assert r_extra.json()["error"]["code"] == "VALIDATION_ERROR"

    # Register valid user, inspect cookie & argon2 hash
    r = client.post("/api/v1/auth/register", json={"email": "sinta@example.com", "password": "SintaPassword1"})
    assert r.status_code == 201
    set_cookie = r.headers.get("set-cookie", "").lower()
    assert "fb_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    with session_factory()() as db:
        u = db.scalar(select(User).where(User.email == "sinta@example.com"))
        assert u is not None
        assert u.password_hash.startswith("$argon2id$")

    # S4: 5 failed logins -> locked out even with right password on 6th attempt
    for _ in range(5):
        bad = _login(client, "sinta@example.com", "WrongPassword999")
        assert bad.status_code == 401
    locked = _login(client, "sinta@example.com", "SintaPassword1")
    assert locked.status_code == 401


def test_i1_i2_i3_i10_profile_consent_target_history_and_screening(client):
    client.post("/api/v1/auth/register", json={"email": "u1@example.com", "password": "User1Password1"})
    # Without consent -> 403 CONSENT_REQUIRED
    r_no_c = client.get("/api/v1/profile")
    assert r_no_c.status_code == 403
    assert r_no_c.json()["error"]["code"] == "CONSENT_REQUIRED"

    client.post("/api/v1/consent", json={"consent_version": "1.0", "data_processing": True, "ai_cloud": False})

    # BMI 17.5 + lose_weight -> 422 GOAL_NOT_ALLOWED
    r_goal = client.put(
        "/api/v1/profile",
        json={
            "age_years": 22,
            "sex": "female",
            "weight_kg": 50.6,
            "height_cm": 170,
            "activity_level": "light",
            "goal": "lose_weight",
            "daily_budget_idr": 45000,
            "workout_days": [0, 2, 4],
            "session_minutes": 60,
            "experience_level": "beginner",
            "equipment_access": "gym_full",
        },
    )
    assert r_goal.status_code == 422
    assert r_goal.json()["error"]["code"] == "GOAL_NOT_ALLOWED"

    # Valid save creates nutrition_target v1; changing weight creates v2 (FR-05 history)
    r_ok = client.put(
        "/api/v1/profile",
        json={
            "age_years": 22,
            "sex": "male",
            "weight_kg": 70.0,
            "height_cm": 170,
            "activity_level": "light",
            "goal": "maintain",
            "daily_budget_idr": 45000,
            "workout_days": [0, 2, 4],
            "session_minutes": 60,
            "experience_level": "beginner",
            "equipment_access": "gym_full",
        },
    )
    assert r_ok.status_code == 200
    client.patch("/api/v1/profile", json={"weight_kg": 72.0})
    hist = client.get("/api/v1/nutrition/target/history").json()
    assert hist["total"] == 2

    # I10 / U8: health screening flag blocks plan generation with 403 PROFESSIONAL_CONSULT_REQUIRED
    client.patch("/api/v1/profile", json={"screening": {"kidney_disease": True}})
    prof = client.get("/api/v1/profile").json()
    assert prof["plan_generation_allowed"] is False
    r_gen = client.post("/api/v1/meal-plans/generate", json={"start_date": "2026-11-09"})
    assert r_gen.status_code == 403
    assert r_gen.json()["error"]["code"] == "PROFESSIONAL_CONSULT_REQUIRED"


def test_i4_i5_o5_d3_catalog_admin_import_and_price_reproducibility(client):
    register_and_setup_user(client, "raka@example.com", "RakaStrong123")
    foods = client.get("/api/v1/foods").json()["items"]
    assert len(foods) == 25
    assert any(f["code"] == "BERAS" for f in foods)

    # Generate & confirm meal plan under original seed prices (BERAS = 16000)
    mp1 = client.post("/api/v1/meal-plans/generate", json={"start_date": "2026-11-09", "daily_budget_idr": 24000}).json()
    client.post(f"/api/v1/meal-plans/{mp1['id']}/confirm", json={"base_version": 1})

    # S2: normal user cannot access /admin/*
    assert client.get("/api/v1/admin/foods").status_code == 403

    # Login as seeded admin
    _login(client, "admin@example.com", "AdminPass123")
    today_s = date.today().isoformat()

    # Invalid CSV (bad food_code) -> all-or-nothing 422, nothing applied
    bad_csv = f"food_code,region,package_g,price_idr,source,recorded_at\nNOPE,default,1000,20000,uji,{today_s}\n"
    r_bad = client.post(
        "/api/v1/admin/prices/import?dry_run=false",
        files={"file": ("bad.csv", bad_csv.encode("utf-8"), "text/csv")},
    )
    assert r_bad.status_code == 422
    assert r_bad.json()["error"]["details"]["applied"] is False

    # Valid CSV updating BERAS 16000 -> 18000 (TC-03 / O5)
    good_csv = f"food_code,region,package_g,price_idr,source,recorded_at\nBERAS,default,1000,18000,survei pasar,{today_s}\n"
    r_dry = client.post(
        "/api/v1/admin/prices/import?dry_run=true",
        files={"file": ("good.csv", good_csv.encode("utf-8"), "text/csv")},
    )
    assert r_dry.status_code == 200
    assert r_dry.json()["applied"] is False

    r_apply = client.post(
        "/api/v1/admin/prices/import?dry_run=false",
        files={"file": ("good.csv", good_csv.encode("utf-8"), "text/csv")},
    )
    assert r_apply.status_code == 200
    assert r_apply.json()["applied"] is True
    assert len(client.get("/api/v1/admin/audit").json()["items"]) >= 1

    # Switch back to Raka: old plan is untouched & re-running saved generation_params reproduces old plan
    _login(client, "raka@example.com", "RakaStrong123")
    mp1_after = client.get(f"/api/v1/meal-plans/{mp1['id']}").json()
    assert mp1_after["days"] == mp1["days"]

    with session_factory()() as db:
        re_run = generate_and_save_meal_plan(
            db,
            user_id=client.get("/api/v1/auth/me").json()["user_id"],
            start_date=date.fromisoformat(mp1["generation_params"]["start_date"]),
            daily_budget_idr=mp1["generation_params"]["daily_budget_idr"],
            excluded_food_ids=mp1["generation_params"]["excluded_food_ids"],
            fixed_price_ids=mp1["generation_params"]["price_ids"],
            dry_run=True,
        )
        assert [d["totals"] for d in re_run["days"]] == [d["totals"] for d in mp1["days"]]

    # D3: raise price of a non-BERAS food used in mp1 high enough so repriced cost > budget -> PLAN_OVER_BUDGET_AFTER_PRICE_CHANGE
    used_code = next(
        f["code"]
        for sl in mp1["days"][0]["slots"]
        for it in sl["items"]
        for f in foods
        if f["id"] == it["food_id"] and f["code"] != "BERAS"
    )
    _login(client, "admin@example.com", "AdminPass123")
    spike_csv = f"food_code,region,package_g,price_idr,source,recorded_at\n{used_code},default,1000,450000,lonjakan,{today_s}\n"
    r_spike = client.post(
        "/api/v1/admin/prices/import?dry_run=false&confirm_large_changes=true",
        files={"file": ("spike.csv", spike_csv.encode("utf-8"), "text/csv")},
    )
    assert r_spike.status_code == 200

    _login(client, "raka@example.com", "RakaStrong123")
    dash = client.get("/api/v1/dashboard?week_start=2026-11-09").json()
    assert any(a["code"] == "PLAN_OVER_BUDGET_AFTER_PRICE_CHANGE" for a in dash["alerts"])


def test_i6_o9_meal_plan_versioning_manual_edit_and_confirm(client):
    register_and_setup_user(client, "edit@example.com", "EditStrong123")
    mp = client.post("/api/v1/meal-plans/generate", json={"start_date": "2026-11-09", "daily_budget_idr": 45000}).json()
    first_item = max(
        (it for sl in mp["days"][0]["slots"] for it in sl["items"]),
        key=lambda it: it["cost_idr"] / max(1, it["grams"]),
    )

    # Wrong base_version -> 409 PLAN_VERSION_CONFLICT
    r_conflict = client.patch(
        f"/api/v1/meal-plans/{mp['id']}",
        json={"base_version": 99, "operations": [{"op": "set_grams", "item_id": first_item["id"], "grams": 100}]},
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json()["error"]["code"] == "PLAN_VERSION_CONFLICT"

    # O9: edit grams huge so cost > budget -> status becomes INFEASIBLE + BUDGET_EXCEEDED, cannot confirm
    r_v2 = client.patch(
        f"/api/v1/meal-plans/{mp['id']}",
        json={"base_version": 1, "operations": [{"op": "set_grams", "item_id": first_item["id"], "grams": 1900}]},
    )
    assert r_v2.status_code == 200
    v2 = r_v2.json()
    assert v2["version"] == 2
    assert v2["result_status"] == "INFEASIBLE"
    assert any(u["code"] == "BUDGET_EXCEEDED" for u in v2["unmet_constraints"])

    r_conf_fail = client.post(f"/api/v1/meal-plans/{v2['id']}/confirm", json={"base_version": 2})
    assert r_conf_fail.status_code == 422
    assert r_conf_fail.json()["error"]["code"] == "NO_FEASIBLE_PLAN"


def test_w4_w5_w7_workout_reschedule_conflict_and_swap(client):
    register_and_setup_user(client, "gym@example.com", "GymStrong1234")
    wp = client.post("/api/v1/workout-plans/generate", json={"week_start": "2026-11-09"}).json()
    assert len(wp["sessions"]) == 3
    mon_s, wed_s, fri_s = wp["sessions"]

    # W5: move Wed session onto Mon (already occupied) -> 409 SESSION_CONFLICT
    r_conf = client.patch(
        f"/api/v1/workout-plans/{wp['id']}",
        json={"base_version": wp["version"], "moves": [{"session_id": wed_s["id"], "new_date": mon_s["date"]}]},
    )
    assert r_conf.status_code == 409
    assert r_conf.json()["error"]["code"] == "SESSION_CONFLICT"

    # W4 (TC-04): move Wed (2026-11-11) -> Thu (2026-11-12): no duplicate sessions, version +1, RECOVERY_WARNING
    r_move = client.patch(
        f"/api/v1/workout-plans/{wp['id']}",
        json={"base_version": wp["version"], "moves": [{"session_id": wed_s["id"], "new_date": "2026-11-12"}]},
    )
    assert r_move.status_code == 200
    moved = r_move.json()
    assert moved["version"] == wp["version"] + 1
    assert len(moved["sessions"]) == 3
    assert [s["date"] for s in moved["sessions"]] == ["2026-11-09", "2026-11-12", "2026-11-13"]
    assert any(w["code"] == "RECOVERY_WARNING" for w in moved["warnings"])

    # W7: swap exercise to a different pattern -> 400 VALIDATION_ERROR
    first_ex = moved["sessions"][0]["exercises"][0]  # squat pattern
    all_ex = client.get("/api/v1/exercises").json()["items"]
    hinge_ex = next(e for e in all_ex if e["pattern"] == "hinge")
    r_bad_swap = client.patch(
        f"/api/v1/workout-sessions/{moved['sessions'][0]['id']}/exercises/{first_ex['id']}",
        json={"exercise_id": hinge_ex["id"]},
    )
    assert r_bad_swap.status_code == 400
    assert r_bad_swap.json()["error"]["code"] == "VALIDATION_ERROR"

    # Valid swap to alternative of same pattern
    alt_id = first_ex["alternatives"][0]["exercise_id"]
    r_ok_swap = client.patch(
        f"/api/v1/workout-sessions/{moved['sessions'][0]['id']}/exercises/{first_ex['id']}",
        json={"exercise_id": alt_id},
    )
    assert r_ok_swap.status_code == 200


def test_i7_i8_i9_i11_d1_d2_logs_and_dashboard_alerts(client):
    register_and_setup_user(client, "log@example.com", "LogStrong1234")
    foods = client.get("/api/v1/foods").json()["items"]
    tempe = next(f for f in foods if f["code"] == "TEMP")
    ex = client.get("/api/v1/exercises").json()["items"][0]

    # Log 3 consecutive days with low protein (<80% of 112g = 89.6g) and day 1 over budget (>45000)
    r_f1 = client.post(
        "/api/v1/logs/food",
        json={"date": "2026-11-09", "meal_slot": "lunch", "food_id": tempe["id"], "grams": 100, "actual_price_idr": 50000},
    )
    assert r_f1.status_code == 201
    client.post("/api/v1/logs/food", json={"date": "2026-11-10", "meal_slot": "lunch", "food_id": tempe["id"], "grams": 100})
    client.post("/api/v1/logs/food", json={"date": "2026-11-11", "meal_slot": "lunch", "food_id": tempe["id"], "grams": 100})

    # Workout log + weight log (with apply_to_profile)
    r_wl = client.post(
        "/api/v1/logs/workout",
        json={"date": "2026-11-09", "exercise_id": ex["id"], "sets": [{"reps": 12, "weight_kg": 16}], "effort_rating": 7},
    )
    assert r_wl.status_code == 201
    r_wt = client.post("/api/v1/logs/weight", json={"date": "2026-11-09", "weight_kg": 69.5, "apply_to_profile": True})
    assert r_wt.status_code == 201
    assert client.get("/api/v1/profile").json()["profile"]["weight_kg"] == 69.5

    dash = client.get("/api/v1/dashboard?week_start=2026-11-09").json()
    codes = {a["code"] for a in dash["alerts"]}
    assert "BUDGET_OVERRUN" in codes  # D1
    assert "PROTEIN_LOW" in codes  # D2


def test_s1_s5_s6_idor_sql_xss_and_account_deletion(client):
    # User A creates resources
    a = register_and_setup_user(client, "usera@example.com", "UserAPassword1")
    mp_a = client.post("/api/v1/meal-plans/generate", json={"start_date": "2026-11-09"}).json()
    wp_a = client.post("/api/v1/workout-plans/generate", json={"week_start": "2026-11-09"}).json()
    food_id = client.get("/api/v1/foods").json()["items"][0]["id"]
    fl_a = client.post(
        "/api/v1/logs/food", json={"date": "2026-11-09", "meal_slot": "lunch", "food_id": food_id, "grams": 100}
    ).json()["item"]

    # Switch to User B -> every ID belonging to User A returns 404 (S1)
    register_and_setup_user(client, "userb@example.com", "UserBPassword1")
    assert client.get(f"/api/v1/meal-plans/{mp_a['id']}").status_code == 404
    assert client.patch(
        f"/api/v1/meal-plans/{mp_a['id']}",
        json={"base_version": 1, "operations": [{"op": "remove_item", "item_id": "x"}]},
    ).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{mp_a['id']}/confirm", json={"base_version": 1}).status_code == 404
    assert client.get(f"/api/v1/meal-plans/{mp_a['id']}/shopping-list").status_code == 404
    assert client.get(f"/api/v1/workout-plans/{wp_a['id']}").status_code == 404
    assert client.patch(f"/api/v1/workout-sessions/{wp_a['sessions'][0]['id']}", json={"status": "completed"}).status_code == 404
    assert client.delete(f"/api/v1/logs/food/{fl_a['id']}").status_code == 404

    # S5: SQL injection / XSS payload in food search query is handled safely
    r_sqli = client.get("/api/v1/foods", params={"query": "' OR 1=1; DROP TABLE foods; -- <script>alert(1)</script>"})
    assert r_sqli.status_code == 200
    assert r_sqli.json()["total"] == 0

    # S6: User A deletes account -> all rows for user A across every personal table are gone
    _login(client, "usera@example.com", "UserAPassword1")
    exp = client.get("/api/v1/account/export")
    assert exp.status_code == 200
    del_r = client.request("DELETE", "/api/v1/account", json={"password": "UserAPassword1"})
    assert del_r.status_code == 204

    uid_a = a["user_id"]
    with session_factory()() as db:
        for model in (
            Consent,
            Profile,
            Preferences,
            NutritionTarget,
            MealPlan,
            WorkoutPlan,
            PlanChangeLog,
            FoodLog,
            WorkoutLog,
            WeightLog,
            ChatMessage,
            AIProposal,
            AIInteraction,
        ):
            assert db.scalars(select(model).where(model.user_id == uid_a)).all() == []
        assert db.get(User, uid_a) is None

    assert _login(client, "usera@example.com", "UserAPassword1").status_code == 401
