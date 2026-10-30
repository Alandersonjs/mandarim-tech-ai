"""HSK 3.0 vocabulary: new filters, seed integrity and level summary."""

import pytest
from pypinyin import lazy_pinyin
from sqlalchemy import select

from app.models import HSKLevel, VocabularyTerm
from app.seed_data import CHARACTER_BLOCKS, SEED_TERMS, build_radical_breakdown, load_handwriting_characters
from app.seeder import is_handwriting_required, sync_handwriting_flags
from app.text_utils import HANZI_PATTERN, normalize_pinyin


def _hanzi_list(client, **params):
    body = client.get("/api/vocabulary", params={"page_size": 100, **params}).json()
    return [item["hanzi"] for item in body["items"]]


# ------------------------------- API filters ------------------------------- #
@pytest.mark.parametrize("query", ["shùjùkù", "shu4ju4ku4", "shuju", "SHU JU"])
def test_search_pinyin_with_or_without_tones(client, query):
    assert "数据库" in _hanzi_list(client, search=query)


def test_filter_by_hsk_level(client):
    hsk1 = _hanzi_list(client, hsk_level="HSK1_3.0")
    assert "电脑" in hsk1 and "数据" not in hsk1
    assert "数据" in _hanzi_list(client, hsk_level="HSK_TECH")
    assert set(_hanzi_list(client, hsk_level="HSK2_3.0")) == {"网络", "程序", "公司"}
    assert _hanzi_list(client, hsk_level="HSK4_3.0") == []


def test_invalid_hsk_level_returns_422(client):
    assert client.get("/api/vocabulary", params={"hsk_level": "HSK9"}).status_code == 422


def test_handwriting_filter(client, session_factory):
    assert _hanzi_list(client, is_handwriting_required="true") == []  # the shipped list is empty

    with session_factory() as db:
        # Only terms whose characters are ALL in the list are flagged: 电脑 and 电话.
        assert sync_handwriting_flags(db, frozenset("电脑话")) == 2

    assert set(_hanzi_list(client, is_handwriting_required="true")) == {"电脑", "电话"}
    assert "手机" in _hanzi_list(client, is_handwriting_required="false")
    assert "电脑" not in _hanzi_list(client, is_handwriting_required="false")


def test_term_exposes_beginner_fields(client):
    term = client.get("/api/vocabulary", params={"search": "电脑"}).json()["items"][0]
    assert term["hsk_level"] == "HSK1_3.0"
    assert term["pinyin_numeric"] == "dian4nao3"
    assert term["radical_breakdown"][0].startswith("电 (")
    assert "脑 (cérebro" in term["radical_breakdown"][1]
    assert term["pinyin_guide"].startswith("tiên-nau")


def test_hsk_levels_summary(client):
    body = client.get("/api/vocabulary/hsk-levels").json()
    targets = {item["level"]: item["target_cumulative_words"] for item in body["levels"]}
    assert targets == {
        "HSK1_3.0": 300, "HSK2_3.0": 500, "HSK3_3.0": 1000, "HSK4_3.0": 2000, "HSK_TECH": None,
    }
    seeded = {item["level"]: item["seeded_terms"] for item in body["levels"]}
    assert seeded["HSK_TECH"] > 0 and seeded["HSK1_3.0"] > 0 and seeded["HSK4_3.0"] == 0


def test_hsk_levels_route_is_not_shadowed_by_term_id(client):
    assert client.get("/api/vocabulary/hsk-levels").status_code == 200


# ------------------------------ seed integrity ------------------------------ #
def test_every_seed_character_has_a_radical_block():
    used = {char for term in SEED_TERMS for char in term.hanzi if HANZI_PATTERN.match(char)}
    assert used <= set(CHARACTER_BLOCKS)


def test_seed_hanzi_are_unique():
    hanzi = [term.hanzi for term in SEED_TERMS]
    assert len(hanzi) == len(set(hanzi))


def test_seed_pinyin_matches_pypinyin_ignoring_tone_of_neutral_syllables():
    for term in SEED_TERMS:
        expected = normalize_pinyin("".join(lazy_pinyin(term.hanzi)))
        assert normalize_pinyin(term.pinyin) == expected, term.hanzi


def test_user_requested_examples_are_seeded_with_the_expected_levels(session_factory):
    with session_factory() as db:
        levels = dict(db.execute(select(VocabularyTerm.hanzi, VocabularyTerm.hsk_level)).all())
    assert levels["电脑"] == HSKLevel.HSK1.value
    assert levels["数据"] == HSKLevel.TECH.value
    assert levels["程序"] == HSKLevel.HSK2.value
    assert levels["网络"] == HSKLevel.HSK2.value


def test_radical_breakdown_format():
    assert build_radical_breakdown("电脑") == ["电 (eletricidade)", "脑 (cérebro · radical 月 = carne/órgão)"]


def test_unknown_character_fails_loudly():
    with pytest.raises(KeyError):
        build_radical_breakdown("龘")


def test_handwriting_rule_requires_all_characters():
    assert is_handwriting_required("电脑", frozenset("电脑")) is True
    assert is_handwriting_required("电脑", frozenset("电")) is False
    assert is_handwriting_required("ERP", frozenset("电")) is False


def test_shipped_handwriting_file_is_parseable():
    assert isinstance(load_handwriting_characters(), frozenset)
