"""Time helpers: the whole application works with timezone-aware UTC datetimes."""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    """Current moment as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """DateTime column that always returns timezone-aware UTC values.

    SQLite (and plain PostgreSQL `timestamp`) drop the timezone, which would make
    API responses ambiguous. This type stores naive UTC and restores `tzinfo=UTC`
    when reading. Naive datetimes received on write are assumed to be UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
