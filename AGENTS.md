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
- Install dependencies: `uv sync`
- Run API locally: `uv run python -m bsentinel.infrastructure.api`
- Run tests: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Docker stack: `docker-compose up --build`
- Fallback (venv): `.venv/bin/python -m pytest -q`

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
- Maintain `context.md` as the implementation logbook.
- After each implementation session, append:
  - objective and scope,
  - key decisions,
  - files changed,
  - verification commands/results,
  - risks/debt and next steps.
- `context.md` is not a documentation fallback source; its purpose is historical session tracking.
- At the end of each implemented plan/session, explicitly suggest updating both `Readme.md` and `context.md` when applicable.

## End-of-Session Checklist
- Verify implementation scope against the agreed plan.
- Run relevant checks/tests and capture outcomes.
- Suggest updating `Readme.md` when behavior, setup, or API usage changed.
- Suggest updating `context.md` with a new session entry (objective, changes, validations, next steps).
- Ensure commit messages follow Conventional Commits in English.
