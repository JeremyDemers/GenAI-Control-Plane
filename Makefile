.PHONY: setup dev stop test lint typecheck migrate migration-check security-audit seed reset e2e api web compose-config docker-build

PODMAN_ENV = case "$${XDG_DATA_HOME:-}" in "$$HOME"/snap/code/*/.local/share) unset XDG_DATA_HOME ;; esac;
CONTAINER_ENGINE ?= podman

setup:
	cd apps/api && uv sync --all-groups
	npm install

dev:
	$(PODMAN_ENV) $(CONTAINER_ENGINE) compose up --build

stop:
	$(PODMAN_ENV) $(CONTAINER_ENGINE) compose down

api:
	cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	npm --workspace apps/web run dev

test:
	cd apps/api && uv run pytest
	npm --workspace apps/web run test

lint:
	cd apps/api && uv run ruff check .
	npm --workspace apps/web run lint

typecheck:
	cd apps/api && uv run mypy .
	npm --workspace apps/web run typecheck

migrate:
	cd apps/api && uv run alembic upgrade head

migration-check:
	rm -f apps/api/ci_migration_check.db
	cd apps/api && DATABASE_URL=sqlite:///./ci_migration_check.db uv run alembic upgrade head
	rm -f apps/api/ci_migration_check.db

security-audit:
	npm audit --audit-level=high

seed:
	cd apps/api && uv run python -m scripts.seed

reset:
	$(PODMAN_ENV) $(CONTAINER_ENGINE) compose down -v
	rm -f apps/api/control_plane.db apps/api/tests/test_control_plane.db

e2e:
	npm --workspace apps/web run test:e2e

docker-build:
	$(PODMAN_ENV) $(CONTAINER_ENGINE) compose build

compose-config:
	$(PODMAN_ENV) $(CONTAINER_ENGINE) compose config --quiet
