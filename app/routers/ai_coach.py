"""Routes for the AI Conversation Coach."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import InputNotUnderstoodError, LLMServiceError, PinyinConversionError
from app.schemas import CoachRequest, CoachResponse
from app.services.ai_coach_service import AICoachService
from app.services.llm_client import LLMClient, MockLLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Conversation Coach"])


def get_llm_client() -> LLMClient:
    """Dependency that provides the LLM adapter.

    Swap `MockLLMClient` for a real provider adapter here (or override this
    dependency in tests) without touching the rest of the code.
    """
    return MockLLMClient()


@router.post(
    "/coach",
    response_model=CoachResponse,
    summary="Analyse a Mandarin sentence (Hanzi or raw Pinyin) and get feedback in Portuguese",
)
def coach_sentence(
    payload: CoachRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> CoachResponse:
    """Receive a sentence in Mandarin and return grammar, Pinyin and explanation."""
    service = AICoachService(db=db, llm_client=llm_client)
    try:
        return service.analyze(payload.sentence)
    except PinyinConversionError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Não consegui converter para Hanzi: {', '.join(exc.unresolved)}. "
                "Envie a frase em Hanzi ou use palavras do vocabulário (GET /api/vocabulary)."
            ),
        ) from exc
    except InputNotUnderstoodError as exc:
        raise HTTPException(
            status_code=422,
            detail="A frase deve estar em Hanzi ou em Pinyin válido.",
        ) from exc
    except LLMServiceError as exc:
        logger.exception("LLM provider failure in /api/ai/coach.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O serviço de IA está indisponível no momento. Tente novamente em instantes.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Database error in /api/ai/coach.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao consultar o vocabulário. Tente novamente mais tarde.",
        ) from exc
