"""Web-document ingestion.

Previously this endpoint (and its byte-identical twin `ingest_web.py`) accepted
documents, `print()`ed a count and discarded them, so callers got a success
response for data that was never stored. Documents are now appended to a JSONL
staging file that `build_index` can consume.
"""
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.app.core.config import ROOT_DIR
from src.app.core.security import get_current_user
from src.app.models.user import User

logger = logging.getLogger("app.ingest")
router = APIRouter()

STAGING_PATH = ROOT_DIR / "data" / "scraped" / "ingested_web.jsonl"


class WebDoc(BaseModel):
    title: str = Field(..., max_length=1000)
    text: str = Field(..., min_length=1)
    url: str = Field(..., max_length=2000)
    source: str = Field(default="web")


class WebIngest(BaseModel):
    docs: list[WebDoc] = Field(..., max_length=1000)


@router.post("/web", status_code=status.HTTP_202_ACCEPTED)
async def ingest_web(payload: WebIngest, current_user: User = Depends(get_current_user)):
    """Stage documents for the next index build. Requires authentication."""
    if not payload.docs:
        return {"received": 0, "staged": 0}

    received_at = datetime.now(UTC).isoformat()
    try:
        STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STAGING_PATH, "a", encoding="utf-8") as f:
            for doc in payload.docs:
                record = doc.model_dump()
                record["received_at"] = received_at
                record["received_by"] = current_user.email
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.exception("Failed to stage ingested documents")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not stage documents",
        ) from exc

    logger.info("Staged %d documents to %s", len(payload.docs), STAGING_PATH)
    return {
        "received": len(payload.docs),
        "staged": len(payload.docs),
        "staging_file": str(STAGING_PATH.relative_to(ROOT_DIR)),
    }
