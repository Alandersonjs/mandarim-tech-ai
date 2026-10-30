"""Spaced repetition with the SuperMemo SM-2 algorithm.

Reference: P. A. Wozniak, "Application of a computer to improve the results
obtained in working with the SuperMemo method" (SM-2, 1987).

For a review graded q (0-5):
  * q >= 3 (correct):  I(1) = 1 day, I(2) = 6 days, I(n) = round(I(n-1) * EF) for n > 2,
                       and EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)),
                       never below 1.3.
  * q <  3 (lapse):    the repetitions restart from the beginning (repetition = 0,
                       interval = 1 day) WITHOUT changing the ease factor.
Many online implementations also change EF on a lapse; this one follows the
original description.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.exceptions import TermNotFoundError
from app.models import UserCardReview, VocabularyTerm

DEFAULT_EASE_FACTOR = 2.5
MIN_EASE_FACTOR = 1.3
FIRST_INTERVAL_DAYS = 1
SECOND_INTERVAL_DAYS = 6
MIN_GRADE, MAX_GRADE = 0, 5
PASSING_GRADE = 3


@dataclass(frozen=True)
class SM2Result:
    """New scheduling state of a card."""

    interval: int
    repetition: int
    ease_factor: float


def _round_half_up(value: float) -> int:
    """Round .5 upwards (Python's round() would use banker's rounding)."""
    return int(math.floor(value + 0.5))


def calculate_sm2(interval: int, repetition: int, ease_factor: float, grade: int) -> SM2Result:
    """Pure SM-2 step: compute the next state from the current state and the grade.

    Args:
        interval: Current interval in days.
        repetition: Consecutive correct answers so far.
        ease_factor: Current ease factor (>= 1.3).
        grade: 0-2 = wrong/reset, 3 = hard, 4 = good, 5 = perfect.

    Raises:
        ValueError: if the grade is outside 0-5.
    """
    if not MIN_GRADE <= grade <= MAX_GRADE:
        raise ValueError(f"grade must be between {MIN_GRADE} and {MAX_GRADE}, got {grade}.")

    if grade < PASSING_GRADE:
        return SM2Result(interval=FIRST_INTERVAL_DAYS, repetition=0, ease_factor=ease_factor)

    if repetition == 0:
        new_interval = FIRST_INTERVAL_DAYS
    elif repetition == 1:
        new_interval = SECOND_INTERVAL_DAYS
    else:
        # max(1, ...) protects against inconsistent stored data (interval 0 after 2+ repetitions).
        new_interval = max(FIRST_INTERVAL_DAYS, _round_half_up(interval * ease_factor))

    distance = MAX_GRADE - grade
    new_ease = ease_factor + (0.1 - distance * (0.08 + distance * 0.02))
    # Rounded to 2 decimals: every SM-2 step is a multiple of 0.02, so this only removes float noise.
    new_ease = max(MIN_EASE_FACTOR, round(new_ease, 2))

    return SM2Result(interval=new_interval, repetition=repetition + 1, ease_factor=new_ease)


def ensure_cards_exist(db: Session, now: datetime) -> int:
    """Create a card (due immediately) for every term that does not have one yet.

    Returns the number of cards created. Idempotent.
    """
    missing_term_ids = db.scalars(
        select(VocabularyTerm.id)
        .outerjoin(UserCardReview, UserCardReview.term_id == VocabularyTerm.id)
        .where(UserCardReview.id.is_(None))
    ).all()
    db.add_all(
        UserCardReview(
            term_id=term_id,
            interval=0,
            repetition=0,
            ease_factor=DEFAULT_EASE_FACTOR,
            next_review_date=now,
        )
        for term_id in missing_term_ids
    )
    db.commit()
    return len(missing_term_ids)


def get_due_cards(db: Session, now: datetime, limit: int = 20) -> tuple[list[UserCardReview], int]:
    """Return the cards due at `now` (oldest first) and the total number of due cards."""
    due_filter = UserCardReview.next_review_date <= now
    total_due = db.scalar(select(func.count()).select_from(UserCardReview).where(due_filter)) or 0
    cards = db.scalars(
        select(UserCardReview)
        .options(joinedload(UserCardReview.term))
        .where(due_filter)
        .order_by(UserCardReview.next_review_date, UserCardReview.id)
        .limit(limit)
    ).all()
    return list(cards), total_due


def review_card(db: Session, term_id: int, grade: int, now: datetime) -> UserCardReview:
    """Apply a review to the card of a term and schedule the next one.

    A card is created on the fly if the term does not have one yet.

    Raises:
        TermNotFoundError: if the term does not exist.
        ValueError: if the grade is outside 0-5.
    """
    if db.get(VocabularyTerm, term_id) is None:
        raise TermNotFoundError(term_id)

    card = db.scalar(
        select(UserCardReview).options(joinedload(UserCardReview.term)).where(UserCardReview.term_id == term_id)
    )
    if card is None:
        card = UserCardReview(
            term_id=term_id, interval=0, repetition=0, ease_factor=DEFAULT_EASE_FACTOR, next_review_date=now
        )
        db.add(card)

    result = calculate_sm2(card.interval, card.repetition, card.ease_factor, grade)
    card.interval = result.interval
    card.repetition = result.repetition
    card.ease_factor = result.ease_factor
    card.next_review_date = now + timedelta(days=result.interval)

    db.commit()
    db.refresh(card)
    return card
