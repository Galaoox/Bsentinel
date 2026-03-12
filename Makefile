.DEFAULT_GOAL := help

.PHONY: help install browsers-install db-up db-down migrate run lint test check

help: ## Show available development commands
	@awk 'BEGIN {FS = ":.*## "; printf "Available targets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install project dependencies with uv
	uv sync

browsers-install: ## Install bundled Chromium for Scrapling/Playwright
	uv run python -m playwright install chromium

db-up: ## Start local PostgreSQL container
	docker-compose up -d postgres

db-down: ## Stop local Docker services
	docker-compose down

migrate: ## Apply Alembic migrations
	uv run alembic upgrade head

run: ## Start the FastAPI application locally
	uv run python -m bsentinel.infrastructure.api

lint: ## Run Ruff checks
	uv run ruff check .

test: ## Run the test suite
	uv run pytest -q

check: lint test ## Run lint and tests
