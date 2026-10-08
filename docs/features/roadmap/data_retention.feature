# language: es
Feature: Retención y archivado de datos
  Como consumidor autenticado de la API v1
  Quiero usar el flujo real de archivado y retención disponible hoy
  Para gestionar histórico sin prometer capacidades inexistentes

  Background:
    Given que la API expone retención bajo "/api/v1/retention"
    And que los endpoints de retención requieren bearer token

  Scenario: Crear un job de archivado
    When envío una petición POST autenticada a "/api/v1/retention/jobs/archive"
    And el body JSON incluye "older_than_days" y "min_active_records_per_book"
    Then la API responde 202
    And la respuesta incluye "id"
    And la respuesta incluye "status"
    And la respuesta incluye "started_at"
    And la respuesta incluye "finished_at"
    And la respuesta incluye "moved_records"
    And la respuesta incluye "errors"

  Scenario: Consultar el estado de un job de archivado
    Given que existe un "job_id" válido
    When envío una petición GET autenticada a "/api/v1/retention/jobs/archive/{job_id}"
    Then la API responde 200
    And la respuesta devuelve el estado actual del job

  Scenario: Rechazar parámetros inválidos del job
    When envío una petición POST autenticada a "/api/v1/retention/jobs/archive" con valores fuera de rango
    Then la petición se rechaza
    And "older_than_days" debe ser mayor o igual a 1
    And "min_active_records_per_book" debe ser mayor o igual a 1

  Scenario: Aplicar la política de archivado implementada
    Given que existen registros históricos no archivados
    When el job de archivado se ejecuta
    Then solo marca registros como archivados cuando están por fuera del cutoff temporal configurado
    And conserva al menos los últimos N registros activos por libro según "min_active_records_per_book"
    And no elimina físicamente registros del historial

  Scenario: Consultar un job inexistente
    When envío una petición GET autenticada a "/api/v1/retention/jobs/archive/{job_id}" con un UUID inexistente
    Then la API responde 404
    And el código de error es "ENTITY_NOT_FOUND"

  Rule: Contrato observable actual
    - El archivado se implementa marcando el campo "archived" en registros de historial; no mueve datos a otra tabla ni a otro storage.
    - El job transita por estados "queued", "running", "completed" o "failed".
    - La retención expuesta por API hoy cubre jobs de archivado; la baja lógica y restore de libros se documentan en la feature de catálogo.

  Rule: Fuera de alcance actual
    - No existen endpoints para eliminar físicamente libros, tiendas o relaciones.
    - No existen endpoints para reportes administrativos, restauraciones masivas ni configuración dinámica de políticas de retención.
    - No existe contrato implementado de backups automáticos previos al archivado.
