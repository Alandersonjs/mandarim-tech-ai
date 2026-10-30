"""Pydantic schemas (request/response contracts of the API)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import HSKLevel, TermCategory
from app.text_utils import contains_hanzi, looks_like_pinyin


# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #
class VocabularyTermRead(BaseModel):
    """A vocabulary term as returned by the API (Pinyin is a first-class citizen)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    portuguese: str = Field(description="Termo em português.")
    hanzi: str = Field(description="Termo em caracteres chineses simplificados.")
    pinyin: str = Field(description="Pronúncia em Pinyin, com marcas de tom.")
    pinyin_numeric: str = Field(description="Pinyin com tons numéricos (1-4; 0 = tom neutro), ex.: dian4nao3.")
    pinyin_guide: str = Field(description="Dica de pronúncia para falantes de português do Brasil.")
    category: TermCategory
    hsk_level: HSKLevel = Field(description="Nível do HSK 3.0 ou HSK_TECH (vocabulário técnico).")
    is_handwriting_required: bool = Field(description="True se pertence à lista de caligrafia obrigatória (书写字).")
    radical_breakdown: list[str] = Field(description="Blocos semânticos (um por caractere) para memorização.")
    example_sentence: str = Field(description="Frase de exemplo em Hanzi.")
    example_pinyin: str = Field(description="Frase de exemplo em Pinyin.")
    example_translation: str = Field(description="Tradução da frase de exemplo para o português.")


class VocabularyListResponse(BaseModel):
    """Paginated list of vocabulary terms."""

    items: list[VocabularyTermRead]
    total: int = Field(description="Total de termos que correspondem aos filtros.")
    page: int
    page_size: int
    total_pages: int


class HSKLevelSummary(BaseModel):
    """Progress of the seeded vocabulary against the cumulative target of one level."""

    level: HSKLevel
    target_cumulative_words: int | None = Field(
        description="Meta acumulada de palavras do nível (None para HSK_TECH, fora das listas oficiais)."
    )
    seeded_terms: int = Field(description="Termos cadastrados neste nível.")
    handwriting_required_terms: int = Field(description="Termos cadastrados que exigem caligrafia.")


class HSKLevelsResponse(BaseModel):
    """Summary of every HSK 3.0 level handled by the platform."""

    levels: list[HSKLevelSummary]
    note: str


# --------------------------------------------------------------------------- #
# AI Conversation Coach
# --------------------------------------------------------------------------- #
class CoachRequest(BaseModel):
    """Payload sent by the learner to the AI Conversation Coach (Hanzi or raw Pinyin)."""

    sentence: str = Field(
        min_length=1,
        max_length=300,
        description=(
            "Frase em mandarim: Hanzi (我是很忙。) ou Pinyin bruto, com ou sem tons "
            "(wo shi hen mang / wo3 shi4 hen3 mang2 / wǒ shì hěn máng)."
        ),
        examples=["我是很忙。", "wo shi hen mang"],
    )

    @field_validator("sentence")
    @classmethod
    def sentence_must_be_hanzi_or_pinyin(cls, value: str) -> str:
        """Trim whitespace and make sure the text is Mandarin in Hanzi or Pinyin."""
        cleaned = value.strip()
        if not contains_hanzi(cleaned) and not looks_like_pinyin(cleaned):
            raise ValueError("A frase deve conter Hanzi (ex.: 我很忙) ou Pinyin válido (ex.: wo hen mang).")
        return cleaned


class GrammarIssue(BaseModel):
    """A single grammar or naturalness problem found in the learner's sentence."""

    category: str = Field(description="Tipo do problema (ex.: Negação, Ordem das palavras).")
    original_fragment: str = Field(description="Trecho original com problema.")
    corrected_fragment: str = Field(description="Trecho corrigido.")
    explanation: str = Field(description="Explicação do erro em português.")
    computing_metaphor: str = Field(description="Explicação por analogia com programação.")
    hsk_level: HSKLevel | None = Field(
        default=None, description="Nível HSK estimado do ponto gramatical (heurístico, não oficial)."
    )


class HSKAssessment(BaseModel):
    """Heuristic estimate of the HSK level shown by a sentence."""

    estimated_level: HSKLevel | None = Field(
        description="Maior nível entre vocabulário reconhecido e pontos gramaticais; None se indeterminado."
    )
    vocabulary_terms_by_level: dict[str, int] = Field(
        description="Quantidade de termos reconhecidos por nível (inclui HSK_TECH)."
    )
    basis: str
    disclaimer: str


class CoachResponse(BaseModel):
    """Structured feedback returned by the AI Conversation Coach."""

    original_sentence: str
    input_mode: Literal["hanzi", "pinyin"] = Field(description="Formato detectado na submissão.")
    converted_sentence: str | None = Field(
        default=None, description="Frase convertida para Hanzi (apenas quando a entrada foi Pinyin)."
    )
    corrected_sentence: str = Field(description="Frase corrigida (igual à original se estiver correta).")
    pinyin: str = Field(description="Pinyin com marcas de tom da frase corrigida.")
    pinyin_numeric: str = Field(description="Pinyin com tons numéricos da frase corrigida.")
    pinyin_guide: str = Field(description="Dica de pronúncia em português da frase corrigida.")
    is_correct: bool = Field(description="True quando nenhum problema foi encontrado.")
    naturalness_score: int = Field(ge=0, le=100, description="Nota de naturalidade de 0 a 100.")
    grammar_issues: list[GrammarIssue]
    explanation: str = Field(description="Explicação geral em português.")
    hsk_assessment: HSKAssessment
    recognized_technical_terms: list[VocabularyTermRead] = Field(
        description="Termos técnicos (fora da categoria General) do vocabulário encontrados na frase."
    )
    study_tip: str = Field(description="Sugestão de estudo em português.")
    analysis_engine: str = Field(description="Identificador do motor de análise utilizado.")


# --------------------------------------------------------------------------- #
# Sentence Compiler / HSK Task Evaluator
# --------------------------------------------------------------------------- #
class CompileRequest(BaseModel):
    """Loose pieces of a sentence, each one in Hanzi or Pinyin."""

    model_config = ConfigDict(populate_by_name=True)

    subject: str | None = Field(default=None, max_length=60, description="Sujeito (S). Ex.: 我 / wo", examples=["wo"])
    time: str | None = Field(default=None, max_length=60, description="Tempo (T). Ex.: 昨天 / zuotian", examples=["zuotian"])
    place: str | None = Field(default=None, max_length=60, description="Local (L). O 在 é inserido sozinho.", examples=["gongsi"])
    verb: str | None = Field(default=None, max_length=60, description="Verbo (V). Ex.: 修复 / xiufu", examples=["xiufu"])
    object_: str | None = Field(
        default=None, alias="object", max_length=60, description="Objeto (O). Termos não chineses (bug) são mantidos.",
        examples=["bug"],
    )
    completed: bool = Field(default=False, description="Ação concluída: acrescenta a partícula 了.")
    le_position: Literal["sentence_end", "after_verb"] = Field(
        default="sentence_end", description="Posição do 了: fim da frase (我昨天修复bug了) ou depois do verbo."
    )
    target_level: HSKLevel | None = Field(
        default=None, description="Nível-alvo: palavras acima dele geram alerta na checagem HSK."
    )

    @field_validator("subject", "time", "place", "verb", "object_", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        """Treat empty or whitespace-only strings as 'not provided'."""
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def at_least_one_piece(self) -> "CompileRequest":
        if not any([self.subject, self.time, self.place, self.verb, self.object_]):
            raise ValueError("Informe pelo menos uma parte da frase (subject, time, place, verb ou object).")
        return self


class CompiledComponent(BaseModel):
    """One piece of the compiled sentence."""

    role: Literal["S", "T", "L", "V", "O", "LE"]
    role_label: str
    input_text: str
    hanzi: str
    pinyin: str
    pinyin_numeric: str
    resolved: bool = Field(description="False quando o texto não pôde ser convertido para Hanzi/Pinyin.")
    hsk_level: HSKLevel | None = Field(description="Maior nível HSK entre as palavras reconhecidas.")
    note: str | None = None


class SyllableInfo(BaseModel):
    """One syllable of the numeric-tone Pinyin."""

    syllable: str = Field(description="Sílaba com tom numérico, ex.: wo3.")
    hanzi: str | None = Field(description="Caractere correspondente (None para termos não chineses).")
    tone: int | None = Field(description="Tom 0-4 (0 = neutro); None para termos não chineses.")


class CheckItem(BaseModel):
    """A single validation performed by the compiler."""

    name: str
    passed: bool
    severity: Literal["error", "warning", "info"]
    message: str


class HSKTaskCheck(BaseModel):
    """Checklist inspired by HSK 3.0 sentence-building tasks (not an official scorer)."""

    conforms: bool = Field(description="True quando nenhuma checagem de severidade 'error' falhou.")
    estimated_level: HSKLevel | None
    target_level: HSKLevel | None
    technical_terms: list[str] = Field(description="Palavras HSK_TECH usadas (fora das listas HSK).")
    checks: list[CheckItem]
    disclaimer: str


class CompileResponse(BaseModel):
    """The assembled sentence plus its syntactic and HSK validation."""

    sentence_hanzi: str
    sentence_pinyin: str = Field(description="Pinyin com marcas de tom.")
    sentence_pinyin_numeric: str = Field(description="Pinyin com tons numéricos, ex.: Wo3 zuo2tian1 xiu1fu4 bug le0.")
    syllables: list[SyllableInfo]
    components: list[CompiledComponent]
    structure_pattern: str = Field(description="Estrutura montada, ex.: S + T + V + O + 了.")
    structure_valid: bool = Field(description="True quando a estrutura S + T + L + V + O é válida.")
    hsk_task_check: HSKTaskCheck
    warnings: list[str]


# --------------------------------------------------------------------------- #
# Spaced repetition (SRS / SM-2)
# --------------------------------------------------------------------------- #
class SRSReviewRequest(BaseModel):
    """A review answer given by the learner for one term."""

    term_id: int = Field(ge=1, description="Id do termo revisado.", examples=[1])
    grade: int = Field(
        ge=0,
        le=5,
        description="Nota SM-2: 0-2 = errou (reinicia), 3 = difícil, 4 = bom, 5 = perfeito.",
        examples=[4],
    )


class SRSCardResponse(BaseModel):
    """A flashcard: the term plus its current spaced-repetition state."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    term: VocabularyTermRead
    interval: int = Field(description="Dias até a próxima revisão (0 = nunca revisado).")
    repetition: int = Field(description="Acertos consecutivos (nota >= 3).")
    ease_factor: float = Field(description="Fator de facilidade do SM-2 (mínimo 1.3).")
    next_review_date: datetime = Field(description="Próxima revisão agendada (UTC).")


class SRSDueResponse(BaseModel):
    """Cards due for review."""

    total_due: int = Field(description="Total de cartões devidos (pode ser maior que os itens retornados).")
    items: list[SRSCardResponse]
