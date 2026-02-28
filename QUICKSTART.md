# Guía de Inicio Rápido - Bsentinel (MVP)

Esta guía arranca la API MVP localmente y valida los endpoints principales.

## Prerrequisitos

1. Python 3.12+
2. Git
3. Entorno virtual `.venv` (si no existe, créalo)
4. `uv` opcional (recomendado)
5. PostgreSQL local (si usarás `DATABASE_URL` por defecto)

## 1) Preparar entorno

```bash
# desde la raíz del repositorio
uv sync
```

Si `uv` no está disponible, usa el entorno virtual existente para ejecutar comandos.

## 2) Configurar persistencia

Por defecto se usa backend SQL (`PERSISTENCE_BACKEND=sql`).

Aplicar migraciones:

```bash
uv run alembic upgrade head
```

Si deseas usar persistencia en memoria temporalmente:

```bash
export PERSISTENCE_BACKEND=in_memory
```

## 3) Ejecutar la API

Opción recomendada:

```bash
uv run python -m bsentinel.infrastructure.api
```

Fallback:

```bash
.venv/bin/python -m bsentinel.infrastructure.api
```

## 4) Verificar servicio

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 5) Ejecutar pruebas

Comando principal:

```bash
uv run pytest -q
```

Lint:

```bash
uv run ruff check .
```

Fallback:

```bash
.venv/bin/python -m pytest -q
```

## 6) Qué está implementado hoy

- API v1 (`/api/v1/system|catalog|pricing|retention`)
- Scheduler local
- Integración básica con OpenLibrary
- Persistencia SQLAlchemy + Alembic
- Seed inicial de tienda Buscalibre CO

## Solución de problemas común

### `uv: command not found`
Usa el fallback con `.venv/bin/python` o instala `uv` y reinicia la terminal.

### Error de conexión a PostgreSQL
Verifica `DATABASE_URL`, credenciales y que el servicio esté arriba.

### No existen tablas
Ejecuta: `uv run alembic upgrade head`.

## Documentación relacionada

- Estado del proyecto: `PROGRESS.md`
- Features MVP: `docs/features/mvp/`
- Features roadmap: `docs/features/roadmap/`
- Contexto acumulado de sesiones: `context.md`
