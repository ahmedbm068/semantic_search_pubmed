from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from ..services.retriever import retriever_singleton

router = APIRouter(tags=["search"])

class SearchReq(BaseModel):
    query: str
    k: int = 10
    min_score: float = 0.0

def _run_search(q: str, k: int, min_score: float = 0.0):
    try:
        hits = retriever_singleton.topk(q, k)
        filtered = [h for h in hits if h.get("score", 0.0) >= min_score]
        return {"query": q, "k": k, "results": filtered}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
def search_get(q: str = Query(..., min_length=1), k: int = 10, min_score: float = 0.0):
    return _run_search(q, k, min_score)

@router.post("/search")
def search_post(req: SearchReq):
    return _run_search(req.query, req.k, req.min_score)
