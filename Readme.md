# Bsentinel

Backend para rastreo de precios de libros (MVP) con FastAPI y API versionada en `/api/v1`.

## Estado actual 🚀

El proyecto implementa un MVP funcional para entorno local/dev con:

- API `v1` protegida con autenticación JWT para endpoints funcionales
- Soporte público MVP para **Buscalibre Colombia** y **Panamericana Colombia**
- Seeds iniciales de Buscalibre (`www.buscalibre.com.co`) y Panamericana (`www.panamericana.com.co`)
- Reglas de extracción por tienda en JSON con fallbacks (`css` / `json_ld` / `vtex_property`)
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
- Las URL de `buscalibre.com.co` y `panamericana.com.co` se resuelven a sus dominios canónicos `www.*`; el alias solo afecta scraping, persistencia y búsqueda de la tienda. No se aceptan subdominios arbitrarios, userinfo ni puertos.
- El libro se identifica por `ISBN`; si no se puede extraer un ISBN válido, la API responde `VALIDATION_ERROR` y no persiste el libro.
- Un mismo libro puede tener múltiples relaciones `book-store`, cada una con su `product_url`, precio actual e historial de precios.
- La URL del producto ya no pertenece a `Book`; pertenece solo a `BookStoreRelation`.
- Si intentas registrar de nuevo el mismo libro para la misma tienda, la API responde `ENTITY_ALREADY_EXISTS`.
- El scraping y la extracción ya no dependen de lógica fija de Buscalibre; usan `Store.extraction_rules` persistidas y el runtime HTTP de Scrapling por defecto; Chromium se selecciona con `SCRAPING_RUNTIME=browser`.

## Alcance MVP de Sitios 🏪

- La API pública NO expone administración dinámica de tiendas en `/api/v1/stores`.
- El soporte público actual del MVP incluye **Buscalibre Colombia** y **Panamericana Colombia**.
- Internamente se conservan contratos neutrales por tienda para catálogo, scraping e historial.

## Endpoints MVP 🔌

- `GET /health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/system/info`
- `POST /api/v1/catalog/books`
- `POST /api/v1/catalog/books/bulk`
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

## Identidad, transacciones y consultas

El ISBN se normaliza quitando espacios y guiones, convirtiendo `x` a `X` y validando
el checksum ISBN-10 o ISBN-13. Ambos formatos conservan identidades distintas.
Un ISBN faltante, inválido o extraído como fragmento de un número mayor devuelve
`400 VALIDATION_ERROR` sin escrituras. Las fuentes de extracción pueden usar fallbacks.

El alta individual confirma libro, relación, precio e historial en una sola
transacción antes de devolver `201`. Una sola extracción HTTP aporta datos del libro y
la oferta; se registra ese resultado sin una segunda consulta. Un fallo de scraping, flush o commit revierte
el alta; su respuesta conserva el formato individual, sin índice ni URL del lote.

El batch usa tres workers y cola acotada; reserva cada ventana en una transacción
corta antes de HTTP y publica precio/historial juntos en otra. Fallos recuperables
(`ScrapingError`/`UnsupportedStoreError`) y resultados explícitos de pausa/omisión
permiten continuar. Tiendas o libros deshabilitados se omiten al revalidar.
Un error inesperado, de reserva o de publicación SQL aborta el lote: `TaskGroup`
cancela y espera producer/workers (puede propagar `ExceptionGroup`). Los éxitos
ya confirmados y las reservas durables permanecen; las reservas no se repiten
tras reiniciar. La cancelación se propaga y libera sesiones, locks y permisos.
Pausas por tienda y evidencia de tráfico se persisten independientemente del catálogo.

Catálogo e historial aplican filtros y conteo antes de paginar. El orden es
`created_at DESC, id DESC` para libros y `checked_at DESC, id DESC` para historial;
`%` y `_` en búsquedas de texto son literales. Historial `source=all` combina ambas
tablas antes de ordenar y paginar. Las fechas sin zona de SQLite representan UTC.

El archivado responde con `id` (usarlo en el path `{job_id}`). Conserva los últimos
N registros por libro y archiva los restantes anteriores al corte. SQL mueve filas
de `price_history` a `price_history_archive` preservando IDs en una transacción;
memoria cambia la marca `archived`.

### Migración parcial de ISBN

Antes de `make migrate`, crea y verifica un backup restaurable de la base.
La revisión `0007_normalize_isbn`, posterior a `0006`, inspecciona también libros
eliminados. Solo normaliza grupos válidos de un único libro. Conserva intactos
todos los miembros de grupos conflictivos, incluidos los ya normalizados, y los
ISBN inválidos, nulos o vacíos. Reporta cantidades, IDs y motivos en el log Alembic.
No fusiona, borra ni reasigna relaciones y no agrega unicidad al índice ISBN.
Solo actualiza patrones ISBN predeterminados conocidos; conserva reglas custom.
Los conflictos requieren revisión manual antes de registrar la misma identidad.
El downgrade no reconstruye formatos previos: para recuperarlos restaura el backup.

El único head es `0010_merge_audit_scraping`, una revisión vacía que une
`0007_normalize_isbn` y `0009_store_blocks_daily_windows` sin modificar las
migraciones previas. `alembic upgrade head` funciona desde una base vacía o desde
cualquiera de esos heads. Aplica solo las ramas pendientes: un calendario ya
migrado por 0009 conserva fechas y generaciones. 0009 no reconstruye el calendario
horario al hacer downgrade. Un rollback de aplicación requiere revisar su política
antes de reactivar el scheduler; no ejecutar downgrades ni migraciones productivas
como parte de esta reconciliación. El candidato se verifica únicamente con bases
locales desechables y CI; esto no acredita despliegue ni comportamiento merchant.


## Alta masiva de libros

`POST /api/v1/catalog/books/bulk` requiere JWT y recibe `{"urls": ["URL", "URL"]}`.
Acepta **1 a 20 strings estrictos**, hasta **2048 caracteres** por URL; rechaza
URL repetidas exactamente, listas vacías, exceso de tamaño y tipos incorrectos
con `422`, antes de scraping. URL inválida, tienda no soportada/inactiva, ISBN
faltante o scraping fallido producen `400`; relación libro-tienda existente,
`409`. Las tiendas permitidas son las mismas del alta individual.

```bash
curl --request POST "${API_BASE_URL}/api/v1/catalog/books/bulk" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{"urls":["https://www.buscalibre.com.co/libro-ejemplo-isbn-9780134494166","https://www.panamericana.com.co/libro-ejemplo-isbn-9780134494166/p"]}'
```

URL ilustrativas, no productos reales verificados. Éxito: `201 Created` **después
del commit**, `items` en orden de entrada y `meta.total` igual al número de URL:

```json
{
  "items": [
    {"index": 0, "url": "URL de entrada", "book_id": "UUID", "relation_id": "UUID", "isbn": "9780134494166", "title": "Ejemplo", "authors": ["Autor"], "site": "www.buscalibre.com.co", "status": "activo"}
  ],
  "meta": {"total": 1}
}
```

Cada item inicializa precio e historial. El mismo ISBN en dos tiendas reutiliza
un libro y crea dos relaciones: `meta.total` cuenta relaciones, no libros únicos.
No se enriquecen de nuevo libros existentes ni se restauran libros borrados.

La operación es síncrona, secuencial, **todo o nada y fail-fast**. Un fallo revierte
libros, relaciones e historiales del lote. Los errores por item conservan el
contrato habitual y añaden índice base cero y URL sanitizada:

```json
{"error":{"code":"ENTITY_ALREADY_EXISTS","message":"Book-store relation already exists","details":{"index":1,"url":"URL causante"}},"request_id":"UUID"}
```

Errores inesperados de infraestructura/flush/commit devuelven `500` genérico, no
`201`; incluyen `request_id` y `X-Request-ID`. En SQL el lote toma posesión de la
transacción ya abierta por la petición/auth, hace flush por item y confirma antes
de responder; la dependencia de sesión no repite ese commit. En memoria trabaja
sobre una copia aislada y publica sin puntos de suspensión solo al éxito. Si
cambia el catálogo compartido durante el lote, aborta con `500` sin sobrescribir
al escritor concurrente (reintentar). Memoria es process-local, no thread-safe.

Límites: el índice ISBN SQL **no es único**, por lo que sigue existiendo una carrera
entre peticiones concurrentes; no se garantiza deduplicación global ni se migran
datos con esta operación. El rollback no deshace llamadas externas. No hay claves
de idempotencia: reintentar un lote confirmado tras perder la respuesta puede
devolver `409`. El límite de 20 no es un benchmark; no subirlo sin medir latencias
y timeouts reales o cambiar a jobs persistentes.

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

La aplicación carga `secrets/.env`. En la primera ejecución, copia
`secrets/.env.example` a `secrets/.env` (`Copy-Item secrets/.env.example secrets/.env`
en PowerShell, o `cp secrets/.env.example secrets/.env` en Bash).
Si el archivo ya existe, incorpora las variables faltantes de la plantilla.
Para usar un proxy, descomenta `SCRAPING_HTTP_PROXY` y sustituye la URL de ejemplo
por el endpoint y las credenciales de tu proveedor. Esta opción se aplica con
`SCRAPING_RUNTIME=http`; sin ella, la conexión es directa.

Atajo recomendado con `Makefile`:

```bash
make install
make browsers-install
make db-up
make migrate
make run
```

`make browsers-install` solo es necesario si seleccionas `SCRAPING_RUNTIME=browser`.
El runtime HTTP no cambia automáticamente al navegador cuando falla.

Para ejecutar también la API en Docker, sigue la alternativa de Docker Compose
en [QUICKSTART.md](QUICKSTART.md#alternative-run-the-api-and-database-with-docker-compose).
Compose configura la conexión interna a PostgreSQL mediante el servicio `postgres`.

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

Las fichas JSON-LD se reconocen con `@type: "Product"` o con una lista que incluya
`"Product"`, como `["Product", "Book"]`. En ambos casos se extraen los datos del
libro y su oferta con las reglas configuradas por tienda.

En Panamericana, el título, precio y disponibilidad provienen del producto JSON-LD.
El autor y el ISBN editorial se resuelven desde las propiedades referenciadas de
`__STATE__` para el mismo slug VTEX; el `gtin` interno de la tienda no se usa como ISBN.

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

El scheduler usa ventanas absolutas en `America/Bogota`: **08:00/17:00**, **08:20/17:20** y **08:40/17:40** por cohorte (dos revisiones diarias). Los campos de intervalo/tick legacy no cambian esta política. AWS WAF CAPTCHA/challenge pausa únicamente la tienda por `SCRAPING_BLOCK_COOLDOWN_MINUTES=60`; el estado SQL sobrevive reinicios y rollback del catálogo. Aplicar `alembic upgrade head` hasta el único head `0010_merge_audit_scraping` antes de arrancar el candidato; no rebasar calendarios en cada restart. Revisiones manuales/creación inicial siguen permitidas salvo pausa. Ver [calendario, pausa y rollout](docs/scraping-schedule.md).
Cada cohorte dispone de 20 minutos de trabajo (08–09 y 17–18, límite exclusivo), pero nuevos lotes sólo inician dentro de los primeros 120 segundos de su slot; cron conserva misfire grace de 119 s. Reiniciar no reproduce un slot perdido. No comienza HTTP/retry después del límite, aunque requests ya admitidos pueden completar.

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
- Seeds iniciales automáticos para las tiendas Buscalibre CO y Panamericana CO

## Limitaciones actuales ⚠️

- Solo existe un usuario admin definido por variables de entorno.
- El runtime `browser` requiere Chromium instalado (`make browsers-install`); el runtime `http` sigue siendo el default operativo.
- `logout` revoca refresh tokens; el access token actual sigue válido hasta expirar.
- Integración OpenLibrary simplificada (best-effort).
- Solo se persisten libros cuando la extracción produce un ISBN válido.
- La administración pública multi-store quedó fuera del alcance del MVP actual.
- El reemplazo profundo de `ConfiguredStoreScraper` sigue fuera de scope del MVP.
- `tool.uv.dev-dependencies` está deprecado en `pyproject.toml` y debe migrarse a `dependency-groups.dev`.

## Documentación 📚

- Estado actual del proyecto: `PROGRESS.md`
- Ejecución rápida MVP: `QUICKSTART.md`
- Índice de docs: `docs/README.md`
- Features implementados: `docs/features/mvp/`
- Features de roadmap: `docs/features/roadmap/`
- Histórico de diseño: `docs/archive/first_idea.md`
