"""Domain-level exceptions, translated into HTTP errors by the routers."""


class LLMServiceError(Exception):
    """Raised when the LLM provider fails or returns an unusable answer."""


class InputNotUnderstoodError(Exception):
    """Raised when the learner's text cannot be interpreted as Hanzi or Pinyin."""


class PinyinConversionError(InputNotUnderstoodError):
    """Raised when raw Pinyin cannot be fully converted to Hanzi with the known vocabulary."""

    def __init__(self, unresolved: list[str]) -> None:
        self.unresolved = unresolved
        super().__init__(f"Could not convert to Hanzi: {', '.join(unresolved)}")


class TermNotFoundError(Exception):
    """Raised when an operation references a vocabulary term that does not exist."""

    def __init__(self, term_id: int) -> None:
        self.term_id = term_id
        super().__init__(f"Vocabulary term {term_id} not found.")


class TTSServiceError(Exception):
    """Raised when the text-to-speech provider fails or returns no audio."""


class TTSTimeoutError(TTSServiceError):
    """Raised when the text-to-speech provider takes too long to answer."""
