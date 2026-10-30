"""Helpers for working with Chinese text (Hanzi detection and Pinyin conversion)."""

import re
import unicodedata

from pypinyin import Style, lazy_pinyin
from pypinyin.pinyin_dict import pinyin_dict

# Basic CJK Unified Ideographs block (covers all common Hanzi).
HANZI_PATTERN = re.compile(r"[\u4e00-\u9fff]")

# Chinese full-width punctuation -> ASCII equivalents used in Pinyin output.
_PUNCTUATION_MAP = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "？": "?",
        "！": "!",
        "、": ",",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
    }
)
_SPACE_BEFORE_CLOSING = re.compile(r"\s+([,.!?;:)])")
_SPACE_AFTER_OPENING = re.compile(r"\(\s+")


def contains_hanzi(text: str) -> bool:
    """Return True if the text has at least one Chinese character."""
    return bool(HANZI_PATTERN.search(text))


def to_pinyin(text: str) -> str:
    """Convert Chinese text to Pinyin with tone marks.

    Each syllable is separated by a space and punctuation is attached to the
    previous syllable, e.g. "我很忙。" -> "wǒ hěn máng.".
    """
    syllables = lazy_pinyin(text, style=Style.TONE)
    pinyin = " ".join(syllables).translate(_PUNCTUATION_MAP)
    pinyin = _SPACE_BEFORE_CLOSING.sub(r"\1", pinyin)
    return _SPACE_AFTER_OPENING.sub("(", pinyin).strip()


# --------------------------------------------------------------------------- #
# Raw Pinyin handling (search normalisation, syllable splitting, numeric tones)
# --------------------------------------------------------------------------- #
_PINYIN_PUNCTUATION = re.compile(r"[,.!?;:，。！？、；：]")
_HAN_RUNS = re.compile(r"([\u4e00-\u9fff]+)")
_FULLWIDTH_PUNCTUATION = str.maketrans(
    {",": "，", ".": "。", "!": "！", "?": "？", ";": "；", ":": "：", "、": "、"}
)


def _strip_tone_marks(text: str) -> str:
    """Lowercase and remove tone marks: "Nǚ" -> "nu" (ü is mapped to u)."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_pinyin(text: str) -> str:
    """Return the Pinyin as plain lowercase letters, without tones, digits or spaces.

    "shùjùkù", "shu4ju4ku4" and "shu ju ku" all become "shujuku". The letter "v"
    (a common ASCII stand-in for ü) is mapped to "u", as ü itself is.
    """
    return re.sub(r"[^a-z]", "", _strip_tone_marks(text).replace("v", "u"))


def _build_syllable_inventory() -> frozenset[str]:
    """Collect every valid toneless Mandarin syllable from pypinyin's own dictionary."""
    syllables: set[str] = set()
    for readings in pinyin_dict.values():
        for reading in readings.split(","):
            normalized = normalize_pinyin(reading)
            # Drop the non-syllabic entries ("m", "n", "ng", "hm", "hng").
            if re.search(r"[aeiou]", normalized):
                syllables.add(normalized)
    return frozenset(syllables)


PINYIN_SYLLABLES: frozenset[str] = _build_syllable_inventory()
_MAX_SYLLABLE_LENGTH = max(len(syllable) for syllable in PINYIN_SYLLABLES)


def _split_chunk(chunk: str) -> list[str] | None:
    """Split a run of letters into the fewest valid syllables (dynamic programming)."""
    best: list[list[str] | None] = [None] * (len(chunk) + 1)
    best[0] = []
    for end in range(1, len(chunk) + 1):
        for start in range(max(0, end - _MAX_SYLLABLE_LENGTH), end):
            previous = best[start]
            if previous is None or chunk[start:end] not in PINYIN_SYLLABLES:
                continue
            candidate = previous + [chunk[start:end]]
            if best[end] is None or len(candidate) < len(best[end]):
                best[end] = candidate
    return best[-1]


def split_pinyin_syllables(text: str) -> list[str] | None:
    """Split raw Pinyin into toneless syllables, or return None if it is not Pinyin.

    Spaces, apostrophes, hyphens and tone digits act as syllable separators:
    "wǒ shì hěn máng", "wo3 shi4 hen3 mang2" and "woshihenmang" all work.
    """
    plain = _strip_tone_marks(text).replace("v", "u")
    chunks = [chunk for chunk in re.split(r"[^a-z]+", plain) if chunk]
    syllables: list[str] = []
    for chunk in chunks:
        parts = _split_chunk(chunk)
        if parts is None:
            return None
        syllables.extend(parts)
    return syllables or None


def looks_like_pinyin(text: str) -> bool:
    """True when the text (ignoring punctuation) is made only of valid Pinyin syllables."""
    return split_pinyin_syllables(_PINYIN_PUNCTUATION.sub(" ", text)) is not None


def to_fullwidth_punctuation(text: str) -> str:
    """Convert ASCII punctuation to the Chinese full-width equivalents."""
    return text.translate(_FULLWIDTH_PUNCTUATION)


def han_syllables(text: str, *, numeric: bool) -> list[str]:
    """One Pinyin syllable per Han character (non-Han characters are skipped).

    numeric=True gives numeric tones with 0 for the neutral tone ("le0");
    numeric=False gives tone marks ("le").
    """
    han_only = "".join(_HAN_RUNS.findall(text))
    if not han_only:
        return []
    if numeric:
        raw = lazy_pinyin(han_only, style=Style.TONE3, v_to_u=True, neutral_tone_with_five=True)
        return [syllable[:-1] + "0" if syllable.endswith("5") else syllable for syllable in raw]
    return lazy_pinyin(han_only, style=Style.TONE)


def word_to_pinyin(text: str, *, numeric: bool = False) -> str:
    """Pinyin of a word or phrase, with syllables of the same word glued together.

    Han runs become "shùjùkù" (or "shu4ju4ku4"); Latin runs such as "ERP" or
    "bug" are kept as they are, separated by spaces.
    """
    parts: list[str] = []
    for chunk in _HAN_RUNS.split(text):
        if not chunk.strip():
            continue
        if _HAN_RUNS.fullmatch(chunk):
            parts.append("".join(han_syllables(chunk, numeric=numeric)))
        else:
            parts.append(chunk.strip())
    return " ".join(parts)


_TONE_MARK_TO_NUMBER = {"\u0304": 1, "\u0301": 2, "\u030c": 3, "\u0300": 4}


def pinyin_to_numeric(pinyin: str) -> str:
    """Convert Pinyin with tone marks to numeric tones, keeping the dictionary form.

    Words (separated by spaces) keep their syllables glued together and the
    neutral tone is written as 0: "wǎngshang" -> "wang3shang0",
    "réngōng zhìnéng" -> "ren2gong1 zhi4neng2", "nǚ" -> "nü3".
    Text that is not valid Pinyin (e.g. "ERP") is returned unchanged.
    """
    words: list[str] = []
    for word in pinyin.split():
        letters: list[str] = []
        tones: list[int] = []
        for char in unicodedata.normalize("NFD", word.lower()):
            if char in _TONE_MARK_TO_NUMBER and letters:
                tones[-1] = _TONE_MARK_TO_NUMBER[char]
            elif char == "\u0308" and letters and letters[-1] == "u":
                letters[-1] = "ü"
            elif "a" <= char <= "z":
                letters.append(char)
                tones.append(0)
        plain = "".join("u" if letter == "ü" else letter for letter in letters)
        syllables = _split_chunk(plain) if plain else None
        if syllables is None:
            words.append(word)
            continue
        result, position = [], 0
        for syllable in syllables:
            end = position + len(syllable)
            tone = max(tones[position:end])
            result.append("".join(letters[position:end]) + str(tone))
            position = end
        words.append("".join(result))
    return " ".join(words)
