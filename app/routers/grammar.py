"""Routes for the Sentence Compiler / HSK Task Evaluator."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CompileRequest, CompileResponse
from app.services.grammar_service import SentenceCompilerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/grammar", tags=["Sentence Compiler"])


@router.post(
    "/compile",
    response_model=CompileResponse,
    summary="Assemble S + T + L + V + O pieces (Hanzi or Pinyin) and validate them",
)
def compile_sentence(payload: CompileRequest, db: Session = Depends(get_db)) -> CompileResponse:
    """Assemble the pieces into a sentence and return Hanzi, Pinyin, syllables and HSK checks."""
    try:
        return SentenceCompilerService(db).compile(payload)
    except SQLAlchemyError as exc:
        logger.exception("Database error in /api/grammar/compile.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao consultar o vocabulário. Tente novamente mais tarde.",
        ) from exc
