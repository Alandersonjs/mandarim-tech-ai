"""HSK 3.0 level metadata shared by the whole application."""

from dataclasses import dataclass

from app.models import HSKLevel

# Rank used to compare levels. HSK_TECH is intentionally absent: technical
# vocabulary is not part of the official HSK word lists.
LEVEL_RANK: dict[str, int] = {
    HSKLevel.HSK1.value: 1,
    HSKLevel.HSK2.value: 2,
    HSKLevel.HSK3.value: 3,
    HSKLevel.HSK4.value: 4,
    HSKLevel.TECH.value: 5,
}

_RANK_TO_LEVEL: dict[int, HSKLevel] = {
    1: HSKLevel.HSK1,
    2: HSKLevel.HSK2,
    3: HSKLevel.HSK3,
    4: HSKLevel.HSK4,
}


def is_official_level(level: str) -> bool:
    """True for HSK1..HSK4 (the levels backed by the official word lists)."""
    return level != HSKLevel.TECH.value


def level_from_rank(rank: int) -> HSKLevel | None:
    """Return the HSK level for a rank (1-4) or None when out of range."""
    return _RANK_TO_LEVEL.get(rank)


@dataclass(frozen=True)
class LevelTarget:
    """Cumulative word goal of one HSK level."""

    level: HSKLevel
    cumulative_words: int


# Cumulative targets of the HSK 3.0 syllabus effective from July 2026
# (HSK 1: 300 | HSK 2: 500 | HSK 3: 1,000 | HSK 4: 2,000).
# NOTE: the 2021 draft of the standard used 500 / 1,272 / 2,245 / 3,245. Word
# lists published before the 2025/2026 revision (e.g. the "500 words" HSK 1 PDF)
# follow that older distribution.
LEVEL_TARGETS: tuple[LevelTarget, ...] = (
    LevelTarget(HSKLevel.HSK1, 300),
    LevelTarget(HSKLevel.HSK2, 500),
    LevelTarget(HSKLevel.HSK3, 1000),
    LevelTarget(HSKLevel.HSK4, 2000),
)
