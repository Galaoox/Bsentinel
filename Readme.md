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
- Persistencia en memoria (sin base de datos persistente todavía)

## Arquitectura 🏗️

Estructura por capas (estilo hexagonal):

- `bsentinel/domain/`: entidades y reglas de negocio puras
- `bsentinel/application/`: casos de uso y orquestación
- `bsentinel/infrastructure/`: API, scheduler, scraping y cliente OpenLibrary
- `bsentinel/infrastructure/api/v1/`: rutas separadas por controlador (`system`, `catalog`, `pricing`, `retention`)
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

2. Levantar API:

```bash
uv run python -m bsentinel.infrastructure.api
```

3. Verificar:

- Swagger 📘: `http://localhost:8000/docs`
- Health ✅: `http://localhost:8000/health`

## Testing 🧪

Comando principal:

```bash
uv run pytest -q
```

Fallback en entorno local con venv:

```bash
.venv/bin/python -m pytest -q
```

## Limitaciones actuales ⚠️

- No hay autenticación/autorización en endpoints.
- Persistencia en memoria (los datos se reinician al reiniciar el proceso).
- Integración OpenLibrary simplificada (best-effort).
- En este entorno, `uv run` puede requerir configuración explícita de `PYTHONPATH` y `--python`.

## Documentación 📚

- Estado actual del proyecto: `PROGRESS.md`
- Ejecución rápida MVP: `QUICKSTART.md`
- Índice de docs: `docs/README.md`
- Features implementados: `docs/features/mvp/`
- Features de roadmap: `docs/features/roadmap/`
- Histórico de diseño: `docs/archive/first_idea.md`
