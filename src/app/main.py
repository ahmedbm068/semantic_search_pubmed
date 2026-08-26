import logging
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

import redis.asyncio as redis
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_limiter import FastAPILimiter
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.core.config import ROOT_DIR, settings
from src.app.core.logging import setup_logging
from src.app.core.ratelimit import OptionalRateLimiter
from src.app.routers.auth import router as auth_router
from src.app.routers.chat import router as chat_router
from src.app.routers.ingest import router as ingest_router
from src.app.routers.nhs_live import router as nhs_router
from src.app.routers.rewrite import router as rewrite_router
from src.app.routers.search import router as search_router

setup_logging()
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Replaces the deprecated @app.on_event("startup") hooks."""
    try:
        client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await client.ping()
        await FastAPILimiter.init(client)
        logger.info("Rate limiter initialised against %s", settings.redis_url)
    except Exception as exc:
        logger.warning("Redis unavailable (%s); rate limiting is disabled", exc)

    from src.app.db.bootstrap import ensure_core_tables

    try:
        await ensure_core_tables()
        logger.info("Database tables ensured")
    except Exception:
        logger.exception("Database bootstrap failed")

    yield

    try:
        await FastAPILimiter.close()
    except Exception:
        pass


app = FastAPI(
    title="PubMed Semantic Search",
    description="Hybrid (dense + BM25) semantic search over PubMed abstracts.",
    version="1.0.0",
    lifespan=lifespan,
)

# A wildcard origin cannot be combined with credentials -- browsers reject the
# response outright. Only send credentials when origins are explicitly listed.
allow_origins = settings.cors_origins or ["*"]
allow_credentials = allow_origins != ["*"]
if not settings.cors_origins and settings.is_prod:
    logger.warning("CORS_ORIGINS is unset in production; falling back to '*' without credentials")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((perf_counter() - start) * 1000)
            if response is not None:
                response.headers["X-Process-Time"] = f"{duration_ms}ms"
                response.headers["X-Request-ID"] = request_id
            logger.info(
                "http_access",
                extra={
                    "extra": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": getattr(response, "status_code", 500),
                        "duration_ms": duration_ms,
                        "client": request.client.host if request.client else None,
                    }
                },
            )


app.add_middleware(AccessLogMiddleware)

# Endpoints that run a model or reach out to the network are rate limited;
# auth and chat are cheap and already require a token.
expensive = [Depends(OptionalRateLimiter())]

app.include_router(auth_router, prefix="/v1", tags=["auth"])
app.include_router(chat_router, prefix="/v1")
app.include_router(search_router, prefix="/v1", tags=["search"], dependencies=expensive)
app.include_router(rewrite_router, prefix="/v1", tags=["rewrite"], dependencies=expensive)
app.include_router(nhs_router, dependencies=expensive)
app.include_router(ingest_router, prefix="/v1/ingest", tags=["ingest"])


@app.get("/health", tags=["health"])
async def health():
    """Liveness only -- deliberately does not touch the index, so it stays fast."""
    return {"ok": True}


@app.get("/v1/health", tags=["health"])
async def api_health():
    return {"ok": True}


@app.get("/v1/ready", tags=["health"])
async def ready():
    """Readiness: reports whether the index has been loaded yet."""
    from src.app.services.retriever import search_service

    return {"ok": True, "index_loaded": search_service.is_loaded}


# Mounted last so it never shadows an API route. Guarded because the Docker
# image does not necessarily ship the frontend.
_frontend = ROOT_DIR / "src" / "frontend"
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
else:
    logger.info("Frontend directory not found at %s; static files not mounted", _frontend)
