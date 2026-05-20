# Progreso del Proyecto: Bsentinel

## Estado General

- **Proyecto**: Bsentinel (Backend de rastreo de precios de libros)
- **Fecha de actualización**: 2026-03-06
- **Estado actual**: **MVP implementado y funcional en entorno local/dev**
- **Versión API activa**: `v1` (`/api/v1`)

## Resumen Ejecutivo

El proyecto cuenta con un MVP funcional con FastAPI, autenticación JWT, persistencia SQL y scraping SSR configurado por tienda.

La API v1 ya no depende de lógica fija por tienda: la configuración de extracción se persiste en `stores.extraction_rules`, existe una API admin básica para administrar tiendas y el catálogo sigue modelado por ISBN con relaciones `book-store`.

## Implementado en Código

### API y Contratos (MVP)

Endpoints actualmente disponibles:

- `GET /health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
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
- `POST /api/v1/stores`
- `GET /api/v1/stores`
- `GET /api/v1/stores/{store_id}`
- `PUT /api/v1/stores/{store_id}`
- `PATCH /api/v1/stores/{store_id}`

Notas:
- Swagger/ReDoc activos (`/docs`, `/redoc`) con agrupación por controlador (`auth`, `system`, `catalog`, `pricing`, `retention`, `stores`).
- Contrato de errores estandarizado con `error.code`, `error.message`, `error.details`, `request_id`.
- `/api/v1/*` requiere Bearer token salvo `/api/v1/auth/*`.
- La administración de tiendas usa dependencia de admin.
- Flujo auth MVP: login, refresh con rotación, logout con revocación persistida de refresh token.

### Arquitectura

- Estructura en capas (hexagonal): `domain`, `application`, `infrastructure`.
- API v1 modular por controlador en `bsentinel/infrastructure/api/v1/`.
- Scheduler local con APScheduler para tareas periódicas.
- Scraper configurado por reglas persistidas (`css` / `json_ld`) y seed inicial de Buscalibre CO.
- Persistencia SQL con repositorios en `bsentinel/infrastructure/persistence/sqlalchemy/`.
- Seguridad JWT con servicio de aplicación dedicado y adapter de token en `bsentinel/infrastructure/security/`.

### Persistencia y Migraciones

- Backend por defecto: SQL (`PERSISTENCE_BACKEND=sql`).
- Migraciones con Alembic (`alembic/`, `alembic.ini`).
- Esquema inicial creado con seed de tienda Buscalibre CO.
- `stores.extraction_rules` persiste configuración JSON/JSONB por tienda.
- Tabla de archivo incluida: `price_history_archive`.
- Tabla de revocación de refresh incluida: `revoked_refresh_tokens`.

### Calidad y Testing

- Pruebas implementadas en:
  - `tests/unit/`
  - `tests/integration/`
- Última validación conocida:
  - `make lint` -> OK
  - `make test` -> `36 passed`

## Documentación Funcional

- **MVP vigente**: `docs/features/mvp/`
- **Roadmap / no implementado aún**: `docs/features/roadmap/`
- **Histórico de diseño**: `docs/archive/first_idea.md`

## Pendiente (Roadmap)

## Seguridad
- Endurecer credenciales admin MVP hacia gestión más robusta si se introduce multiusuario.
- Diseñar RBAC real si aparecen roles adicionales.

## Scraping y Escalado
- Implementar delete/restore/test/stats para tiendas si pasan a MVP.
- Añadir más seeds/configuraciones de tiendas reales y endurecer reglas ante cambios HTML.
- Evaluar arquitectura de ejecución distribuida según carga futura.

## Observabilidad y Operación
- Endurecer métricas/telemetría para operación continua.
- Endurecer estrategia de archivado/retención sobre crecimiento real de datos.

## Riesgos y Deuda Técnica

- **Admin único por env**: adecuado para MVP interno, insuficiente para multiusuario.
- **Dependencias externas**: OpenLibrary y scraping sujetos a cambios de terceros.
- **Cobertura de tiendas**: la arquitectura ya es configurable, pero solo Buscalibre CO viene seeded y validado por defecto.
- **Configuración UV**: `tool.uv.dev-dependencies` está deprecado y debe migrarse a `dependency-groups.dev`.

## Próximos Hitos Sugeridos

1. Implementar endpoints pendientes de gestión de tiendas (`delete/restore/test/stats`) solo si el roadmap inmediato lo justifica.
2. Agregar smoke tests opcionales con PostgreSQL real.
3. Evaluar tabla real de usuarios si deja de ser suficiente el admin único por entorno.
4. Promover escenarios de `docs/features/roadmap/` a `docs/features/mvp/` conforme se implementen.

## Referencias

- Guía rápida de ejecución: `QUICKSTART.md`
- Documentación principal: `Readme.md`
- Continuidad de sesiones: Engram (memoria persistente operativa, fuera del repo)
