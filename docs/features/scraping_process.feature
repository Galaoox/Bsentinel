# language: es
Feature: Proceso de Scraping de Precios
  Como sistema de rastreo de precios
  Quiero poder extraer y actualizar precios de libros automáticamente
  Para mantener información actualizada de los precios

  Background:
    Given que el sistema de scraping está configurado exclusivamente para sitios con server-side rendering
    And que hay libros registrados para rastrear
    And que la configuración de tiendas está disponible
    And que el sistema de rotación de proxies está activo

  Scenario: Un scraper actualiza el precio de un libro en una tienda específica
    Given que un libro existe en el sistema y está disponible en Buscalibre
    And que la configuración para Buscalibre especifica los selectores CSS correctos
    And que el libro tiene la URL "https://www.buscalibre.com.co/libro-exemplo"
    When la tarea de scraping para esa relación libro-tienda se ejecuta
    Then el sistema debe hacer una petición a la URL específica del libro en Buscalibre
    And debe usar un User-Agent aleatorio para la petición
    And debe usar un Proxy aleatorio para la petición
    And debe extraer el nuevo precio usando el selector configurado
    And debe actualizar los campos "precio_actual", "estado" y "last_checked" en "libro_tienda"
    And debe crear un nuevo registro en "historial_precios" vinculado a la relación libro-tienda
    And el sistema debe registrar el éxito en los logs

  Scenario: El scraper detecta que un libro ya no está disponible en una tienda
    Given que un libro existe en el sistema y está marcado como "activo" en Buscalibre
    When la tarea de scraping se ejecuta
    And la página indica que el libro no está disponible
    Then el sistema debe marcar "estado" como "agotado" en "libro_tienda"
    And debe registrar un precio de 0 en "historial_precios" con estado "agotado"
    And debe actualizar "last_checked" en "libro_tienda"

  Scenario: El scraper falla porque la estructura de la página cambió
    Given que un libro existe en el sistema en una tienda específica
    When la tarea de scraping se ejecuta
    And el selector CSS para el precio no encuentra ningún elemento en la página
    Then el sistema NO debe actualizar el precio en "libro_tienda"
    And debe marcar "estado" como "desconocido" en "libro_tienda"
    And debe registrar un error de tipo "Selector no encontrado" en los logs
    And la tarea no debe ser reintentada por este tipo de error

  Scenario: El scraper falla por error de red
    Given que un libro existe en el sistema
    And que hay problemas de conectividad de red
    When la tarea de scraping se ejecuta
    And la petición HTTP falla con un error de red
    Then el sistema debe registrar el error en los logs
    And la tarea debe ser reintentada hasta 2 veces más
    And si todos los reintentos fallan, debe marcar la tarea como fallida

  Scenario: El scraper encuentra un precio inválido
    Given que un libro existe en el sistema
    And que la página devuelve un precio con formato inválido
    When la tarea de scraping se ejecuta
    And el sistema extrae un precio que no es numérico
    Then el sistema NO debe actualizar el precio en "libro_tienda"
    And debe marcar "estado" como "desconocido" en "libro_tienda"
    And debe registrar un error de tipo "Precio inválido" en los logs
    And la tarea no debe ser reintentada por este tipo de error

  Scenario: El scraper es bloqueado por el sitio web
    Given que un libro existe en el sistema
    And que el sitio web ha bloqueado nuestras peticiones
    When la tarea de scraping se ejecuta
    And la petición recibe un código de respuesta 403 o 429
    Then el sistema debe cambiar automáticamente a un proxy diferente
    And debe cambiar el User-Agent
    And debe reintentar la petición con las nuevas credenciales

  Scenario: El scraper procesa múltiples libros en lote
    Given que hay 10 libros registrados para rastrear
    And que todos los libros son de tiendas soportadas
    When el planificador ejecuta el proceso de scraping en lote
    Then el sistema debe procesar todos los libros de forma asíncrona
    And debe respetar los límites de velocidad configurados
    And debe actualizar los precios de todos los libros exitosos
    And debe registrar los errores de los libros fallidos

  Scenario: El scraper maneja timeouts correctamente
    Given que un libro existe en el sistema
    And que el sitio web responde muy lentamente
    When la tarea de scraping se ejecuta
    And la petición excede el timeout configurado
    Then el sistema debe cancelar la petición
    And debe registrar un error de tipo "Timeout" en los logs
    And debe reintentar la petición con un timeout mayor

  Scenario: El scraper valida la estructura de datos extraída
    Given que un libro existe en el sistema
    And que la página devuelve datos incompletos
    When la tarea de scraping se ejecuta
    And el sistema extrae información parcial del libro
    Then el sistema debe validar que los datos requeridos estén presentes
    And debe actualizar solo los campos que tengan datos válidos
    And debe registrar una advertencia sobre datos incompletos

  Scenario: Scraping de múltiples tiendas para el mismo libro
    Given que un libro existe en Buscalibre y Librería Nacional
    When el planificador ejecuta el scraping para este libro
    Then debe procesar ambas tiendas de forma independiente
    And debe actualizar "precio_actual" y "estado" en cada relación libro-tienda por separado
    And debe crear registros separados en "historial_precios" para cada tienda

  Scenario: El scraper respeta los límites de velocidad por tienda
    Given que hay múltiples libros de la misma tienda en la cola
    When el sistema procesa la cola de scraping
    Then debe respetar el delay configurado entre peticiones a la misma tienda
    And debe alternar entre diferentes tiendas para evitar sobrecarga
    And debe registrar el tiempo de espera en los logs

  Scenario: El scraper maneja cambios de estructura de página gradualmente
    Given que un libro existe en el sistema
    And que la tienda ha cambiado parcialmente su estructura
    When la tarea de scraping se ejecuta
    And algunos selectores funcionan pero otros no
    Then el sistema debe actualizar los campos que se pueden extraer
    And debe marcar como "desconocido" los campos que no se pueden extraer
    And debe registrar una advertencia sobre selectores parcialmente rotos
    And debe sugerir revisión manual de la configuración