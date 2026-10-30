"""Tests for POST /api/grammar/compile (Sentence Compiler / HSK Task Evaluator)."""

import pytest


def _compile(client, **payload):
    return client.post("/api/grammar/compile", json=payload)


def test_compiles_pinyin_pieces_into_the_documented_example(client):
    response = _compile(client, subject="wo", time="zuotian", verb="xiufu", object="bug", completed=True)

    body = response.json()
    assert response.status_code == 200
    assert body["sentence_hanzi"] == "我昨天修复bug了。"
    assert body["sentence_pinyin"] == "Wǒ zuótiān xiūfù bug le."
    assert body["sentence_pinyin_numeric"] == "Wo3 zuo2tian1 xiu1fu4 bug le0"
    assert body["structure_pattern"] == "S + T + V + O + 了"
    assert body["structure_valid"] is True
    assert body["hsk_task_check"]["conforms"] is True
    assert body["hsk_task_check"]["technical_terms"] == ["修复"]


def test_hanzi_input_gives_the_same_result_as_pinyin(client):
    pinyin = _compile(client, subject="wo", time="zuotian", verb="xiufu", object="bug", completed=True).json()
    hanzi = _compile(client, subject="我", time="昨天", verb="修复", object="bug", completed=True).json()
    assert hanzi["sentence_pinyin_numeric"] == pinyin["sentence_pinyin_numeric"]


def test_syllables_are_split_with_numeric_tones_and_aligned_with_hanzi(client):
    body = _compile(client, subject="我", time="昨天", verb="修复", object="bug", completed=True).json()
    flat = [(s["syllable"], s["hanzi"], s["tone"]) for s in body["syllables"]]
    assert flat == [
        ("wo3", "我", 3), ("zuo2", "昨", 2), ("tian1", "天", 1), ("xiu1", "修", 1),
        ("fu4", "复", 4), ("bug", None, None), ("le0", "了", 0),
    ]


def test_place_gets_zai_inserted_and_goes_before_the_verb(client):
    body = _compile(client, subject="wo", time="zuotian", place="gongsi", verb="xiufu", object="bug").json()
    assert body["sentence_hanzi"] == "我昨天在公司修复bug。"
    assert body["structure_pattern"] == "S + T + L + V + O"
    assert body["sentence_pinyin_numeric"] == "Wo3 zuo2tian1 zai4 gong1si1 xiu1fu4 bug"


def test_place_already_with_zai_is_not_duplicated(client):
    body = _compile(client, subject="我", place="在公司", verb="工作").json()
    assert body["sentence_hanzi"] == "我在公司工作。"


def test_le_after_the_verb(client):
    body = _compile(client, subject="我", verb="修复", object="bug", completed=True, le_position="after_verb").json()
    assert body["sentence_hanzi"] == "我修复了bug。"
    assert body["structure_pattern"] == "S + V + 了 + O"


def test_missing_subject_and_verb_are_reported(client):
    body = _compile(client, object="bug").json()
    failed = {c["name"] for c in body["hsk_task_check"]["checks"] if not c["passed"]}
    assert failed == {"Sujeito (S)", "Verbo (V)"}
    assert body["structure_valid"] is False
    assert body["hsk_task_check"]["conforms"] is False


def test_completed_marker_with_future_time_is_rejected(client):
    body = _compile(client, subject="我", time="明天", verb="修复", object="bug", completed=True).json()
    assert body["structure_valid"] is False
    assert any("futuro" in warning for warning in body["warnings"])


def test_time_field_must_look_like_time(client):
    body = _compile(client, subject="我", time="公司", verb="修复").json()
    assert body["structure_valid"] is False


def test_target_level_flags_words_above_it(client):
    body = _compile(client, subject="我", verb="修复", object="程序", target_level="HSK1_3.0").json()
    assert body["hsk_task_check"]["conforms"] is False  # 程序 is HSK2
    assert any("程序" in warning for warning in body["warnings"])
    assert body["structure_valid"] is True  # the structure itself is fine

    ok = _compile(client, subject="我", verb="工作", target_level="HSK1_3.0").json()
    assert ok["hsk_task_check"]["conforms"] is True


def test_unknown_pinyin_is_kept_and_reported_as_warning(client):
    body = _compile(client, subject="wo", verb="qiu").json()
    verb = next(c for c in body["components"] if c["role"] == "V")
    assert verb["resolved"] is False
    assert any("qiu" in warning for warning in body["warnings"])


def test_empty_request_returns_422(client):
    assert _compile(client).status_code == 422
    assert _compile(client, subject="  ").status_code == 422


def test_invalid_le_position_returns_422(client):
    assert _compile(client, subject="我", le_position="middle").status_code == 422


@pytest.mark.parametrize("time_text", ["三点", "星期一", "今年"])
def test_common_time_expressions_are_accepted(client, time_text):
    body = _compile(client, subject="我", time=time_text, verb="工作").json()
    assert body["structure_valid"] is True
