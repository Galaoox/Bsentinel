"""Aplicación raíz de FastAPI para bsentinel."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bsentinel import settings
from bsentinel._logging import configure_logging
from bsentinel._logging_context import reset_request_id, set_request_id
from bsentinel.application.services import (
    AuthService,
    CatalogCommandService,
    CatalogQueryService,
    PricingQueryService,
    RetentionService,
    ScrapingService,
    SystemQueryService,
)
from bsentinel.application.services.catalog_bulk import CatalogBulkService
from bsentinel.application.services.scraping_batch import ScrapingBatch
from bsentinel.application.services.traffic_context import traffic_context
from bsentinel.exceptions import (
    AuthenticationError,
    BulkItemError,
    EntityAlreadyExistsError,
    EntityDoesNotExistError,
    ForbiddenError,
    ScrapingError,
    StandardException,
    UnsupportedStoreError,
    ValidationError,
)
from bsentinel.infrastructure.api.v1 import build_v1_router
from bsentinel.infrastructure.api.v1.traffic import build_traffic_router
from bsentinel.infrastructure.openlibrary import OpenLibraryClient
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryArchiveJobRepository,
    InMemoryBookRepository,
    InMemoryHistoryRepository,
    InMemoryRefreshTokenRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)
from bsentinel.infrastructure.persistence.in_memory.transactions import InMemoryCatalogTransaction
from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLArchiveJobRepository,
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRefreshTokenRepository,
    SQLRelationRepository,
    SQLStoreRepository,
    session_scope,
)
from bsentinel.infrastructure.persistence.sqlalchemy.transactions import SQLCatalogTransaction
from bsentinel.infrastructure.persistence.store_blocks import SQLBlockPersistence
from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository
from bsentinel.infrastructure.scheduler import LocalScheduler
from bsentinel.infrastructure.scraping import ConfiguredStoreScraper, build_scraping_runtime
from bsentinel.infrastructure.scraping.sanitization import sanitize_proxy_observable
from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence, StoreGuard
from bsentinel.infrastructure.security import JWTTokenManager

logger = logging.getLogger(__name__)

in_memory_store = InMemoryStore()
metadata_client = OpenLibraryClient()
scraping_runtime = build_scraping_runtime(settings)
browser_session = scraping_runtime


async def _persist_traffic(event):
    if settings.persistence_backend == 'in_memory':
        raise RuntimeError('Traffic requires SQL persistence')
    async with asynccontextmanager(session_scope)() as session:
        await SQLTrafficRepository(session).add(event)


if hasattr(getattr(scraping_runtime, 'backend', None), 'traffic_sink'):
    scraping_runtime.backend.traffic_sink = _persist_traffic

store_guard = StoreGuard(
    MemoryBlockPersistence() if settings.persistence_backend == "in_memory"
    else SQLBlockPersistence(lambda: asynccontextmanager(session_scope)()),
    cooldown_minutes=settings.scraping_block_cooldown_minutes,
)

scraper_client = ConfiguredStoreScraper(
    store_guard=store_guard,
    browser_session=scraping_runtime,
    transient_retry_attempts=settings.scraping_http_transient_retry_attempts,
    transient_retry_delay_ms=settings.scraping_http_transient_retry_delay_ms,
)
token_manager = JWTTokenManager(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
)

book_repository = InMemoryBookRepository(in_memory_store)
store_repository = InMemoryStoreRepository(in_memory_store)
relation_repository = InMemoryRelationRepository(in_memory_store)
history_repository = InMemoryHistoryRepository(in_memory_store)
archive_job_repository = InMemoryArchiveJobRepository(in_memory_store)
refresh_token_repository = InMemoryRefreshTokenRepository(in_memory_store)

catalog_command_service = CatalogCommandService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    metadata=metadata_client,
    scraper=scraper_client,
)
catalog_query_service = CatalogQueryService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
)
scraping_service = ScrapingService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    history=history_repository,
    scraper=scraper_client,
    refresh_relation=lambda relation: _refresh_relation(relation),
)
pricing_query_service = PricingQueryService(
    books=book_repository,
    stores=store_repository,
    relations=relation_repository,
    history=history_repository,
)
retention_service = RetentionService(jobs=archive_job_repository)
system_query_service = SystemQueryService(stores=store_repository)
auth_service = AuthService(
    admin_username=settings.auth_admin_username,
    admin_password=settings.auth_admin_password,
    token_manager=token_manager,
    refresh_tokens=refresh_token_repository,
    access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in session_scope():
        yield session


async def get_optional_session() -> AsyncIterator[AsyncSession | None]:
    if settings.persistence_backend == "in_memory":
        yield None
        return
    async for session in session_scope():
        yield session


async def get_traffic_repository(session=Depends(get_optional_session)):
    if session is None:
        raise HTTPException(503, 'Traffic reporting requires SQL persistence')
    return SQLTrafficRepository(session)


def _build_sql_services(session: AsyncSession) -> dict[str, Any]:
    books = SQLBookRepository(session)
    stores = SQLStoreRepository(session)
    relations = SQLRelationRepository(session)
    history = SQLHistoryRepository(session)
    jobs = SQLArchiveJobRepository(session)
    refresh_tokens = SQLRefreshTokenRepository(session)

    return {
        "system": SystemQueryService(stores=stores),
        "auth": AuthService(
            admin_username=settings.auth_admin_username,
            admin_password=settings.auth_admin_password,
            token_manager=token_manager,
            refresh_tokens=refresh_tokens,
            access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
        ),
        "catalog_command": CatalogCommandService(
            books=books,
            stores=stores,
            relations=relations,
            metadata=metadata_client,
            scraper=scraper_client,
        ),
        "catalog_query": CatalogQueryService(
            books=books,
            stores=stores,
            relations=relations,
        ),
        "scraping": ScrapingService(
            books=books,
            stores=stores,
            relations=relations,
            history=history,
            scraper=scraper_client,
            refresh_relation=lambda relation: _refresh_relation(relation),
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


async def get_catalog_bulk_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> CatalogBulkService:
    if settings.persistence_backend == "in_memory":
        transaction = InMemoryCatalogTransaction(in_memory_store)
        books = InMemoryBookRepository(transaction.working)
        stores = InMemoryStoreRepository(transaction.working)
        relations = InMemoryRelationRepository(transaction.working)
        history = InMemoryHistoryRepository(transaction.working)
        command = CatalogCommandService(books=books, stores=stores, relations=relations,
                                        metadata=metadata_client, scraper=scraper_client)
        scraping = ScrapingService(books=books, stores=stores, relations=relations,
                                  history=history, scraper=scraper_client)
        return CatalogBulkService(command, scraping, transaction)
    assert session is not None
    services = _build_sql_services(session)
    return CatalogBulkService(services["catalog_command"], services["scraping"], SQLCatalogTransaction(session))


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


async def get_auth_service(
    session: AsyncSession | None = Depends(get_optional_session),
) -> AuthService:
    if settings.persistence_backend == "in_memory":
        return auth_service
    assert session is not None
    return _build_sql_services(session)["auth"]


@asynccontextmanager
async def _scraping_repositories():
    if settings.persistence_backend == "in_memory":
        # No HTTP occurs inside this optimistic, short context.
        async with InMemoryCatalogTransaction(in_memory_store) as transaction:
            working = transaction.working
            yield SimpleNamespace(books=InMemoryBookRepository(working), stores=InMemoryStoreRepository(working), relations=InMemoryRelationRepository(working), history=InMemoryHistoryRepository(working))
    else:
        # Wrap the actual async generator: commit/rollback/close finish before exit.
        async with asynccontextmanager(session_scope)() as session:
            yield _build_sql_services(session)["scraping"]


async def _refresh_relation(relation):
    from bsentinel.domain.models import now_utc
    with traffic_context(scope='manual', relation_id=str(relation.id), operation_id=str(uuid.uuid4())):
        await RelationProcessor(_scraping_repositories, scraper_client).process(relation, now_utc(), force=True)
    async with _scraping_repositories() as repos:
        current = await repos.relations.get(relation.id)
    if current is not None:
        relation.current_price = current.current_price
        relation.status = current.status
        relation.last_checked = current.last_checked
        relation.next_check_at = current.next_check_at
        relation.scrape_generation = current.scrape_generation


async def _process_due_relation(candidate, cutoff):
    return await RelationProcessor(_scraping_repositories, scraper_client).process(candidate, cutoff)


async def _list_due_relations(cutoff, limit, after):
    return await RelationProcessor(_scraping_repositories, scraper_client).list_page(cutoff, limit, after)


scraping_batch = ScrapingBatch(_list_due_relations, _process_due_relation)


async def run_scraping_batch() -> int:
    summary = await scraping_batch.run()
    logger.info("Scraping runtime budget", extra={"peak_fetches": getattr(scraping_runtime, "peak_active", None), "concurrency": settings.scraping_concurrency})
    return summary.successful


scheduler = LocalScheduler(run_scraping_batch)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    configure_logging()
    await scraping_runtime.start()
    app.state.scraping_runtime = scraping_runtime
    scheduler.start(tick_minutes=settings.scheduler_scrape_tick_minutes)
    logger.info("Scraping schedule ready", extra={
        "timezone": "America/Bogota", "local_hours": "8,17", "cohort_minutes": "0,20,40",
        "scrape_groups": 3, "concurrency": settings.scraping_concurrency, "daily_reviews": 2,
        "block_cooldown_minutes": settings.scraping_block_cooldown_minutes,
    })
    app.state.scheduler = scheduler
    if settings.persistence_backend == "in_memory":
        app.state.store = in_memory_store
    try:
        yield
    finally:
        await scheduler.aclose()
        await scraping_runtime.close()


root_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Sistema de rastreo de precios de libros mediante web scraping",
    openapi_tags=[
        {"name": "Root", "description": "Punto de entrada base de la API."},
        {"name": "Health", "description": "Estado operativo del servicio y dependencias."},
        {"name": "auth", "description": "Autenticación JWT y gestión de tokens."},
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
        headers={"X-Request-ID": str(getattr(request.state, "request_id", ""))},
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
    token = set_request_id(request_id)
    try:
        with traffic_context(scope='catalog', operation_id=request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_request_id(token)


@root_app.exception_handler(StandardException)
async def standard_exception_handler(request: Request, exc: StandardException):
    """Mapea excepciones de negocio a contrato de error API."""
    if isinstance(exc, BulkItemError):
        response = await standard_exception_handler(request, exc.cause)
        content = json.loads(bytes(response.body))
        content["error"]["details"].update({
            "index": exc.index, "url": sanitize_proxy_observable(exc.url),
        })
        return JSONResponse(status_code=response.status_code,
                            headers={"X-Request-ID": response.headers["X-Request-ID"]}, content=content)
    if isinstance(exc, ScrapingError):
        safe_message = str(sanitize_proxy_observable(str(exc)))
        safe_diagnostics = sanitize_proxy_observable(getattr(exc, "diagnostics", {}))
        logger.warning(
            "Scraping request failed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "method": request.method,
                "path": str(request.url.path),
                "error_code": "SCRAPING_ERROR",
                "error_message": safe_message,
                "scraping_reason": getattr(exc, "reason", None),
                "scraping_diagnostics": safe_diagnostics,
            },
        )
        return _error_response(
            request,
            status_code=400,
            code="SCRAPING_ERROR",
            message=safe_message,
            details={
                "scraping_reason": getattr(exc, "reason", None),
                "scraping_diagnostics": safe_diagnostics,
            },
        )
    if isinstance(exc, EntityDoesNotExistError):
        return _error_response(request, status_code=404, code="ENTITY_NOT_FOUND", message=str(exc))
    if isinstance(exc, EntityAlreadyExistsError):
        return _error_response(request, status_code=409, code="ENTITY_ALREADY_EXISTS", message=str(exc))
    if isinstance(exc, UnsupportedStoreError):
        return _error_response(request, status_code=400, code="UNSUPPORTED_STORE", message=str(exc))
    if isinstance(exc, ValidationError):
        return _error_response(request, status_code=400, code="VALIDATION_ERROR", message=str(exc))
    if isinstance(exc, AuthenticationError):
        return _error_response(
            request,
            status_code=401,
            code=getattr(exc, "code", "AUTH_ERROR"),
            message=str(exc),
        )
    if isinstance(exc, ForbiddenError):
        return _error_response(
            request,
            status_code=403,
            code=getattr(exc, "code", "AUTH_FORBIDDEN"),
            message=str(exc),
        )
    return _error_response(request, status_code=400, code="STANDARD_ERROR", message=str(exc))


@root_app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return _error_response(
        request,
        status_code=422,
        code="REQUEST_VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": sanitize_proxy_observable([
            {
                **{key: value for key, value in error.items() if key != "input"},
                **({"ctx": {key: str(value) for key, value in error["ctx"].items()}}
                   if "ctx" in error else {}),
            }
            for error in exc.errors()
        ])},
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
        "scraping": "ready" if scraping_runtime.is_started else "not_initialized",
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
root_app.include_router(build_traffic_router(get_traffic_repository, get_auth_service))
root_app.include_router(
    build_v1_router(
        get_system_service,
        get_catalog_command_service,
        get_catalog_query_service,
        get_scraping_service,
        get_pricing_service,
        get_retention_service,
        get_auth_service,
        get_catalog_bulk_service,
    )
)
