"""Password hashing (argon2id), JWT session cookie, login lockout, CSRF Origin check (PRD §5.1)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request, Response

from app.core.config import get_settings
from app.core.errors import AppError, validation_error

COOKIE_NAME = "fb_session"
_hasher = PasswordHasher()  # argon2id default
_PW_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{10,128}$")

LOCKOUT_MAX_FAILS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
LOCKOUT_DURATION = timedelta(minutes=15)


def validate_password_policy(pw: str) -> None:
    if not _PW_RE.match(pw or ""):
        raise validation_error(
            "Kata sandi minimal 10 karakter dan harus mengandung huruf serta angka.",
            field="password",
            issue="weak_password",
        )


def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, pw)
    except (VerifyMismatchError, Exception):
        return False


def create_session_token(user_id: str, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.session_ttl_minutes)
    payload = {"sub": user_id, "role": role, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.secret_key, algorithms=["HS256"])
    except Exception as exc:
        raise AppError("UNAUTHORIZED") from exc


def set_session_cookie(response: Response, user_id: str, role: str) -> None:
    s = get_settings()
    token = create_session_token(user_id, role)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=s.session_ttl_minutes * 60,
        httponly=True,
        samesite="lax",
        path="/",
        secure=s.cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="lax", httponly=True)


def check_csrf_and_content_type(request: Request) -> None:
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if origin and host:
        origin_host = urlparse(origin).netloc
        extra = {o.strip() for o in get_settings().allowed_origins.split(",") if o.strip()}
        same_loopback = origin_host.split(":")[0] in ("localhost", "127.0.0.1") and host.split(":")[0] in (
            "localhost",
            "127.0.0.1",
            "testserver",
        )
        if origin_host != host and origin not in extra and not same_loopback:
            raise AppError("FORBIDDEN", "Origin tidak diizinkan.")
    cl = request.headers.get("content-length")
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if cl and cl.isdigit():
        limit = get_settings().max_csv_bytes if ctype == "multipart/form-data" else get_settings().max_body_bytes
        if int(cl) > limit:
            raise AppError("VALIDATION_ERROR", "Ukuran permintaan melebihi batas.", status=413)
    if cl and int(cl) > 0:
        is_import = request.url.path.endswith("/prices/import")
        allowed = {"application/json"} | ({"multipart/form-data"} if is_import else set())
        if ctype and ctype not in allowed:
            raise AppError("VALIDATION_ERROR", "Content-Type harus application/json.")

