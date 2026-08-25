from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()


class WebDoc(BaseModel):
    title: str
    text: str
    url: str
    source: str = "nhs_scraper"


class WebIngest(BaseModel):
    docs: List[WebDoc]


@router.post("/web")
async def ingest_web(payload: WebIngest):
    docs = payload.docs
    print(f"Received {len(docs)} docs from n8n")
    return {"received": len(docs)}
