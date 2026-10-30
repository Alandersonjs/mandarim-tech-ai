"""Routes for the vocabulary."""

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.hsk import LEVEL_TARGETS
from app.models import HSKLevel, TermCategory
from app.schemas import HSKLevelsResponse, HSKLevelSummary, VocabularyListResponse, VocabularyTermRead
from app.services import vocabulary_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vocabulary", tags=["Vocabulary"])

_DATABASE_ERROR = "Erro ao consultar o vocabulário. Tente novamente mais tarde."


@router.get("", response_model=VocabularyListResponse, summary="List and filter vocabulary")
def list_vocabulary(
    category: TermCategory | None = Query(default=None, description="Filtra por categoria."),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Busca em português, Hanzi ou Pinyin (com ou sem tom: shùjùkù, shu4ju4ku4, shuju).",
    ),
    hsk_level: HSKLevel | None = Query(default=None, description="Nível do HSK 3.0 (ou HSK_TECH)."),
    is_handwriting_required: bool | None = Query(
        default=None, description="true: apenas termos de escrita obrigatória (书写字)."
    ),
    page: int = Query(default=1, ge=1, description="Número da página (começa em 1)."),
    page_size: int = Query(default=10, ge=1, le=100, description="Itens por página."),
    db: Session = Depends(get_db),
) -> VocabularyListResponse:
    """Return a paginated list of terms, filtered by category, HSK level, handwriting and text."""
    try:
        terms, total = vocabulary_service.list_terms(
            db,
            category=category,
            search=search,
            hsk_level=hsk_level,
            handwriting_required=is_handwriting_required,
            page=page,
            page_size=page_size,
        )
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing vocabulary.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_DATABASE_ERROR) from exc

    return VocabularyListResponse(
        items=[VocabularyTermRead.model_validate(term) for term in terms],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


# Declared before "/{term_id}" so that "hsk-levels" is not parsed as an id.
@router.get("/hsk-levels", response_model=HSKLevelsResponse, summary="HSK 3.0 levels and seeded coverage")
def list_hsk_levels(db: Session = Depends(get_db)) -> HSKLevelsResponse:
    """Return the cumulative word target of each HSK 3.0 level and how many terms are seeded."""
    try:
        counts = vocabulary_service.count_terms_by_level(db)
    except SQLAlchemyError as exc:
        logger.exception("Database error while counting terms by level.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_DATABASE_ERROR) from exc

    levels = [
        HSKLevelSummary(
            level=target.level,
            target_cumulative_words=target.cumulative_words,
            seeded_terms=counts.get(target.level.value, (0, 0))[0],
            handwriting_required_terms=counts.get(target.level.value, (0, 0))[1],
        )
        for target in LEVEL_TARGETS
    ]
    tech_total, tech_handwriting = counts.get(HSKLevel.TECH.value, (0, 0))
    levels.append(
        HSKLevelSummary(
            level=HSKLevel.TECH,
            target_cumulative_words=None,
            seeded_terms=tech_total,
            handwriting_required_terms=tech_handwriting,
        )
    )
    return HSKLevelsResponse(
        levels=levels,
        note=(
            "Metas acumuladas do HSK 3.0 em vigor desde julho de 2026 (300/500/1.000/2.000). "
            "Listas anteriores à revisão usam 500/1.272/2.245/3.245."
        ),
    )


@router.get("/{term_id}", response_model=VocabularyTermRead, summary="Get one term by id")
def get_vocabulary_term(term_id: int, db: Session = Depends(get_db)) -> VocabularyTermRead:
    """Return a single term, or 404 when it does not exist."""
    try:
        term = vocabulary_service.get_term_by_id(db, term_id)
    except SQLAlchemyError as exc:
        logger.exception("Database error while fetching term %s.", term_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_DATABASE_ERROR) from exc

    if term is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Termo com id {term_id} não encontrado.",
        )
    return VocabularyTermRead.model_validate(term)
