# Quickstart - Bsentinel MVP

This guide starts the current MVP locally with PostgreSQL, Alembic migrations, and JWT authentication enabled for `/api/v1/*`.

## Prerequisites

1. Python 3.12+
2. `uv`
3. Docker and Docker Compose
4. Chromium runtime for Playwright/Scrapling (`make browsers-install`)

## 1. Create local environment file

The application loads environment variables from `secrets/.env`.

```bash
mkdir -p secrets
cat > secrets/.env <<'ENV'
APP_ENVIRONMENT=local
PORT=8000
LOG_LEVEL=INFO

PERSISTENCE_BACKEND=sql
DATABASE_URL=postgresql+asyncpg://bsentinel:bsentinel@localhost:5432/bsentinel
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

AUTH_ADMIN_USERNAME=admin
AUTH_ADMIN_PASSWORD=changeme
JWT_SECRET_KEY=change-me-in-production-32-bytes
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

SCRAPING_DELAY=2.0
SCRAPING_TIMEOUT=30
SCRAPING_MAX_RETRIES=3
SCRAPING_BROWSER_ENABLED=true
SCRAPING_BROWSER_HEADLESS=true
SCRAPING_BROWSER_TIMEOUT_MS=45000
SCRAPING_BROWSER_MAX_PAGES=3
SCRAPING_BROWSER_DISABLE_RESOURCES=true
SCRAPING_BROWSER_NETWORK_IDLE=true
SCRAPING_BROWSER_SOLVE_CLOUDFLARE=false
SCRAPING_BROWSER_REAL_CHROME=false
SCHEDULER_SCRAPE_INTERVAL_HOURS=6

OPENLIBRARY_API_URL=https://openlibrary.org
OPENLIBRARY_RATE_LIMIT=1.0
ENV
```

## 2. Install dependencies

```bash
make install
```

## 3. Install Chromium for Scrapling

```bash
make browsers-install
```

## 4. Start PostgreSQL

```bash
make db-up
```

## 5. Apply migrations

```bash
make migrate
```

## 6. Start the API

```bash
make run
```

Fallback without `uv`:

```bash
.venv/bin/python -m bsentinel.infrastructure.api
```

## 7. Verify the service

- Root: `http://localhost:8000/`
- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 8. Authenticate in Swagger

Public endpoints:
- `/`
- `/health`
- `/docs`
- `/redoc`
- `/openapi.json`
- `/api/v1/auth/*`

Protected endpoints:
- `/api/v1/system/*`
- `/api/v1/catalog/*`
- `/api/v1/pricing/*`
- `/api/v1/retention/*`

Login with `POST /api/v1/auth/login` using form fields:
- `username=admin`
- `password=changeme`

Then use the returned `access_token` as:

```text
Authorization: Bearer <access_token>
```

## 9. Current route groups

- `GET /api/v1/system/info`
- `POST /api/v1/catalog/books`
- `GET /api/v1/catalog/books`
- `GET /api/v1/catalog/books/{book_id}`
- `DELETE /api/v1/catalog/books/{book_id}`
- `POST /api/v1/catalog/books/{book_id}/restore`
- `GET /api/v1/pricing/books/{book_id}/history`
- `GET /api/v1/pricing/books/{book_id}/comparison`
- `POST /api/v1/retention/jobs/archive`
- `GET /api/v1/retention/jobs/archive/{job_id}`

## 10. Development checks

```bash
make lint
make test
# or run everything together
make check
```

Fallback:

```bash
.venv/bin/python -m pytest -q
```

## Troubleshooting

### PostgreSQL connection error

Check that `docker-compose up -d postgres` is running and that `DATABASE_URL` points to `localhost:5432`.

### Missing tables

Run:

```bash
uv run alembic upgrade head
```

### Browser runtime not installed

Run:

```bash
make browsers-install
```

### Invalid admin credentials

Verify `AUTH_ADMIN_USERNAME` and `AUTH_ADMIN_PASSWORD` in `secrets/.env`.

### JWT errors

Verify `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and token expiration values in `secrets/.env`.

## Related docs

- `Readme.md`
- `PROGRESS.md`
- `docs/README.md`
- `context.md`
