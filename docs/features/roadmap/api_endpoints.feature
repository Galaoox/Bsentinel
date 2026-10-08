# language: es
Feature: Endpoints de la API
  Como desarrollador o usuario de la API
  Quiero tener acceso a endpoints versionados y consistentes con la implementación actual
  Para integrar y usar el sistema de rastreo de precios sin ambigüedad contractual

  Background:
    Given que la API está funcionando bajo el prefijo "/api/v1"
    And que la documentación OpenAPI está disponible
    And que el sistema de autenticación JWT está configurado

  Scenario: Acceder a la documentación de la API
    Given que la API está funcionando
    When visito la URL "/docs"
    Then debo ver la documentación interactiva de Swagger
    And debo poder inspeccionar los endpoints disponibles
    And debo ver códigos de estado y esquemas de datos expuestos por FastAPI

  Scenario: Verificar el estado de salud del sistema
    Given que el sistema está funcionando
    When envío una petición GET a "/health"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir el estado de la base de datos
    And debe incluir el estado de los servicios de scraping
    And debe incluir el estado de OpenLibrary API
    And debe incluir la versión de la API

  Scenario: Obtener información de la API
    Given que la API está funcionando
    And que tengo un token de autenticación válido
    When envío una petición GET a "/api/v1/system/info"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir la versión de la API
    And debe incluir la fecha de última actualización
    And debe incluir las tiendas web soportadas

  Scenario: Autenticación con token válido
    Given que tengo credenciales válidas
    When envío una petición POST a "/api/v1/auth/login" con credenciales form-encoded
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir un token de acceso
    And debe incluir un refresh token
    And debe incluir el tipo de token (bearer)
    And debe incluir el tiempo de expiración del token

  Scenario: Autenticación con credenciales inválidas
    Given que tengo credenciales inválidas
    When envío una petición POST a "/api/v1/auth/login" con credenciales incorrectas
    Then la API debe responder con un error (401 Unauthorized)
    And el mensaje de error debe indicar credenciales inválidas
    And NO debe incluir un token de acceso

  Scenario: Acceso a endpoint protegido sin autenticación
    Given que no tengo un token de autenticación
    When envío una petición GET a "/api/v1/catalog/books"
    Then la API debe responder con un error (401 Unauthorized)
    And el endpoint no debe devolver datos de catálogo

  Scenario: Renovación de token de acceso
    Given que tengo un refresh token válido
    When envío una petición POST a "/api/v1/auth/refresh" con body JSON que contiene "refresh_token"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir un nuevo token de acceso
    And la respuesta debe incluir un nuevo refresh token

  Scenario: Cierre de sesión
    Given que tengo una sesión activa
    When envío una petición POST a "/api/v1/auth/logout" con body JSON que contiene "refresh_token"
    Then la API debe responder con estado 204 No Content

  Scenario: Manejo de peticiones con formato incorrecto
    Given que tengo un token de autenticación válido
    When envío una petición POST a "/api/v1/catalog/books" con payload inválido
    Then la API debe responder con un error de validación
    And la respuesta debe seguir el contrato de error expuesto por FastAPI y la aplicación

  Scenario: Manejo de peticiones con parámetros de consulta inválidos
    Given que tengo un token de autenticación válido
    When envío una petición GET a "/api/v1/catalog/books?page=invalid&limit=abc"
    Then la API debe responder con un error de validación

  Scenario: Manejo de peticiones a endpoints inexistentes
    Given que tengo un token de autenticación válido
    When envío una petición GET a "/api/endpoint-inexistente"
    Then la API debe responder con un error (404 Not Found)
    And la respuesta debe seguir el contrato de error activo

  Scenario: Manejo de peticiones con métodos HTTP no permitidos
    Given que tengo un token de autenticación válido
    When envío una petición DELETE a "/api/v1/catalog/books" sin identificador
    Then la API debe responder con un error (405 Method Not Allowed)

  Scenario: Versionado de la API
    Given que la API expone rutas bajo "/api/v1"
    When envío una petición GET autenticada a "/api/v1/catalog/books"
    Then la API debe responder usando el contrato actual de la versión v1

  Scenario: CORS para peticiones desde el navegador
    Given que estoy haciendo una petición desde un navegador web
    When envío una petición OPTIONS a cualquier endpoint
    Then la API debe responder con los headers CORS apropiados
    And debe incluir "Access-Control-Allow-Origin"
    And debe incluir "Access-Control-Allow-Methods"
    And debe incluir "Access-Control-Allow-Headers"

  Rule: Fuera de alcance actual de esta feature
    - No hay rate limiting contractual documentado en la API activa.
    - No existen endpoints públicos de estadísticas del sistema ni de configuración global en "/api/stats" o "/api/config".
    - Los mensajes exactos de errores de validación dependen del contrato real de FastAPI y de los handlers de la aplicación.
