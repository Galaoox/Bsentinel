# language: es
Feature: Historial de Precios
  Como usuario del sistema
  Quiero poder consultar el historial de precios de los libros
  Para analizar tendencias y tomar decisiones de compra

  Background:
    Given que el sistema está funcionando
    And que hay libros con historial de precios en el sistema
    And que los libros están disponibles en múltiples tiendas

  Scenario: Consultar historial de precios de un libro en una tienda específica
    Given que un libro con id "12345" tiene historial de precios en Buscalibre
    When envío una petición GET a "/api/books/12345/history?tienda=buscalibre.com.co"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir todos los registros de precios históricos de esa tienda
    And cada registro debe incluir el precio, estado y fecha
    And los registros deben estar ordenados por fecha (más reciente primero)

  Scenario: Consultar historial de precios de un libro en todas las tiendas
    Given que un libro con id "12345" tiene historial en múltiples tiendas
    When envío una petición GET a "/api/books/12345/history"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir el historial de todas las tiendas
    And debe agrupar los resultados por tienda
    And debe incluir el nombre de cada tienda

  Scenario: Consultar historial con filtro de fechas
    Given que un libro tiene historial de precios desde hace 6 meses
    When envío una petición GET a "/api/books/12345/history?start_date=2024-01-01&end_date=2024-03-31"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir solo los precios del rango de fechas especificado
    And debe incluir metadatos sobre el total de registros encontrados

  Scenario: Consultar historial con paginación
    Given que un libro tiene más de 100 registros de precios
    When envío una petición GET a "/api/books/12345/history?page=1&limit=50"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir máximo 50 registros
    And debe incluir metadatos de paginación (total, página actual, total de páginas)

  Scenario: Obtener estadísticas de precios de un libro
    Given que un libro tiene historial de precios
    When envío una petición GET a "/api/books/12345/stats"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir el precio mínimo
    And debe incluir el precio máximo
    And debe incluir el precio promedio
    And debe incluir el número total de registros
    And debe incluir la fecha del primer y último registro
    And debe incluir estadísticas por tienda

  Scenario: Consultar el precio más bajo de un libro entre todas las tiendas
    Given que un libro existe en múltiples tiendas con precios diferentes
    When envío una petición GET a "/api/books/12345/price-comparison"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe mostrar el precio más bajo disponible (estado "activo")
    And debe indicar en qué tienda está ese precio
    And debe mostrar todos los precios disponibles ordenados de menor a mayor
    And debe excluir tiendas con estado "agotado" o "inactivo"

  Scenario: Consultar disponibilidad de un libro en todas las tiendas
    Given que un libro está disponible en algunas tiendas pero no en otras
    When envío una petición GET a "/api/books/12345/availability"
    Then la API debe responder con un estado de éxito (200 OK)
    And debe mostrar en qué tiendas está disponible (estado "activo")
    And debe mostrar en qué tiendas no está disponible (estado "agotado", "inactivo", etc.)
    And debe mostrar los precios solo de las tiendas donde está disponible
    And debe mostrar el estado específico de cada tienda

  Scenario: Consultar historial de un libro inexistente
    Given que un libro con id "99999" NO existe
    When envío una petición GET a "/api/books/99999/history"
    Then la API debe responder con un error (404 Not Found)
    And el mensaje de error debe ser "Libro no encontrado"

  Scenario: Consultar historial con parámetros inválidos
    Given que un libro existe en el sistema
    When envío una petición GET a "/api/books/12345/history?start_date=invalid-date"
    Then la API debe responder con un error (400 Bad Request)
    And el mensaje de error debe indicar que el formato de fecha es inválido

  Scenario: Exportar historial de precios a CSV
    Given que un libro tiene historial de precios
    When envío una petición GET a "/api/books/12345/history/export?format=csv"
    Then la API debe responder con un estado de éxito (200 OK)
    And el contenido debe ser un archivo CSV válido
    And el Content-Type debe ser "text/csv"
    And debe incluir headers apropiados para descarga
    And debe incluir columnas para precio, estado, fecha y tienda

  Scenario: Exportar historial de precios a JSON
    Given que un libro tiene historial de precios
    When envío una petición GET a "/api/books/12345/history/export?format=json"
    Then la API debe responder con un estado de éxito (200 OK)
    And el contenido debe ser un archivo JSON válido
    And el Content-Type debe ser "application/json"
    And debe incluir headers apropiados para descarga

  Scenario: Consultar tendencia de precios
    Given que un libro tiene historial de precios con tendencia
    When envío una petición GET a "/api/books/12345/trend?period=30d"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir la tendencia de precios (subiendo/bajando/estable)
    And debe incluir el porcentaje de cambio
    And debe incluir datos agregados por período
    And debe incluir la tendencia por tienda

  Scenario: Consultar historial con agregaciones por período
    Given que un libro tiene historial de precios detallado
    When envío una petición GET a "/api/books/12345/history?aggregate=daily"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir precios agregados por día
    And cada día debe mostrar el precio mínimo, máximo y promedio
    And debe incluir el número de registros por día
    And debe incluir agregaciones por tienda

  Scenario: Consultar historial de precios con filtro por estado
    Given que un libro tiene historial con diferentes estados
    When envío una petición GET a "/api/books/12345/history?estado=activo"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir solo los registros con estado "activo"
    And debe excluir registros con otros estados

  Scenario: Consultar historial de precios con filtro por tienda
    Given que un libro tiene historial en múltiples tiendas
    When envío una petición GET a "/api/books/12345/history?tienda=buscalibre.com.co"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir solo el historial de Buscalibre
    And debe excluir el historial de otras tiendas

  Scenario: Limpiar historial antiguo automáticamente
    Given que un libro tiene registros de precios muy antiguos (más de 2 años)
    When el sistema ejecuta la tarea de limpieza de historial
    Then debe archivar los registros más antiguos que el límite configurado
    And debe mantener al menos los últimos 1000 registros
    And debe registrar la limpieza en los logs
    And debe crear un backup antes de la limpieza