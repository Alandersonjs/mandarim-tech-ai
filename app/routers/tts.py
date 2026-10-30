"""Routes for neural text-to-speech."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.exceptions import TTSServiceError, TTSTimeoutError
from app.services.tts_service import TTSService, Voice, validate_rate
from app.text_utils import contains_hanzi

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["Text-to-Speech"])


def get_tts_service() -> TTSService:
    """Dependency that provides the TTS service (tests override it with a fake)."""
    settings = get_settings()
    return TTSService(Path(settings.tts_cache_dir), settings.tts_timeout_seconds)


@router.get(
    "/generate",
    response_class=FileResponse,
    responses={200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio of the text."}},
    summary="Generate Mandarin speech (MP3) with a neural voice",
)
async def generate_speech(
    text: str = Query(min_length=1, max_length=300, description="Texto em Hanzi.", examples=["你好，我是程序员。"]),
    voice: Voice = Query(default=Voice.FEMALE, description="female = Xiaoxiao, male = Yunxi."),
    rate: str = Query(
        default="+0%",
        description="Velocidade de -50% a +100%, com sinal explícito. Em URLs, codifique o '+' como %2B.",
        examples=["-10%"],
    ),
    service: TTSService = Depends(get_tts_service),
) -> FileResponse:
    """Synthesize the text and return it as an MP3 file (cached for repeated requests)."""
    clean_text = text.strip()
    if not contains_hanzi(clean_text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="O texto deve conter pelo menos um caractere chinês (Hanzi).",
        )
    try:
        normalized_rate = validate_rate(rate)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    try:
        audio_path = await service.synthesize(clean_text, voice, normalized_rate)
    except TTSTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="O serviço de voz demorou demais para responder. Tente novamente.",
        ) from exc
    except TTSServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O serviço de voz está indisponível no momento. Tente novamente em instantes.",
        ) from exc

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename="speech.mp3",
        content_disposition_type="inline",
    )
