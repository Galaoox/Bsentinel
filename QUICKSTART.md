# 🚀 Guía de Inicio Rápido - Bsentinel

Esta guía te ayudará a poner en marcha el proyecto en menos de 5 minutos.

## ✅ Prerrequisitos

1. **Python 3.12+** instalado
2. **Docker Desktop** instalado y en ejecución
3. **Git** instalado
4. **Windows** como sistema operativo

## 📦 Paso 1: Instalar uv

Abre PowerShell y ejecuta:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cierra y vuelve a abrir PowerShell para que los cambios surtan efecto.

## 🔧 Paso 2: Configurar el proyecto

```bash
# 1. Navegar al directorio del proyecto
cd book_tracker_backend

# 2. Instalar dependencias
uv sync

# 3. Copiar archivo de configuración
copy secrets\.env.example secrets\.env
```

## 🐳 Paso 3: Iniciar PostgreSQL

```bash
docker-compose up postgres -d
```

Espera unos segundos hasta que PostgreSQL esté listo (verifica con `docker-compose ps`).

## 🚀 Paso 4: Ejecutar la aplicación

### Opción A: Con uv (Recomendado para desarrollo)

```bash
uv run python -m bsentinel.infrastructure.api
```

### Opción B: Con Docker (Todo en contenedores)

```bash
docker-compose up
```

## ✨ Paso 5: Verificar que funciona

Abre tu navegador en:

- **API Health Check**: http://localhost:8000/health
- **Documentación Swagger**: http://localhost:8000/docs
- **Documentación ReDoc**: http://localhost:8000/redoc

Si ves la documentación de la API, ¡felicidades! 🎉

## 🧪 Ejecutar Tests (Opcional)

```bash
# Ejecutar tests
uv run pytest

# Con cobertura
uv run pytest --cov=bsentinel
```

## 🛑 Detener los servicios

```bash
# Detener solo PostgreSQL
docker-compose down

# O si usaste docker-compose up para todo
docker-compose down
```

## 📝 Próximos Pasos

- Lee el archivo [PROGRESS.md](PROGRESS.md) para ver el estado del proyecto
- Revisa [docs/features/](docs/features/) para entender las funcionalidades planificadas
- La **Fase 1** está completa ✅
- La **Fase 2** (Base de Datos) es el siguiente paso

## ❓ Problemas Comunes

### Error: "uv: command not found"
- Cierra y vuelve a abrir la terminal después de instalar uv

### Error: "Cannot connect to Docker daemon"
- Asegúrate de que Docker Desktop está en ejecución

### Error: "Port 5432 already in use"
- Ya tienes PostgreSQL corriendo localmente
- Opción 1: Detén tu PostgreSQL local
- Opción 2: Cambia el puerto en `docker-compose.yml` y `secrets/.env`

### Error: "Port 8000 already in use"
- Ya tienes algo corriendo en el puerto 8000
- Cambia el puerto en `secrets/.env` (variable `PORT`)

## 📞 Soporte

Si encuentras problemas, revisa:
1. Los logs de Docker: `docker-compose logs`
2. Los logs de la aplicación en la terminal
3. El archivo [PROGRESS.md](PROGRESS.md) para el estado actual

---

**¡Disfruta desarrollando con Bsentinel! 📚✨**
