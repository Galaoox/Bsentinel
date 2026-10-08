# language: es
Feature: Integración actual con OpenLibrary
  Como sistema de enriquecimiento de catálogo
  Quiero completar metadatos desde OpenLibrary cuando el código realmente lo hace
  Para documentar el comportamiento observable sin sobreprometer

  Background:
    Given que el cliente de OpenLibrary usa la base configurada en settings
    And que el enriquecimiento ocurre dentro del alta de catálogo para libros nuevos

  Scenario: Enriquecer un libro nuevo por ISBN
    Given que el scraping produjo un ISBN usable y el libro todavía no existe
    When el servicio de catálogo crea el libro
    Then consulta "{openlibrary_api_url}/api/books"
    And envía "bibkeys=ISBN:{isbn}", "format=json" y "jscmd=data"
    And si hay datos, completa metadatos del libro antes de persistirlo

  Scenario: Mapear los campos soportados hoy
    When OpenLibrary devuelve datos válidos para el ISBN pedido
    Then el sistema puede completar "publisher"
    And puede completar "publication_year"
    And puede completar "language"
    And puede completar "pages"
    And puede completar "description"
    And puede completar "image_url"
    And puede completar "categories"
    And las categorías se limitan a los primeros 10 subjects con nombre

  Scenario: Continuar cuando OpenLibrary falla o no devuelve datos
    When la petición a OpenLibrary falla o la respuesta no trae información útil para ese ISBN
    Then el cliente devuelve un objeto vacío
    And el alta del libro continúa con los datos obtenidos por scraping
    And no se aborta la creación del libro por este motivo

  Scenario: No re-enriquecer un libro ya existente reutilizado por ISBN
    Given que el ISBN ya existe en el catálogo
    When se crea una nueva relación para otra tienda
    Then el sistema reutiliza el libro existente
    And no vuelve a crear el libro ni a ejecutar enriquecimiento obligatorio adicional en ese flujo

  Rule: Contrato observable actual
    - El enriquecimiento implementado hoy es solamente por ISBN.
    - "publication_year" se infiere buscando el primer token de cuatro dígitos en "publish_date".
    - "language" se toma del primer item de "languages" y usa el último segmento de su key.
    - "description" acepta tanto string directo como objeto con "value".

  Rule: Fuera de alcance actual
    - No existe cache contractual de respuestas de OpenLibrary.
    - No existe rate limiting activo, cola de reintentos, búsqueda por título/autor ni sincronización periódica implementada en este cliente.
    - No existe validación avanzada de consistencia ni selección de múltiples resultados porque el flujo actual no usa búsqueda abierta.
