.PHONY: up down test seed gen-types lint

up:
	docker compose up --build -d

down:
	docker compose down

seed:
	cd apps/api && uv run python -m app.core.seed

gen-types:
	sh scripts/gen-types.sh

test:
	cd apps/api && uv run pytest
	cd apps/web && npm test

lint:
	cd apps/api && uv run ruff check .
	cd apps/web && npm run lint

