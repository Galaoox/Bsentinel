"""Aplicación raíz de FastAPI para bsentinel."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bsentinel import settings
from bsentinel._logging import configure_logging
from bsentinel.application.services import (
    CatalogCommandService,
    CatalogQueryService,
    PricingQueryService,
    RetentionService,
    ScrapingService,
    SystemQueryService,
)
from bsentinel.exceptions import (
    EntityAlreadyExistsError,
    EntityDoesNotExistError,
    StandardException,
    UnsupportedStoreError,
    ValidationError,
)
from bsentinel.infrastructure.api.v1 import build_v1_router
from bsentinel.infrastructure.openlibrary import OpenLibraryClient
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryArchiveJobRepository,
    InMemoryBookRepository,
    InMemoryHistoryRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)
from bsentinel.infrastructure.scheduler import LocalScheduler
from bsentinel.infrastructure.scraping import BuscalibreScraper

in_memory_store = InMemoryStore()

book_repository = InMemoryBookRepository(in_memory_store)
store_repository = InMemoryStoreRepository(in_memory_store)
relation_repository = InMemoryRelationRepository(in_memory_store)
history_repository = InMemoryHistoryRepository(in_memory_store)
archive_job_repository = InMemoryArchiveJobRepository(in_memory_store)

catalog_command_service = CatalogCommandService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    metadata=OpenLibraryClient(),
)
catalog_query_service = CatalogQueryService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
)
scraping_service = ScrapingService(
    books=book_repository,
    relations=relation_repository,
    history=history_repository,
    scraper=BuscalibreScraper(),
)
pricing_query_service = PricingQueryService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    history=history_repository,
)
retention_service = RetentionService(jobs=archive_job_repository)
system_query_service = SystemQueryService(stores=store_repository)

scheduler = LocalScheduler(scraping_service)


def get_system_service() -> SystemQueryService:
    return system_query_service


def get_catalog_command_service() -> CatalogCommandService:
    return catalog_command_service


def get_catalog_query_service() -> CatalogQueryService:
    return catalog_query_service


def get_scraping_service() -> ScrapingService:
    return scraping_service


def get_pricing_service() -> PricingQueryService:
    return pricing_query_service


def get_retention_service() -> RetentionService:
    return retention_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    configure_logging()
    scheduler.start(interval_hours=settings.scheduler_scrape_interval_hours)
    app.state.store = in_memory_store
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
        {"name": "catalog", "description": "Gestión de catálogo de libros rastreados."},
        {"name": "pricing", "description": "Consulta de historial y comparación de precios."},
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


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@root_app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Añade un ID único a cada petición."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@root_app.exception_handler(StandardException)
async def standard_exception_handler(request: Request, exc: StandardException):
    """Mapea excepciones de negocio a contrato de error API."""
    if isinstance(exc, EntityDoesNotExistError):
        return _error_response(request, status_code=404, code="ENTITY_NOT_FOUND", message=str(exc))
    if isinstance(exc, EntityAlreadyExistsError):
        return _error_response(request, status_code=409, code="ENTITY_ALREADY_EXISTS", message=str(exc))
    if isinstance(exc, UnsupportedStoreError):
        return _error_response(request, status_code=400, code="UNSUPPORTED_STORE", message=str(exc))
    if isinstance(exc, ValidationError):
        return _error_response(request, status_code=400, code="VALIDATION_ERROR", message=str(exc))
    return _error_response(request, status_code=400, code="STANDARD_ERROR", message=str(exc))


@root_app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return _error_response(
        request,
        status_code=422,
        code="REQUEST_VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


@root_app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=str(detail["code"]),
            message=str(detail["message"]),
            details=detail.get("details") if isinstance(detail.get("details"), dict) else {},
        )

    return _error_response(
        request,
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=str(detail),
    )


@root_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Maneja excepciones globales."""
    return _error_response(
        request,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="Internal server error",
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
        "message": "Welcome to Bsentinel API",
        "version": settings.app_version,
        "docs": "/docs",
    }


root_app.include_router(common_router)
root_app.include_router(
    build_v1_router(
        get_system_service,
        get_catalog_command_service,
        get_catalog_query_service,
        get_scraping_service,
        get_pricing_service,
        get_retention_service,
    )
)
