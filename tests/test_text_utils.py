"""Unit tests for Pinyin utilities and the PT-BR pronunciation guide."""

import pytest

from app.pinyin_guide import _approximate, build_pinyin_guide
from app.text_utils import (
    PINYIN_SYLLABLES,
    looks_like_pinyin,
    normalize_pinyin,
    pinyin_to_numeric,
    split_pinyin_syllables,
    word_to_pinyin,
)


@pytest.mark.parametrize("raw", ["shùjùkù", "shu4ju4ku4", "shu ju ku", "SHUJUKU"])
def test_normalize_pinyin_ignores_tones_digits_spaces_and_case(raw):
    assert normalize_pinyin(raw) == "shujuku"


def test_normalize_pinyin_maps_umlaut_and_v_to_u():
    assert normalize_pinyin("nǚ") == normalize_pinyin("nv") == "nu"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("wǒ shì hěn máng", ["wo", "shi", "hen", "mang"]),
        ("zuo2tian1 xiu1fu4", ["zuo", "tian", "xiu", "fu"]),
        ("woshihenmang", ["wo", "shi", "hen", "mang"]),
        ("xi'an", ["xi", "an"]),
    ],
)
def test_split_pinyin_syllables(raw, expected):
    assert split_pinyin_syllables(raw) == expected


@pytest.mark.parametrize("text", ["bug", "hello world", "123", "ERP"])
def test_non_pinyin_is_rejected(text):
    assert looks_like_pinyin(text) is False


def test_looks_like_pinyin_accepts_punctuation():
    assert looks_like_pinyin("wo shi hen mang.") is True


def test_pinyin_to_numeric_keeps_dictionary_form_with_neutral_tone():
    assert pinyin_to_numeric("wǎngshang") == "wang3shang0"
    assert pinyin_to_numeric("réngōng zhìnéng") == "ren2gong1 zhi4neng2"
    assert pinyin_to_numeric("nǚ") == "nü3"
    assert pinyin_to_numeric("ERP") == "ERP"


def test_word_to_pinyin_numeric_uses_zero_for_neutral_tone_and_keeps_latin_runs():
    assert word_to_pinyin("了", numeric=True) == "le0"
    assert word_to_pinyin("ERP系统") == "ERP xìtǒng"


def test_guide_follows_the_beginner_conventions():
    guide = build_pinyin_guide("数据库")
    assert guide.startswith("chu-djü-ku")  # sh = ch, j = dj
    assert "j = 'dj'" in guide
    assert build_pinyin_guide("去").startswith("tchü")  # q = tch
    assert build_pinyin_guide("程序员").startswith("tchâng-chü")  # x = ch suave
    assert "zh = 'dj'" in build_pinyin_guide("知道")


def test_guide_is_empty_without_hanzi():
    assert build_pinyin_guide("ERP") == ""


def test_guide_covers_every_valid_syllable():
    assert all(_approximate(syllable)[0] for syllable in PINYIN_SYLLABLES)
