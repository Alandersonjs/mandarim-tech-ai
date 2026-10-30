"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 - import registers the ORM models on Base.metadata
from app.config import get_settings
from app.database import Base, SessionLocal, engine, ensure_schema_is_current
from app.routers import ai_coach, grammar, srs, tts, vocabulary
from app.seeder import seed_vocabulary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables and load the initial vocabulary on startup."""
    try:
        ensure_schema_is_current(engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_vocabulary(db)
    except Exception:
        logger.exception("Failed to initialise the database. Aborting startup.")
        raise
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API de apoio ao aprendizado de mandarim (HSK 3.0) com foco em vocabulário técnico de TI, ERP e Negócios. Pinyin é cidadão de primeira classe; revisão espaçada (SM-2) e áudio neural (TTS) para retenção e compreensão auditiva.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(vocabulary.router)
app.include_router(grammar.router)
app.include_router(ai_coach.router)
app.include_router(srs.router)
app.include_router(tts.router)


@app.get("/health", tags=["Health"], summary="Health check")
def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}
