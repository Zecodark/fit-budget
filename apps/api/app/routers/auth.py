"""Authentication & session endpoints (PRD §5.1)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import as_utc, current_user, has_active_consent
from app.core.errors import AppError, validation_error
from app.core.security import (
    LOCKOUT_DURATION,
    LOCKOUT_MAX_FAILS,
    LOCKOUT_WINDOW,
    clear_session_cookie,
    hash_password,
    set_session_cookie,
    validate_password_policy,
    verify_password,
)
from app.models import Preferences, Profile, User, new_id
from app.schemas import AuthCredentials, ChangePasswordRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: AuthCredentials, response: Response, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise validation_error("Format email tidak valid.", field="email")
    validate_password_policy(body.password)
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise validation_error("Email sudah terdaftar.", field="email", issue="duplicate")
    user = User(id=new_id(), email=email, password_hash=hash_password(body.password), role="user")
    db.add(user)
    db.flush()
    set_session_cookie(response, user.id, user.role)
    return {"user_id": user.id, "role": user.role}


@router.post("/login")
def login(body: AuthCredentials, response: Response, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    now = datetime.now(UTC)
    if not user:
        raise AppError("UNAUTHORIZED", "Email atau kata sandi salah.")

    locked_until = as_utc(user.locked_until)
    if locked_until and locked_until > now:
        raise AppError("UNAUTHORIZED", "Email atau kata sandi salah.")

    if not verify_password(body.password, user.password_hash):
        first = as_utc(user.first_failed_at)
        if not first or (now - first) > LOCKOUT_WINDOW:
            user.first_failed_at = now
            user.failed_login_count = 1
        else:
            user.failed_login_count = int(user.failed_login_count or 0) + 1
        if user.failed_login_count >= LOCKOUT_MAX_FAILS:
            user.locked_until = now + LOCKOUT_DURATION
        db.commit()  # persist failed attempt even though we return 401
        raise AppError("UNAUTHORIZED", "Email atau kata sandi salah.")

    user.failed_login_count = 0
    user.first_failed_at = None
    user.locked_until = None
    db.flush()
    set_session_cookie(response, user.id, user.role)
    return {"user_id": user.id, "role": user.role}


@router.post("/logout", status_code=204)
def logout(response: Response, _user: User = Depends(current_user)) -> Response:
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    consent_ok = has_active_consent(db, user.id)
    prof = db.get(Profile, user.id)
    pref = db.get(Preferences, user.id)
    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "consent_required": not consent_ok,
        "profile_complete": bool(prof and pref),
    }


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(body.current_password, user.password_hash):
        raise AppError("UNAUTHORIZED", "Kata sandi saat ini salah.")
    validate_password_policy(body.new_password)
    user.password_hash = hash_password(body.new_password)
    db.flush()
    return Response(status_code=204)

