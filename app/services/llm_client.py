"""LLM abstraction layer for the AI Conversation Coach.

The coach depends only on the `LLMClient` interface. For the MVP we ship
`MockLLMClient`, a rule-based simulation of an LLM. To use a real provider
(Anthropic, OpenAI, ...), create a new subclass of `LLMClient` that calls the
provider API and return it from `get_llm_client()` in `app/routers/ai_coach.py`.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.exceptions import LLMServiceError
from app.models import HSKLevel
from app.schemas import GrammarIssue


@dataclass(frozen=True)
class LLMAnalysis:
    """Raw judgement produced by an LLM about a learner's sentence."""

    corrected_sentence: str
    grammar_issues: list[GrammarIssue]
    naturalness_score: int
    explanation: str


class LLMClient(ABC):
    """Contract that every LLM provider adapter must fulfil."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Identifier of the engine, returned to the API consumer."""

    @abstractmethod
    def analyze_sentence(self, sentence: str) -> LLMAnalysis:
        """Analyse a Mandarin sentence.

        Raises:
            LLMServiceError: if the provider fails or answers with invalid data.
        """


@dataclass(frozen=True)
class GrammarRule:
    """A regex-based correction rule for a typical mistake of Portuguese speakers."""

    category: str
    pattern: re.Pattern[str]
    replacement: str
    explanation: str
    computing_metaphor: str
    hsk_level: HSKLevel  # heuristic estimate of the level of the grammar point


# Characters that cannot be part of the "verb phrase" in the word-order rule below.
_NOT_IN_VERB_PHRASE = r"是在有没不们，。！？,.!?\s"

_GRAMMAR_RULES: tuple[GrammarRule, ...] = (
    GrammarRule(
        category="Negação",
        pattern=re.compile(r"不有"),
        replacement="没有",
        explanation="O verbo 有 (ter/haver) é sempre negado com 没, nunca com 不. O correto é 没有.",
        computing_metaphor=(
            "有 é como um método `exists()` cujo único modificador de negação aceito é 没. "
            "Chamar `不有` é invocar um método que não existe na classe: um AttributeError gramatical."
        ),
        hsk_level=HSKLevel.HSK1,
    ),
    GrammarRule(
        category="Negação",
        pattern=re.compile(r"没是"),
        replacement="不是",
        explanation="O verbo 是 (ser) é negado com 不, formando 不是. 没 só nega ações passadas e o verbo 有.",
        computing_metaphor=(
            "是 é o operador de igualdade (==) e 不是 é o seu oposto (!=). "
            "Usar 没 aqui é aplicar o operador errado ao tipo errado: falha de tipagem."
        ),
        hsk_level=HSKLevel.HSK1,
    ),
    GrammarRule(
        category="Verbo de ligação",
        # "是很 + adjective" without a following 的 ("他是很忙" -> "他很忙").
        pattern=re.compile(r"是很([好高大小忙累快慢难易贵多少])(?![^，。！？,.!?]*的)"),
        replacement=r"很\1",
        explanation=(
            "Em mandarim, adjetivos funcionam como verbos: não se usa 是 antes de "
            "'很 + adjetivo'. Diga '我很忙' (estou ocupado), não '我是很忙'."
        ),
        computing_metaphor=(
            "O adjetivo já vem com o 'verbo ser' embutido, como uma função que já retorna o estado. "
            "Embrulhar `很忙` em um 是 extra é um wrapper redundante: código morto que o linter derrubaria."
        ),
        hsk_level=HSKLevel.HSK1,
    ),
    GrammarRule(
        category="Redundância",
        pattern=re.compile(r"很非常|非常很"),
        replacement="非常",
        explanation="很 e 非常 são ambos advérbios de intensidade; use apenas um deles na frase.",
        computing_metaphor=(
            "很 e 非常 são decoradores de intensidade (@amplify). Empilhar os dois é aplicar o mesmo "
            "decorator duas vezes: o segundo não acrescenta nada. Mantenha apenas um."
        ),
        hsk_level=HSKLevel.HSK1,
    ),
    GrammarRule(
        category="Ordem das palavras",
        # "我工作在公司" -> "我在公司工作": the place goes BEFORE the main verb.
        pattern=re.compile(
            rf"^([我你他她]们?)(?!们)([^{_NOT_IN_VERB_PHRASE}]{{1,6}}?)(?<![住坐放站躺生])在"
            r"(公司|学校|办公室|家|北京|上海|巴西)([。！？.!?]?)$"
        ),
        replacement=r"\1在\3\2\4",
        explanation=(
            "Em mandarim, o local da ação vem ANTES do verbo principal: "
            "sujeito + 在 + local + verbo. Exceções como 住在 e 坐在 mantêm 在 depois do verbo."
        ),
        computing_metaphor=(
            "A ordem é uma pilha de chamadas fixa: Sujeito → Tempo → Local → Verbo → Objeto. "
            "O local é o contexto (como um `with local:`) e precisa ser aberto ANTES de executar o verbo. "
            "`我工作在公司` roda a ação fora do contexto; `我在公司工作` abre o contexto primeiro."
        ),
        hsk_level=HSKLevel.HSK2,
    ),
)


class MockLLMClient(LLMClient):
    """Rule-based simulation of an LLM, good enough for demos and tests."""

    @property
    def engine_name(self) -> str:
        return "mock-llm-v1"

    def analyze_sentence(self, sentence: str) -> LLMAnalysis:
        if not sentence or not sentence.strip():
            raise LLMServiceError("Cannot analyse an empty sentence.")

        corrected = sentence
        issues: list[GrammarIssue] = []

        for rule in _GRAMMAR_RULES:
            for match in rule.pattern.finditer(corrected):
                issues.append(
                    GrammarIssue(
                        category=rule.category,
                        original_fragment=match.group(0),
                        corrected_fragment=match.expand(rule.replacement),
                        explanation=rule.explanation,
                        computing_metaphor=rule.computing_metaphor,
                        hsk_level=rule.hsk_level,
                    )
                )
            corrected = rule.pattern.sub(rule.replacement, corrected)

        return LLMAnalysis(
            corrected_sentence=corrected,
            grammar_issues=issues,
            naturalness_score=self._score(issues),
            explanation=self._build_explanation(issues, corrected),
        )

    @staticmethod
    def _score(issues: list[GrammarIssue]) -> int:
        """95 for a clean sentence, minus 20 per issue (never below 30)."""
        return max(30, 95 - 20 * len(issues))

    @staticmethod
    def _build_explanation(issues: list[GrammarIssue], corrected: str) -> str:
        if not issues:
            return (
                "Sua frase passou no 'linter' gramatical: nenhum erro de sintaxe encontrado e ela soa "
                "natural para um falante nativo. Continue praticando com frases mais longas e "
                "vocabulário técnico!"
            )

        plural = "s" if len(issues) > 1 else ""
        lines = [f"Encontrei {len(issues)} erro{plural} de 'compilação' na sua frase."]
        seen: set[str] = set()
        for issue in issues:
            if issue.explanation in seen:
                continue
            seen.add(issue.explanation)
            lines.append(f"[{issue.category}] {issue.explanation} Em código: {issue.computing_metaphor}")
        lines.append(f"Versão corrigida: {corrected}")
        return " ".join(lines)
