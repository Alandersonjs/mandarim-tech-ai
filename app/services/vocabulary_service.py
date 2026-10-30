"""Business logic for querying the vocabulary."""

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import HSKLevel, TermCategory, VocabularyTerm
from app.text_utils import normalize_pinyin


def list_terms(
    db: Session,
    *,
    category: TermCategory | None = None,
    search: str | None = None,
    hsk_level: HSKLevel | None = None,
    handwriting_required: bool | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[VocabularyTerm], int]:
    """Return one page of terms plus the total number of matches.

    Args:
        category: Keep only terms from this category.
        search: Case-insensitive text matched against Portuguese, Hanzi and Pinyin.
            Pinyin is matched with or without tones: "shùjùkù", "shu4ju4ku4"
            and "shuju" all find 数据库.
        hsk_level: Keep only terms of this HSK 3.0 level (or HSK_TECH).
        handwriting_required: True keeps only handwriting-required terms
            (书写字); False keeps only the others; None disables the filter.
        page: 1-based page number.
        page_size: Number of items per page.
    """
    filters = []

    if category is not None:
        filters.append(VocabularyTerm.category == category.value)
    if hsk_level is not None:
        filters.append(VocabularyTerm.hsk_level == hsk_level.value)
    if handwriting_required is not None:
        filters.append(VocabularyTerm.is_handwriting_required.is_(handwriting_required))

    if search:
        # autoescape=True makes "%" and "_" typed by the user behave as plain text.
        conditions = [
            VocabularyTerm.portuguese.icontains(search, autoescape=True),
            VocabularyTerm.hanzi.icontains(search, autoescape=True),
            VocabularyTerm.pinyin.icontains(search, autoescape=True),
        ]
        toneless = normalize_pinyin(search)
        if toneless:  # empty for pure Hanzi searches
            conditions.append(VocabularyTerm.pinyin_search.contains(toneless, autoescape=True))
        filters.append(or_(*conditions))

    total = db.scalar(select(func.count()).select_from(VocabularyTerm).where(*filters)) or 0

    statement = (
        select(VocabularyTerm)
        .where(*filters)
        .order_by(VocabularyTerm.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement)), total


def get_term_by_id(db: Session, term_id: int) -> VocabularyTerm | None:
    """Return a single term or None when it does not exist."""
    return db.get(VocabularyTerm, term_id)


def count_terms_by_level(db: Session) -> dict[str, tuple[int, int]]:
    """Return {hsk_level: (terms, handwriting_required_terms)} for the levels in use."""
    handwriting_count = func.sum(case((VocabularyTerm.is_handwriting_required.is_(True), 1), else_=0))
    rows = db.execute(
        select(VocabularyTerm.hsk_level, func.count(), handwriting_count).group_by(VocabularyTerm.hsk_level)
    ).all()
    return {level: (total, int(handwriting or 0)) for level, total, handwriting in rows}
