# Tráfico del scraping HTTP

## Qué se registra

`HttpFetcherSession` instrumenta **cada llamada real `curl_cffi.AsyncSession.request`** de su sesión privada: también los retries internos de Scrapling y los nuevos fetches del extractor. No cambia proxy, timeout ni concurrencia. El guard de tienda/ventana comprueba admisión antes de cada intento de transporte, incluyendo retries de red. Se conserva el proxy explícito en `session.get(url, proxy=...)`.

La evidencia es append-only en `scraping_traffic_events`, independiente de la transacción de precio. Una extracción que falla después de recibir HTTP 403 no borra los bytes ni convierte la respuesta en éxito. Se guardan UUIDs de evento/operación/relación/lote, dominio (no IP), fecha UTC, scope (`periodic`, `manual`, `catalog`, `unattributed`), HTTP status, outcome y contadores. **No** se guardan URL completa, ruta, query, contenido, headers, cookies, proxy o credenciales.

Contadores de libcurl:

- `download_bytes`: `SIZE_DOWNLOAD_T`, payload recibido en el transporte; no `len(page.body)` descomprimido. Excluye headers. Con redirects sólo describe la última transferencia.
- `upload_bytes`: `SIZE_UPLOAD_T`, reportado por separado; este adaptador sólo hace GET sin cuerpo.
- `request_bytes`: `REQUEST_SIZE`, tamaño reportado de las peticiones HTTP emitidas, incluyendo seguimiento de redirects.
- `header_bytes`: `HEADER_SIZE`, todos los headers recibidos representados en formato HTTP/1. Puede incluir headers de CONNECT. En HTTP/2/3 **no representa bytes exactos en wire** por compresión de headers.
- `redirects`: `REDIRECT_COUNT`.

El agregado `known_bytes` es **contabilidad HTTP parcial**: `request_bytes + header_bytes + download_bytes`, sumando únicamente componentes disponibles. `sent_request_bytes` y `received_http_bytes` separan las dos direcciones. **No se añade upload otra vez**; no se suman headers reconstruidos desde el selector. No debe interpretarse como tráfico exacto facturado por Decodo, ni siquiera como cota inferior universal del wire (headers HTTP/2 pueden tener otra representación). No mide TLS, TCP/IP, framing ni todo el overhead de CONNECT. No hay cálculo monetario.

`known` significa que libcurl expuso todos los contadores y no hubo redirects; **no significa wire/billing exacto**. `incomplete` indica redirect chain o componentes ausentes; `unknown` indica contadores ausentes. NULL nunca se convierte en una afirmación de cero bytes por request. Los totales de componentes conocidos se acompañan de conteos unknown/incomplete.

`successful_attempts` significa transporte con respuesta HTTP <400, **no extracción ni precio exitosos**. HTTP 4xx/5xx cuentan como `http_error`, dentro de `failed_attempts`; se incluye conteo específico de 403. Fallos de transporte y cancelaciones conservan los contadores de la respuesta parcial cuando curl la expone; una cancelación sin respuesta registra unknown. Los redirects son un intento curl con contador de saltos, no eventos inventados por salto.

## Persistencia y cobertura

Nueva migración `0008_add_scraping_traffic`, posterior a 0007; no modifica catálogo ni precios. Dos índices: fecha/scope y lote/fecha. **La migración está escrita, no aplicada a producción.**

Cada evento tiene una transacción SQL propia. Un error del sink se captura con log sanitizado y contador `missing_writes_since_start`, sin hacer fallar precio/lote. La escritura tiene timeout de 5 segundos. No hay cola/Redis ni reintentos del sink: si DB falla, puede perderse evidencia. Los contadores de salud son del proceso, se reinician al reiniciar y no recuperan pérdidas históricas. Ausencia del hook aumenta `unobserved_fetches_since_start` y emite warning sanitizado. Un reporte histórico no puede garantizar que no hubo pérdidas ni reconstruir tráfico anterior a la instrumentación.

Sólo runtime **HTTP** y backend **SQL** tienen medición persistente. Browser/subrecursos no están instrumentados. Backend in-memory devuelve 503 para el reporte. El hook privado queda encapsulado en `infrastructure/scraping/traffic.py`, sin monkeypatch global ni estado compartido entre sesiones concurrentes. Contratos offline verifican Scrapling **0.4.2** y curl_cffi **0.14.0**, y el recorrido real de retries/proxy de la biblioteca instalada. Revisar estos contratos antes de actualizar dependencias.

## API autenticada

`GET /api/v1/metrics/traffic` usa la misma dependencia JWT de las demás rutas v1. Filtros:

- `start`, `end`: timestamps con timezone; ventana `[start,end)`, máximo 366 días. Por defecto últimos 30 días.
- `scope`: enum indicado arriba.
- `batch_id`: UUID, útil para sumar un lote cuyo ID aparece en el log de finalización.
- `relation_count`: opcional, 0..1000000. Sin él se cuenta por SQL el **dataset actual** de relaciones programadas con libro no eliminado y tienda activa/no eliminada. Con él se etiqueta `relation_count_source=requested`.

Devuelve `observed`, `daily`, `monthly` (buckets UTC), `batches` (máximo 100 con `batches_truncated` explícito), `projection`, `process_health`, definición y advertencia de completitud. Agregación SQL (`COUNT/SUM/GROUP BY`), no `list_all` ni carga del historial completo. Los eventos por request permanecen en SQL para auditoría; el endpoint no expone URLs ni detalle sensible.

## Estimaciones

La media se calcula por **operación periódica** (una relación en un lote), sumando sus intentos/retries, sólo si todos los eventos observados de esa operación tienen contadores known. También las operaciones fallidas generan tráfico; 403 no cuenta como intento exitoso. No se proyecta desde operaciones manuales/de catálogo. Sin muestra completa: `status=insufficient_sample`, bytes estimados NULL, no cero inventado.

`bytes_24h = media_por_operación × relaciones × 2`; `bytes_30d = bytes_24h × 30`. El factor se deriva de `DAILY_REVIEW_COUNT`, la política efectiva del calendario, no del campo legacy de horas. Se publica `scheduled_reviews_per_relation_day=2`, cantidad de operaciones de muestra, media, origen del conteo y assumptions: dos revisiones diarias Colombia, tres grupos separados 20 minutos; tráfico manual/de catálogo adicional al nominal; mismo tamaño de respuestas, distribución de retries y catálogo durante el período. Las ventanas pueden cortar operaciones; las pérdidas del sink y sesgo de muestras complete también afectan la estimación. No es una garantía, pronóstico de éxito ni factura.

## Verificación offline

Tests con transportes sustituidos, SQLite desechable y PostgreSQL aislado: payload comprimido distinto de body decoded, retries internos/proxy explícito, HTTP403, cancelación, counters ausentes, redirects, sink fallido, aislamiento de tres workers, transacción independiente del precio, buckets UTC, overflow de lotes, autenticación/validación, no sample y migración additive upgrade/downgrade. No requieren requests a tiendas, proxy real ni lectura de `.env`.

Fuentes primarias: [SIZE_DOWNLOAD_T](https://curl.se/libcurl/c/CURLINFO_SIZE_DOWNLOAD_T.html), [REQUEST_SIZE](https://curl.se/libcurl/c/CURLINFO_REQUEST_SIZE.html), [HEADER_SIZE](https://curl.se/libcurl/c/CURLINFO_HEADER_SIZE.html), [SIZE_UPLOAD_T](https://curl.se/libcurl/c/CURLINFO_SIZE_UPLOAD_T.html). También se inspeccionó código instalado de ambas bibliotecas; Context7 no está disponible en esta sesión.
