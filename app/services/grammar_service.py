"""Sentence Compiler / HSK Task Evaluator.

Assembles loose sentence pieces (Subject, Time, Place, Verb, Object, 了) into a
sentence following the Mandarin order S + T + L + V + O, then validates the
structure and checks the vocabulary level. The checklist is inspired by HSK 3.0
sentence-building tasks; it is a study aid, not an official scorer.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.hsk import LEVEL_RANK, is_official_level, level_from_rank
from app.models import HSKLevel, VocabularyTerm
from app.schemas import (
    CheckItem,
    CompiledComponent,
    CompileRequest,
    CompileResponse,
    HSKTaskCheck,
    SyllableInfo,
)
from app.services.lexicon import Lexicon
from app.text_utils import HANZI_PATTERN, contains_hanzi, looks_like_pinyin, word_to_pinyin

_ROLE_LABELS = {
    "S": "Sujeito", "T": "Tempo", "L": "Local", "V": "Verbo", "O": "Objeto", "LE": "Partícula 了",
}
_TIME_WORDS = {
    "今天", "昨天", "明天", "前天", "后天", "现在", "刚才", "最近", "早上", "上午", "中午", "下午",
    "晚上", "今年", "去年", "明年", "每天", "以前", "以后", "将来", "周末",
}
_FUTURE_TIME_WORDS = {"明天", "后天", "明年", "将来", "下周", "下个月", "下星期"}
_TIME_PATTERN = re.compile(r"^(?:[零一二三四五六七八九十两\d]+(?:点|号|月|年|天)|星期[一二三四五六日天]|(?:上|下|这)(?:个)?(?:星期|周|月))")
_DISCLAIMER = (
    "Checklist didático inspirado nas tarefas de montagem de frases do HSK 3.0; "
    "não é uma correção oficial do exame."
)


@dataclass
class _Piece:
    """A resolved sentence piece before it becomes a CompiledComponent."""

    role: str
    input_text: str
    hanzi: str
    pinyin: str
    numeric: str
    resolved: bool
    terms: list[VocabularyTerm]
    note: str | None = None


def is_time_expression(text: str) -> bool:
    """Heuristic: does this Hanzi text look like a time expression?"""
    return text in _TIME_WORDS or text in _FUTURE_TIME_WORDS or bool(_TIME_PATTERN.match(text))


class SentenceCompilerService:
    """Builds and validates sentences from their syntactic pieces."""

    def __init__(self, db: Session) -> None:
        self._lexicon = Lexicon.load(db)

    def compile(self, request: CompileRequest) -> CompileResponse:
        """Assemble the sentence and run the structural + HSK checks."""
        pieces = self._build_pieces(request)
        components = [self._to_component(piece) for piece in pieces]

        hanzi = "".join(piece.hanzi for piece in pieces)
        words_pinyin = " ".join(piece.pinyin for piece in pieces)
        numeric = " ".join(piece.numeric for piece in pieces)
        checks = self._run_checks(request, pieces)
        task_check = self._build_task_check(request, pieces, checks)

        return CompileResponse(
            sentence_hanzi=hanzi + "。",
            sentence_pinyin=_capitalize(words_pinyin) + ".",
            sentence_pinyin_numeric=_capitalize(numeric),
            syllables=self._build_syllables(pieces),
            components=components,
            structure_pattern=" + ".join("了" if piece.role == "LE" else piece.role for piece in pieces),
            structure_valid=all(c.passed for c in checks if c.severity == "error" and c.name != "Nível-alvo"),
            hsk_task_check=task_check,
            warnings=[c.message for c in checks if not c.passed and c.severity != "info"],
        )

    # ----------------------------------------------------------------- pieces
    def _build_pieces(self, request: CompileRequest) -> list[_Piece]:
        ordered = [
            ("S", request.subject), ("T", request.time), ("L", request.place),
            ("V", request.verb), ("O", request.object_),
        ]
        pieces: list[_Piece] = []
        for role, text in ordered:
            if not text:
                continue
            piece = self._resolve(role, text)
            if role == "L":
                piece = self._ensure_zai(piece)
            pieces.append(piece)
            if role == "V" and request.completed and request.le_position == "after_verb":
                pieces.append(self._particle_le())

        if request.completed and request.le_position == "sentence_end":
            pieces.append(self._particle_le())
        return pieces

    @staticmethod
    def _particle_le() -> _Piece:
        return _Piece("LE", "了", "了", "le", "le0", True, [], "Partícula de ação concluída.")

    def _resolve(self, role: str, text: str) -> _Piece:
        """Turn one user piece (Hanzi, Pinyin or a foreign term) into a resolved piece."""
        if contains_hanzi(text):
            return self._resolve_hanzi(role, text)
        if looks_like_pinyin(text):
            conversion = self._lexicon.convert_pinyin(text)
            if not conversion.unresolved:
                note = None
                if conversion.ambiguities:
                    options = "; ".join(f"{k}: {'/'.join(v)}" for k, v in conversion.ambiguities.items())
                    note = f"Pinyin ambíguo, usei o primeiro candidato ({options})."
                piece = self._resolve_hanzi(role, conversion.hanzi)
                piece.input_text, piece.note = text, note
                return piece
            return _Piece(
                role, text, text, text, text, False, [],
                f"Não encontrei no vocabulário: {', '.join(conversion.unresolved)}. Mantido como escrito.",
            )
        # Not Hanzi and not Pinyin (e.g. "bug"): loanwords are kept untouched.
        return _Piece(role, text, text, text, text, True, [], "Termo não chinês mantido como está.")

    def _resolve_hanzi(self, role: str, hanzi: str) -> _Piece:
        exact = self._lexicon.find_by_hanzi(hanzi)
        if exact is not None:  # prefer the dictionary form (neutral tones included)
            return _Piece(role, hanzi, hanzi, exact.pinyin, exact.pinyin_numeric, True, [exact])
        return _Piece(
            role, hanzi, hanzi,
            word_to_pinyin(hanzi), word_to_pinyin(hanzi, numeric=True),
            True, self._lexicon.segment_hanzi(hanzi),
        )

    @staticmethod
    def _ensure_zai(piece: _Piece) -> _Piece:
        """Introduce the place with 在, as Mandarin requires before the verb."""
        if piece.hanzi.startswith("在") or not piece.resolved:
            return piece
        piece.hanzi = "在" + piece.hanzi
        piece.pinyin = f"zài {piece.pinyin}"
        piece.numeric = f"zai4 {piece.numeric}"
        piece.note = (piece.note + " " if piece.note else "") + "在 inserido automaticamente antes do local."
        return piece

    # ----------------------------------------------------------------- output
    @staticmethod
    def _to_component(piece: _Piece) -> CompiledComponent:
        official = [LEVEL_RANK[t.hsk_level] for t in piece.terms]
        top_rank = max(official) if official else None
        level = None
        if top_rank is not None:
            level = HSKLevel.TECH if top_rank == LEVEL_RANK[HSKLevel.TECH.value] else level_from_rank(top_rank)
        return CompiledComponent(
            role=piece.role, role_label=_ROLE_LABELS[piece.role], input_text=piece.input_text,
            hanzi=piece.hanzi, pinyin=piece.pinyin, pinyin_numeric=piece.numeric,
            resolved=piece.resolved, hsk_level=level, note=piece.note,
        )

    @staticmethod
    def _build_syllables(pieces: list[_Piece]) -> list[SyllableInfo]:
        """One entry per syllable of the numeric Pinyin, aligned with the Hanzi when possible."""
        syllables: list[SyllableInfo] = []
        for piece in pieces:
            for word in piece.numeric.split():
                tokens = re.findall(r"[a-zü]+[0-5]", word)
                if "".join(tokens) != word:  # not numeric Pinyin (e.g. "bug"): keep as one token
                    syllables.append(SyllableInfo(syllable=word, hanzi=None, tone=None))
                    continue
                syllables.extend(SyllableInfo(syllable=t, hanzi=None, tone=int(t[-1])) for t in tokens)
            _attach_hanzi(syllables, piece)
        return syllables

    # ----------------------------------------------------------------- checks
    def _run_checks(self, request: CompileRequest, pieces: list[_Piece]) -> list[CheckItem]:
        by_role = {piece.role: piece for piece in pieces}
        checks = [
            CheckItem(name="Sujeito (S)", passed="S" in by_role, severity="error",
                      message="Sujeito presente." if "S" in by_role else "Falta o sujeito (S)."),
            CheckItem(name="Verbo (V)", passed="V" in by_role, severity="error",
                      message="Verbo presente." if "V" in by_role else "Falta o verbo (V)."),
            CheckItem(name="Ordem S + T + L + V + O", passed=True, severity="error",
                      message="As peças foram montadas na ordem Sujeito, Tempo, Local, Verbo, Objeto."),
        ]
        if "T" in by_role and by_role["T"].resolved:
            ok = is_time_expression(by_role["T"].hanzi)
            checks.append(CheckItem(
                name="Tempo (T)", passed=ok, severity="error",
                message="O tempo vem antes do verbo." if ok
                else f"'{by_role['T'].hanzi}' não parece uma expressão de tempo (ex.: 昨天, 今天, 三点).",
            ))
        if "L" in by_role and by_role["L"].resolved:
            looks_like_time = is_time_expression(by_role["L"].hanzi.removeprefix("在"))
            checks.append(CheckItem(
                name="Local (L)", passed=not looks_like_time, severity="error",
                message="O local é introduzido por 在 e vem antes do verbo." if not looks_like_time
                else "O campo 'place' parece uma expressão de tempo: troque-o para 'time'.",
            ))
        if request.completed and "T" in by_role and by_role["T"].hanzi in _FUTURE_TIME_WORDS:
            checks.append(CheckItem(
                name="了 e tempo", passed=False, severity="error",
                message=f"了 indica ação concluída, mas '{by_role['T'].hanzi}' é futuro: use 了 apenas com passado.",
            ))
        elif request.completed:
            checks.append(CheckItem(name="了 e tempo", passed=True, severity="info",
                                    message="了 compatível com o tempo informado."))

        unresolved = [p.input_text for p in pieces if not p.resolved]
        checks.append(CheckItem(
            name="Vocabulário", passed=not unresolved, severity="warning",
            message="Todas as peças foram reconhecidas." if not unresolved
            else f"Peças não reconhecidas no vocabulário: {', '.join(unresolved)}.",
        ))
        if request.target_level is not None:
            target_rank = LEVEL_RANK[request.target_level.value]
            above = sorted({
                term.hanzi for piece in pieces for term in piece.terms
                if is_official_level(term.hsk_level) and LEVEL_RANK[term.hsk_level] > target_rank
            })
            checks.append(CheckItem(
                name="Nível-alvo", passed=not above, severity="error",
                message=f"Vocabulário dentro de {request.target_level.value}." if not above
                else f"Palavras acima de {request.target_level.value}: {', '.join(above)}.",
            ))
        return checks

    @staticmethod
    def _build_task_check(request: CompileRequest, pieces: list[_Piece], checks: list[CheckItem]) -> HSKTaskCheck:
        terms = [term for piece in pieces for term in piece.terms]
        ranks = [LEVEL_RANK[t.hsk_level] for t in terms if is_official_level(t.hsk_level)]
        technical = sorted({t.hanzi for t in terms if t.hsk_level == HSKLevel.TECH.value})
        return HSKTaskCheck(
            conforms=all(c.passed for c in checks if c.severity == "error"),
            estimated_level=level_from_rank(max(ranks)) if ranks else None,
            target_level=request.target_level,
            technical_terms=technical,
            checks=checks,
            disclaimer=_DISCLAIMER,
        )


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _attach_hanzi(syllables: list[SyllableInfo], piece: _Piece) -> None:
    """Fill `hanzi` of this piece's syllables, in order, with its Han characters."""
    characters = HANZI_PATTERN.findall(piece.hanzi)
    pending = [s for s in syllables if s.hanzi is None and s.tone is not None]
    # Only the syllables created for this piece are still without Hanzi.
    for syllable, character in zip(pending[-len(characters):] if characters else [], characters):
        syllable.hanzi = character
