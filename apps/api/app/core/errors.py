"""Standard error format (PRD §2.6) and error codes (PRD §5.9)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger("errors")

DEFAULT_MESSAGES: dict[str, str] = {
    "VALIDATION_ERROR": "Input tidak valid.",
    "UNAUTHORIZED": "Silakan masuk terlebih dahulu.",
    "FORBIDDEN": "Anda tidak memiliki akses.",
    "CONSENT_REQUIRED": "Persetujuan pemrosesan data diperlukan.",
    "PROFESSIONAL_CONSULT_REQUIRED": "Rencana otomatis tidak dibuat. Silakan konsultasi dengan tenaga kesehatan profesional.",
    "AI_CONSENT_REQUIRED": "Persetujuan penggunaan AI cloud diperlukan.",
    "NOT_FOUND": "Data tidak ditemukan.",
    "PLAN_VERSION_CONFLICT": "Rencana telah berubah. Muat ulang lalu coba lagi.",
    "SESSION_CONFLICT": "Sudah ada sesi lain pada tanggal tersebut.",
    "PROPOSAL_EXPIRED": "Usulan sudah kedaluwarsa.",
    "NO_FEASIBLE_PLAN": "Tidak ada menu yang memenuhi semua target dengan budget ini.",
    "GOAL_NOT_ALLOWED": "Tujuan ini tidak diizinkan untuk data tubuh Anda.",
    "AI_RATE_LIMIT": "Kuota asisten AI habis. Coba lagi nanti.",
    "INTERNAL_ERROR": "Terjadi kesalahan pada server.",
    "AI_UNAVAILABLE": "Asisten AI sedang tidak tersedia.",
    "OPTIMIZER_TIMEOUT": "Pembuatan menu melebihi batas waktu.",
    "CONFLICT": "Permintaan bertentangan dengan status data saat ini.",
}

STATUS_FOR_CODE: dict[str, int] = {
    "VALIDATION_ERROR": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "CONSENT_REQUIRED": 403,
    "PROFESSIONAL_CONSULT_REQUIRED": 403,
    "AI_CONSENT_REQUIRED": 403,
    "NOT_FOUND": 404,
    "PLAN_VERSION_CONFLICT": 409,
    "SESSION_CONFLICT": 409,
    "CONFLICT": 409,
    "PROPOSAL_EXPIRED": 410,
    "NO_FEASIBLE_PLAN": 422,
    "GOAL_NOT_ALLOWED": 422,
    "AI_RATE_LIMIT": 429,
    "INTERNAL_ERROR": 500,
    "AI_UNAVAILABLE": 503,
    "OPTIMIZER_TIMEOUT": 504,
}


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: Any = None,
        status: int | None = None,
    ) -> None:
        self.code = code
        self.message = message or DEFAULT_MESSAGES.get(code, code)
        self.details = details if details is not None else []
        self.status = status or STATUS_FOR_CODE.get(code, 400)
        super().__init__(self.message)


def validation_error(message: str, field: str | None = None, issue: str = "invalid", **extra: Any) -> AppError:
    detail: dict[str, Any] = {"issue": issue, **extra}
    if field:
        detail = {"field": field, **detail}
    return AppError("VALIDATION_ERROR", message, [detail])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""


def error_body(code: str, message: str, details: Any, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details, "request_id": request_id}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request.state.error_code = exc.code
    return JSONResponse(
        status_code=exc.status,
        content=error_body(exc.code, exc.message, exc.details, _request_id(request)),
    )


_FIELD_LABELS = {
    "age_years": ("Umur", "tahun"),
    "weight_kg": ("Berat badan", "kg"),
    "height_cm": ("Tinggi badan", "cm"),
    "daily_budget_idr": ("Budget harian", "rupiah"),
}


def _humanize(err: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
    field = ".".join(loc) if loc else None
    etype = err.get("type", "")
    ctx = err.get("ctx") or {}
    leaf = loc[-1] if loc else ""
    detail: dict[str, Any] = {"field": field, "issue": etype}
    label, unit = _FIELD_LABELS.get(leaf, (leaf or "Input", ""))
    if etype == "extra_forbidden":
        return f"Field '{field}' tidak dikenal.", {**detail, "issue": "unknown_field"}
    if etype == "missing":
        return f"Field '{field}' wajib diisi.", {**detail, "issue": "required"}
    if etype in ("greater_than_equal", "less_than_equal", "greater_than", "less_than"):
        detail["issue"] = "out_of_range"
        for k in ("ge", "le", "gt", "lt"):
            if k in ctx:
                detail[{"ge": "min", "gt": "min", "le": "max", "lt": "max"}[k]] = ctx[k]
        if "min" in detail and "max" in detail:
            return f"{label} harus antara {detail['min']} dan {detail['max']} {unit}.".replace("  ", " ").strip(), detail
        return f"{label} di luar rentang yang diizinkan.", detail
    msg = err.get("msg", "Input tidak valid.")
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
    return msg, detail


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errs = exc.errors()
    details = []
    first_msg = "Input tidak valid."
    for i, e in enumerate(errs):
        msg, d = _humanize(e)
        details.append(d)
        if i == 0:
            first_msg = msg
    request.state.error_code = "VALIDATION_ERROR"
    return JSONResponse(status_code=400, content=error_body("VALIDATION_ERROR", first_msg, details, _request_id(request)))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "VALIDATION_ERROR", 413: "VALIDATION_ERROR"}.get(
        exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR"
    )
    msg = DEFAULT_MESSAGES.get(code, "Terjadi kesalahan.")
    if exc.status_code == 413:
        msg = "Ukuran permintaan terlalu besar."
    request.state.error_code = code
    return JSONResponse(status_code=exc.status_code, content=error_body(code, msg, [], _request_id(request)))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", exc_type=type(exc).__name__, request_id=_request_id(request))
    request.state.error_code = "INTERNAL_ERROR"
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", DEFAULT_MESSAGES["INTERNAL_ERROR"], [], _request_id(request)),
    )

