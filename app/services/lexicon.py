"""In-memory lexicon built from the vocabulary table.

It powers the three "smart" features that need to understand words and not only
characters: Hanzi segmentation, raw Pinyin -> Hanzi conversion and HSK level lookup.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.hsk import LEVEL_RANK
from app.models import VocabularyTerm
from app.text_utils import split_pinyin_syllables, to_fullwidth_punctuation

_PUNCTUATION_SPLIT = re.compile(r"([,.!?;:，。！？、；：])")
_MAX_SYLLABLES_PER_TERM = 8


@dataclass
class PinyinConversion:
    """Result of converting raw Pinyin into Hanzi."""

    hanzi: str = ""
    terms: list[VocabularyTerm] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    # Pinyin that matched more than one term -> candidates (first one was used).
    ambiguities: dict[str, list[str]] = field(default_factory=dict)


class Lexicon:
    """Fast lookups over the vocabulary, ordered by HSK level (easier words win ties)."""

    def __init__(self, terms: list[VocabularyTerm]) -> None:
        ordered = sorted(terms, key=lambda term: (LEVEL_RANK.get(term.hsk_level, 99), term.id))
        self._by_hanzi = {term.hanzi: term for term in ordered}
        self._by_pinyin: dict[str, list[VocabularyTerm]] = defaultdict(list)
        for term in ordered:
            self._by_pinyin[term.pinyin_search].append(term)
        self._max_hanzi_length = max((len(hanzi) for hanzi in self._by_hanzi), default=1)

    @classmethod
    def load(cls, db: Session) -> "Lexicon":
        """Build the lexicon from the whole vocabulary table."""
        return cls(list(db.scalars(select(VocabularyTerm))))

    def find_by_hanzi(self, hanzi: str) -> VocabularyTerm | None:
        """Exact lookup of a word."""
        return self._by_hanzi.get(hanzi)

    def tokenize_hanzi(self, text: str) -> list[tuple[str, VocabularyTerm | None]]:
        """Split a text into known words (greedy longest-match, left to right).

        Characters that are not part of any known word come back alone, paired with None.
        """
        tokens: list[tuple[str, VocabularyTerm | None]] = []
        position = 0
        while position < len(text):
            for length in range(min(self._max_hanzi_length, len(text) - position), 0, -1):
                chunk = text[position : position + length]
                term = self._by_hanzi.get(chunk)
                if term is not None:
                    tokens.append((chunk, term))
                    position += length
                    break
            else:
                tokens.append((text[position], None))
                position += 1
        return tokens

    def segment_hanzi(self, text: str) -> list[VocabularyTerm]:
        """Find the known words in a text, left to right."""
        return [term for _, term in self.tokenize_hanzi(text) if term is not None]

    def convert_pinyin(self, text: str) -> PinyinConversion:
        """Convert raw Pinyin (tones optional) to Hanzi, word by word.

        Syllables that do not belong to any known word stay as Pinyin and are
        listed in `unresolved`. Punctuation becomes its Chinese full-width form.
        """
        result = PinyinConversion()
        parts: list[str] = []
        for piece in _PUNCTUATION_SPLIT.split(text):
            if not piece.strip():
                continue
            if _PUNCTUATION_SPLIT.fullmatch(piece):
                parts.append(to_fullwidth_punctuation(piece))
                continue
            syllables = split_pinyin_syllables(piece)
            if syllables is None:
                result.unresolved.append(piece.strip())
                parts.append(piece.strip())
                continue
            self._convert_syllables(syllables, parts, result)
        result.hanzi = "".join(parts)
        return result

    def _convert_syllables(self, syllables: list[str], parts: list[str], result: PinyinConversion) -> None:
        position = 0
        while position < len(syllables):
            for length in range(min(_MAX_SYLLABLES_PER_TERM, len(syllables) - position), 0, -1):
                key = "".join(syllables[position : position + length])
                candidates = self._by_pinyin.get(key)
                if candidates:
                    result.terms.append(candidates[0])
                    parts.append(candidates[0].hanzi)
                    if len(candidates) > 1:
                        result.ambiguities[key] = [term.hanzi for term in candidates]
                    position += length
                    break
            else:
                result.unresolved.append(syllables[position])
                parts.append(syllables[position])
                position += 1
