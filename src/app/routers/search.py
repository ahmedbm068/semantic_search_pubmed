import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.app.core.config import settings
from src.app.services.retriever import IndexUnavailable, search_service

logger = logging.getLogger("app.search")
router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    k: int = Field(default=10, ge=1, le=settings.max_top_k)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    hybrid: bool | None = Field(
        default=None, description="Override HYBRID_ENABLED for this request."
    )
    rerank: bool | None = Field(
        default=None, description="Override RERANK_ENABLED for this request."
    )


class SearchHit(BaseModel):
    id: int
    score: float
    text: str
    meta: dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    k: int
    count: int
    results: list[SearchHit]


def _run_search(
    q: str, k: int, min_score: float, hybrid: bool | None, rerank: bool | None
) -> SearchResponse:
    try:
        hits = search_service.search(q, k=k, min_score=min_score, hybrid=hybrid, rerank=rerank)
    except IndexUnavailable as exc:
        # A misconfigured or missing index is an operator problem, not a client
        # one, and the message is safe to surface: it names no internals.
        logger.error("Index unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:
        # Never echo str(exc) to the client: it leaks file paths and stack detail.
        logger.exception("Search failed for query=%r", q)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search failed"
        ) from exc
    return SearchResponse(query=q, k=k, count=len(hits), results=hits)


@router.get("/search", response_model=SearchResponse)
def search_get(
    q: str = Query(..., min_length=1, max_length=2000),
    k: int = Query(default=10, ge=1, le=settings.max_top_k),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    hybrid: bool | None = Query(default=None),
    rerank: bool | None = Query(default=None),
) -> SearchResponse:
    return _run_search(q, k, min_score, hybrid, rerank)


@router.post("/search", response_model=SearchResponse)
def search_post(req: SearchRequest) -> SearchResponse:
    return _run_search(req.query, req.k, req.min_score, req.hybrid, req.rerank)


@router.get("/search/stats")
def search_stats() -> dict[str, Any]:
    """Index/model provenance. Useful for confirming which model is actually serving."""
    return search_service.stats()
