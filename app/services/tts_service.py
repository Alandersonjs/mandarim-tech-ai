"""Neural text-to-speech in Mandarin with edge-tts (no API key required).

Generated MP3 files are cached on disk, named after a SHA-256 of
(voice, rate, text). Vocabulary is repeated a lot in language learning, so the
cache avoids calling the provider again and makes replays instant. The cache
has no automatic eviction: files are small and the text length is limited, but
you can safely delete the folder (TTS_CACHE_DIR) at any time.
"""

import asyncio
import hashlib
import logging
import os
import re
import uuid
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import edge_tts

from app.exceptions import TTSServiceError, TTSTimeoutError

logger = logging.getLogger(__name__)

# Slowest and fastest speed accepted by this API (an application choice; the
# provider itself accepts wider ranges).
MIN_RATE_PERCENT = -50
MAX_RATE_PERCENT = 100
_RATE_PATTERN = re.compile(r"^([+-])(\d{1,3})%$")


class Voice(str, Enum):
    """Voices exposed by the API."""

    FEMALE = "female"
    MALE = "male"


VOICE_NAMES: dict[Voice, str] = {
    Voice.FEMALE: "zh-CN-XiaoxiaoNeural",
    Voice.MALE: "zh-CN-YunxiNeural",
}


def validate_rate(rate: str) -> str:
    """Validate and normalise the speaking rate (e.g. "-10%", "+0%").

    A leading space is read as "+": in a URL query string an unencoded "+" is
    decoded as a space, so "?rate=+0%" would otherwise be rejected.

    Raises:
        ValueError: if the format is wrong or the value is outside -50%..+100%.
    """
    candidate = ("+" + rate.lstrip()) if rate.startswith(" ") else rate.strip()
    match = _RATE_PATTERN.match(candidate)
    if match is None:
        raise ValueError("rate must look like '-10%' or '+0%' (explicit sign, then digits, then %).")
    value = int(match.group(2)) * (-1 if match.group(1) == "-" else 1)
    if not MIN_RATE_PERCENT <= value <= MAX_RATE_PERCENT:
        raise ValueError(f"rate must be between {MIN_RATE_PERCENT:+d}% and {MAX_RATE_PERCENT:+d}%.")
    return f"{value:+d}%"


class TTSService:
    """Synthesizes Mandarin speech into cached MP3 files."""

    def __init__(
        self,
        cache_dir: Path,
        timeout_seconds: float = 20.0,
        communicate_factory: Callable[..., Any] = edge_tts.Communicate,
    ) -> None:
        self._cache_dir = cache_dir
        self._timeout_seconds = timeout_seconds
        self._communicate_factory = communicate_factory

    def cache_path(self, text: str, voice: Voice, rate: str) -> Path:
        """Deterministic file path of the audio for these parameters."""
        key = hashlib.sha256(f"{VOICE_NAMES[voice]}|{rate}|{text}".encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key}.mp3"

    async def synthesize(self, text: str, voice: Voice, rate: str) -> Path:
        """Return the MP3 file for the text, generating it when it is not cached.

        Raises:
            TTSTimeoutError: if the provider takes longer than the configured timeout.
            TTSServiceError: if the provider fails or returns no audio.
        """
        target = self.cache_path(text, voice, rate)
        if target.exists() and target.stat().st_size > 0:
            return target

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        # Write to a unique temporary file and rename at the end, so a failed or
        # concurrent request can never leave a half-written MP3 in the cache.
        temporary = target.with_name(f"{target.stem}.{uuid.uuid4().hex}.tmp")
        try:
            communicate = self._communicate_factory(text, VOICE_NAMES[voice], rate=rate)
            await asyncio.wait_for(communicate.save(str(temporary)), timeout=self._timeout_seconds)
            if not temporary.exists() or temporary.stat().st_size == 0:
                raise TTSServiceError("The TTS provider returned no audio.")
            os.replace(temporary, target)
        except asyncio.TimeoutError as exc:
            raise TTSTimeoutError("The TTS provider took too long to answer.") from exc
        except TTSServiceError:
            raise
        except Exception as exc:  # noqa: BLE001 - edge-tts raises network and protocol errors
            logger.exception("TTS synthesis failed.")
            raise TTSServiceError("The TTS provider failed.") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return target
