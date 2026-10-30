"""SQLAlchemy ORM models."""

from enum import Enum

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base
from app.text_utils import normalize_pinyin
from app.timeutils import UTCDateTime, utc_now


class TermCategory(str, Enum):
    """Allowed categories for technical vocabulary terms."""

    COMPUTER_SCIENCE = "Computer Science"
    ARTIFICIAL_INTELLIGENCE = "Artificial Intelligence"
    SOFTWARE_ENGINEERING = "Software Engineering"
    ERP = "ERP"
    BUSINESS = "Business"
    GENERAL = "General"


class HSKLevel(str, Enum):
    """HSK 3.0 level of a term. HSK_TECH marks technical vocabulary outside the HSK lists."""

    HSK1 = "HSK1_3.0"
    HSK2 = "HSK2_3.0"
    HSK3 = "HSK3_3.0"
    HSK4 = "HSK4_3.0"
    TECH = "HSK_TECH"


class VocabularyTerm(Base):
    """A technical term with its Mandarin translation and an example sentence."""

    __tablename__ = "vocabulary_terms"
    # The Hanzi is the natural key: it prevents duplicates and keeps the seeder idempotent.
    __table_args__ = (UniqueConstraint("hanzi", name="uq_vocabulary_terms_hanzi"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portuguese: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    hanzi: Mapped[str] = mapped_column(String(60), nullable=False)
    pinyin: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # --- HSK 3.0 / beginner support ------------------------------------------
    hsk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=HSKLevel.TECH.value, index=True
    )
    # True when every character of the term is in the handwriting list (书写字).
    is_handwriting_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    # Semantic "lego blocks", one entry per character, e.g. ["电 (eletricidade)", ...].
    radical_breakdown: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Pronunciation hint for Brazilian Portuguese speakers.
    pinyin_guide: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    # Pinyin with numeric tones, e.g. "dian4nao3".
    pinyin_numeric: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    # Pinyin without tones/spaces ("shuju"): lets users search with or without tones.
    pinyin_search: Mapped[str] = mapped_column(String(150), nullable=False, default="", index=True)

    # Example sentence: Hanzi, Pinyin and Portuguese translation.
    example_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    example_pinyin: Mapped[str] = mapped_column(Text, nullable=False)
    example_translation: Mapped[str] = mapped_column(Text, nullable=False)

    @validates("pinyin")
    def _sync_pinyin_search(self, _key: str, value: str) -> str:
        """Keep the search column in sync every time the pinyin changes."""
        self.pinyin_search = normalize_pinyin(value)
        return value

    def __repr__(self) -> str:
        return f"<VocabularyTerm id={self.id} hanzi={self.hanzi!r} category={self.category!r}>"


class UserCardReview(Base):
    """Spaced-repetition (SM-2) state of one vocabulary term.

    The MVP has no user accounts, so there is exactly one card per term. To
    support several learners, add a `user_id` column and extend the unique
    constraint to (user_id, term_id).
    """

    __tablename__ = "user_card_reviews"
    __table_args__ = (UniqueConstraint("term_id", name="uq_user_card_reviews_term_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    term_id: Mapped[int] = mapped_column(
        ForeignKey("vocabulary_terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Days until the next review (0 = never reviewed yet).
    interval: Mapped[int] = mapped_column(nullable=False, default=0)
    # Consecutive correct answers (grade >= 3).
    repetition: Mapped[int] = mapped_column(nullable=False, default=0)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    next_review_date: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, index=True
    )

    term: Mapped[VocabularyTerm] = relationship()

    def __repr__(self) -> str:
        return f"<UserCardReview term_id={self.term_id} interval={self.interval} ef={self.ease_factor}>"
