Feature: API v1 MVP endpoints
  Como consumidor interno del MVP
  Quiero usar la API v1 real para gestionar libros, consultar precios y ejecutar archivado
  Para validar el flujo funcional implementado actualmente

  Background:
    Given que la API expone rutas bajo "/api/v1"
    And que los endpoints de "system", "catalog", "pricing" y "retention" requieren bearer token

  Scenario: Health check del servicio
    When envío una petición GET a "/health"
    Then recibo estado 200
    And la respuesta incluye "status": "healthy"
    And la respuesta incluye "service"
    And la respuesta incluye "version"

  Scenario: Información de la API v1
    When envío una petición GET autenticada a "/api/v1/system/info"
    Then recibo estado 200
    And la respuesta incluye "version"
    And la respuesta incluye "supported_sites"
    And la respuesta incluye "updated_at"

  Scenario: Crear libro desde URL soportada
    When envío una petición POST autenticada a "/api/v1/catalog/books" con body JSON válido
    Then recibo estado 201
    And la respuesta incluye "book_id"
    And la respuesta incluye "relation_id"
    And la respuesta incluye "isbn"
    And la respuesta incluye "site"
    And la respuesta incluye "status"

  Scenario: Listar libros
    Given que existe al menos un libro registrado
    When envío una petición GET autenticada a "/api/v1/catalog/books"
    Then recibo estado 200
    And la respuesta incluye "items"
    And la respuesta incluye "meta"

  Scenario: Obtener detalle de libro
    Given que existe un "book_id" válido
    When envío una petición GET autenticada a "/api/v1/catalog/books/{book_id}"
    Then recibo estado 200

  Scenario: Soft delete y restore de libro
    Given que existe un "book_id" válido
    When envío una petición DELETE autenticada a "/api/v1/catalog/books/{book_id}"
    Then recibo estado 204
    When envío una petición POST autenticada a "/api/v1/catalog/books/{book_id}/restore"
    Then recibo estado 200

  Scenario: Consultar historial de precios
    Given que existe un "book_id" válido con datos en historial
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/history"
    Then recibo estado 200
    And la respuesta incluye "book_id"
    And la respuesta incluye "records"
    And la respuesta incluye "meta"

  Scenario: Consultar comparación de precios
    Given que existe un "book_id" válido
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/comparison"
    Then recibo estado 200
    And la respuesta incluye "book_id"
    And la respuesta incluye "offers"

  Scenario: Crear y consultar job de archivado
    When envío una petición POST autenticada a "/api/v1/retention/jobs/archive" con body JSON válido
    Then recibo estado 202
    And la respuesta incluye "job_id"
    When envío una petición GET autenticada a "/api/v1/retention/jobs/archive/{job_id}"
    Then recibo estado 200

  Rule: Contrato actual del MVP
    - La API v1 requiere autenticación JWT en los módulos "system", "catalog", "pricing" y "retention".
    - La API activa también expone endpoints de autenticación en "/api/v1/auth".
    - Los endpoints administrativos de tiendas existen bajo "/api/v1/stores" y requieren permisos de admin.
    - La persistencia depende de la configuración del entorno y soporta backend SQL además de in-memory.
