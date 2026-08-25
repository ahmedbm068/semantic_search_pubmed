from pathlib import Path
import os

from .session import engine, DATABASE_URL
from src.app.db.base import Base
from src.app.models import *  # noqa: F401,F403


async def ensure_core_tables():
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            Path(db_dir).mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
