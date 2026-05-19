# language: es
Feature: Configuración administrativa de tiendas
  Como administrador de la API v1
  Quiero crear y mantener tiendas con reglas de extracción
  Para habilitar dominios soportados por el scraping configurado

  Background:
    Given que la API expone administración de tiendas bajo "/api/v1/stores"
    And que estos endpoints requieren bearer token de administrador

  Scenario: Crear una tienda nueva
    When envío una petición POST autenticada a "/api/v1/stores" con un body JSON válido
    Then la API responde 201
    And la respuesta incluye "id"
    And la respuesta incluye "name"
    And la respuesta incluye "domain"
    And la respuesta incluye "country_code"
    And la respuesta incluye "scrape_interval_hours"
    And la respuesta incluye "is_active"
    And la respuesta incluye "extraction_rules"

  Scenario: Crear una tienda duplicada
    Given que ya existe una tienda no eliminada para el mismo dominio
    When envío una petición POST autenticada a "/api/v1/stores" con ese dominio
    Then la API responde 409
    And el código de error es "ENTITY_ALREADY_EXISTS"

  Scenario: Validar el contrato mínimo de extraction_rules
    When envío una petición POST autenticada a "/api/v1/stores" con reglas inválidas
    Then la petición se rechaza
    And las reglas deben incluir "title", "authors", "isbn" y "price"
    And "availability" es opcional
    And cada field debe definir al menos un source
    And cada source soporta únicamente los tipos "css" o "json_ld"

  Scenario: Validar country code y selectores
    When envío una petición POST autenticada a "/api/v1/stores" con un country code semánticamente inválido o con un selector CSS inválido
    Then la API responde 400 o 422 según la capa que rechace el payload
    And el contrato activo no acepta códigos de país fuera de ISO alpha-2

  Scenario: Listar tiendas configuradas
    When envío una petición GET autenticada a "/api/v1/stores"
    Then la API responde 200
    And la respuesta incluye "items"
    And la respuesta incluye "meta.total"
    And cada item expone "id", "name", "domain", "country_code", "scrape_interval_hours" e "is_active"

  Scenario: Obtener una tienda puntual por id
    Given que existe un "store_id" válido
    When envío una petición GET autenticada a "/api/v1/stores/{store_id}"
    Then la API responde 200
    And la respuesta incluye el detalle completo
    And la respuesta incluye "extraction_rules"

  Scenario: Actualizar completamente una tienda
    Given que existe un "store_id" válido
    When envío una petición PUT autenticada a "/api/v1/stores/{store_id}" con el body completo
    Then la API responde 200
    And reaplica las validaciones de dominio, country code y extraction_rules

  Scenario: Actualizar parcialmente una tienda
    Given que existe un "store_id" válido
    When envío una petición PATCH autenticada a "/api/v1/stores/{store_id}"
    And el body incluye "is_active" y/o "scrape_interval_hours"
    Then la API responde 200
    And la tienda queda actualizada solo en esos campos

  Scenario: Rechazar acceso sin autenticación administrativa
    When envío una petición a "/api/v1/stores" sin bearer token
    Then la API responde 401
    And el código de error es "AUTH_INVALID_TOKEN"

  Rule: Contrato observable actual
    - Los endpoints usan UUID como identificador de tienda en path; no usan dominio como key primaria del endpoint.
    - El sistema normaliza el dominio a minúsculas y el country code a mayúsculas.
    - El PATCH exige al menos un campo entre "is_active" y "scrape_interval_hours".
    - Los normalizers soportados hoy incluyen "text_trim", "isbn_digits", "price_latam", "price_cop", "price_decimal", "price_cop_mixed" y "availability_buscalibre".

  Rule: Fuera de alcance actual
    - No existen endpoints de delete, restore, test de tienda ni estadísticas de tienda.
    - No existe un catálogo contractual de países más allá de la validación alpha-2 aplicada por la implementación.
