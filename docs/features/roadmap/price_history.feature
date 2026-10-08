# language: es
Feature: Historial y comparación de precios
  Como consumidor autenticado de la API v1
  Quiero consultar el historial real de precios y comparar ofertas activas
  Para observar el comportamiento implementado hoy

  Background:
    Given que la API expone precios bajo "/api/v1/pricing"
    And que los endpoints de pricing requieren bearer token

  Scenario: Consultar historial de precios de un libro
    Given que existe un "book_id" válido con registros de precio
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/history"
    Then la API responde 200
    And la respuesta incluye "book_id"
    And la respuesta incluye "records"
    And la respuesta incluye "meta"
    And cada registro expone "price", "state", "checked_at", "domain" y "archived"
    And los registros se ordenan del más reciente al más antiguo

  Scenario: Filtrar historial por fuente, estado y rango de fechas
    Given que existe un "book_id" válido con historial activo y archivado
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/history"
    And uso los query params "source", "state", "start_date" y "end_date"
    Then la API responde 200
    And "source" acepta únicamente "active", "archive" o "all"
    And el filtro de estado compara contra el campo "state"

  Scenario: Paginar el historial
    Given que existe un "book_id" válido con muchos registros
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/history?page=1&limit=50"
    Then la API responde 200
    And la respuesta incluye "meta.total"
    And la respuesta incluye "meta.page"
    And la respuesta incluye "meta.limit"
    And la respuesta incluye "meta.pages"

  Scenario: Comparar precios activos de un libro
    Given que existe un "book_id" válido con relaciones en tiendas activas
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/comparison"
    Then la API responde 200
    And la respuesta incluye "book_id"
    And la respuesta incluye "offers"
    And la respuesta incluye "best_offer"
    And solo aparecen ofertas con estado "activo" y precio actual no nulo
    And las ofertas se ordenan por precio ascendente

  Scenario: Consultar historial de un libro inexistente
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/history" con un UUID inexistente
    Then la API responde 404
    And el código de error es "ENTITY_NOT_FOUND"

  Scenario: Rechazar parámetros de consulta inválidos
    When envío una petición GET autenticada a "/api/v1/pricing/books/{book_id}/history?source=foo&start_date=invalid"
    Then la API responde 422
    And el código de error es "REQUEST_VALIDATION_ERROR"

  Rule: Contrato observable actual
    - El query param "source" tiene valor por defecto "all".
    - El query param "limit" acepta valores entre 1 y 200.
    - La comparación de precios no devuelve tiendas agotadas, desconocidas ni sin precio actual.

  Rule: Fuera de alcance actual
    - No existen endpoints de estadísticas, disponibilidad, exportación, tendencia ni agregaciones por período.
    - El archivado del historial se dispara mediante jobs de retención; esta feature no expone limpieza automática por sí sola.
