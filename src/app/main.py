from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis
from time import perf_counter
import os
import uuid
import logging

from .core.logging import setup_logging
from .routers.search import router as search_router
from .routers.ingest import router as ingest_router
from .routers.rewrite import router as rewrite_router
from .routers.auth import router as auth_router
from .routers.rate import router as rate_router
from .routers.chat import router as chat_router
from .routers.nhs_live import router as nhs_router
from .routers.ingest_web import router as ingest_web_router  # NEW

setup_logging()
app = FastAPI(title="Semantic API")


def _parse_origins(v: str):
    if not v:
        return ["*"]
    return [x.strip() for x in v.split(",") if x.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(os.getenv("CORS_ORIGINS", "")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("app")


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        start = perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            dur_ms = int((perf_counter() - start) * 1000)
            if response is not None:
                response.headers["X-Process-Time"] = f"{dur_ms}ms"
            logger.info(
                "http_access",
                extra={
                    "extra": {
                        "request_id": rid,
                        "method": request.method,
                        "path": request.url.path,
                        "status": getattr(response, "status_code", 500),
                        "duration_ms": dur_ms,
                        "client": request.client.host if request.client else None,
                    }
                },
            )


app.add_middleware(AccessLogMiddleware)


@app.on_event("startup")
async def _init_rate_limiter():
    logger = logging.getLogger("app")
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(url, encoding="utf-8", decode_responses=True)
        pong = await r.ping()
        if not pong:
            logger.warning("Redis ping returned False at %s", url)
        await FastAPILimiter.init(r)
        logger.info("FastAPI-Limiter initialized with Redis at %s", url)
    except Exception as e:
        logger.warning("FastAPI-Limiter init failed: %s", e)

    from .db.bootstrap import ensure_core_tables

    try:
        await ensure_core_tables()
        logger.info("DB bootstrap: core tables ensured")
    except Exception as e:
        logger.exception("DB bootstrap failed: %s", e)


app.include_router(auth_router, prefix="/v1", tags=["auth"])
app.include_router(rate_router, prefix="/v1", tags=["rate"])
app.include_router(search_router, prefix="/v1", tags=["search"])
app.include_router(ingest_router, prefix="/v1", tags=["ingest"])
app.include_router(rewrite_router, prefix="/v1", tags=["rewrite"])
app.include_router(chat_router, prefix="/v1")
app.include_router(nhs_router)
app.include_router(ingest_web_router, prefix="/v1/ingest", tags=["ingest"])  # NEW


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/v1/health")
async def api_health():
    return {"ok": True}


app.mount("/", StaticFiles(directory="src/frontend", html=True), name="frontend")
