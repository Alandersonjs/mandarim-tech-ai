"""Routes for the spaced-repetition system (SM-2)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import TermNotFoundError
from app.schemas import SRSCardResponse, SRSDueResponse, SRSReviewRequest
from app.services import srs_service
from app.timeutils import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/srs", tags=["Spaced Repetition (SRS)"])

_DATABASE_ERROR = "Erro ao acessar os cartões de revisão. Tente novamente mais tarde."


def get_current_time() -> datetime:
    """Dependency that provides 'now' (UTC); tests override it to control the clock."""
    return utc_now()


@router.get("/due", response_model=SRSDueResponse, summary="List the cards due for review")
def list_due_cards(
    limit: int = Query(default=20, ge=1, le=100, description="Máximo de cartões retornados."),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_current_time),
) -> SRSDueResponse:
    """Return the cards whose next review date has arrived, oldest first."""
    try:
        cards, total_due = srs_service.get_due_cards(db, now, limit)
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing due cards.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_DATABASE_ERROR) from exc

    return SRSDueResponse(
        total_due=total_due,
        items=[SRSCardResponse.model_validate(card) for card in cards],
    )


@router.post("/review", response_model=SRSCardResponse, summary="Submit a review (SM-2)")
def review_card(
    payload: SRSReviewRequest,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_current_time),
) -> SRSCardResponse:
    """Grade a card (0-5), recalculate its SM-2 state and schedule the next review."""
    try:
        card = srs_service.review_card(db, payload.term_id, payload.grade, now)
    except TermNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Termo com id {exc.term_id} não encontrado.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Database error while reviewing term %s.", payload.term_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_DATABASE_ERROR) from exc

    return SRSCardResponse.model_validate(card)
