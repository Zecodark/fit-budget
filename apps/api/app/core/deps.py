"""FastAPI dependencies: current_user, require_admin, require_consent, require_plan_allowed."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import COOKIE_NAME, decode_session_token
from app.models import Consent, SystemState, User

CONSENT_VERSION = "1.0"
CONSENT_TEXT = (
    "FitBudget AI memproses data tubuh, preferensi makanan/latihan, dan catatan harian Anda untuk "
    "menghitung estimasi kebutuhan gizi dan menyusun rencana secara lokal. Aplikasi ini bukan layanan "
    "medis. Penggunaan penyedia AI cloud bersifat opsional (default nonaktif) dan hanya mengirim ringkasan "
    "rencana teranonimkan tanpa identitas pribadi."
)


def latest_consent(db: Session, user_id: str) -> Consent | None:
    stmt = (
        select(Consent)
        .where(Consent.user_id == user_id, Consent.consent_version == CONSENT_VERSION)
        .order_by(desc(Consent.created_at), desc(Consent.id))
        .limit(1)
    )
    return db.scalar(stmt)


def has_active_consent(db: Session, user_id: str) -> bool:
    c = latest_consent(db, user_id)
    return bool(c and c.data_processing)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise AppError("UNAUTHORIZED")
    payload = decode_session_token(token)
    uid = payload.get("sub")
    if not uid:
        raise AppError("UNAUTHORIZED")
    user = db.get(User, uid)
    if not user:
        raise AppError("UNAUTHORIZED")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise AppError("FORBIDDEN")
    return user


def require_consent(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    if not has_active_consent(db, user.id):
        raise AppError("CONSENT_REQUIRED")
    return user


def get_catalog_version(db: Session) -> int:
    st = db.get(SystemState, "catalog_version")
    if not st:
        st = SystemState(key="catalog_version", value="1")
        db.add(st)
        db.flush()
    return int(st.value)


def bump_catalog_version(db: Session) -> int:
    st = db.get(SystemState, "catalog_version")
    if not st:
        st = SystemState(key="catalog_version", value="2")
        db.add(st)
    else:
        st.value = str(int(st.value) + 1)
    db.flush()
    return int(st.value)


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
