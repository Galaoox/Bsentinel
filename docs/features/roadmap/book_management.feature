# language: es
Feature: Gestión de libros rastreados
  Como consumidor autenticado de la API v1
  Quiero registrar, consultar y dar de baja lógica a libros rastreados
  Para operar el catálogo real implementado hoy

  Background:
    Given que la API expone catálogo bajo "/api/v1/catalog"
    And que los endpoints de catálogo requieren bearer token

  Scenario: Crear un libro desde una URL soportada
    Given que existe una tienda activa para el dominio de la URL
    When envío una petición POST autenticada a "/api/v1/catalog/books"
    And el body JSON contiene "url"
    Then la API responde 201
    And la respuesta incluye "book_id"
    And la respuesta incluye "relation_id"
    And la respuesta incluye "isbn"
    And la respuesta incluye "title"
    And la respuesta incluye "authors"
    And la respuesta incluye "site"
    And la respuesta incluye "status"
    And el sistema ejecuta un scraping inmediato para la nueva relación libro-tienda

  Scenario: Reusar un libro existente por ISBN y crear una nueva relación
    Given que ya existe un libro con el mismo ISBN en otra tienda soportada
    When envío una petición POST autenticada a "/api/v1/catalog/books" con una URL válida de la nueva tienda
    Then la API responde 201
    And el sistema reutiliza el libro existente por ISBN
    And crea una nueva relación libro-tienda para el dominio solicitado
    And no duplica el registro del libro

  Scenario: Rechazar URL inválida
    When envío una petición POST autenticada a "/api/v1/catalog/books" con una URL malformada
    Then la API responde 400
    And el código de error es "VALIDATION_ERROR"

  Scenario: Rechazar una tienda no soportada o inactiva
    When envío una petición POST autenticada a "/api/v1/catalog/books" con una URL cuyo dominio no tiene tienda activa registrada
    Then la API responde 400
    And el código de error es "UNSUPPORTED_STORE"

  Scenario: Rechazar una relación duplicada para el mismo libro y la misma tienda
    Given que ya existe una relación libro-tienda para esa URL soportada
    When envío nuevamente una petición POST autenticada a "/api/v1/catalog/books" con la misma tienda para el mismo ISBN
    Then la API responde 409
    And el código de error es "ENTITY_ALREADY_EXISTS"

  Scenario: Rechazar alta cuando no se puede registrar ISBN
    Given que el scraping de detalle no entrega un ISBN usable
    When envío una petición POST autenticada a "/api/v1/catalog/books"
    Then la API responde 400
    And el código de error es "VALIDATION_ERROR"

  Scenario: Listar libros con paginación y filtros disponibles
    When envío una petición GET autenticada a "/api/v1/catalog/books"
    Then la API responde 200
    And la respuesta incluye "items"
    And la respuesta incluye "meta"
    And acepta los filtros "include_deleted", "q", "isbn", "author", "category", "page" y "limit"
    And cada item expone "book_id", "title", "authors", "isbn", "is_deleted", "current_price" y "status"

  Scenario: Obtener el detalle de un libro
    Given que existe un "book_id" válido
    When envío una petición GET autenticada a "/api/v1/catalog/books/{book_id}"
    Then la API responde 200
    And la respuesta incluye los datos básicos del libro
    And la respuesta incluye el bloque "openlibrary"
    And la respuesta incluye la colección "stores"

  Scenario: Eliminar lógicamente un libro
    Given que existe un "book_id" válido
    When envío una petición DELETE autenticada a "/api/v1/catalog/books/{book_id}"
    Then la API responde 204
    And el libro queda marcado como eliminado lógico

  Scenario: Restaurar un libro eliminado
    Given que existe un "book_id" marcado como eliminado
    When envío una petición POST autenticada a "/api/v1/catalog/books/{book_id}/restore"
    Then la API responde 200
    And la respuesta incluye "book_id"
    And la respuesta incluye "is_deleted": false

  Rule: Contrato observable actual
    - Los IDs de libros y relaciones son UUID.
    - La búsqueda está integrada en GET "/api/v1/catalog/books"; no existe un endpoint separado como "/search".
    - GET "/api/v1/catalog/books/{book_id}" devuelve 404 con código "ENTITY_NOT_FOUND" cuando el libro no existe.
    - El restore devuelve 400 con código "VALIDATION_ERROR" si el libro existe pero no está eliminado.

  Rule: Fuera de alcance actual
    - No existen endpoints para eliminar una relación libro-tienda individual.
    - No existe alta contractual de libros sin ISBN usando identificadores temporales.
    - No existen endpoints documentados de búsqueda avanzada, merge de libros ni listado público sin autenticación.
