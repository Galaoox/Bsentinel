# language: es
Feature: Manejo de errores y resiliencia observable
  Como consumidor de la API y operador del sistema
  Quiero un contrato de errores consistente con la implementación actual
  Para diagnosticar fallas sin asumir capacidades inexistentes

  Background:
    Given que la API agrega un request id por petición
    And que los errores se serializan en un contrato JSON uniforme

  Scenario: Recibir el contrato estándar de error
    When una petición falla en la API
    Then la respuesta incluye "error"
    And la respuesta incluye "request_id"
    And "error" expone "code", "message" y "details"

  Scenario: Obtener request id también en respuestas exitosas
    When hago una petición al servicio
    Then la respuesta HTTP incluye el header "X-Request-ID"

  Scenario: Recibir errores de negocio mapeados por tipo
    When la aplicación lanza una excepción de negocio conocida
    Then la API mapea 404 a "ENTITY_NOT_FOUND"
    And mapea 409 a "ENTITY_ALREADY_EXISTS"
    And mapea 400 a "UNSUPPORTED_STORE", "VALIDATION_ERROR" o "SCRAPING_ERROR" según corresponda
    And mapea 401 a códigos de autenticación como "AUTH_INVALID_TOKEN" o "AUTH_REFRESH_REVOKED"
    And mapea 403 a "AUTH_FORBIDDEN"

  Scenario: Manejar errores de validación de request
    When FastAPI rechaza body, path o query params
    Then la API responde 422
    And el código de error es "REQUEST_VALIDATION_ERROR"
    And los detalles incluyen la colección "errors"

  Scenario: Manejar excepciones HTTP explícitas
    When un componente lanza un HTTPException con "code" y "message"
    Then la API conserva ese status code
    And responde usando el mismo contrato estándar de error

  Scenario: Manejar errores inesperados del servidor
    When ocurre una excepción no controlada
    Then la API responde 500
    And el código de error es "INTERNAL_SERVER_ERROR"
    And el mensaje expuesto es "Internal server error"
    And no expone detalles internos en la respuesta

  Scenario: Registrar errores de scraping con contexto adicional
    When ocurre un ScrapingError
    Then la API responde 400 con código "SCRAPING_ERROR"
    And el servidor registra request_id, método, path, reason y diagnostics del scraping

  Scenario: Responder sin credenciales en endpoints protegidos
    When accedo a un endpoint protegido sin bearer token
    Then la API responde 401
    And el código de error es "AUTH_INVALID_TOKEN"

  Rule: Contrato observable actual
    - El health check devuelve 200 con claves "status", "service", "version", "environment", "db", "scraping" y "openlibrary".
    - La API raíz devuelve un payload básico con "message", "version" y "docs".
    - Los errores de autenticación se devuelven con el contrato JSON de la aplicación, no con el detail crudo de FastAPI.

  Rule: Fuera de alcance actual
    - No existe rate limiting contractual ni respuestas 429 implementadas por la API.
    - No existe notificación automática a administradores, modo mantenimiento ni recuperación automática orquestada de errores temporales.
    - No hay promesa contractual de headers "WWW-Authenticate" preservados por el handler final de errores.
