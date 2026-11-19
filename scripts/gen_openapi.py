"""Generate apps/api/openapi.json, docs/API.md, and apps/web/src/lib/api-types.ts from FastAPI OpenAPI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from app.main import app  # noqa: E402

WEB_TYPES = ROOT / "apps" / "web" / "src" / "lib" / "api-types.ts"
DOCS_API = ROOT / "docs" / "API.md"


def main() -> None:
    spec = app.openapi()
    (API_DIR / "openapi.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    # Auto-generate docs/API.md
    lines = [
        "# FitBudget AI — OpenAPI Reference (Auto-Generated)",
        "",
        f"Version: `{spec.get('info', {}).get('version', '2.0.0')}`",
        "",
        "| Method | Path | Summary | Tags |",
        "|---|---|---|---|",
    ]
    for path, methods in sorted(spec.get("paths", {}).items()):
        for m, meta in methods.items():
            if m.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            summary = meta.get("summary") or meta.get("operationId") or ""
            tags = ", ".join(meta.get("tags") or [])
            lines.append(f"| `{m.upper()}` | `{path}` | {summary} | {tags} |")
    DOCS_API.parent.mkdir(parents=True, exist_ok=True)
    DOCS_API.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Auto-generate TypeScript path & schema map from OpenAPI
    ts_lines = [
        "// AUTO-GENERATED FROM apps/api/openapi.json BY scripts/gen_openapi.py — DO NOT EDIT MANUALLY",
        "",
        "export interface ApiErrorDetail {",
        "  field?: string | null;",
        "  issue?: string;",
        "  min?: number;",
        "  max?: number;",
        "  [key: string]: unknown;",
        "}",
        "",
        "export interface ApiErrorEnvelope {",
        "  error: {",
        "    code: string;",
        "    message: string;",
        "    details: ApiErrorDetail[] | Record<string, unknown>;",
        "    request_id: string;",
        "  };",
        "}",
        "",
        "export interface OpenApiPaths {",
    ]
    for path, methods in sorted(spec.get("paths", {}).items()):
        ms = [m.upper() for m in methods if m.lower() in ("get", "post", "put", "patch", "delete")]
        ts_lines.append(f'  "{path}": {{ methods: {" | ".join(json.dumps(m) for m in ms)} }};')
    ts_lines.append("}")
    ts_lines.append("")
    WEB_TYPES.parent.mkdir(parents=True, exist_ok=True)
    WEB_TYPES.write_text("\n".join(ts_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
