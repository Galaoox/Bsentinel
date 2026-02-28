# Progreso del Proyecto: Bsentinel

## Estado General

- **Proyecto**: Bsentinel (Backend de rastreo de precios de libros)
- **Fecha de actualización**: 2026-02-28
- **Estado actual**: **MVP implementado y funcional en entorno local/dev**
- **Versión API activa**: `v1` (`/api/v1`)

## Resumen Ejecutivo

El proyecto ya no está solo en planificación: hoy cuenta con un MVP funcional con FastAPI, scraping para Buscalibre CO, integración básica con OpenLibrary, scheduler local y pruebas unitarias/integración.

La persistencia sigue siendo en memoria, por lo que aún no hay almacenamiento durable ni migraciones de base de datos.

## Implementado en Código

### API y Contratos (MVP)

Endpoints actualmente disponibles:

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

Notas:
- Swagger/ReDoc activos (`/docs`, `/redoc`) con agrupación por controlador (`system`, `books`, `history`, `retention`).
- No hay autenticación/autorización en esta fase.

### Arquitectura

- Estructura en capas (hexagonal): `domain`, `application`, `infrastructure`.
- API v1 modular por controlador en `bsentinel/infrastructure/api/v1/`.
- Scheduler local con APScheduler para tareas periódicas.
- Cliente OpenLibrary y scraper Buscalibre integrados en flujo MVP.

### Calidad y Testing

- Pruebas implementadas en:
  - `tests/unit/`
  - `tests/integration/`
- Última validación conocida de suite: `16 passed`.

## Documentación Funcional

- **MVP vigente**: `docs/features/mvp/`
- **Roadmap / no implementado aún**: `docs/features/roadmap/`
- **Histórico de diseño**: `docs/archive/first_idea.md`

## Pendiente (Roadmap)

## Persistencia y Datos
- Reemplazar repositorio en memoria por persistencia durable (DB).
- Definir estrategia de migraciones/versionado de esquema.

## Seguridad
- Diseñar e implementar autenticación/autorización para endpoints protegidos.

## Scraping y Escalado
- Ampliar cobertura de tiendas y robustez anti-bloqueo.
- Evaluar arquitectura de ejecución distribuida según carga futura.

## Observabilidad y Operación
- Endurecer métricas/telemetría para operación continua.
- Definir política de retención/archivado productiva sobre almacenamiento real.

## Riesgos y Deuda Técnica

- **Persistencia en memoria**: riesgo de pérdida de datos al reiniciar proceso.
- **Sin auth**: API no apta para exposición pública sin capa de seguridad.
- **Dependencias externas**: OpenLibrary y scraping sujetos a cambios de terceros.
- **Entorno local**: `uv run` puede requerir ajustes específicos en algunos entornos.

## Próximos Hitos Sugeridos

1. Implementar persistencia durable y repositorios reales.
2. Incorporar autenticación para operaciones sensibles.
3. Expandir escenarios de pruebas de integración sobre infraestructura persistente.
4. Promover escenarios de `docs/features/roadmap/` a `docs/features/mvp/` conforme se implementen.

## Referencias

- Guía rápida de ejecución: `QUICKSTART.md`
- Documentación principal: `Readme.md`
- Historial de sesiones: `context.md`
