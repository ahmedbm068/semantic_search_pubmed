from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..scraper.nhs_live import fetch_nhs_for_query, fetch_nhs_chunks_for_query

router = APIRouter(prefix="/v1/nhs", tags=["nhs"])


class NHSQuery(BaseModel):
    query: str


class NHSSearchQuery(BaseModel):
    query: str
    k: int = 10


# -------- LIVE (single article) --------

@router.get("/live")
def nhs_live_get(query: str):
    article = fetch_nhs_for_query(query)
    if article is None:
        raise HTTPException(status_code=404, detail="No matching NHS article found")
    return article


@router.post("/live")
def nhs_live_post(payload: NHSQuery):
    article = fetch_nhs_for_query(payload.query)
    if article is None:
        raise HTTPException(status_code=404, detail="No matching NHS article found")
    return article


# -------- SEARCH (paragraph chunks) --------

@router.get("/search")
def nhs_search_get(query: str, k: int = 10) -> List[dict]:
    results = fetch_nhs_chunks_for_query(query, k)
    return results


@router.post("/search")
def nhs_search_post(payload: NHSSearchQuery) -> List[dict]:
    results = fetch_nhs_chunks_for_query(payload.query, payload.k)
    return results
