"""AI Coach: raw Pinyin submissions, computing metaphors and HSK assessment."""

import pytest


def _coach(client, sentence):
    return client.post("/api/ai/coach", json={"sentence": sentence})


@pytest.mark.parametrize(
    "sentence", ["wo shi hen mang", "wo3 shi4 hen3 mang2", "wǒ shì hěn máng", "woshihenmang."]
)
def test_raw_pinyin_is_converted_and_corrected(client, sentence):
    response = _coach(client, sentence)

    body = response.json()
    assert response.status_code == 200
    assert body["input_mode"] == "pinyin"
    assert body["converted_sentence"] == "我是很忙。"
    assert body["corrected_sentence"] == "我很忙。"
    assert body["pinyin_numeric"] == "wo3 hen3 mang2"
    assert body["is_correct"] is False


def test_hanzi_input_keeps_hanzi_mode(client):
    body = _coach(client, "我很忙。").json()
    assert body["input_mode"] == "hanzi"
    assert body["converted_sentence"] is None
    assert body["is_correct"] is True


def test_issues_carry_computing_metaphors_and_hsk_level(client):
    issue = _coach(client, "我是很忙。").json()["grammar_issues"][0]
    assert issue["hsk_level"] == "HSK1_3.0"
    assert "wrapper" in issue["computing_metaphor"] or "código" in issue["computing_metaphor"]


def test_explanation_includes_the_metaphor(client):
    assert "Em código:" in _coach(client, "我不有时间。").json()["explanation"]


def test_word_order_rule_reports_hsk2_grammar_point(client):
    body = _coach(client, "wo gongzuo zai gongsi").json()
    assert body["corrected_sentence"] == "我在公司工作。"
    assert body["hsk_assessment"]["estimated_level"] == "HSK2_3.0"


def test_hsk_assessment_uses_the_highest_vocabulary_level(client):
    body = _coach(client, "这个程序很有用。").json()
    assessment = body["hsk_assessment"]
    assert assessment["estimated_level"] == "HSK2_3.0"  # 程序 is HSK2
    assert assessment["vocabulary_terms_by_level"]["HSK2_3.0"] == 1
    assert "heurística" in assessment["disclaimer"]


def test_pinyin_with_unknown_words_returns_422_with_the_unknown_syllables(client):
    response = _coach(client, "wo shi qiu")
    assert response.status_code == 422
    assert "qiu" in response.json()["detail"]


def test_pinyin_response_has_a_pronunciation_guide(client):
    body = _coach(client, "wo hen mang").json()
    assert body["pinyin_guide"].startswith("uô-rrân-mang")


def test_study_tip_for_pinyin_mentions_the_hanzi(client):
    tip = _coach(client, "wo hen mang").json()["study_tip"]
    assert "我" in tip and "很" in tip


def test_ambiguity_free_pinyin_with_punctuation(client):
    assert _coach(client, "wo hen mang!").json()["converted_sentence"] == "我很忙！"
