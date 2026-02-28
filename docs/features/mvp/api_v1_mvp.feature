Feature: API v1 MVP endpoints
  Como consumidor interno del MVP
  Quiero usar endpoints versionados para gestionar libros y consultar historial
  Para validar el flujo funcional implementado actualmente

  Scenario: Health check del servicio
    When envío una petición GET a "/health"
    Then recibo estado 200
    And la respuesta incluye "status": "healthy"

  Scenario: Información de la API v1
    When envío una petición GET a "/api/v1/info"
    Then recibo estado 200
    And la respuesta incluye "version": "v1"

  Scenario: Crear libro desde URL soportada
    When envío una petición POST a "/api/v1/books" con URL de Buscalibre CO
    Then recibo estado 201
    And la respuesta incluye "book_id"

  Scenario: Listar libros
    Given que existe al menos un libro registrado
    When envío una petición GET a "/api/v1/books"
    Then recibo estado 200
    And la respuesta incluye "items"

  Scenario: Obtener detalle de libro
    Given que existe un "book_id" válido
    When envío una petición GET a "/api/v1/books/{book_id}"
    Then recibo estado 200

  Scenario: Soft delete y restore de libro
    Given que existe un "book_id" válido
    When envío una petición DELETE a "/api/v1/books/{book_id}"
    Then recibo estado 204
    When envío una petición POST a "/api/v1/books/{book_id}/restore"
    Then recibo estado 200

  Scenario: Consultar historial de precios
    Given que existe un "book_id" válido con datos en historial
    When envío una petición GET a "/api/v1/books/{book_id}/history"
    Then recibo estado 200

  Scenario: Consultar comparación de precios
    Given que existe un "book_id" válido
    When envío una petición GET a "/api/v1/books/{book_id}/price-comparison"
    Then recibo estado 200

  Scenario: Crear y consultar job de archivado
    When envío una petición POST a "/api/v1/retention/archive-jobs" con target válido
    Then recibo estado 202
    And la respuesta incluye "id"
    When envío una petición GET a "/api/v1/retention/archive-jobs/{job_id}"
    Then recibo estado 200

  Rule: Fuera de alcance MVP
    - No hay autenticación/autorización implementada.
    - No hay endpoints de tiendas/admin en la API activa.
    - No hay persistencia durable (actualmente in-memory).
