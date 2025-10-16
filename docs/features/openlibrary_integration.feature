# language: es
Feature: Integración con OpenLibrary API
  Como sistema de enriquecimiento de datos
  Quiero poder obtener metadatos y categorías de libros desde OpenLibrary
  Para enriquecer la información de los libros y mantener categorización consistente

  Background:
    Given que el sistema está funcionando
    And que OpenLibrary API está disponible
    And que el sistema de cache está configurado
    And que el rate limiting está configurado para OpenLibrary

  Scenario: Enriquecimiento automático con OpenLibrary
    Given que un libro se ha añadido al sistema con ISBN válido "9781234567890"
    When el sistema procesa el libro para enriquecimiento
    Then el sistema debe consultar la API de OpenLibrary usando el ISBN
    And debe hacer una petición GET a "https://openlibrary.org/api/books?bibkeys=ISBN:9781234567890&format=json&jscmd=data"
    And debe actualizar los metadatos del libro con información de OpenLibrary
    And debe obtener y asignar las categorías del libro desde OpenLibrary
    And debe actualizar campos como publisher, publication_year, language, pages, description
    And debe registrar la fuente de enriquecimiento en los logs

  Scenario: Enriquecimiento fallido por ISBN no encontrado en OpenLibrary
    Given que un libro se ha añadido al sistema con ISBN válido "9789999999999"
    When el sistema intenta enriquecer con OpenLibrary
    And el ISBN no existe en OpenLibrary
    Then el sistema debe mantener los datos originales del libro
    And debe registrar un warning en los logs indicando que no se pudo enriquecer
    And debe continuar con el procesamiento normal del libro
    And NO debe fallar el proceso de scraping

  Scenario: Enriquecimiento con datos parciales de OpenLibrary
    Given que un libro se ha añadido al sistema con ISBN válido
    When el sistema consulta OpenLibrary
    And OpenLibrary devuelve datos parciales (solo título y autor)
    Then el sistema debe actualizar solo los campos disponibles
    And debe mantener los datos originales para campos no disponibles
    And debe registrar una advertencia sobre datos incompletos
    And debe continuar con el procesamiento normal

  Scenario: Actualización de categorías desde OpenLibrary
    Given que un libro existe en el sistema con categorías de OpenLibrary
    When el sistema ejecuta la tarea de actualización de categorías
    And OpenLibrary ha actualizado la información del libro
    Then el sistema debe consultar nuevamente la API de OpenLibrary
    And debe comparar las categorías actuales con las nuevas
    And debe actualizar las categorías si han cambiado
    And debe registrar los cambios en los logs

  Scenario: Manejo de rate limiting de OpenLibrary
    Given que el sistema ha hecho muchas peticiones a OpenLibrary
    And que OpenLibrary responde con error 429 (Too Many Requests)
    When el sistema recibe el error de rate limiting
    Then debe pausar las peticiones a OpenLibrary
    And debe esperar el tiempo indicado en el header Retry-After
    And debe reanudar las peticiones después del tiempo de espera
    And debe registrar el evento en los logs

  Scenario: Cache de respuestas de OpenLibrary
    Given que un libro con ISBN "9781234567890" ya fue consultado en OpenLibrary
    When el sistema necesita enriquecer otro libro con el mismo ISBN
    Then debe usar la respuesta cacheada de OpenLibrary
    And NO debe hacer una nueva petición a la API
    And debe registrar el uso del cache en los logs

  Scenario: Expiración del cache de OpenLibrary
    Given que un libro fue consultado en OpenLibrary hace más de 30 días
    When el sistema necesita enriquecer el mismo libro
    Then debe hacer una nueva petición a OpenLibrary
    And debe actualizar el cache con la nueva respuesta
    And debe registrar la actualización del cache en los logs

  Scenario: Enriquecimiento de libro sin ISBN
    Given que un libro se ha añadido al sistema sin ISBN
    When el sistema intenta enriquecer con OpenLibrary
    Then el sistema debe intentar buscar por título y autor
    And debe usar el endpoint de búsqueda de OpenLibrary
    And debe manejar múltiples resultados posibles
    And debe seleccionar el resultado más probable
    And debe registrar el proceso de búsqueda en los logs

  Scenario: Manejo de errores de conectividad con OpenLibrary
    Given que OpenLibrary API no está disponible temporalmente
    When el sistema intenta enriquecer un libro
    And la petición falla por problemas de conectividad
    Then el sistema debe registrar el error en los logs
    And debe continuar con los datos originales del scraping
    And debe marcar el libro para reintento de enriquecimiento
    And NO debe fallar el proceso de scraping

  Scenario: Validación de datos de OpenLibrary
    Given que OpenLibrary devuelve datos para un libro
    When el sistema procesa la respuesta
    Then debe validar que los datos sean consistentes
    And debe verificar que el ISBN coincida
    And debe validar que el título sea similar al original
    And debe rechazar datos que no pasen la validación
    And debe registrar los datos rechazados en los logs

  Scenario: Enriquecimiento en lote de múltiples libros
    Given que hay 10 libros en la cola de enriquecimiento
    When el sistema ejecuta el proceso de enriquecimiento en lote
    Then debe procesar los libros respetando el rate limiting
    And debe usar el cache cuando sea posible
    And debe manejar errores individuales sin afectar el lote
    And debe registrar el progreso del lote en los logs

  Scenario: Obtención de imagen de portada desde OpenLibrary
    Given que un libro se está enriqueciendo con OpenLibrary
    And que OpenLibrary tiene una imagen de portada disponible
    When el sistema procesa la respuesta
    Then debe extraer la URL de la imagen de portada
    And debe actualizar el campo image_url del libro
    And debe validar que la URL de la imagen sea accesible
    And debe registrar la obtención de la imagen en los logs

  Scenario: Manejo de categorías múltiples de OpenLibrary
    Given que OpenLibrary devuelve múltiples categorías para un libro
    When el sistema procesa las categorías
    Then debe extraer todas las categorías relevantes
    And debe filtrar categorías irrelevantes o muy genéricas
    And debe asignar las categorías al campo categories del libro
    And debe registrar las categorías asignadas en los logs

  Scenario: Sincronización periódica con OpenLibrary
    Given que el sistema está configurado para sincronización periódica
    When se ejecuta la tarea de sincronización
    Then debe revisar todos los libros con datos de OpenLibrary
    And debe verificar si hay actualizaciones disponibles
    And debe actualizar solo los libros que han cambiado
    And debe registrar el proceso de sincronización en los logs