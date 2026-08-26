from fastapi import APIRouter
from pydantic import BaseModel

from ..models.rewrite_model import correct_text

router = APIRouter()

class Payload(BaseModel):
    text: str

@router.post("/rewrite")
def rewrite(p: Payload):
    return correct_text(p.text)
