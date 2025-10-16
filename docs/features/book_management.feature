# language: es
Feature: Gestión de Libros para Rastreo
  Como usuario del sistema de rastreo de precios de libros
  Quiero poder añadir y gestionar libros para su monitoreo
  Para poder hacer seguimiento a los precios de mis libros favoritos

  Background:
    Given que el sistema está configurado y funcionando
    And que la base de datos está inicializada
    And que OpenLibrary API está disponible para enriquecimiento

  Scenario: Añadir un nuevo libro de un sitio web soportado
    Given que la tienda "Buscalibre" está configurada en el sistema
    And que tengo la URL de un libro válido de Buscalibre
    When envío una petición POST a "/api/books" con la URL del libro
    Then el sistema debe extraer la información del libro (título, autores, ISBN)
    And debe crear o encontrar el libro en la tabla "libros" usando el ISBN como identificador único
    And debe crear la relación libro-tienda en la tabla "libro_tienda"
    And debe enriquecer obligatoriamente los datos del libro usando OpenLibrary API
    And el libro debe ser añadido a la cola de scraping para una primera verificación
    And la API debe responder con un estado de éxito (201 Created)
    And la respuesta debe incluir el product_id generado

  Scenario: Añadir el mismo libro desde otra tienda
    Given que un libro ya existe en el sistema desde Buscalibre
    And que la tienda "Librería Nacional" está configurada
    When envío una petición con la URL del mismo libro desde Librería Nacional
    Then el sistema debe identificar que es el mismo libro usando el ISBN
    And debe crear una nueva relación libro-tienda para Librería Nacional
    And NO debe duplicar el registro del libro en la tabla "libros"
    And debe mantener los datos enriquecidos obligatorios de OpenLibrary
    And la API debe responder con un estado de éxito (201 Created)

  Scenario: Intentar añadir un libro de un sitio web no soportado
    Given que la tienda "Librería Inexistente" NO está configurada en el sistema
    And que tengo una URL de un libro de dicha tienda
    When envío una petición POST a "/api/books" con la URL del libro
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (400 Bad Request)
    And el mensaje de error debe ser "Tienda no soportada"

  Scenario: Añadir un libro con URL inválida
    Given que tengo una URL malformada
    When envío una petición POST a "/api/books" con la URL inválida
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (400 Bad Request)
    And el mensaje de error debe indicar que la URL es inválida

  Scenario: Añadir un libro duplicado
    Given que un libro con la misma URL ya existe en el sistema
    When envío una petición POST a "/api/books" con la misma URL
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (409 Conflict)
    And el mensaje de error debe ser "El libro ya existe en el sistema"

  Scenario: Añadir libro sin ISBN disponible
    Given que la tienda "Buscalibre" está configurada
    And que el libro no tiene ISBN visible en la página
    When envío una petición con la URL del libro
    Then el sistema debe crear el libro usando el título y autores como identificador
    And debe generar un identificador único temporal
    And debe marcar el libro para posible fusión futura si se encuentra el ISBN
    And debe intentar enriquecer con OpenLibrary usando título y autores

  Scenario: Obtener lista de libros registrados
    Given que hay varios libros registrados en el sistema
    When envío una petición GET a "/api/books"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir la lista de todos los libros
    And cada libro debe incluir su información básica
    And debe incluir las categorías obtenidas obligatoriamente de OpenLibrary
    And debe incluir el estado actual en cada tienda

  Scenario: Obtener información de un libro específico
    Given que un libro con id "12345" existe en el sistema
    When envío una petición GET a "/api/books/12345"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir toda la información del libro
    And debe incluir los datos enriquecidos obligatorios de OpenLibrary
    And debe incluir el estado actual y precio en cada tienda
    And debe incluir las categorías del libro

  Scenario: Eliminar un libro del sistema (eliminación lógica)
    Given que un libro con id "12345" existe en el sistema
    When envío una petición DELETE a "/api/books/12345"
    Then el sistema debe marcar "is_deleted" como TRUE en la tabla "libros"
    And debe establecer "deleted_at" con la fecha actual
    And NO debe eliminar físicamente el registro
    And la API debe responder con un estado de éxito (204 No Content)

  Scenario: Intentar eliminar un libro inexistente
    Given que un libro con id "99999" NO existe en el sistema
    When envío una petición DELETE a "/api/books/99999"
    Then la API debe responder con un error (404 Not Found)
    And el mensaje de error debe ser "Libro no encontrado"

  Scenario: Restaurar un libro eliminado lógicamente
    Given que un libro con id "12345" está marcado como eliminado
    When envío una petición POST a "/api/books/12345/restore"
    Then el sistema debe marcar "is_deleted" como FALSE en la tabla "libros"
    And debe establecer "deleted_at" como NULL
    And la API debe responder con un estado de éxito (200 OK)

  Scenario: Buscar libros por título
    Given que hay libros registrados en el sistema
    When envío una petición GET a "/api/books/search?q=título_del_libro"
    Then el sistema debe buscar en la tabla "libros" por título
    And debe devolver todos los libros que coincidan con el término de búsqueda
    And debe incluir información básica del libro (título, autores, ISBN)
    And debe incluir el estado actual en cada tienda donde esté disponible
    And debe excluir libros marcados como eliminados

  Scenario: Buscar libros por autor
    Given que hay libros registrados en el sistema
    When envío una petición GET a "/api/books/search?author=nombre_autor"
    Then el sistema debe buscar en la tabla "libros" por autor
    And debe devolver todos los libros del autor especificado
    And debe incluir información básica del libro
    And debe excluir libros marcados como eliminados

  Scenario: Buscar libros por categoría
    Given que hay libros registrados en el sistema con categorías obligatorias de OpenLibrary
    When envío una petición GET a "/api/books/search?category=ficción"
    Then el sistema debe buscar en la tabla "libros" por categoría
    And debe devolver todos los libros de esa categoría
    And debe incluir información básica del libro
    And debe excluir libros marcados como eliminados

  Scenario: Buscar libros por ISBN
    Given que hay libros registrados en el sistema
    When envío una petición GET a "/api/books/search?isbn=9781234567890"
    Then el sistema debe buscar en la tabla "libros" por ISBN exacto
    And debe devolver el libro específico si existe
    And debe incluir toda la información del libro y sus tiendas
    And debe excluir libros marcados como eliminados