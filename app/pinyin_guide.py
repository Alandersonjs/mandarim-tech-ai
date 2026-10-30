"""Pronunciation guide in Brazilian Portuguese for Pinyin syllables.

The guide is an *approximation* meant for absolute beginners: it rewrites each
Pinyin syllable with Portuguese-friendly letters ("shu" -> "chu", "ju" -> "djü")
and lists, in parentheses, the sounds that are not intuitive for a Portuguese
speaker. Tones are not part of the guide (see `pinyin_numeric` for them).
"""

from pypinyin import Style, lazy_pinyin

from app.text_utils import HANZI_PATTERN

# Pinyin initial -> Portuguese approximation.
_INITIAL_SOUNDS: dict[str, str] = {
    "b": "p", "p": "p", "m": "m", "f": "f",
    "d": "t", "t": "t", "n": "n", "l": "l",
    "g": "k", "k": "k", "h": "rr",
    "j": "dj", "q": "tch", "x": "ch",
    "zh": "dj", "ch": "tch", "sh": "ch", "r": "j",
    "z": "dz", "c": "ts", "s": "s",
    "": "",
}

# Explanations shown only for the initials that really need one.
_INITIAL_NOTES: dict[str, str] = {
    "b": "b = 'p' suave, sem sopro",
    "p": "p = 'p' com sopro de ar",
    "d": "d = 't' suave, sem sopro",
    "t": "t = 't' com sopro de ar",
    "g": "g = 'k' suave, sem sopro",
    "k": "k = 'k' com sopro de ar",
    "h": "h = 'rr' áspero, como em 'carro'",
    "j": "j = 'dj' (como em 'Djavan')",
    "q": "q = 'tch' com sopro de ar",
    "x": "x = 'ch' suave, língua baixa",
    "zh": "zh = 'dj' com a língua enrolada",
    "ch": "ch = 'tch' com a língua enrolada",
    "sh": "sh = 'ch' forte, língua enrolada",
    "r": "r = 'j' suave, língua enrolada",
    "z": "z = 'dz'",
    "c": "c = 'ts' com sopro de ar",
}

# Pinyin final (ü written as "v") -> Portuguese approximation.
_FINAL_SOUNDS: dict[str, str] = {
    "a": "a", "o": "uô", "e": "â", "ai": "ai", "ei": "êi", "ao": "au", "ou": "ôu",
    "an": "an", "en": "ân", "ang": "ang", "eng": "âng", "ong": "ung", "er": "âr",
    "i": "i", "ia": "ia", "io": "iô", "ie": "iê", "iao": "iau", "iu": "iôu", "iou": "iôu",
    "ian": "iên", "in": "in", "iang": "iang", "ing": "ing", "iong": "iung",
    "u": "u", "ua": "ua", "uo": "uô", "uai": "uai", "ui": "uêi", "uei": "uêi",
    "uan": "uan", "un": "uên", "uen": "uên", "uang": "uang", "ueng": "uâng",
    "v": "ü", "ve": "üê", "van": "üên", "vn": "ün",
}

_INITIALS_BY_LENGTH = sorted((i for i in _INITIAL_SOUNDS if i), key=len, reverse=True)
_SIBILANT_INITIALS = {"zh", "ch", "sh", "r", "z", "c", "s"}
# Syllables like "shi", "zi": the "i" is a buzzed vowel, not the normal "i".
_BUZZED_I = {"zh": "djr", "ch": "tchr", "sh": "chr", "r": "jr", "z": "dz", "c": "ts", "s": "ss"}


def _split_syllable(syllable: str) -> tuple[str, str]:
    """Split a toneless syllable (ü written as "v") into (initial, final)."""
    if syllable.startswith("y"):
        rest = syllable[1:]
        if rest.startswith("u"):
            return "", "v" + rest[1:]  # yu, yue, yuan, yun
        if rest.startswith("i"):
            return "", rest  # yi, yin, ying
        return "", "i" + rest  # ya, ye, yao, you, yan, yang, yong, yo
    if syllable.startswith("w"):
        rest = syllable[1:]
        return "", rest if rest.startswith("u") else "u" + rest  # wu / wa, wo, wei...
    for initial in _INITIALS_BY_LENGTH:
        if syllable.startswith(initial) and len(syllable) > len(initial):
            final = syllable[len(initial):]
            if initial in {"j", "q", "x"} and final.startswith("u"):
                final = "v" + final[1:]  # ju, qu, xu are really jü, qü, xü
            return initial, final
    return "", syllable


def _approximate(syllable: str) -> tuple[str, str, str]:
    """Return (portuguese_syllable, initial, final) for one toneless syllable."""
    initial, final = _split_syllable(syllable)
    if final == "i" and initial in _SIBILANT_INITIALS:
        return _BUZZED_I[initial], initial, final
    return _INITIAL_SOUNDS[initial] + _FINAL_SOUNDS.get(final, final), initial, final


_UMLAUT_NOTE = "ü = 'i' com os lábios arredondados, como o 'u' francês"


def build_pinyin_guide(text: str) -> str:
    """Build the PT-BR pronunciation guide for the Chinese characters of `text`.

    Example: "数据库" -> "chu-djü-ku (sh = 'ch' forte...; j = 'dj' ...; k = 'k' ...)".
    Returns an empty string when the text has no Han characters.
    """
    han_only = "".join(HANZI_PATTERN.findall(text))
    if not han_only:
        return ""

    approximations: list[str] = []
    notes: list[str] = []
    for syllable in lazy_pinyin(han_only, style=Style.NORMAL, v_to_u=False):
        portuguese, initial, final = _approximate(syllable.replace("ü", "v"))
        approximations.append(portuguese)
        candidate_notes = [_INITIAL_NOTES.get(initial)]
        if final.startswith("v"):
            candidate_notes.append(_UMLAUT_NOTE)
        for note in candidate_notes:
            if note and note not in notes:
                notes.append(note)

    guide = "-".join(approximations)
    return f"{guide} ({'; '.join(notes)})" if notes else guide
