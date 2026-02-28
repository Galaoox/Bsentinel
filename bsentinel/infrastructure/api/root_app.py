"""Aplicación raíz de FastAPI para bsentinel."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bsentinel import settings
from bsentinel._logging import configure_logging
from bsentinel.application import BookService, InMemoryRepository
from bsentinel.infrastructure.api.v1 import build_v1_router
from bsentinel.infrastructure.openlibrary import OpenLibraryClient
from bsentinel.infrastructure.scheduler import LocalScheduler
from bsentinel.infrastructure.scraping import BuscalibreScraper

repository = InMemoryRepository()
book_service = BookService(repository=repository, scraper=BuscalibreScraper(), openlibrary=OpenLibraryClient())
scheduler = LocalScheduler(book_service)


def get_book_service() -> BookService:
    return book_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    configure_logging()
    scheduler.start(interval_hours=settings.scheduler_scrape_interval_hours)
    app.state.repository = repository
    app.state.book_service = book_service
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown()


root_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Sistema de rastreo de precios de libros mediante web scraping",
    openapi_tags=[
        {"name": "Root", "description": "Punto de entrada base de la API."},
        {"name": "Health", "description": "Estado operativo del servicio y dependencias."},
        {"name": "system", "description": "Información del estado y capacidades de la versión v1."},
        {"name": "books", "description": "Gestión de libros rastreados (alta, consulta, baja y restauración)."},
        {"name": "history", "description": "Consulta de historial de precios y comparación por libro."},
        {"name": "retention", "description": "Operaciones de archivado y estado de jobs de retención."},
    ],
    lifespan=lifespan,
)

root_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@root_app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Añade un ID único a cada petición."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@root_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Maneja excepciones globales."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


common_router = APIRouter()


@common_router.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de health check."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "db": "in-memory",
        "scraping": "ready",
        "openlibrary": "ready",
    }


@common_router.get("/", tags=["Root"])
async def root():
    """Endpoint raíz."""
    return {
        "message": "Bienvenido a Bsentinel API",
        "version": settings.app_version,
        "docs": "/docs",
    }


root_app.include_router(common_router)
root_app.include_router(build_v1_router(get_book_service))
