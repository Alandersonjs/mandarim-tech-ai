"""TTS: rate validation, caching, error mapping and the /api/tts/generate route.

The real edge-tts service needs internet access, so the provider is replaced by a
fake. A real-network test is available with RUN_TTS_INTEGRATION=1.
"""

import asyncio
import os
from pathlib import Path

import pytest

from app.exceptions import TTSServiceError, TTSTimeoutError
from app.main import app
from app.routers.tts import get_tts_service
from app.services.tts_service import TTSService, Voice, validate_rate

FAKE_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-bytes"


class FakeCommunicate:
    """Stands in for edge_tts.Communicate and records how it was called."""

    calls: list[dict] = []
    behaviour = "ok"  # "ok" | "fail" | "empty" | "slow"

    def __init__(self, text, voice, rate="+0%"):
        self.text, self.voice, self.rate = text, voice, rate
        FakeCommunicate.calls.append({"text": text, "voice": voice, "rate": rate})

    async def save(self, path):
        if FakeCommunicate.behaviour == "fail":
            raise ConnectionError("provider down")
        if FakeCommunicate.behaviour == "slow":
            await asyncio.sleep(5)
        Path(path).write_bytes(b"" if FakeCommunicate.behaviour == "empty" else FAKE_MP3)


@pytest.fixture(autouse=True)
def reset_fake():
    FakeCommunicate.calls = []
    FakeCommunicate.behaviour = "ok"


@pytest.fixture()
def cache_dir(tmp_path):
    return tmp_path / "tts"


@pytest.fixture()
def tts_client(client, cache_dir):
    """Test client whose TTS service uses the fake provider and a temporary cache."""
    service = TTSService(cache_dir, timeout_seconds=0.2, communicate_factory=FakeCommunicate)
    app.dependency_overrides[get_tts_service] = lambda: service
    return client


# ------------------------------ rate validation ------------------------------ #
@pytest.mark.parametrize(
    "raw, expected",
    [("+0%", "+0%"), ("-10%", "-10%"), ("+100%", "+100%"), ("-50%", "-50%"), ("-0%", "+0%"), (" 0%", "+0%"), (" 25%", "+25%")],
)
def test_validate_rate_accepts_and_normalises(raw, expected):
    assert validate_rate(raw) == expected


@pytest.mark.parametrize("raw", ["10%", "-10", "fast", "", "+101%", "-51%", "+1000%", "--5%", "+5 %"])
def test_validate_rate_rejects(raw):
    with pytest.raises(ValueError):
        validate_rate(raw)


# --------------------------------- route ---------------------------------- #
def test_generates_mp3_with_the_default_female_voice(tts_client):
    response = tts_client.get("/api/tts/generate", params={"text": "你好，我是程序员。"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == FAKE_MP3
    assert FakeCommunicate.calls == [{"text": "你好，我是程序员。", "voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%"}]


def test_male_voice_and_rate_are_forwarded_to_the_provider(tts_client):
    response = tts_client.get("/api/tts/generate", params={"text": "数据库", "voice": "male", "rate": "-10%"})

    assert response.status_code == 200
    assert FakeCommunicate.calls[0]["voice"] == "zh-CN-YunxiNeural"
    assert FakeCommunicate.calls[0]["rate"] == "-10%"


def test_unencoded_plus_in_the_url_is_understood(tts_client):
    # A raw "+" in a query string is decoded as a space by the server.
    response = tts_client.get("/api/tts/generate?text=你好&rate=%200%25")
    assert response.status_code == 200
    assert FakeCommunicate.calls[0]["rate"] == "+0%"


def test_repeated_requests_are_served_from_the_cache(tts_client):
    for _ in range(3):
        assert tts_client.get("/api/tts/generate", params={"text": "你好"}).content == FAKE_MP3
    assert len(FakeCommunicate.calls) == 1

    tts_client.get("/api/tts/generate", params={"text": "你好", "rate": "-20%"})
    tts_client.get("/api/tts/generate", params={"text": "你好", "voice": "male"})
    assert len(FakeCommunicate.calls) == 3  # rate and voice are part of the cache key


@pytest.mark.parametrize(
    "params",
    [
        {"text": "你好", "voice": "robot"},
        {"text": "你好", "rate": "10%"},
        {"text": "你好", "rate": "+500%"},
        {"text": "你好", "rate": "-80%"},
        {"text": "hello"},
        {"text": "wo shi hen mang"},
        {"text": ""},
        {"text": "你" * 301},
        {},
    ],
)
def test_invalid_requests_return_422_without_calling_the_provider(tts_client, params):
    assert tts_client.get("/api/tts/generate", params=params).status_code == 422
    assert FakeCommunicate.calls == []


def test_provider_failure_returns_502_and_leaves_no_files(tts_client, cache_dir):
    FakeCommunicate.behaviour = "fail"

    response = tts_client.get("/api/tts/generate", params={"text": "你好"})

    assert response.status_code == 502
    assert not any(cache_dir.iterdir())


def test_empty_audio_returns_502_and_is_not_cached(tts_client, cache_dir):
    FakeCommunicate.behaviour = "empty"

    assert tts_client.get("/api/tts/generate", params={"text": "你好"}).status_code == 502
    assert not any(cache_dir.iterdir())

    FakeCommunicate.behaviour = "ok"  # recovers on the next request
    assert tts_client.get("/api/tts/generate", params={"text": "你好"}).status_code == 200


def test_provider_timeout_returns_504(tts_client, cache_dir):
    FakeCommunicate.behaviour = "slow"

    assert tts_client.get("/api/tts/generate", params={"text": "你好"}).status_code == 504
    assert not any(cache_dir.iterdir())


def test_openapi_documents_the_audio_response(tts_client):
    responses = tts_client.get("/openapi.json").json()["paths"]["/api/tts/generate"]["get"]["responses"]
    assert "audio/mpeg" in responses["200"]["content"]


# --------------------------------- service ---------------------------------- #
def test_cache_file_name_is_a_hash_and_depends_on_all_parameters(cache_dir):
    service = TTSService(cache_dir, communicate_factory=FakeCommunicate)
    base = service.cache_path("你好", Voice.FEMALE, "+0%")

    assert base.parent == cache_dir and base.suffix == ".mp3"
    assert len(base.stem) == 64 and base.stem.isalnum()  # no user text in the file name
    assert base != service.cache_path("你好", Voice.MALE, "+0%")
    assert base != service.cache_path("你好", Voice.FEMALE, "-10%")
    assert base != service.cache_path("你好吗", Voice.FEMALE, "+0%")


def test_concurrent_identical_requests_produce_one_valid_file(cache_dir):
    service = TTSService(cache_dir, communicate_factory=FakeCommunicate)

    async def run():
        return await asyncio.gather(*(service.synthesize("你好", Voice.FEMALE, "+0%") for _ in range(5)))

    paths = asyncio.run(run())

    assert len(set(paths)) == 1
    assert paths[0].read_bytes() == FAKE_MP3
    assert [p.name for p in cache_dir.iterdir()] == [paths[0].name]  # no temporary leftovers


def test_service_raises_domain_errors(cache_dir):
    service = TTSService(cache_dir, timeout_seconds=0.1, communicate_factory=FakeCommunicate)

    FakeCommunicate.behaviour = "fail"
    with pytest.raises(TTSServiceError):
        asyncio.run(service.synthesize("你好", Voice.FEMALE, "+0%"))

    FakeCommunicate.behaviour = "slow"
    with pytest.raises(TTSTimeoutError):
        asyncio.run(service.synthesize("你好", Voice.FEMALE, "+0%"))


def test_default_dependency_uses_the_configured_cache_folder():
    service = get_tts_service()
    assert isinstance(service, TTSService)


@pytest.mark.skipif(os.getenv("RUN_TTS_INTEGRATION") != "1", reason="needs internet; set RUN_TTS_INTEGRATION=1")
def test_real_edge_tts_synthesis(tmp_path):
    service = TTSService(tmp_path, timeout_seconds=30)
    path = asyncio.run(service.synthesize("你好，欢迎学习中文。", Voice.FEMALE, "+0%"))
    assert path.stat().st_size > 1000
