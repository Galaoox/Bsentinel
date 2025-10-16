# language: es
Feature: Endpoints de la API
  Como desarrollador o usuario de la API
  Quiero tener acceso a endpoints bien documentados y consistentes
  Para integrar y usar el sistema de rastreo de precios

  Background:
    Given que la API está funcionando
    And que la documentación Swagger está disponible
    And que el sistema de autenticación está configurado

  Scenario: Acceder a la documentación de la API
    Given que la API está funcionando
    When visito la URL "/docs"
    Then debo ver la documentación interactiva de Swagger
    And debo poder probar todos los endpoints
    And debo ver ejemplos de peticiones y respuestas
    And debo ver códigos de estado y esquemas de datos

  Scenario: Verificar el estado de salud del sistema
    Given que el sistema está funcionando
    When envío una petición GET a "/health"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir el estado de la base de datos
    And debe incluir el estado de los servicios de scraping
    And debe incluir el estado de OpenLibrary API
    And debe incluir la versión de la API
    And debe incluir métricas básicas del sistema

  Scenario: Obtener información de la API
    Given que la API está funcionando
    When envío una petición GET a "/api/info"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir la versión de la API
    And debe incluir la fecha de última actualización
    And debe incluir las tiendas web soportadas
    And debe incluir estadísticas básicas del sistema

  Scenario: Autenticación con token válido
    Given que tengo credenciales válidas
    When envío una petición POST a "/api/auth/login" con mis credenciales
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir un token de acceso
    And debe incluir el tipo de token (Bearer)
    And debe incluir el tiempo de expiración del token

  Scenario: Autenticación con credenciales inválidas
    Given que tengo credenciales inválidas
    When envío una petición POST a "/api/auth/login" con credenciales incorrectas
    Then la API debe responder con un error (401 Unauthorized)
    And el mensaje de error debe ser "Credenciales inválidas"
    And NO debe incluir un token de acceso

  Scenario: Acceso a endpoint protegido sin autenticación
    Given que no tengo un token de autenticación
    When envío una petición GET a "/api/books"
    Then la API debe responder con un error (401 Unauthorized)
    And el mensaje de error debe ser "Token de autenticación requerido"
    And debe incluir información sobre cómo obtener un token

  Scenario: Acceso a endpoint protegido con token expirado
    Given que tengo un token de autenticación expirado
    When envío una petición GET a "/api/books" con el token expirado
    Then la API debe responder con un error (401 Unauthorized)
    And el mensaje de error debe ser "Token expirado"
    And debe incluir información sobre cómo renovar el token

  Scenario: Renovación de token de acceso
    Given que tengo un token de acceso válido
    When envío una petición POST a "/api/auth/refresh" con mi token actual
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir un nuevo token de acceso
    And el nuevo token debe tener un tiempo de expiración actualizado

  Scenario: Cierre de sesión
    Given que tengo una sesión activa
    When envío una petición POST a "/api/auth/logout"
    Then la API debe responder con un estado de éxito (200 OK)
    And el token debe ser invalidado
    And no debo poder usar el token para futuras peticiones

  Scenario: Manejo de peticiones con formato incorrecto
    Given que tengo un token de autenticación válido
    When envío una petición POST a "/api/books" con JSON malformado
    Then la API debe responder con un error (400 Bad Request)
    And el mensaje de error debe ser "Formato JSON inválido"
    And debe incluir detalles sobre el error de parsing

  Scenario: Manejo de peticiones con Content-Type incorrecto
    Given que tengo un token de autenticación válido
    When envío una petición POST a "/api/books" con Content-Type "text/plain"
    Then la API debe responder con un error (415 Unsupported Media Type)
    And el mensaje de error debe ser "Content-Type no soportado"
    And debe indicar que se requiere "application/json"

  Scenario: Manejo de peticiones con parámetros de consulta inválidos
    Given que tengo un token de autenticación válido
    When envío una petición GET a "/api/books?page=invalid&limit=abc"
    Then la API debe responder con un error (400 Bad Request)
    And el mensaje de error debe ser "Parámetros de consulta inválidos"
    And debe especificar qué parámetros son inválidos

  Scenario: Manejo de peticiones a endpoints inexistentes
    Given que tengo un token de autenticación válido
    When envío una petición GET a "/api/endpoint-inexistente"
    Then la API debe responder con un error (404 Not Found)
    And el mensaje de error debe ser "Endpoint no encontrado"
    And debe incluir sugerencias de endpoints similares si están disponibles

  Scenario: Manejo de peticiones con métodos HTTP no permitidos
    Given que tengo un token de autenticación válido
    When envío una petición DELETE a "/api/books" (endpoint que no acepta DELETE)
    Then la API debe responder con un error (405 Method Not Allowed)
    And el mensaje de error debe ser "Método no permitido"
    And debe incluir los métodos HTTP permitidos para ese endpoint

  Scenario: Rate limiting en endpoints públicos
    Given que no tengo autenticación
    When hago múltiples peticiones rápidas a "/health"
    And excedo el límite de velocidad configurado
    Then la API debe responder con un error (429 Too Many Requests)
    And debe incluir información sobre cuándo puedo volver a intentar
    And debe incluir el límite de velocidad en los headers

  Scenario: Rate limiting en endpoints protegidos
    Given que tengo un token de autenticación válido
    When hago múltiples peticiones rápidas a "/api/books"
    And excedo el límite de velocidad configurado
    Then la API debe responder con un error (429 Too Many Requests)
    And debe incluir información sobre cuándo puedo volver a intentar
    And debe incluir el límite de velocidad en los headers

  Scenario: Versionado de la API
    Given que la API soporta múltiples versiones
    When envío una petición GET a "/api/v1/books"
    Then la API debe responder con la versión v1 de los datos
    And debe incluir el número de versión en los headers de respuesta
    And debe mantener compatibilidad con versiones anteriores

  Scenario: CORS para peticiones desde el navegador
    Given que estoy haciendo una petición desde un navegador web
    When envío una petición OPTIONS a cualquier endpoint
    Then la API debe responder con los headers CORS apropiados
    And debe incluir "Access-Control-Allow-Origin"
    And debe incluir "Access-Control-Allow-Methods"
    And debe incluir "Access-Control-Allow-Headers"

  Scenario: Endpoint de estadísticas del sistema
    Given que tengo un token de autenticación válido
    When envío una petición GET a "/api/stats"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir el número total de libros
    And debe incluir el número total de tiendas
    And debe incluir el número de libros activos vs inactivos
    And debe incluir estadísticas de scraping reciente

  Scenario: Endpoint de configuración del sistema
    Given que tengo un token de administrador válido
    When envío una petición GET a "/api/config"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir la configuración de scraping
    And debe incluir los límites de velocidad configurados
    And debe incluir la configuración de OpenLibrary
    And NO debe incluir información sensible como contraseñas