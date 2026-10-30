"""Shared fixtures: an isolated, already-seeded in-memory database for every test."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seeder import seed_vocabulary


@pytest.fixture()
def session_factory():
    """Fresh in-memory database, already seeded, for every test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # keeps one shared connection so the in-memory DB survives
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        # Empty handwriting list: tests must not depend on the data file contents.
        seed_vocabulary(db, handwriting_characters=frozenset())
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager on purpose: the lifespan (and the real DB) is skipped.
    yield TestClient(app)
    app.dependency_overrides.clear()
