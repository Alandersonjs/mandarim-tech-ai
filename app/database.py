"""Database engine, session factory and declarative base."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite needs this flag because FastAPI runs sync endpoints in a thread pool.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_is_current(bind: Engine) -> None:
    """Fail fast when an existing database was created by an older version.

    `create_all` never alters existing tables, so a database created before the
    HSK 3.0 columns were added would crash on the first query. Instead, we stop
    at startup with an actionable message.

    Raises:
        RuntimeError: if a table exists but lacks columns declared in the models.
    """
    inspector = inspect(bind)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue  # will be created by create_all
        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing_columns = sorted(column.name for column in table.columns if column.name not in existing_columns)
        if missing_columns:
            raise RuntimeError(
                f"Database schema is outdated: table '{table.name}' lacks the columns "
                f"{missing_columns}. Delete the database file (default: mandarim_tech.db) "
                "and restart, or migrate the table with Alembic."
            )
