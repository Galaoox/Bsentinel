# Bsentinel

Backend para rastreo de precios de libros (MVP), con API FastAPI en `/api/v1`.

## Estado actual (MVP implementado)

- API pública sin autenticación (temporal)
- Alta y gestión básica de libros desde URL de Buscalibre CO
- Historial de precios y comparación de ofertas
- Job de archivado de historial (retención por archivo)
- Scheduler local con APScheduler para scraping periódico
- Persistencia en memoria (entorno local/dev)

## Endpoints principales

- `GET /health`
- `GET /api/v1/info`
- `POST /api/v1/books`
- `GET /api/v1/books`
- `GET /api/v1/books/{book_id}`
- `DELETE /api/v1/books/{book_id}`
- `POST /api/v1/books/{book_id}/restore`
- `GET /api/v1/books/{book_id}/history`
- `GET /api/v1/books/{book_id}/price-comparison`
- `POST /api/v1/retention/archive-jobs`
- `GET /api/v1/retention/archive-jobs/{job_id}`

## Ejecución local

1. Instalar dependencias:

```bash
uv sync
```

2. Ejecutar API:

```bash
uv run python -m bsentinel.infrastructure.api
```

3. Verificar:

- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Tests

```bash
uv run pytest
```
