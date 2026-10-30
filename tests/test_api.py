"""End-to-end tests for the vocabulary and AI coach endpoints (isolated in-memory DB)."""

import pytest
from sqlalchemy import func, select

from app.exceptions import LLMServiceError
from app.main import app
from app.models import VocabularyTerm
from app.routers.ai_coach import get_llm_client
from app.seeder import seed_vocabulary
from app.services.llm_client import LLMClient
from app.text_utils import to_pinyin


# --------------------------------------------------------------------------- #
# Seeder
# --------------------------------------------------------------------------- #
def test_seeder_inserts_at_least_five_terms_and_is_idempotent(session_factory):
    with session_factory() as db:
        total_before = db.scalar(select(func.count()).select_from(VocabularyTerm))
        inserted_again = seed_vocabulary(db)
        total_after = db.scalar(select(func.count()).select_from(VocabularyTerm))

    assert total_before >= 5
    assert inserted_again == 0
    assert total_after == total_before


# --------------------------------------------------------------------------- #
# GET /api/vocabulary
# --------------------------------------------------------------------------- #
def test_list_vocabulary_returns_paginated_payload(client):
    response = client.get("/api/vocabulary", params={"page_size": 3})

    body = response.json()
    assert response.status_code == 200
    assert len(body["items"]) == 3
    assert body["page"] == 1
    assert body["total"] >= 5
    assert body["total_pages"] == -(-body["total"] // 3)


def test_list_vocabulary_second_page_has_different_items(client):
    first = client.get("/api/vocabulary", params={"page_size": 3, "page": 1}).json()
    second = client.get("/api/vocabulary", params={"page_size": 3, "page": 2}).json()

    first_ids = {item["id"] for item in first["items"]}
    second_ids = {item["id"] for item in second["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_filter_by_category(client):
    response = client.get("/api/vocabulary", params={"category": "ERP"})

    body = response.json()
    assert response.status_code == 200
    assert body["total"] >= 1
    assert all(item["category"] == "ERP" for item in body["items"])


def test_invalid_category_returns_422(client):
    response = client.get("/api/vocabulary", params={"category": "Cooking"})
    assert response.status_code == 422


def test_search_by_portuguese_hanzi_and_pinyin(client):
    by_portuguese = client.get("/api/vocabulary", params={"search": "banco de dados"}).json()
    by_hanzi = client.get("/api/vocabulary", params={"search": "数据库"}).json()
    by_pinyin = client.get("/api/vocabulary", params={"search": "shùjùkù"}).json()

    assert by_portuguese["total"] == by_hanzi["total"] == by_pinyin["total"] == 1


def test_search_treats_percent_as_plain_text(client):
    body = client.get("/api/vocabulary", params={"search": "%"}).json()
    assert body["total"] == 0


def test_page_size_above_limit_returns_422(client):
    assert client.get("/api/vocabulary", params={"page_size": 1000}).status_code == 422


def test_get_term_by_id_and_404(client):
    assert client.get("/api/vocabulary/1").status_code == 200

    missing = client.get("/api/vocabulary/9999")
    assert missing.status_code == 404
    assert "não encontrado" in missing.json()["detail"]


# --------------------------------------------------------------------------- #
# POST /api/ai/coach
# --------------------------------------------------------------------------- #
def test_coach_corrects_copula_before_adjective(client):
    response = client.post("/api/ai/coach", json={"sentence": "我是很忙。"})

    body = response.json()
    assert response.status_code == 200
    assert body["corrected_sentence"] == "我很忙。"
    assert body["pinyin"] == "wǒ hěn máng."
    assert body["is_correct"] is False
    assert body["grammar_issues"][0]["category"] == "Verbo de ligação"
    assert body["naturalness_score"] < 95


def test_coach_corrects_word_order_of_location(client):
    body = client.post("/api/ai/coach", json={"sentence": "我工作在公司。"}).json()
    assert body["corrected_sentence"] == "我在公司工作。"


def test_coach_corrects_negation_of_you(client):
    body = client.post("/api/ai/coach", json={"sentence": "我不有时间。"}).json()
    assert body["corrected_sentence"] == "我没有时间。"


@pytest.mark.parametrize(
    "valid_sentence",
    ["他是很好的老师。", "他住在北京。", "我们在家学习。", "我是在公司学习的。"],
)
def test_coach_does_not_flag_valid_sentences(client, valid_sentence):
    body = client.post("/api/ai/coach", json={"sentence": valid_sentence}).json()
    assert body["is_correct"] is True
    assert body["corrected_sentence"] == valid_sentence


def test_coach_recognizes_technical_terms(client):
    body = client.post("/api/ai/coach", json={"sentence": "我们使用数据库存储客户信息。"}).json()

    assert body["is_correct"] is True
    assert body["naturalness_score"] == 95
    assert [term["hanzi"] for term in body["recognized_technical_terms"]] == ["数据库"]


def test_coach_rejects_text_without_hanzi(client):
    response = client.post("/api/ai/coach", json={"sentence": "hello world"})
    assert response.status_code == 422


def test_coach_rejects_blank_sentence(client):
    assert client.post("/api/ai/coach", json={"sentence": "   "}).status_code == 422


def test_coach_returns_502_when_llm_fails(client):
    class BrokenLLM(LLMClient):
        engine_name = "broken"

        def analyze_sentence(self, sentence):
            raise LLMServiceError("boom")

    app.dependency_overrides[get_llm_client] = lambda: BrokenLLM()
    try:
        response = client.post("/api/ai/coach", json={"sentence": "我很忙。"})
    finally:
        app.dependency_overrides.pop(get_llm_client, None)

    assert response.status_code == 502


def test_to_pinyin_attaches_punctuation_to_previous_syllable():
    assert to_pinyin("你好，世界！") == "nǐ hǎo, shì jiè!"


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok"}
