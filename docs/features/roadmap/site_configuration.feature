# language: es
Feature: Configuración de Tiendas Web
  Como administrador del sistema
  Quiero poder configurar nuevas tiendas web para scraping
  Para extender la funcionalidad del sistema a más librerías

  Background:
    Given que el sistema está funcionando
    And que la tabla "tiendas" está disponible
    And que tengo permisos de administrador

  Scenario: Añadir una nueva tienda web soportada
    Given que tengo la información de configuración de una nueva tienda
    And que el dominio "www.nuevalibreria.com" no está configurado
    And que especifico el país correspondiente (ej. "CO" para Colombia)
    When envío una petición POST a "/api/tiendas" con la configuración de la tienda incluyendo el país
    Then el sistema debe registrar la tienda en la tabla "tiendas"
    And debe validar que el código de país sea válido (ISO 3166-1 alpha-3)
    And la API debe responder con un estado de éxito (201 Created)
    And la tienda debe estar marcada como activa por defecto
    And debe incluir todos los selectores CSS necesarios

  Scenario: Intentar añadir una tienda duplicada
    Given que la tienda "www.buscalibre.com.co" ya está configurada
    When envío una petición POST a "/api/tiendas" con el mismo dominio
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (409 Conflict)
    And el mensaje de error debe ser "La tienda ya está configurada"

  Scenario: Añadir tienda con configuración incompleta
    Given que tengo información parcial de una tienda
    And que faltan campos requeridos como "selector_precio" o "pais"
    When envío una petición POST a "/api/tiendas" con configuración incompleta
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (400 Bad Request)
    And el mensaje de error debe indicar qué campos son requeridos incluyendo el país

  Scenario: Obtener lista de tiendas configuradas
    Given que hay varias tiendas configuradas en el sistema
    When envío una petición GET a "/api/tiendas"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir todas las tiendas configuradas
    And cada tienda debe incluir su estado (activo/inactivo)
    And debe excluir tiendas marcadas como eliminadas

  Scenario: Obtener configuración de una tienda específica
    Given que la tienda "www.buscalibre.com.co" está configurada
    When envío una petición GET a "/api/tiendas/buscalibre.com.co"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir todos los selectores configurados
    And debe incluir el estado de la tienda
    And debe incluir la información de configuración completa incluyendo el país

  Scenario: Actualizar configuración de una tienda existente
    Given que la tienda "www.buscalibre.com.co" está configurada
    And que necesito actualizar el selector de precio o el país
    When envío una petición PUT a "/api/tiendas/buscalibre.com.co" con la nueva configuración
    Then el sistema debe validar el código de país si se incluye
    And el sistema debe actualizar la configuración en la base de datos
    And la API debe responder con un estado de éxito (200 OK)
    And la nueva configuración debe estar disponible para el scraping

  Scenario: Desactivar una tienda web
    Given que la tienda "www.buscalibre.com.co" está activa
    When envío una petición PATCH a "/api/tiendas/buscalibre.com.co" con "is_active": false
    Then el sistema debe marcar la tienda como inactiva
    And la API debe responder con un estado de éxito (200 OK)
    And la tienda no debe ser usada para nuevos scrapings

  Scenario: Reactivar una tienda web
    Given que la tienda "www.buscalibre.com.co" está inactiva
    When envío una petición PATCH a "/api/tiendas/buscalibre.com.co" con "is_active": true
    Then el sistema debe marcar la tienda como activa
    And la API debe responder con un estado de éxito (200 OK)
    And la tienda debe estar disponible para nuevos scrapings

  Scenario: Eliminar una tienda web (eliminación lógica)
    Given que la tienda "www.buscalibre.com.co" está configurada
    And que no hay libros asociados a esta tienda
    When envío una petición DELETE a "/api/tiendas/buscalibre.com.co"
    Then el sistema debe marcar "is_deleted" como TRUE en la tabla "tiendas"
    And debe establecer "deleted_at" con la fecha actual
    And NO debe eliminar físicamente el registro
    And la API debe responder con un estado de éxito (204 No Content)

  Scenario: Intentar eliminar una tienda con libros asociados
    Given que la tienda "www.buscalibre.com.co" está configurada
    And que hay libros asociados a esta tienda
    When envío una petición DELETE a "/api/tiendas/buscalibre.com.co"
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (409 Conflict)
    And el mensaje de error debe ser "No se puede eliminar una tienda con libros asociados"

  Scenario: Validar selectores CSS antes de guardar
    Given que tengo una configuración con selectores CSS
    When envío una petición POST a "/api/tiendas" con selectores inválidos
    Then el sistema debe validar la sintaxis de los selectores
    And debe rechazar la petición si los selectores son inválidos
    And la API debe responder con un error (400 Bad Request)
    And el mensaje debe indicar qué selectores son inválidos

  Scenario: Configurar regex de limpieza de precios
    Given que una tienda devuelve precios con formato "$1,234.56"
    When configuro la tienda con un regex de limpieza apropiado
    Then el sistema debe aplicar el regex para limpiar los precios
    And debe convertir el precio a formato numérico estándar
    And debe almacenar el precio limpio en la base de datos

  Scenario: Probar configuración de tienda
    Given que una tienda está configurada
    When envío una petición POST a "/api/tiendas/{tienda_id}/test"
    Then el sistema debe hacer una petición de prueba a la tienda
    And debe validar que todos los selectores funcionen correctamente
    And debe devolver un reporte de qué selectores funcionan y cuáles no
    And la API debe responder con un estado de éxito (200 OK)

  Scenario: Restaurar una tienda eliminada lógicamente
    Given que una tienda está marcada como eliminada
    When envío una petición POST a "/api/tiendas/{tienda_id}/restore"
    Then el sistema debe marcar "is_deleted" como FALSE en la tabla "tiendas"
    And debe establecer "deleted_at" como NULL
    And la API debe responder con un estado de éxito (200 OK)

  Scenario: Obtener estadísticas de una tienda
    Given que una tienda está configurada y tiene libros asociados
    When envío una petición GET a "/api/tiendas/{tienda_id}/stats"
    Then la API debe responder con un estado de éxito (200 OK)
    And la respuesta debe incluir el número de libros asociados
    And debe incluir el número de libros activos vs inactivos
    And debe incluir la última vez que se hizo scraping
    And debe incluir estadísticas de éxito/fallo del scraping
    And debe incluir información del país de la tienda