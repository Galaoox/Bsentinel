# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `bsentinel/`.
- Layered architecture (hexagonal style):
  - `bsentinel/domain/`: entities, value objects, pure business rules.
  - `bsentinel/application/`: use cases, orchestration, repository/service contracts.
  - `bsentinel/infrastructure/`: adapters and integrations (FastAPI, scraper, scheduler, OpenLibrary).
  - `bsentinel/infrastructure/api/`: app bootstrap, routers (`/health`, `/api/v1/...`).
- Config/environment: `bsentinel/_settings.py`, `bsentinel/settings/`.
- Tests: `tests/unit/` and `tests/integration/`.
- Product specs/docs: `docs/`, `docs/features/mvp/`, and `docs/features/roadmap/`.

## Architecture Quick Map (Where Things Go)
- Put **business decisions** in `domain/`.
- Put **application flows** (create/list/delete/restore/archive) in `application/`.
- Put **framework code** (FastAPI, APScheduler, HTTP clients, scraping adapters) in `infrastructure/`.
- Do not couple `domain/` directly to FastAPI, DB, or external APIs.

## Build, Test, and Development Commands
- Preferred command surface: use `make help` to discover shortcuts.
- Install dependencies: `make install` (`uv sync`)
- Start PostgreSQL: `make db-up` (`docker-compose up -d postgres`)
- Apply migrations: `make migrate` (`uv run alembic upgrade head`)
- Install bundled Chromium for scraping: `make browsers-install` (`uv run python -m playwright install chromium`)
- Run API locally: `make run` (`uv run python -m bsentinel.infrastructure.api`)
- Run tests: `make test` (`uv run pytest -q`)
- Lint: `make lint` (`uv run ruff check .`)
- Combined validation: `make check`
- Stop local Docker services: `make db-down` (`docker-compose down`)
- Fallback (venv): `.venv/bin/python -m pytest -q`
- Prefer `make <target>` when a matching target exists to keep commands consistent across sessions.

## Technical Research Policy (Context7 First)
- For framework/library usage, API contracts, and up-to-date patterns, use **MCP Context7 first**.
- Required flow:
  1. Resolve library id (`resolve-library-id`).
  2. Query docs (`query-docs`) with concrete implementation intent.
  3. Apply changes using the retrieved guidance.
- If Context7 is unavailable, use official primary documentation as fallback.

## Engineering Principles
- Apply **SOLID** for maintainable boundaries and dependency direction.
- Use **GRASP** to place behavior where information naturally lives.
- Enforce **YAGNI**: implement only what current scope needs.
- Follow **Clean Code**: explicit names, short functions, clear error handling, low coupling.

## Coding Style & Naming Conventions
- Python 3.12+, 4-space indentation, type hints for public functions.
- Naming: `snake_case` (modules/functions), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants).
- Keep modules focused and cohesive; prefer small, testable units.
- Use Ruff rules from `pyproject.toml`.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio`.
- Place unit tests in `tests/unit/`; integration/API behavior in `tests/integration/`.
- Name tests explicitly, e.g. `test_create_book_with_unsupported_store_returns_400`.
- Add tests for new behavior, edge cases, and regressions before merge.
- For unit test runs or syntax verification commands, use sub-agents to avoid consuming main-agent context.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`.
- Keep commits atomic and scoped.
- PRs must include:
  - behavior summary,
  - linked issue/task (if available),
  - test evidence (`pytest` output),
  - docs updates when contracts/flows change.

## Session Context Logging
- Engram is the persistent session memory for implementation history, decisions, and operational continuity.
- After each implementation session, persist:
  - objective and scope,
  - key decisions,
  - files changed,
  - verification commands/results,
  - risks/debt and next steps.
- Do not create or maintain repository logbook files for session history unless a future change explicitly reintroduces that pattern.
- At the end of each implemented plan/session, suggest updating `Readme.md` only when behavior, setup, or API usage changed.

## End-of-Session Checklist
- Verify implementation scope against the agreed plan.
- Run relevant checks/tests and capture outcomes.
- Suggest updating `Readme.md` when behavior, setup, or API usage changed.
- Ensure commit messages follow Conventional Commits in English.
