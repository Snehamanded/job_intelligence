SHELL := /bin/bash
API := apps/api
WEB := apps/web
COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help setup dev down infra api worker web migrate migrate-down types check check-api check-web check-types clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

.env:
	@cp .env.example .env
	@secret=$$(python3 -c "import secrets; print(secrets.token_urlsafe(48))"); \
	  sed -i.bak "s|^JWT_SECRET=$$|JWT_SECRET=$$secret|" .env && rm -f .env.bak
	@echo "Created .env with a generated JWT_SECRET"

setup: .env ## Install API and web dependencies, create .env
	cd $(API) && uv sync
	cd $(WEB) && npm ci --no-audit --no-fund

dev: .env ## Run everything (web, api, db, redis) in Docker
	$(COMPOSE) up --build

down: ## Stop all containers
	$(COMPOSE) down

infra: .env ## Start only Postgres and Redis
	$(COMPOSE) up -d --wait db redis

api: infra ## Run the API locally with reload (needs `make setup`)
	cd $(API) && uv run alembic upgrade head && uv run uvicorn app.asgi:app --reload --port 8000

worker: infra ## Run the resume-parsing worker locally (needs `make setup`)
	cd $(API) && OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python -m app.workers.main

web: ## Run the web app locally (needs `make setup`)
	cd $(WEB) && set -a && source ../../.env && set +a && npm run dev

migrate: infra ## Apply all migrations
	cd $(API) && uv run alembic upgrade head

migrate-down: infra ## Roll back all migrations
	cd $(API) && uv run alembic downgrade base

types: ## Regenerate apps/web/types/api.ts from the API's OpenAPI schema
	cd $(API) && uv run python -m scripts.export_openapi openapi.json
	cd $(WEB) && npm run gen:types

check-types: ## Fail if the generated TS types are out of date
	cd $(API) && uv run python -m scripts.export_openapi openapi.json
	@cd $(WEB) && tmp=$$(mktemp) && npx openapi-typescript ../api/openapi.json -o $$tmp >/dev/null && \
	  if diff -q $$tmp types/api.ts >/dev/null; then echo "types/api.ts is up to date"; rm -f $$tmp; \
	  else rm -f $$tmp; echo "types/api.ts is stale: run 'make types'"; exit 1; fi

check-api: ## Lint, type-check and test the API
	cd $(API) && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest

check-web: ## Lint, type-check and test the web app
	cd $(WEB) && npm run lint && npm run format:check && npm run typecheck && npm test

check: infra check-api check-web check-types ## Run every check (needs `make setup`)
	@echo "All checks passed."

clean: ## Remove containers and volumes (deletes local data)
	$(COMPOSE) down -v
