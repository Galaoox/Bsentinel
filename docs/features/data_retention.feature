# language: es
Feature: Retención y Eliminación de Datos
  Como administrador del sistema
  Quiero poder gestionar la retención y eliminación de datos
  Para mantener el sistema optimizado y cumplir con políticas de privacidad

  Background:
    Given que el sistema está funcionando
    And que hay datos históricos en el sistema
    And que las políticas de retención están configuradas

  Scenario: Eliminación lógica de un libro
    Given que un libro con id "12345" existe en el sistema
    And que el libro tiene historial de precios
    When envío una petición DELETE a "/api/books/12345"
    Then el sistema debe marcar "is_deleted" como TRUE en la tabla "libros"
    And debe establecer "deleted_at" con la fecha actual
    And NO debe eliminar físicamente el registro
    And debe mantener todo el historial de precios
    And la API debe responder con un estado de éxito (204 No Content)

  Scenario: Restaurar un libro eliminado lógicamente
    Given que un libro con id "12345" está marcado como eliminado
    When envío una petición POST a "/api/books/12345/restore"
    Then el sistema debe marcar "is_deleted" como FALSE en la tabla "libros"
    And debe establecer "deleted_at" como NULL
    And debe restaurar la visibilidad del libro
    And la API debe responder con un estado de éxito (200 OK)

  Scenario: Eliminación lógica de una tienda
    Given que una tienda con id "5" existe en el sistema
    And que no hay libros asociados a esta tienda
    When envío una petición DELETE a "/api/tiendas/5"
    Then el sistema debe marcar "is_deleted" como TRUE en la tabla "tiendas"
    And debe establecer "deleted_at" con la fecha actual
    And NO debe eliminar físicamente el registro
    And la API debe responder con un estado de éxito (204 No Content)

  Scenario: Intentar eliminar tienda con libros asociados
    Given que una tienda con id "5" existe en el sistema
    And que hay libros asociados a esta tienda
    When envío una petición DELETE a "/api/tiendas/5"
    Then el sistema debe rechazar la petición
    And la API debe responder con un error (409 Conflict)
    And el mensaje de error debe ser "No se puede eliminar una tienda con libros asociados"

  Scenario: Eliminación lógica de relación libro-tienda
    Given que un libro está asociado a múltiples tiendas
    When envío una petición DELETE a "/api/books/12345/tiendas/5"
    Then el sistema debe marcar "is_deleted" como TRUE en la tabla "libro_tienda"
    And debe establecer "deleted_at" con la fecha actual
    And NO debe eliminar físicamente el registro
    And debe mantener el historial de precios de esa relación
    And la API debe responder con un estado de éxito (204 No Content)

  Scenario: Consultar solo datos no eliminados
    Given que hay libros eliminados y activos en el sistema
    When envío una petición GET a "/api/books"
    Then la API debe devolver solo los libros no eliminados
    And debe excluir libros con "is_deleted" = TRUE
    And debe incluir metadatos sobre el total de libros (incluyendo eliminados)

  Scenario: Consultar datos eliminados con permisos de administrador
    Given que tengo permisos de administrador
    And que hay libros eliminados en el sistema
    When envío una petición GET a "/api/books?include_deleted=true"
    Then la API debe devolver todos los libros incluyendo los eliminados
    And debe marcar claramente cuáles están eliminados
    And debe incluir la fecha de eliminación

  Scenario: Limpieza automática de logs antiguos
    Given que el sistema tiene logs de scraping acumulados
    And que algunos logs son más antiguos que 30 días
    When el sistema ejecuta la tarea de limpieza de logs
    Then debe eliminar logs más antiguos que 30 días
    And debe mantener logs de errores críticos por 1 año
    And debe comprimir logs antiguos antes de eliminarlos
    And debe registrar la limpieza en los logs del sistema

  Scenario: Archivo de historial de precios antiguo
    Given que un libro tiene historial de precios de más de 5 años
    When el sistema ejecuta la tarea de archivo de historial
    Then debe mover registros antiguos a una tabla de archivo
    And debe mantener al menos los últimos 1000 registros en la tabla principal
    And debe crear un backup antes del archivo
    And debe registrar el proceso de archivo en los logs

  Scenario: Limpieza de datos de sesión temporales
    Given que el sistema tiene datos de sesión acumulados
    And que algunas sesiones han expirado
    When el sistema ejecuta la tarea de limpieza de sesiones
    Then debe eliminar sesiones expiradas
    And debe mantener sesiones activas
    And debe registrar la limpieza en los logs

  Scenario: Eliminación física de datos después del período de retención
    Given que una tienda fue eliminada hace más de 2 años
    And que no tiene libros asociados
    When el sistema ejecuta la tarea de limpieza física
    Then debe eliminar físicamente el registro de la tienda
    And debe registrar la eliminación física en los logs
    And debe crear un backup antes de la eliminación

  Scenario: Eliminación física de relaciones libro-tienda después del período de retención
    Given que una relación libro-tienda fue eliminada hace más de 1 año
    When el sistema ejecuta la tarea de limpieza física
    Then debe eliminar físicamente el registro de la relación
    And debe mantener el historial de precios asociado
    And debe registrar la eliminación física en los logs

  Scenario: Backup antes de eliminación física
    Given que el sistema va a eliminar datos físicamente
    When se ejecuta la tarea de eliminación física
    Then debe crear un backup completo de los datos a eliminar
    And debe verificar que el backup se creó correctamente
    And debe proceder con la eliminación solo si el backup es exitoso
    And debe registrar el proceso de backup en los logs

  Scenario: Reporte de datos eliminados
    Given que el sistema ha eliminado datos recientemente
    When envío una petición GET a "/api/admin/deleted-data-report"
    Then la API debe devolver un reporte de datos eliminados
    And debe incluir el número de libros eliminados
    And debe incluir el número de tiendas eliminadas
    And debe incluir el número de relaciones eliminadas
    And debe incluir fechas de eliminación

  Scenario: Restauración masiva de datos eliminados
    Given que hay múltiples libros eliminados lógicamente
    And que tengo permisos de administrador
    When envío una petición POST a "/api/admin/restore-all-books"
    Then el sistema debe restaurar todos los libros eliminados
    And debe marcar "is_deleted" como FALSE para todos
    And debe establecer "deleted_at" como NULL para todos
    And debe registrar la restauración masiva en los logs

  Scenario: Configuración de políticas de retención
    Given que tengo permisos de administrador
    When envío una petición PUT a "/api/admin/retention-policies"
    And especifico nuevos períodos de retención
    Then el sistema debe actualizar las políticas de retención
    And debe aplicar las nuevas políticas en la próxima limpieza
    And debe registrar los cambios en los logs
    And la API debe responder con un estado de éxito (200 OK)

  Scenario: Verificación de integridad de datos antes de eliminación
    Given que el sistema va a eliminar datos
    When se ejecuta la verificación de integridad
    Then debe verificar que no hay referencias huérfanas
    And debe verificar que los backups están completos
    And debe proceder solo si la verificación es exitosa
    And debe registrar el resultado de la verificación en los logs