# Guía de Inicio Rápido - Bsentinel (MVP)

Esta guía arranca la API MVP localmente y valida los endpoints principales.

## Prerrequisitos

1. Python 3.12+
2. Git
3. Entorno virtual `.venv` (si no existe, créalo)
4. `uv` opcional (recomendado)

## 1) Preparar entorno

```bash
# desde la raíz del repositorio
uv sync
```

Si `uv` no está disponible, usa el entorno virtual existente para ejecutar comandos.

## 2) Ejecutar la API

Opción recomendada:

```bash
uv run python -m bsentinel.infrastructure.api
```

Fallback:

```bash
.venv/bin/python -m bsentinel.infrastructure.api
```

## 3) Verificar servicio

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 4) Ejecutar pruebas

Comando principal:

```bash
uv run pytest -q
```

Fallback:

```bash
.venv/bin/python -m pytest -q
```

## 5) Qué está implementado hoy

- API v1 para libros, historial y retención en `/api/v1/...`
- Scheduler local
- Integración básica con OpenLibrary
- Persistencia en memoria (no durable)

## Solución de problemas común

### `uv: command not found`
Usa el fallback con `.venv/bin/python` o instala `uv` y reinicia la terminal.

### Puerto `8000` ocupado
Ajusta `PORT` en configuración/entorno o detén el proceso que usa ese puerto.

## Documentación relacionada

- Estado del proyecto: `PROGRESS.md`
- Features MVP: `docs/features/mvp/`
- Features roadmap: `docs/features/roadmap/`
- Contexto acumulado de sesiones: `context.md`
