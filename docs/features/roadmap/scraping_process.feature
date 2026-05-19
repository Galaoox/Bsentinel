# language: es
Feature: Proceso de scraping configurado
  Como sistema de rastreo de precios
  Quiero extraer detalle y precio usando reglas configuradas por tienda
  Para sostener el flujo observable implementado hoy

  Background:
    Given que el scraper usa reglas de extracción configuradas por tienda
    And que la sesión de navegador debe estar inicializada para hacer fetch

  Scenario: Extraer los datos base de un libro al registrarlo
    Given que la tienda soportada tiene reglas para "title", "authors" e "isbn"
    When el sistema procesa una URL de producto para crear el libro
    Then hace fetch de la página del producto
    And intenta extraer datos desde fuentes "css" y/o "json_ld"
    And exige título, autores e ISBN utilizables para completar el alta

  Scenario: Ejecutar scraping inmediato después de crear una relación
    Given que una nueva relación libro-tienda fue creada correctamente
    When el servicio de catálogo completa el alta
    Then ejecuta un scraping inmediato de esa relación
    And actualiza "current_price", "status" y "last_checked"
    And agrega un registro en el historial de precios

  Scenario: Calcular precio y estado desde la respuesta utilizable
    Given que la página devolvió HTML utilizable
    When el scraper procesa las reglas de "price" y "availability"
    Then el precio se normaliza según la regla configurada
    And si no hay availability usable el estado por defecto es "activo"
    And si el precio no puede determinarse y el estado es "agotado", el precio guardado es 0.0
    And si el precio no puede determinarse y el estado no es "agotado", el estado final pasa a "desconocido" y el precio guardado es 0.0

  Scenario: Rechazar respuestas HTTP no utilizables
    When el fetch devuelve una respuesta vacía, no HTML o con status mayor o igual a 400
    Then el scraper falla con un error de scraping
    And el motivo puede ser "empty_body", "unexpected_content_type", "http_error" o "accepted_without_html"

  Scenario: Registrar diagnóstico cuando falta un campo obligatorio
    Given que no se puede extraer alguno de los campos obligatorios del detalle
    When el sistema intenta registrar el libro
    Then falla con un error de scraping
    And el error conserva diagnósticos sobre "field_name", intentos de source y presencia de JSON-LD

  Scenario: Ejecutar scraping batch sobre libros activos
    Given que existen relaciones libro-tienda registradas
    When corre el batch de scraping del scheduler
    Then se procesan únicamente relaciones cuyos libros no están eliminados lógicamente
    And cada relación reutiliza el mismo flujo de scraping individual

  Rule: Contrato observable actual
    - La implementación actual usa una sesión de navegador stealth compartida, no un cliente HTTP simple por tienda.
    - Las reglas soportan sources "css" y "json_ld" con normalizers configurables.
    - El proceso batch existe en la aplicación, pero no tiene endpoint público propio en la API v1.

  Rule: Fuera de alcance actual
    - No hay contrato implementado de rotación de proxies, user-agents aleatorios, cola distribuida ni backoff automático de scraping.
    - No hay contrato implementado de reintentos selectivos por timeout, 403 o 429.
    - No hay procesamiento asíncrono expuesto por API para lanzar scrapings manuales por lote o por tienda.
