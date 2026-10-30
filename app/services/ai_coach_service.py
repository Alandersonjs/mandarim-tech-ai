"""Orchestrates the AI Conversation Coach: input detection + LLM + Pinyin + HSK assessment."""

import logging
import re
from collections import Counter

from sqlalchemy.orm import Session

from app.exceptions import InputNotUnderstoodError, LLMServiceError, PinyinConversionError
from app.hsk import LEVEL_RANK, is_official_level, level_from_rank
from app.models import TermCategory, VocabularyTerm
from app.pinyin_guide import build_pinyin_guide
from app.schemas import CoachResponse, GrammarIssue, HSKAssessment, VocabularyTermRead
from app.services.lexicon import Lexicon
from app.services.llm_client import LLMAnalysis, LLMClient
from app.text_utils import contains_hanzi, looks_like_pinyin, to_pinyin, word_to_pinyin

logger = logging.getLogger(__name__)

_SENTENCE_END = ("。", "！", "？", ".", "!", "?")
_ASSESSMENT_DISCLAIMER = (
    "Estimativa heurística baseada no vocabulário cadastrado e em regras simples; "
    "não substitui a avaliação oficial do HSK."
)


class AICoachService:
    """Builds structured feedback for a sentence written in Hanzi or raw Pinyin."""

    def __init__(self, db: Session, llm_client: LLMClient) -> None:
        self._db = db
        self._llm_client = llm_client

    def analyze(self, sentence: str) -> CoachResponse:
        """Analyse a sentence and return structured feedback in Portuguese.

        Raises:
            InputNotUnderstoodError: the text is neither Hanzi nor Pinyin
                (PinyinConversionError when the Pinyin has unknown words).
            LLMServiceError: when the LLM provider fails.
            sqlalchemy.exc.SQLAlchemyError: when the vocabulary lookup fails.
        """
        lexicon = Lexicon.load(self._db)
        input_mode, hanzi_sentence = self._prepare_input(sentence, lexicon)

        analysis = self._call_llm(hanzi_sentence)
        corrected = analysis.corrected_sentence
        matched_terms = lexicon.segment_hanzi(corrected)
        technical_terms = self._unique_technical_terms(matched_terms)

        return CoachResponse(
            original_sentence=sentence,
            input_mode=input_mode,
            converted_sentence=hanzi_sentence if input_mode == "pinyin" else None,
            corrected_sentence=corrected,
            # Pinyin is generated deterministically instead of trusting the LLM with it.
            pinyin=to_pinyin(corrected),
            pinyin_numeric=self._numeric_pinyin(corrected, lexicon),
            pinyin_guide=build_pinyin_guide(corrected),
            is_correct=not analysis.grammar_issues,
            naturalness_score=analysis.naturalness_score,
            grammar_issues=analysis.grammar_issues,
            explanation=analysis.explanation,
            hsk_assessment=self._assess_hsk_level(matched_terms, analysis.grammar_issues),
            recognized_technical_terms=[VocabularyTermRead.model_validate(term) for term in technical_terms],
            study_tip=self._build_study_tip(input_mode, matched_terms, technical_terms),
            analysis_engine=self._llm_client.engine_name,
        )

    # ------------------------------------------------------------------ input
    @staticmethod
    def _prepare_input(sentence: str, lexicon: Lexicon) -> tuple[str, str]:
        """Return (input_mode, hanzi_sentence), converting raw Pinyin when needed."""
        if contains_hanzi(sentence):
            return "hanzi", sentence

        if not looks_like_pinyin(sentence):
            raise InputNotUnderstoodError("The text is neither Hanzi nor valid Pinyin.")

        conversion = lexicon.convert_pinyin(sentence)
        if conversion.unresolved:
            raise PinyinConversionError(conversion.unresolved)

        hanzi = conversion.hanzi
        return "pinyin", hanzi if hanzi.endswith(_SENTENCE_END + ("。",)) else hanzi + "。"

    @staticmethod
    def _numeric_pinyin(sentence: str, lexicon: Lexicon) -> str:
        """Numeric-tone Pinyin grouped by word, e.g. "wo3 hen3 mang2" (punctuation dropped).

        Known words use the dictionary form stored in the vocabulary; other
        characters fall back to pypinyin.
        """
        words: list[str] = []
        for clause in _split_clauses(sentence):
            for chunk, term in lexicon.tokenize_hanzi(clause):
                words.append(term.pinyin_numeric if term else word_to_pinyin(chunk, numeric=True))
        return " ".join(word for word in words if word)

    # -------------------------------------------------------------------- LLM
    def _call_llm(self, sentence: str) -> LLMAnalysis:
        """Call the LLM and normalise any unexpected failure into LLMServiceError."""
        try:
            return self._llm_client.analyze_sentence(sentence)
        except LLMServiceError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider SDKs raise many error types
            logger.exception("Unexpected failure while calling the LLM client.")
            raise LLMServiceError("Unexpected failure in the LLM provider.") from exc

    # ------------------------------------------------------------ assessment
    @staticmethod
    def _unique_technical_terms(terms: list[VocabularyTerm]) -> list[VocabularyTerm]:
        """Terms outside the General category, without repetitions, in sentence order."""
        unique = {term.id: term for term in terms if term.category != TermCategory.GENERAL.value}
        return list(unique.values())

    @staticmethod
    def _assess_hsk_level(terms: list[VocabularyTerm], issues: list[GrammarIssue]) -> HSKAssessment:
        by_level = Counter(term.hsk_level for term in terms)
        ranks = [LEVEL_RANK[term.hsk_level] for term in terms if is_official_level(term.hsk_level)]
        ranks += [LEVEL_RANK[issue.hsk_level.value] for issue in issues if issue.hsk_level]
        estimated = level_from_rank(max(ranks)) if ranks else None

        if estimated is None:
            basis = "Nenhuma palavra HSK do vocabulário cadastrado foi reconhecida na frase."
        else:
            basis = (
                f"Maior nível encontrado entre {len(terms)} palavra(s) reconhecida(s) "
                f"e {len(issues)} ponto(s) gramatical(is) com erro."
            )
        return HSKAssessment(
            estimated_level=estimated,
            vocabulary_terms_by_level=dict(by_level),
            basis=basis,
            disclaimer=_ASSESSMENT_DISCLAIMER,
        )

    @staticmethod
    def _build_study_tip(mode: str, terms: list[VocabularyTerm], technical: list[VocabularyTerm]) -> str:
        parts: list[str] = []
        if mode == "pinyin":
            hanzi_list = ", ".join(dict.fromkeys(term.hanzi for term in terms))
            parts.append(f"Você escreveu em Pinyin; treine reconhecer os Hanzi: {hanzi_list}.")
        if technical:
            names = ", ".join(f"{term.hanzi} ({term.portuguese})" for term in technical)
            parts.append(
                f"Você usou {len(technical)} termo(s) técnico(s): {names}. "
                "Tente criar novas frases com eles em contextos diferentes."
            )
        else:
            parts.append(
                "Nenhum termo técnico cadastrado foi encontrado na frase. "
                "Consulte GET /api/vocabulary e inclua um deles na sua próxima frase."
            )
        return " ".join(parts)


def _split_clauses(sentence: str) -> list[str]:
    """Split a sentence at punctuation so each clause is converted on its own."""
    return [clause for clause in re.split(r"[，。！？、；：,.!?;:]", sentence) if clause.strip()]
