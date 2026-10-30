"""The app must refuse to start on a database created by the pre-HSK schema."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.database import Base, ensure_schema_is_current


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_outdated_table_raises_actionable_error():
    engine = _engine()
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE vocabulary_terms (id INTEGER PRIMARY KEY, hanzi VARCHAR(60))"))

    with pytest.raises(RuntimeError, match="Delete the database file"):
        ensure_schema_is_current(engine)


def test_empty_or_current_database_passes():
    engine = _engine()
    ensure_schema_is_current(engine)  # no tables yet: create_all will build them
    Base.metadata.create_all(bind=engine)
    ensure_schema_is_current(engine)  # up to date
