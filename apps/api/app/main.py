"""FastAPI application entrypoint, security headers, X-Request-ID, /health (PRD §2.2, §4.5, §8)."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.db import get_db, get_engine, session_factory
from app.core.errors import (
    AppError,
    app_error_handler,
    error_body,
    http_exception_handler,
    request_validation_handler,
    unhandled_exception_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.security import check_csrf_and_content_type
from app.core.seed import seed_all
from app.models import Base
from app.routers import account, admin, ai, auth, catalog, logs, meal_plans, profile, workout_plans
from app.services.ai.providers import resolve_provider

configure_logging()
log = get_logger("http")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    if s.auto_bootstrap:
        eng = get_engine()
        Base.metadata.create_all(bind=eng)
        with session_factory()() as db:
            seed_all(db)
    yield


app = FastAPI(title="FitBudget AI API", version="2.0.0", lifespan=lifespan)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request.state.request_id = req_id
    request.state.error_code = None
    t0 = time.monotonic()
    try:
        check_csrf_and_content_type(request)
        response = await call_next(request)
    except AppError as exc:
        from fastapi.responses import JSONResponse

        request.state.error_code = exc.code
        response = JSONResponse(
            status_code=exc.status,
            content=error_body(exc.code, exc.message, exc.details, req_id),
        )
    dur_ms = int((time.monotonic() - t0) * 1000)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    log.info(
        "http_request",
        request_id=req_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        error_code=request.state.error_code,
        duration_ms=dur_ms,
    )
    return response


@app.get("/health", tags=["system"])
@app.get("/api/v1/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    prov = resolve_provider()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "ai": prov.name if prov else "none",
    }


API_PREFIX = "/api/v1"
for rtr in (
    auth.router,
    account.router,
    profile.router,
    catalog.router,
    meal_plans.router,
    workout_plans.router,
    logs.router,
    ai.router,
    admin.router,
):
    app.include_router(rtr, prefix=API_PREFIX)

