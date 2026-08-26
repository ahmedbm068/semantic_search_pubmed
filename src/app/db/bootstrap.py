from src.app.db.base import Base
from src.app.db.session import engine
from src.app.models import *  # noqa: F401,F403  (registers mappers on Base.metadata)


async def ensure_core_tables() -> None:
    """Create any missing tables.

    Fine for dev/SQLite. For schema *changes* on a real database, use Alembic --
    create_all never alters an existing table.
    """
    Base.metadata.create_all(bind=engine)
