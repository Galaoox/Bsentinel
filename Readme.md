# Bsentinel

Backend para rastreo de precios de libros (MVP) con FastAPI y API versionada en `/api/v1`.

## Estado actual 🚀

El proyecto implementa un MVP funcional para entorno local/dev con:

- API pública sin autenticación (temporal en esta fase)
- Soporte de tienda: **Buscalibre Colombia** (`www.buscalibre.com.co`)
- Gestión básica de libros desde URL
- Historial y comparación de precios
- Archivado de historial por job
- Scheduler local con APScheduler
- Persistencia durable con **SQLAlchemy + Alembic** (por defecto)

## Arquitectura 🏗️

Estructura por capas (estilo hexagonal):

- `bsentinel/domain/`: entidades y reglas de negocio puras
- `bsentinel/application/`: casos de uso y orquestación
- `bsentinel/infrastructure/`: API, scheduler, scraping, cliente OpenLibrary y persistencia
- `bsentinel/infrastructure/api/v1/`: rutas separadas por controlador (`system`, `catalog`, `pricing`, `retention`)
- `bsentinel/infrastructure/persistence/sqlalchemy/`: modelos ORM, repositorios SQL y sesión
- `alembic/`: migraciones de esquema y seed inicial
- `tests/unit` y `tests/integration`: pruebas por nivel

Swagger organiza las rutas de `v1` por controlador/tag, evitando agrupado único por versión.

## Endpoints MVP 🔌

- `GET /health`
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

Nota de contrato de errores v1:
- Respuesta estándar: `error.code`, `error.message`, `error.details` y `request_id`.

## Ejecución local ▶️

1. Instalar dependencias:

```bash
uv sync
```

2. Aplicar migraciones:

```bash
uv run alembic upgrade head
```

3. Levantar API:

```bash
uv run python -m bsentinel.infrastructure.api
```

4. Verificar:

- Swagger 📘: `http://localhost:8000/docs`
- Health ✅: `http://localhost:8000/health`

## Testing 🧪

Comando principal:

```bash
uv run pytest -q
```

Lint:

```bash
uv run ruff check .
```

Fallback en entorno local con venv:

```bash
.venv/bin/python -m pytest -q
```

## Persistencia y migraciones 🗃️

- Backend por defecto: `PERSISTENCE_BACKEND=sql`
- URL DB configurable vía `DATABASE_URL`
- Migración inicial crea:
  - `stores`, `books`, `book_authors`, `book_categories`, `book_store_relations`,
  - `price_history`, `price_history_archive`, `archive_jobs`
- Seed inicial automático para la tienda Buscalibre CO

## Limitaciones actuales ⚠️

- No hay autenticación/autorización en endpoints.
- Integración OpenLibrary simplificada (best-effort).
- `tool.uv.dev-dependencies` está deprecado en `pyproject.toml` y debe migrarse a `dependency-groups.dev`.

## Documentación 📚

- Estado actual del proyecto: `PROGRESS.md`
- Ejecución rápida MVP: `QUICKSTART.md`
- Índice de docs: `docs/README.md`
- Features implementados: `docs/features/mvp/`
- Features de roadmap: `docs/features/roadmap/`
- Histórico de diseño: `docs/archive/first_idea.md`
