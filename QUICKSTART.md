# Quickstart - Bsentinel MVP

This guide starts the current MVP locally with PostgreSQL, Alembic migrations, and JWT authentication enabled for `/api/v1/*`.

## Prerequisites

1. Python 3.12+
2. `uv`
3. Docker and Docker Compose
4. Chromium runtime only if using `SCRAPING_RUNTIME=browser` (`make browsers-install`)

## 1. Create local environment file

The application loads environment variables from `secrets/.env`. Copy the example on first setup:

```bash
cp secrets/.env.example secrets/.env
```

On Windows PowerShell:

```powershell
Copy-Item secrets/.env.example secrets/.env
```

If `secrets/.env` already exists, add the missing variables from the example to that file.
The example includes local database and authentication defaults, HTTP/browser options,
and scheduler settings. For a proxy, uncomment `SCRAPING_HTTP_PROXY` in `secrets/.env`
and replace the sample URL with your provider's endpoint and credentials:

```dotenv
SCRAPING_RUNTIME=http
SCRAPING_HTTP_PROXY=http://usuario:contrasena@host:puerto
```

Omit `SCRAPING_HTTP_PROXY` to connect directly. This variable applies only to the HTTP runtime.

## 2. Install dependencies

```bash
make install
```

## 3. Install Chromium if using the browser runtime

```bash
make browsers-install
```

Skip this step with `SCRAPING_RUNTIME=http`. To use Chromium, explicitly set
`SCRAPING_RUNTIME=browser`; the application does not switch to it automatically on HTTP failures.

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

### Alternative: run the API and database with Docker Compose

After creating `secrets/.env` in step 1, run from the repository root:

```bash
docker compose build --pull bsentinel
docker compose up -d postgres
docker compose run --rm bsentinel alembic upgrade head
docker compose up -d bsentinel
```

Compose sets `DATABASE_URL` to use the `postgres` service inside the Docker network.
Keep `localhost` in `secrets/.env` for running the API directly on the host.
The image uses Python 3.12 on Debian Bookworm and installs dependencies from `uv.lock`.
It includes the default HTTP scraping runtime; Chromium must be installed separately
if you select the browser runtime.

If a build fails, capture the complete output with
`docker compose --progress plain build --pull bsentinel`.

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

### HTTP proxy runtime

If you use the default HTTP runtime with a proxy, verify at least:

- `SCRAPING_RUNTIME=http`
- `SCRAPING_HTTP_PROXY=http://user:pass@host:port`

If the proxy URL includes credentials, the application redacts them in observable logs and error payloads.

### Invalid admin credentials

Verify `AUTH_ADMIN_USERNAME` and `AUTH_ADMIN_PASSWORD` in `secrets/.env`.

### JWT errors

Verify `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and token expiration values in `secrets/.env`.

## Related docs

- `Readme.md`
- `PROGRESS.md`
- `docs/README.md`

## Data and transaction behavior

Back up the database before `make migrate`. Revision `0007_normalize_isbn` only
normalizes valid, unambiguous ISBN groups (including deleted books), and logs
IDs/counts for invalid, empty and conflicting values. Collisions and custom
extraction rules remain intact. Downgrade cannot recover previous spelling;
restore the backup to recover it. See [migration policy](Readme.md#migración-parcial-de-isbn).

ISBN-10/13 checksums are required; spaces/hyphens are removed and `x` becomes `X`.
The formats remain distinct identities. Individual creation commits book,
relation, initial price and history together before returning `201`, using one
product extraction for both metadata and the initial offer.
Scheduler batches commit each relation separately: scraping/unsupported-store
failures continue; database/unexpected failures cancel and await all workers and
the producer through `TaskGroup` (fatal errors may be an `ExceptionGroup`). Prior
commits and durable window reservations survive; failed publication cannot replay
a consumed window. Traffic/cooldown persistence remains independent.
`/api/v1/stores` returns `404`. Archive responses expose `id`; SQL moves rows
between active/archive tables while memory marks them `archived`.

The single migration head is `0010_merge_audit_scraping`, an empty merge of
`0007_normalize_isbn` and `0009_store_blocks_daily_windows`. After a verified backup,
`make migrate` upgrades an empty database or either previous head, running only
pending migrations. An already applied 0009 calendar/generation is never rebased.
Downgrade cannot restore ISBN spelling or hourly calendars; application rollback
needs an explicit cadence decision before restarting its scheduler. This candidate
has no production migration/deployment verification.

CI runs the full SQLite suite, then the full PostgreSQL-enabled suite using
disposable PostgreSQL 16 on loopback port 55432. For the same local PostgreSQL pass,
set `BULK_TEST_POSTGRES_URL` to the isolated `bulk_test` database and
`SCHEDULE_TEST_POSTGRES_URL` to `bsentinel_schedule_test`, both at
`127.0.0.1:55432`, and `REQUIRE_TEST_POSTGRES=1`. Missing URLs, unavailable
databases, or skipped tests fail that mandatory pass. See [scraping policy](docs/scraping-schedule.md).
