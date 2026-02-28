# Book tracker - Servicio de Web Scraping

**Versión:** 1.0.0
**Fecha:** 2025-10-05
**Autor:** [Erick Vergara]

## 1. Descripción General del Proyecto 📖

Este proyecto consiste en el desarrollo de un servicio de web scraping en Python, diseñado para rastrear y almacenar el historial de precios de libros de diversas tiendas en línea. El servicio se centrará inicialmente en `buscalibre.com.co` y será extensible para soportar múltiples sitios web a través de una configuración dinámica, incluyendo manejo de subdominios por país (ej. co.buscalibre.com, mx.buscalibre.com).

El sistema contará con una API para gestionar los libros a rastrear y utilizará una arquitectura robusta y escalable basada en **FastAPI** para la API y **Scrapy** para el núcleo de scraping. El enriquecimiento de metadatos con OpenLibrary API será obligatorio para todos los libros añadidos al sistema.

---

## 2. Arquitectura del Sistema 🏗️

El servicio se compone de los siguientes módulos principales:

- **API de Gestión (FastAPI)**: Punto de entrada para los usuarios. Permite añadir nuevos libros para su rastreo y (en el futuro) consultar el estado y el historial de precios. Generará automáticamente documentación interactiva con Swagger UI.

- **Núcleo de Scraping (Scrapy)**: El motor principal encargado de realizar las peticiones web, extraer la información de precios y guardar los datos. Está diseñado para ser asíncrono, eficiente y resiliente.

- **Planificador de Tareas (Scheduler)**: Un componente (ej. Celery con Redis, o un script con APScheduler) que orquesta la ejecución de las tareas de scraping de manera periódica y aleatorizada para evitar patrones de tráfico predecibles.

- **Base de Datos (PostgreSQL)**: Almacena la información de los libros, el historial de precios y la configuración de los sitios web soportados.

- **Módulo Anti-Bloqueo**: Integrado en Scrapy a través de _middlewares_, gestiona la rotación de proxies y User-Agents para minimizar el riesgo de ser bloqueado por l## 3. Esquema de la Base de Datos (PostgreSQL)

La persistencia de datos se gestionará con las siguientes tablas, diseñadas para separar la entidad "libro" de las "tiendas" y permitir que un libro esté disponible en múltiples tiendas:

````sql
-- Tabla para almacenar la información principal de los libros (entidad independiente)
CREATE TABLE libros (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(20) UNIQUE, -- ISBN como identificador único del libro
    title VARCHAR(500) NOT NULL,
    authors TEXT[], -- Array de autores
    publisher VARCHAR(255),
    publication_year INTEGER,
    language VARCHAR(10),
    pages INTEGER,
    description TEXT,
    categories TEXT[], -- Array de categorías/temas
    is_deleted BOOLEAN DEFAULT FALSE, -- Eliminación lógica
    deleted_at TIMESTAMPTZ, -- Cuándo se eliminó
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla para la configuración de tiendas/sitios web
CREATE TABLE tiendas (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    pais VARCHAR(3), -- Código ISO de país
    moneda VARCHAR(3) DEFAULT 'COP', -- Código ISO de moneda
    selector_precio VARCHAR(255) NOT NULL,
    selector_titulo VARCHAR(255),
    selector_autores VARCHAR(255),
    selector_isbn VARCHAR(255),
    selector_disponibilidad VARCHAR(255),
    price_cleanup_regex VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE, -- Eliminación lógica
    deleted_at TIMESTAMPTZ, -- Cuándo se eliminó
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de relación entre libros y tiendas (un libro puede estar en múltiples tiendas)
CREATE TABLE libro_tienda (
    id SERIAL PRIMARY KEY,
    libro_id INTEGER REFERENCES libros(id) ON DELETE CASCADE,
    tienda_id INTEGER REFERENCES tiendas(id) ON DELETE CASCADE,
    product_url TEXT NOT NULL, -- URL específica del libro en esta tienda
    product_id_tienda VARCHAR(255), -- ID del producto en la tienda específica
    image_url TEXT, -- URL de imagen específica de esta tienda
    estado VARCHAR(50) NOT NULL DEFAULT 'desconocido', -- 'activo', 'inactivo', 'desconocido', 'agotado', 'discontinuado'
    precio_actual NUMERIC(10, 2),
    last_checked TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT FALSE, -- Eliminación lógica
    deleted_at TIMESTAMPTZ, -- Cuándo se eliminó
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(libro_id, tienda_id) -- Un libro solo puede estar una vez por tienda
);

-- Tabla para almacenar el historial de precios por libro-tienda
CREATE TABLE historial_precios (
    id SERIAL PRIMARY KEY,
    libro_tienda_id INTEGER REFERENCES libro_tienda(id) ON DELETE CASCADE,
    precio NUMERIC(10, 2) NOT NULL,
    estado VARCHAR(50) NOT NULL, -- Estado del libro cuando se registró el precio
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- NO se agrega eliminación lógica aquí - los datos históricos se mantienen
    -- pero se pueden archivar después de X años
);

-- Índices para optimizar consultas frecuentes
CREATE INDEX idx_libros_isbn ON libros(isbn);
CREATE INDEX idx_libros_title ON libros USING gin(to_tsvector('spanish', title));
CREATE INDEX idx_libros_authors ON libros USING gin(authors);
CREATE INDEX idx_libros_is_deleted ON libros(is_deleted);
CREATE INDEX idx_historial_precios_fecha ON historial_precios(fecha);
CREATE INDEX idx_historial_precios_libro_tienda ON historial_precios(libro_tienda_id);
CREATE INDEX idx_libro_tienda_libro ON libro_tienda(libro_id);
CREATE INDEX idx_libro_tienda_tienda ON libro_tienda(tienda_id);
CREATE INDEX idx_libro_tienda_estado ON libro_tienda(estado);
CREATE INDEX idx_libro_tienda_last_checked ON libro_tienda(last_checked);
CREATE INDEX idx_libro_tienda_is_deleted ON libro_tienda(is_deleted);
CREATE INDEX idx_tiendas_is_deleted ON tiendas(is_deleted);
```LEAN DEFAULT TRUE,
    price_cleanup_regex VARCHAR(255)
);
````

---

## 4. Requisitos Funcionales (Gherkin) 📋

A continuación se definen los compo### Feature: Gestión de Libros para Rastreo

````gherkin
Scenario: Añadir un nuevo libro de un sitio web soportado
  Given que la tienda "Buscalibre" está configurada en el sistema
  When un usuario envía una petición a la API con la URL de un libro de Buscalibre
  Then el sistema debe extraer la información del libro (título, autores, ISBN)
  And debe crear o encontrar el libro en la tabla "libros" usando el ISBN como identificador único
  And debe crear la relación libro-tienda en la tabla "libro_tienda"
  And el libro debe ser añadido a la cola de scraping para una primera verificación
  And la API debe responder con un estado de éxito (201 Created)

Scenario: Añadir el mismo libro desde otra tienda
  Given que un libro ya existe en el sistema desde Buscalibre
  And que la tienda "Librería Nacional" está configurada
  When un usuario envía una petición con la URL del mismo libro desde Librería Nacional
  Then el sistema debe identificar que es el mismo libro usando el ISBN
  And debe crear una nueva relación libro-tienda para Librería Nacional
  And NO debe duplicar el registro del libro en la tabla "libros"
  And la API debe responder con un estado de éxito (201 Created)

Scenario: Intentar añadir un libro de un sitio web no soportado
  Given que la tienda "Librería Inexistente" NO está configurada en el sistema
  When un usuario envía una petición a la API con una URL de dicha tienda
  Then el sistema debe rechazar la petición
  And la API debe responder con un error (400 Bad Request) y un mensaje "Tienda no soportada"

Scenario: Añadir libro sin ISBN disponible
  Given que la tienda "Buscalibre" está configurada
  And que el libro no tiene ISBN visible en la página
  When un usuario envía una petición con la URL del libro
  Then el sistema debe crear el libro usando el título y autores como identificador
  And debe generar un identificador único temporal
  And debe marcar el libro para posible fusión futura si se encuentra el ISBN

Scenario: Enriquecimiento automático con OpenLibrary
  Given que un libro se ha añadido al sistema con ISBN válido
  When el sistema procesa el libro para enriquecimiento
  Then el sistema debe consultar la API de OpenLibrary usando el ISBN
  And debe actualizar los metadatos del libro con información de OpenLibrary
  And debe obtener y asignar las categorías del libro desde OpenLibrary
  And debe actualizar campos como publisher, publication_year, language, pages, description
  And debe registrar la fuente de enriquecimiento en los logs

Scenario: Enriquecimiento fallido por ISBN no encontrado en OpenLibrary
  Given que un libro se ha añadido al sistema con ISBN válido
  When el sistema intenta enriquecer con OpenLibrary
  And el ISBN no existe en OpenLibrary
  Then el sistema debe mantener los datos originales del libro
  And debe registrar un warning en los logs indicando que no se pudo enriquecer
  And debe continuar con el procesamiento normal del libro

Scenario: Actualización de categorías desde OpenLibrary
  Given que un libro existe en el sistema con categorías de OpenLibrary
  When el sistema ejecuta la tarea de actualización de categorías
  And OpenLibrary ha actualizado la información del libro
  Then el sistema debe consultar nuevamente la API de OpenLibrary
  And debe comparar las categorías actuales con las nuevas
  And debe actualizar las categorías si han cambiado
  And debe registrar los cambios en los logs
```ad Request) y un m### Feature: Proceso de Scraping de Precios

```gherkin
Scenario: Un scraper actualiza el precio de un libro en una tienda específica
  Given que un libro existe en el sistema y está disponible en Buscalibre
  And la configuración para Buscalibre especifica los selectores CSS correctos
  When la tarea de scraping para esa relación libro-tienda se ejecuta
  Then el sistema debe hacer una petición a la URL específica del libro en Buscalibre
  And debe usar un User-Agent y un Proxy aleatorios
  And debe extraer el nuevo precio usando el selector configurado
  And debe actualizar los campos "precio_actual", "estado" y "last_checked" en "libro_tienda"
  And debe crear un nuevo registro en "historial_precios" vinculado a la relación libro-tienda

Scenario: El scraper detecta que un libro ya no está disponible en una tienda
  Given que un libro existe en el sistema y está marcado como "activo" en Buscalibre
  When la tarea de scraping se ejecuta
  And la página indica que el libro no está disponible
  Then el sistema debe marcar "estado" como "agotado" en "libro_tienda"
  And debe registrar un precio de 0 en "historial_precios" con estado "agotado"
  And debe actualizar "last_checked" en "libro_tienda"

Scenario: El scraper falla porque la estructura de la página cambió
  Given que un libro existe en el sistema en una tienda específica
  When la tarea de scraping se ejecuta
  And el selector CSS para el precio no encuentra ningún elemento en la página
  Then el sistema NO debe actualizar el precio en "libro_tienda"
  And debe marcar "estado" como "desconocido" en "libro_tienda"
  And debe registrar un error de tipo "Selector no encontrado" en los logs
  And la tarea no debe ser reintentada por este tipo de error

Scenario: Scraping de múltiples tiendas para el mismo libro
  Given que un libro existe en Buscalibre y Librería Nacional
  When el planificador ejecuta el scraping para este libro
  Then debe procesar ambas tiendas de forma independiente
  And debe actualizar "precio_actual" y "estado" en cada relación libro-tienda por separado
  And debe crear registros separados en "historial_precios" para cada tienda

### Feature: Comparación de Precios entre Tiendas

```gherkin
Scenario: Consultar el precio más bajo de un libro
  Given que un libro existe en múltiples tiendas con precios diferentes
  When un usuario consulta el precio del libro
  Then el sistema debe mostrar el precio más bajo disponible (estado "activo")
  And debe indicar en qué tienda está ese precio
  And debe mostrar todos los precios disponibles ordenados de menor a mayor
  And debe excluir tiendas con estado "agotado" o "inactivo"

Scenario: Consultar disponibilidad de un libro en todas las tiendas
  Given que un libro está disponible en algunas tiendas pero no en otras
  When un usuario consulta la disponibilidad del libro
  Then el sistema debe mostrar en qué tiendas está disponible (estado "activo")
  And debe mostrar en qué tiendas no está disponible (estado "agotado", "inactivo", etc.)
  And debe mostrar los precios solo de las tiendas donde está disponible
  And debe mostrar el estado específico de cada tienda
````

### Feature: Búsqueda y Filtrado de Libros

````gherkin
Scenario: Buscar libros por título
  Given que hay libros registrados en el sistema
  When un usuario envía una petición GET a "/api/books/search?q=título_del_libro"
  Then el sistema debe buscar en la tabla "libros" por título
  And debe devolver todos los libros que coincidan con el término de búsqueda
  And debe incluir información básica del libro (título, autores, ISBN)
  And debe incluir el estado actual en cada tienda donde esté disponible

Scenario: Buscar libros por autor
  Given que hay libros registrados en el sistema
  When un usuario envía una petición GET a "/api/books/search?author=nombre_autor"
  Then el sistema debe buscar en la tabla "libros" por autor
  And debe devolver todos los libros del autor especificado
  And debe incluir información básica del libro

Scenario: Buscar libros por ISBN
  Given que hay libros registrados en el sistema
  When un usuario envía una petición GET a "/api/books/search?isbn=9781234567890"
  Then el sistema debe buscar en la tabla "libros" por ISBN exacto
  And debe devolver el libro específico si existe
  And debe incluir toda la información del libro y sus tiendas

Scenario: Obtener detalles completos de un libro
  Given que un libro existe en el sistema
  When un usuario envía una petición GET a "/api/books/{libro_id}"
  Then el sistema debe devolver toda la información del libro
  And debe incluir la lista de tiendas donde está disponible
  And debe incluir el estado actual y precio actual en cada tienda
  And debe incluir el historial de precios de cada tienda
```tarea no debe ser reintentada por este tipo de error
````

---

## 5. Requisitos Técnicos y de Implementación 🛠️

- **Lenguaje de Programación**: Python 3.9+
- **Framework API**: FastAPI con Pydantic para validación y Swagger para documentación.
- **Framework Scraping**: Scrapy.
- **Integración OpenLibrary**: Se utilizará la API REST de OpenLibrary (https://openlibrary.org/dev/docs/api/books) para enriquecimiento de datos y categorización automática.
- **Gestión de Proxies**: Se utilizará una librería como `scrapy-rotating-proxies` para la rotación automática de proxies en cada petición. La lista de proxies se gestionará en el archivo `settings.py`.
- **Rotación de User-Agents**: Se implementará a través de un middleware de Scrapy, utilizando una lista de User-Agents comunes para simular diferentes navegadores.
- **Manejo de Errores y Reintentos**:
  - Se configurará el `RetryMiddleware` de Scrapy para realizar un máximo de **2 reintentos** (3 intentos en total).
  - Los reintentos solo se activarán para errores de red o servidor (códigos HTTP 5xx, timeouts, etc.). **No se reintentará** si el error es de parseo (selectores rotos).
  - Se utilizará una estrategia de **espera exponencial (exponential backoff)** entre reintentos.
- **Manejo de JavaScript**: No se implementará en la versión inicial. El sistema se enfocará exclusivamente en sitios con renderizado del lado del servidor (Server-Side Rendering), evitando páginas que requieran JavaScript para cargar precios o datos dinámicos.
- **Integración OpenLibrary**:
  - **Rate Limiting**: Respetar los límites de la API de OpenLibrary (máximo 100 requests por minuto).
  - **Cache**: Implementar cache local para respuestas de OpenLibrary para evitar consultas repetidas.
  - **Fallback**: Si OpenLibrary no está disponible, continuar con los datos originales del scraping.
  - **Retry Logic**: Implementar reintentos con backoff exponencial para errores temporales de OpenLibrary.
- **Logging y Monitoreo**:
  - **Logging**: Se configurará el sistema de logging de Scrapy para registrar eventos importantes (libros scrapeados, errores, precios encontrados) en un archivo `scrapy_logs.log` con un nivel `INFO`.
  - **Monitoreo**: La API de FastAPI incluirá un endpoint `GET /health` para verificaciones de estado básicas.

## 6. Consideraciones Adicionales y Mejoras Futuras 🚀

### Identificación y Fusión de Libros Duplicados

- **Identificación por ISBN**: El ISBN es el identificador principal para determinar si dos registros representan el mismo libro. Si dos registros tienen el mismo ISBN, se consideran el mismo libro.
- **Identificación por similitud**: Para libros sin ISBN, implementar un algoritmo de similitud basado en título y autores para detectar posibles duplicados.
- **Fusión automática**: Cuando se detecte que dos registros representan el mismo libro (mismo ISBN), fusionar automáticamente manteniendo el historial de ambas fuentes.
- **Validación manual**: Proporcionar una interfaz para que los administradores revisen y aprueben fusiones automáticas de libros sin ISBN.

### Gestión de Metadatos y Sincronización

- **Sincronización de metadatos**: Cuando se actualice información de un libro (título, autores, etc.) en una tienda, considerar si actualizar la información maestra del libro en la tabla `libros`.
- **Resolución de conflictos**: Definir reglas para manejar cuando diferentes tiendas tienen información contradictoria del mismo libro (ej: títulos ligeramente diferentes, diferentes formatos de autor).
- **Priorización de fuentes**: Establecer una jerarquía de confiabilidad de fuentes para resolver conflictos (ej: ISBN oficial > tienda principal > tienda secundaria).
- **Enriquecimiento de datos con OpenLibrary**: Integrar con la API de OpenLibrary para enriquecer la información de los libros de forma obligatoria, obtener categorías automáticamente y validar metadatos usando ISBN como identificador principal. El enriquecimiento será un paso requerido en el proceso de añadir libros al sistema.

### Integración con OpenLibrary API

- **Endpoint principal**: `https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data`
- **Identificación**: Usar ISBN como identificador principal para todas las consultas
- **Datos obtenidos**:
  - **Metadatos básicos**: Título, autores, editor, año de publicación, idioma, número de páginas
  - **Descripción**: Resumen del libro desde OpenLibrary
  - **Categorías**: Extraer de los campos `subjects` y `subject_places`
  - **Portada**: URL de la imagen de portada si está disponible
- **Rate Limiting**: Respetar límite de 100 requests por minuto de OpenLibrary
- **Cache**: Implementar cache local para evitar consultas repetidas del mismo ISBN
- **Fallback**: Si OpenLibrary no está disponible, continuar con datos originales del scraping
- **Retry Logic**: Reintentos con backoff exponencial para errores temporales

### Categorización de Libros con OpenLibrary

- **Categorías automáticas y obligatorias**: Los libros tendrán categorías obtenidas automáticamente y de forma obligatoria de OpenLibrary usando el ISBN como identificador principal.
- **Categorías independientes de tienda**: Las categorías se asignan en la tabla `libros` (campo `categories`) y son independientes de cualquier tienda específica. Esto permite:
  - Clasificar libros por género, tema, edad, etc. usando el sistema estándar de OpenLibrary
  - Buscar libros por categoría sin importar en qué tiendas estén disponibles
  - Generar reportes y análisis por categoría de manera unificada
  - Mantener consistencia en la clasificación usando un sistema estándar reconocido
  - Actualizar categorías automáticamente cuando OpenLibrary actualice su información

### Análisis y Reportes

- **Análisis de precios**: Generar reportes de tendencias de precios por categoría, autor, o tienda.
- **Comparación de tiendas**: Analizar qué tiendas ofrecen mejores precios en general.
- **Recomendaciones**: Sugerir cuándo es el mejor momento para comprar un libro basado en patrones históricos.

### Escalabilidad y Performance

- **Cache de consultas frecuentes**: Implementar cache para consultas de precios actuales y búsquedas populares.
- **Indexación optimizada**: Usar índices de texto completo para búsquedas rápidas por título y autor.
- **Particionado de tablas**: Considerar particionar la tabla de historial de precios por fecha para mejorar el rendimiento.

### Integración y APIs Externas

- **APIs de tiendas**: Integrar con APIs oficiales de tiendas cuando estén disponibles para obtener datos más precisos.
- **Webhooks**: Permitir que las tiendas notifiquen cambios de precio directamente al sistema.
- **Sincronización en tiempo real**: Implementar actualizaciones de precio en tiempo real para libros de alta demanda.

### Seguridad y Privacidad

- **Rate limiting por IP**: Implementar límites de velocidad para prevenir abuso de la API.
- **Autenticación y autorización**: Sistema robusto de autenticación para usuarios y administradores.
- **Auditoría**: Registrar todas las acciones importantes para auditoría y debugging.

### Internacionalización

- **Soporte multi-idioma**: Preparar el sistema para manejar libros en diferentes idiomas.
- **Conversión de monedas**: Implementar conversión automática de precios entre diferentes monedas.
- **Localización**: Adaptar formatos de fecha, números y texto según la región del usuario.

## 7. Preguntas Pendientes y Consideraciones Futuras ❓

### Preguntas Técnicas Pendientes

1. **Comparación de precios**: ¿Cómo mostrar el precio más bajo disponible de un libro entre todas las tiendas? ¿Implementar un endpoint específico o incluir esta información en la búsqueda general?

2. **Estados de libro-tienda**: ¿Qué otros estados además de 'activo', 'inactivo', 'desconocido' podrían ser necesarios? (ej: 'agotado', 'discontinuado', 'próximamente', 'solo preventa')

3. **Frecuencia de scraping**: ¿Con qué frecuencia se debe actualizar el estado y precio de cada libro? ¿Diferentes frecuencias según la tienda o tipo de libro?

4. **Límites de scraping**: ¿Cuántos libros simultáneos se pueden rastrear por tienda sin ser bloqueados? ¿Implementar colas de prioridad?

5. **Manejo de errores de scraping**: ¿Qué hacer cuando una tienda cambia completamente su estructura y los selectores dejan de funcionar? ¿Sistema de notificación automática?

### Consideraciones de Negocio

1. **Monetización**: ¿El sistema será gratuito o tendrá planes de pago? ¿Qué funcionalidades serían premium?

2. **Usuarios**: ¿Sistema de usuarios individuales o solo API pública? ¿Autenticación necesaria para todas las funcionalidades?

3. **Límites de API**: ¿Implementar límites de uso por usuario/IP? ¿Rate limiting por endpoint?

4. **Datos históricos**: ¿Cuánto tiempo mantener el historial de precios? ¿Archivado automático de datos antiguos?

5. **Integración con tiendas**: ¿Las tiendas estarán interesadas en integrar APIs oficiales? ¿Consideraciones legales del scraping?

## 8. Política de Retención y Eliminación de Datos 🗂️

### Datos con Eliminación Lógica (Soft Delete)

Estos datos se marcan como eliminados pero se mantienen en la base de datos:

#### **Libros** (`libros` table)

- **Tiempo de retención**: Indefinido (datos históricos valiosos)
- **Recuperación**: Posible si se necesita restaurar

#### **Tiendas** (`tiendas` table)

- **Tiempo de retención**: 2 años después de eliminación
- **Recuperación**: Posible para restaurar configuración

#### **Relaciones Libro-Tienda** (`libro_tienda` table)

- **Tiempo de retención**: 1 año después de eliminación
- **Recuperación**: Posible si la relación se restablece

### Datos con Eliminación Física (Hard Delete)

Estos datos se eliminan completamente del sistema:

#### **Logs de Scraping Detallados**

- **Tiempo de retención**: 30 días
- **Razón**: Datos temporales, alto volumen, poco valor histórico
- **Excepción**: Mantener logs de errores críticos por 1 año

#### **Datos de Sesión y Cache**

- **Tiempo de retención**: 24 horas
- **Razón**: Datos temporales, no críticos

#### **Archivos Temporales**

- **Tiempo de retención**: 7 días
- **Razón**: Imágenes descargadas, archivos de procesamiento

### Datos que NUNCA se Eliminan

Estos datos se mantienen indefinidamente:

#### **Historial de Precios** (`historial_precios` table)

- **Razón**: Datos históricos valiosos para análisis de tendencias
- **Archivado**: Después de 5 años, mover a tabla de archivo
- **Uso**: Análisis de precios, reportes históricos, machine learning

### Políticas de Limpieza Automática

```sql
-- Ejemplo de consultas para limpieza automática

-- 1. Archivar historial de precios antiguo (ejecutar mensualmente)
INSERT INTO historial_precios_archivo
SELECT * FROM historial_precios
WHERE fecha < NOW() - INTERVAL '5 years';

-- 2. Eliminar logs antiguos (ejecutar semanalmente)
DELETE FROM scraping_logs
WHERE created_at < NOW() - INTERVAL '30 days';

-- 3. Limpiar datos de sesión (ejecutar diariamente)
DELETE FROM user_sessions
WHERE expires_at < NOW();

-- 4. Eliminar tiendas eliminadas lógicamente después de 2 años
DELETE FROM tiendas
WHERE is_deleted = TRUE
AND deleted_at < NOW() - INTERVAL '2 years';
```
