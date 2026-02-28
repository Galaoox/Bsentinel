"""Aplicación raíz de FastAPI para bsentinel."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLArchiveJobRepository,
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
    session_scope,
)
from bsentinel.infrastructure.scheduler import LocalScheduler
from bsentinel.infrastructure.scraping import BuscalibreScraper

in_memory_store = InMemoryStore()
metadata_client = OpenLibraryClient()
scraper_client = BuscalibreScraper()

book_repository = InMemoryBookRepository(in_memory_store)
store_repository = InMemoryStoreRepository(in_memory_store)
relation_repository = InMemoryRelationRepository(in_memory_store)
history_repository = InMemoryHistoryRepository(in_memory_store)
archive_job_repository = InMemoryArchiveJobRepository(in_memory_store)

catalog_command_service = CatalogCommandService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    metadata=metadata_client,
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
    scraper=scraper_client,
)
pricing_query_service = PricingQueryService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    history=history_repository,
)
retention_service = RetentionService(jobs=archive_job_repository)
system_query_service = SystemQueryService(stores=store_repository)


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in session_scope():
        yield session


async def get_optional_session() -> AsyncIterator[AsyncSession | None]:
    if settings.persistence_backend == "in_memory":
        yield None
        return
    async for session in session_scope():
        yield session


def _build_sql_services(session: AsyncSession) -> dict[str, Any]:
    books = SQLBookRepository(session)
    stores = SQLStoreRepository(session)
    relations = SQLRelationRepository(session)
    history = SQLHistoryRepository(session)
    jobs = SQLArchiveJobRepository(session)

    return {
        "system": SystemQueryService(stores=stores),
        "catalog_command": CatalogCommandService(
            books=books,
            stores=stores,
            relations=relations,
            metadata=metadata_client,
        ),
        "catalog_query": CatalogQueryService(
            books=books,
            stores=stores,
            relations=relations,
        ),
        "scraping": ScrapingService(
            books=books,
            relations=relations,
            history=history,
            scraper=scraper_client,
        ),
        "pricing": PricingQueryService(
            books=books,
            stores=stores,
            relations=relations,
            history=history,
        ),
        "retention": RetentionService(jobs=jobs),
    }


async def get_system_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> SystemQueryService:
    if settings.persistence_backend == "in_memory":
        return system_query_service
    assert session is not None
    return _build_sql_services(session)["system"]


async def get_catalog_command_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> CatalogCommandService:
    if settings.persistence_backend == "in_memory":
        return catalog_command_service
    assert session is not None
    return _build_sql_services(session)["catalog_command"]


async def get_catalog_query_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> CatalogQueryService:
    if settings.persistence_backend == "in_memory":
        return catalog_query_service
    assert session is not None
    return _build_sql_services(session)["catalog_query"]


async def get_scraping_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ScrapingService:
    if settings.persistence_backend == "in_memory":
        return scraping_service
    assert session is not None
    return _build_sql_services(session)["scraping"]


async def get_pricing_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> PricingQueryService:
    if settings.persistence_backend == "in_memory":
        return pricing_query_service
    assert session is not None
    return _build_sql_services(session)["pricing"]


async def get_retention_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> RetentionService:
    if settings.persistence_backend == "in_memory":
        return retention_service
    assert session is not None
    return _build_sql_services(session)["retention"]


async def run_scraping_batch() -> int:
    if settings.persistence_backend == "in_memory":
        return await scraping_service.scrape_all_active()

    async for session in session_scope():
        services = _build_sql_services(session)
        return await services["scraping"].scrape_all_active()
    return 0


scheduler = LocalScheduler(run_scraping_batch)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    configure_logging()
    scheduler.start(interval_hours=settings.scheduler_scrape_interval_hours)
    app.state.scheduler = scheduler
    if settings.persistence_backend == "in_memory":
        app.state.store = in_memory_store
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
        "db": "in-memory" if settings.persistence_backend == "in_memory" else "sqlalchemy",
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
