from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.core.config import settings


def _sync_url(url: str) -> str:
    """The app uses a synchronous engine; strip async drivers if configured.

    The old .env.example shipped `sqlite+aiosqlite://`, which create_engine
    rejects outright. Normalising here means a stale .env degrades to a working
    sync driver instead of crashing at import.
    """
    for async_driver, sync_driver in (
        ("sqlite+aiosqlite", "sqlite"),
        ("postgresql+asyncpg", "postgresql+psycopg"),
        ("mysql+aiomysql", "mysql+pymysql"),
    ):
        if url.startswith(async_driver):
            return url.replace(async_driver, sync_driver, 1)
    return url


DATABASE_URL = _sync_url(settings.database_url)

engine_kwargs: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    # FastAPI serves requests across threads; SQLite objects are thread-bound.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    # Make sure the parent directory exists before SQLite tries to open the file.
    db_path = DATABASE_URL.split("sqlite:///", 1)[-1]
    if db_path and db_path != ":memory:":
        Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
