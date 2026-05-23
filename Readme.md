# Bsentinel

Backend para rastreo de precios de libros (MVP) con FastAPI y API versionada en `/api/v1`.

## Estado actual 🚀

El proyecto implementa un MVP funcional para entorno local/dev con:

- API `v1` protegida con autenticación JWT para endpoints funcionales
- Soporte público MVP limitado a **Buscalibre Colombia**
- Seed inicial de **Buscalibre Colombia** (`www.buscalibre.com.co`)
- Reglas de extracción por tienda en JSON con fallbacks (`css` / `json_ld`)
- Gestión de catálogo por ISBN con relaciones libro-tienda
- Historial y comparación de precios
- Archivado de historial por job
- Scheduler local con APScheduler
- Persistencia durable con **SQLAlchemy + Alembic** (por defecto)

## Arquitectura 🏗️

Estructura por capas (estilo hexagonal):

- `bsentinel/domain/`: entidades y reglas de negocio puras
- `bsentinel/application/`: casos de uso y orquestación
- `bsentinel/infrastructure/`: API, scheduler, scraping, cliente OpenLibrary y persistencia
- `bsentinel/infrastructure/api/v1/`: rutas separadas por controlador (`auth`, `system`, `catalog`, `pricing`, `retention`)
- `bsentinel/infrastructure/persistence/sqlalchemy/`: modelos ORM, repositorios SQL y sesión
- `bsentinel/infrastructure/scraping/`: scraper configurado por reglas + runtime principal con Scrapling/Chromium
- `alembic/`: migraciones de esquema y seed inicial
- `tests/unit` y `tests/integration`: pruebas por nivel

Swagger organiza las rutas de `v1` por controlador/tag, evitando agrupado único por versión.

## Reglas Actuales de Catálogo 📘

- `POST /api/v1/catalog/books` resuelve la tienda por dominio y no por hardcode en el servicio.
- El libro se identifica por `ISBN`; si no se puede extraer un ISBN válido, la API responde `VALIDATION_ERROR` y no persiste el libro.
- Un mismo libro puede tener múltiples relaciones `book-store`, cada una con su `product_url`, precio actual e historial de precios.
- La URL del producto ya no pertenece a `Book`; pertenece solo a `BookStoreRelation`.
- Si intentas registrar de nuevo el mismo libro para la misma tienda, la API responde `ENTITY_ALREADY_EXISTS`.
- El scraping y la extracción ya no dependen de lógica fija de Buscalibre; usan `Store.extraction_rules` persistidas y un navegador compartido con Scrapling `AsyncStealthySession`.

## Alcance MVP de Sitios 🏪

- La API pública NO expone administración dinámica de tiendas en `/api/v1/stores`.
- El soporte público actual del MVP está recortado a **Buscalibre Colombia**.
- Internamente se conservan contratos neutrales por tienda para catálogo, scraping e historial.

## Endpoints MVP 🔌

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

Nota de contrato de errores v1:
- Respuesta estándar: `error.code`, `error.message`, `error.details` y `request_id`.

## Autenticación 🔐

- `POST /api/v1/auth/login` usa `application/x-www-form-urlencoded`
- Credenciales MVP por entorno: `AUTH_ADMIN_USERNAME` y `AUTH_ADMIN_PASSWORD`
- Tokens configurables con:
  - `JWT_SECRET_KEY`
  - `JWT_ALGORITHM`
  - `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
  - `JWT_REFRESH_TOKEN_EXPIRE_DAYS`
- `/api/v1/**` requiere `Authorization: Bearer <access_token>`, excepto `/api/v1/auth/*`

## Ejecución local ▶️

Atajo recomendado con `Makefile`:

```bash
make install
make browsers-install
make db-up
make migrate
make run
```

Equivalente con comandos directos:

1. Instalar dependencias:

```bash
uv sync
```

2. Instalar Chromium para el scraper:

```bash
make browsers-install
```

3. Levantar PostgreSQL:

```bash
docker-compose up -d postgres
```

4. Aplicar migraciones:

```bash
uv run alembic upgrade head
```

5. Levantar API:

```bash
uv run python -m bsentinel.infrastructure.api
```

6. Verificar:

- Swagger 📘: `http://localhost:8000/docs`
- Health ✅: `http://localhost:8000/health`

Variables nuevas del runtime de scraping:

- `SCRAPING_RUNTIME` (`http` por defecto, `browser` para forzar Chromium)
- `SCRAPING_HTTP_PROXY` (proxy HTTP/HTTPS único opcional; si incluye credenciales, la aplicación las redacta en logs/errores observables)
- `SCRAPING_BROWSER_HEADLESS`
- `SCRAPING_BROWSER_TIMEOUT_MS`
- `SCRAPING_BROWSER_MAX_PAGES`
- `SCRAPING_BROWSER_DISABLE_RESOURCES`
- `SCRAPING_BROWSER_NETWORK_IDLE`
- `SCRAPING_BROWSER_SOLVE_CLOUDFLARE`
- `SCRAPING_BROWSER_REAL_CHROME`

## Testing 🧪

Con `Makefile`:

```bash
make test
make lint
make check
```

Comandos directos:

```bash
uv run pytest -q
uv run ruff check .
```

Fallback en entorno local con venv:

```bash
.venv/bin/python -m pytest -q
```

## Persistencia y migraciones 🗃️

- Backend por defecto: `PERSISTENCE_BACKEND=sql`
- URL DB configurable vía `DATABASE_URL`
- Migraciones actuales crean y evolucionan:
  - `stores`, `books`, `book_authors`, `book_categories`, `book_store_relations`,
  - `price_history`, `price_history_archive`, `archive_jobs`, `revoked_refresh_tokens`
- `stores.extraction_rules` persiste configuración JSON/JSONB por tienda
- Seed inicial automático para la tienda Buscalibre CO

## Limitaciones actuales ⚠️

- Solo existe un usuario admin definido por variables de entorno.
- El runtime `browser` requiere Chromium instalado (`make browsers-install`); el runtime `http` sigue siendo el default operativo.
- `logout` revoca refresh tokens; el access token actual sigue válido hasta expirar.
- Integración OpenLibrary simplificada (best-effort).
- Solo se persisten libros cuando la extracción produce un ISBN válido.
- La administración pública multi-store quedó fuera del alcance del MVP actual.
- El reemplazo profundo de `ConfiguredStoreScraper` sigue fuera de scope en este recorte Buscalibre-only.
- `tool.uv.dev-dependencies` está deprecado en `pyproject.toml` y debe migrarse a `dependency-groups.dev`.

## Documentación 📚

- Estado actual del proyecto: `PROGRESS.md`
- Ejecución rápida MVP: `QUICKSTART.md`
- Índice de docs: `docs/README.md`
- Features implementados: `docs/features/mvp/`
- Features de roadmap: `docs/features/roadmap/`
- Histórico de diseño: `docs/archive/first_idea.md`
