"""Loads the initial vocabulary (technical terms + HSK 3.0 words) and their SRS cards."""

import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import VocabularyTerm
from app.pinyin_guide import build_pinyin_guide
from app.seed_data import (
    SEED_TERMS,
    SeedTerm,
    build_radical_breakdown,
    load_handwriting_characters,
)
from app.services.srs_service import ensure_cards_exist
from app.text_utils import HANZI_PATTERN, pinyin_to_numeric, to_pinyin
from app.timeutils import utc_now

logger = logging.getLogger(__name__)


def is_handwriting_required(hanzi: str, handwriting_characters: frozenset[str]) -> bool:
    """A term needs handwriting only when ALL its Han characters are in the list."""
    characters = HANZI_PATTERN.findall(hanzi)
    return bool(characters) and all(char in handwriting_characters for char in characters)


def _build_term(seed: SeedTerm, handwriting_characters: frozenset[str]) -> VocabularyTerm:
    """Create the ORM object, deriving every computed field from the seed data."""
    return VocabularyTerm(
        portuguese=seed.portuguese,
        hanzi=seed.hanzi,
        pinyin=seed.pinyin,
        category=seed.category.value,
        hsk_level=seed.hsk_level.value,
        is_handwriting_required=is_handwriting_required(seed.hanzi, handwriting_characters),
        radical_breakdown=build_radical_breakdown(seed.hanzi),
        pinyin_guide=build_pinyin_guide(seed.hanzi),
        pinyin_numeric=pinyin_to_numeric(seed.pinyin),
        example_sentence=seed.example_sentence,
        example_pinyin=to_pinyin(seed.example_sentence),
        example_translation=seed.example_translation,
    )


def sync_handwriting_flags(db: Session, handwriting_characters: frozenset[str]) -> int:
    """Recompute `is_handwriting_required` for every stored term.

    Returns the number of terms flagged as handwriting-required afterwards.
    """
    flagged = 0
    for term_id, hanzi in db.execute(select(VocabularyTerm.id, VocabularyTerm.hanzi)).all():
        required = is_handwriting_required(hanzi, handwriting_characters)
        flagged += int(required)
        db.execute(
            update(VocabularyTerm)
            .where(VocabularyTerm.id == term_id)
            .values(is_handwriting_required=required)
        )
    db.commit()
    return flagged


def seed_vocabulary(db: Session, handwriting_characters: frozenset[str] | None = None) -> int:
    """Insert the initial terms that are not in the database yet.

    The function is idempotent: existing terms are detected by their Hanzi and
    never duplicated. The handwriting flags are re-synchronised on every run so
    that edits in `data/handwriting_characters.txt` take effect on restart.

    Returns:
        The number of terms inserted in this run.
    """
    if handwriting_characters is None:
        handwriting_characters = load_handwriting_characters()

    existing_hanzi = set(db.scalars(select(VocabularyTerm.hanzi)))
    new_terms = [
        _build_term(seed, handwriting_characters)
        for seed in SEED_TERMS
        if seed.hanzi not in existing_hanzi
    ]
    if new_terms:
        db.add_all(new_terms)
        db.commit()
        logger.info("Seeder: %d vocabulary term(s) inserted.", len(new_terms))
    else:
        logger.info("Seeder: vocabulary already populated, nothing to insert.")

    flagged = sync_handwriting_flags(db, handwriting_characters)
    logger.info("Seeder: %d term(s) flagged as handwriting-required.", flagged)

    created_cards = ensure_cards_exist(db, utc_now())
    if created_cards:
        logger.info("Seeder: %d SRS card(s) created.", created_cards)
    return len(new_terms)
