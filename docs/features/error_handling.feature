# language: es
Feature: Manejo de Errores y Resiliencia
  Como sistema de rastreo de precios
  Quiero manejar errores de forma robusta y recuperarme de fallos
  Para mantener la estabilidad y confiabilidad del servicio

  Background:
    Given que el sistema está funcionando
    And que hay configuración de manejo de errores activa
    And que el sistema de logging está configurado

  Scenario: Manejo de errores de red durante el scraping
    Given que un libro está programado para scraping
    And que hay problemas de conectividad de red
    When el scraper intenta acceder a la URL del libro
    And la petición falla con un error de red
    Then el sistema debe registrar el error en los logs
    And debe clasificar el error como "Error de Red"
    And debe programar un reintento con backoff exponencial
    And debe continuar con el siguiente libro en la cola

  Scenario: Manejo de errores de timeout
    Given que un libro está programado para scraping
    And que el sitio web responde muy lentamente
    When el scraper hace la petición con timeout configurado
    And la petición excede el tiempo límite
    Then el sistema debe cancelar la petición
    And debe registrar un error de tipo "Timeout" en los logs
    And debe incrementar el timeout para el siguiente intento
    And debe reintentar hasta el máximo configurado

  Scenario: Manejo de errores de selectores CSS
    Given que un libro está programado para scraping
    And que el sitio web ha cambiado su estructura HTML
    When el scraper intenta extraer el precio
    And el selector CSS no encuentra elementos
    Then el sistema NO debe reintentar la petición
    And debe registrar un error de tipo "Selector no encontrado"
    And debe marcar el libro para revisión manual
    And debe notificar al administrador del sistema

  Scenario: Manejo de errores de formato de datos
    Given que un libro está programado para scraping
    And que el sitio devuelve datos en formato inesperado
    When el scraper extrae el precio
    And el precio no puede ser convertido a número
    Then el sistema debe registrar un error de tipo "Formato de datos inválido"
    And debe guardar el valor crudo para análisis
    And debe marcar el libro para revisión manual
    And NO debe actualizar el precio en la base de datos

  Scenario: Manejo de errores de base de datos
    Given que el scraper ha extraído un precio válido
    And que hay problemas de conectividad con la base de datos
    When el sistema intenta guardar el precio
    And la operación de base de datos falla
    Then el sistema debe registrar el error en los logs
    And debe reintentar la operación de base de datos
    And debe mantener el dato en cola hasta que se resuelva
    And debe notificar sobre el problema de persistencia

  Scenario: Manejo de errores de API
    Given que un cliente hace una petición a la API
    And que hay un error interno en el servidor
    When la API procesa la petición
    And ocurre una excepción no manejada
    Then la API debe responder con un error 500
    And debe incluir un mensaje genérico de error
    And NO debe exponer detalles internos del sistema
    And debe registrar el error completo en los logs del servidor

  Scenario: Manejo de errores de validación de entrada
    Given que un cliente envía datos inválidos a la API
    When la API valida los datos de entrada
    And encuentra errores de validación
    Then la API debe responder con un error 400
    And debe incluir detalles específicos de los errores de validación
    And debe usar códigos de error descriptivos
    And debe seguir el formato estándar de errores de la API

  Scenario: Manejo de errores de autenticación
    Given que un endpoint requiere autenticación
    And que el cliente no proporciona credenciales válidas
    When el cliente hace una petición al endpoint
    Then la API debe responder con un error 401
    And debe incluir información sobre cómo autenticarse
    And debe registrar el intento de acceso no autorizado

  Scenario: Manejo de errores de límites de velocidad
    Given que un cliente hace muchas peticiones rápidamente
    And que excede el límite de velocidad configurado
    When el cliente hace una petición adicional
    Then la API debe responder con un error 429
    And debe incluir información sobre cuándo puede volver a intentar
    And debe incluir el límite de velocidad en los headers de respuesta

  Scenario: Recuperación automática de errores temporales
    Given que el sistema experimenta errores temporales
    And que los errores son de tipo recuperable (red, timeout)
    When el sistema detecta que los errores han cesado
    Then debe reanudar automáticamente las operaciones pausadas
    And debe procesar la cola de trabajos pendientes
    And debe notificar sobre la recuperación exitosa

  Scenario: Escalación de errores críticos
    Given que el sistema experimenta errores críticos repetidos
    And que los errores persisten por más de 30 minutos
    When el sistema detecta el patrón de errores críticos
    Then debe escalar el problema a los administradores
    And debe pausar las operaciones automáticas
    And debe activar el modo de mantenimiento si es necesario
    And debe generar un reporte detallado del incidente

  Scenario: Monitoreo de salud del sistema
    Given que el sistema está funcionando
    When se ejecuta el endpoint de health check
    Then debe responder con el estado de todos los componentes
    And debe incluir el estado de la base de datos
    And debe incluir el estado de los servicios de scraping
    And debe incluir métricas de rendimiento básicas
    And debe responder en menos de 5 segundos

  Scenario: Limpieza automática de errores antiguos
    Given que el sistema tiene logs de errores acumulados
    And que algunos errores son muy antiguos
    When se ejecuta la tarea de limpieza de logs
    Then debe eliminar logs de errores más antiguos que 30 días
    And debe mantener un resumen de errores para análisis
    And debe comprimir logs antiguos para ahorrar espacio

  Scenario: Manejo de errores de OpenLibrary API
    Given que el sistema intenta enriquecer un libro con OpenLibrary
    And que la API de OpenLibrary no está disponible
    When el sistema hace la petición a OpenLibrary
    And recibe un error de la API
    Then el sistema debe registrar el error en los logs
    And debe continuar con los datos originales del scraping
    And debe marcar el libro para reintento de enriquecimiento
    And NO debe fallar el proceso de scraping

  Scenario: Manejo de errores de rate limiting de OpenLibrary
    Given que el sistema ha hecho muchas peticiones a OpenLibrary
    And que OpenLibrary responde con error 429 (Too Many Requests)
    When el sistema recibe el error de rate limiting
    Then debe pausar las peticiones a OpenLibrary
    And debe esperar el tiempo indicado en el header Retry-After
    And debe reanudar las peticiones después del tiempo de espera
    And debe registrar el evento en los logs

  Scenario: Manejo de errores de datos corruptos
    Given que el sistema recibe datos corruptos de una tienda
    When el scraper procesa los datos
    And detecta que los datos están corruptos o incompletos
    Then el sistema debe registrar un error de tipo "Datos corruptos"
    And debe intentar extraer la información válida disponible
    And debe marcar los campos corruptos como "desconocido"
    And debe continuar con el procesamiento normal