#!/usr/bin/env sh
set -e
cd apps/api && uv run python ../../scripts/gen_openapi.py

