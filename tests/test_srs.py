"""SRS: SM-2 maths (pure), service behaviour and the /api/srs routes."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import TermNotFoundError
from app.models import UserCardReview, VocabularyTerm
from app.routers.srs import get_current_time
from app.seeder import seed_vocabulary
from app.services import srs_service
from app.services.srs_service import SM2Result, calculate_sm2

UTC = timezone.utc
START = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)  # later than any seeded card, so all are due


# ------------------------------- pure SM-2 maths ------------------------------- #
def test_first_second_and_third_correct_intervals_are_1_6_and_rounded_product():
    first = calculate_sm2(0, 0, 2.5, 4)
    second = calculate_sm2(first.interval, first.repetition, first.ease_factor, 4)
    third = calculate_sm2(second.interval, second.repetition, second.ease_factor, 4)

    assert first == SM2Result(interval=1, repetition=1, ease_factor=2.5)
    assert second == SM2Result(interval=6, repetition=2, ease_factor=2.5)
    assert third == SM2Result(interval=15, repetition=3, ease_factor=2.5)


def test_interval_rounds_half_up():
    assert calculate_sm2(15, 3, 2.5, 4).interval == 38  # 37.5 -> 38
    # 5 * 2.5 = 12.5 -> 13 (Python's round() uses banker's rounding and would give 12)
    assert calculate_sm2(5, 2, 2.5, 4).interval == 13


@pytest.mark.parametrize("grade, expected_ease", [(3, 2.36), (4, 2.5), (5, 2.6)])
def test_ease_factor_update_for_each_passing_grade(grade, expected_ease):
    assert calculate_sm2(6, 2, 2.5, grade).ease_factor == pytest.approx(expected_ease)


@pytest.mark.parametrize("grade", [0, 1, 2])
def test_lapse_resets_progress_and_keeps_ease_factor(grade):
    result = calculate_sm2(interval=40, repetition=5, ease_factor=2.1, grade=grade)
    assert result == SM2Result(interval=1, repetition=0, ease_factor=2.1)


def test_ease_factor_never_drops_below_1_3():
    state = SM2Result(interval=6, repetition=2, ease_factor=1.4)
    for _ in range(5):
        state = calculate_sm2(state.interval, state.repetition, state.ease_factor, 3)
    assert state.ease_factor == 1.3


def test_hard_answers_slowly_lower_the_ease_factor():
    state = SM2Result(0, 0, 2.5)
    eases = []
    for _ in range(4):
        state = calculate_sm2(state.interval, state.repetition, state.ease_factor, 3)
        eases.append(state.ease_factor)
    assert eases == pytest.approx([2.36, 2.22, 2.08, 1.94])


def test_full_review_history():
    state = SM2Result(0, 0, 2.5)
    history = []
    for grade in [5, 5, 4, 2, 4, 4]:
        state = calculate_sm2(state.interval, state.repetition, state.ease_factor, grade)
        history.append((state.interval, state.repetition, state.ease_factor))

    assert history == [
        (1, 1, 2.6), (6, 2, 2.7), (16, 3, 2.7),  # three correct answers
        (1, 0, 2.7),                              # lapse: restart, ease factor untouched
        (1, 1, 2.7), (6, 2, 2.7),                 # climbing again
    ]


def test_interval_is_never_zero_for_inconsistent_stored_data():
    assert calculate_sm2(0, 3, 2.5, 4).interval >= 1


@pytest.mark.parametrize("grade", [-1, 6, 100])
def test_invalid_grade_raises(grade):
    with pytest.raises(ValueError):
        calculate_sm2(0, 0, 2.5, grade)


# ---------------------------------- service ---------------------------------- #
def test_seeder_creates_one_due_card_per_term_and_is_idempotent(session_factory):
    with session_factory() as db:
        terms = db.scalar(select(func.count()).select_from(VocabularyTerm))
        cards = db.scalar(select(func.count()).select_from(UserCardReview))
        assert terms == cards > 0

        seed_vocabulary(db, handwriting_characters=frozenset())
        assert db.scalar(select(func.count()).select_from(UserCardReview)) == cards


def test_ensure_cards_exist_only_creates_the_missing_ones(session_factory):
    with session_factory() as db:
        db.add(VocabularyTerm(
            portuguese="Teste", hanzi="龘龘", pinyin="dádá", category="General", hsk_level="HSK_TECH",
            example_sentence="x", example_pinyin="x", example_translation="x",
        ))
        db.commit()
        assert srs_service.ensure_cards_exist(db, START) == 1
        assert srs_service.ensure_cards_exist(db, START) == 0


def test_review_creates_the_card_when_it_is_missing(session_factory):
    with session_factory() as db:
        db.query(UserCardReview).filter_by(term_id=1).delete()
        db.commit()

        card = srs_service.review_card(db, term_id=1, grade=5, now=START)

        assert (card.interval, card.repetition, card.ease_factor) == (1, 1, 2.6)
        assert card.next_review_date == START + timedelta(days=1)


def test_review_unknown_term_raises(session_factory):
    with session_factory() as db, pytest.raises(TermNotFoundError):
        srs_service.review_card(db, term_id=999_999, grade=4, now=START)


def test_datetimes_come_back_timezone_aware(session_factory):
    with session_factory() as db:
        card = srs_service.review_card(db, term_id=1, grade=4, now=START)
        assert card.next_review_date.tzinfo is not None
        assert card.next_review_date.utcoffset() == timedelta(0)


# ----------------------------------- routes ----------------------------------- #
@pytest.fixture()
def clock(client):
    """A controllable clock injected into the SRS routes."""
    state = {"now": START}
    from app.main import app

    app.dependency_overrides[get_current_time] = lambda: state["now"]
    return state


def _total_terms(session_factory) -> int:
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(VocabularyTerm))


def test_due_lists_all_new_cards_with_their_terms(client, clock, session_factory):
    body = client.get("/api/srs/due", params={"limit": 5}).json()

    assert body["total_due"] == _total_terms(session_factory)
    assert len(body["items"]) == 5
    card = body["items"][0]
    assert (card["interval"], card["repetition"], card["ease_factor"]) == (0, 0, 2.5)
    assert {"hanzi", "pinyin", "pinyin_numeric", "pinyin_guide", "hsk_level"} <= set(card["term"])


def test_due_excludes_cards_scheduled_in_the_future(client, clock, session_factory):
    with session_factory() as db:
        db.query(UserCardReview).filter(UserCardReview.term_id != 2).update(
            {"next_review_date": START + timedelta(days=3)}
        )
        db.commit()

    body = client.get("/api/srs/due").json()
    assert body["total_due"] == 1
    assert [item["term"]["id"] for item in body["items"]] == [2]


def test_due_is_ordered_oldest_first(client, clock, session_factory):
    with session_factory() as db:
        db.query(UserCardReview).update({"next_review_date": START + timedelta(days=9)})
        db.query(UserCardReview).filter_by(term_id=5).update({"next_review_date": START - timedelta(days=2)})
        db.query(UserCardReview).filter_by(term_id=3).update({"next_review_date": START - timedelta(days=1)})
        db.commit()

    clock["now"] = START + timedelta(days=10)
    ids = [item["term"]["id"] for item in client.get("/api/srs/due", params={"limit": 3}).json()["items"]]
    assert ids[:2] == [5, 3]


def test_due_limit_is_validated(client, clock):
    assert client.get("/api/srs/due", params={"limit": 0}).status_code == 422
    assert client.get("/api/srs/due", params={"limit": 101}).status_code == 422


def test_review_updates_state_and_schedules_next_review(client, clock):
    response = client.post("/api/srs/review", json={"term_id": 1, "grade": 5})

    body = response.json()
    assert response.status_code == 200
    assert (body["interval"], body["repetition"], body["ease_factor"]) == (1, 1, 2.6)
    assert datetime.fromisoformat(body["next_review_date"]) == START + timedelta(days=1)
    assert body["term"]["id"] == 1


def test_reviewed_card_leaves_the_due_list_until_its_date(client, clock, session_factory):
    total = _total_terms(session_factory)
    client.post("/api/srs/review", json={"term_id": 1, "grade": 4})

    assert client.get("/api/srs/due").json()["total_due"] == total - 1

    clock["now"] = START + timedelta(days=1)
    assert client.get("/api/srs/due").json()["total_due"] == total


def test_consecutive_reviews_follow_the_1_6_15_day_schedule(client, clock):
    intervals = []
    for _ in range(3):
        body = client.post("/api/srs/review", json={"term_id": 1, "grade": 4}).json()
        intervals.append(body["interval"])
        clock["now"] = datetime.fromisoformat(body["next_review_date"])
    assert intervals == [1, 6, 15]


def test_wrong_answer_resets_the_card(client, clock):
    for _ in range(3):
        client.post("/api/srs/review", json={"term_id": 1, "grade": 5})
    body = client.post("/api/srs/review", json={"term_id": 1, "grade": 1}).json()

    assert (body["interval"], body["repetition"]) == (1, 0)
    assert body["ease_factor"] == pytest.approx(2.8)  # 2.5 + 3 x 0.1, untouched by the lapse


@pytest.mark.parametrize("grade", [-1, 6])
def test_grade_outside_0_to_5_returns_422(client, clock, grade):
    assert client.post("/api/srs/review", json={"term_id": 1, "grade": grade}).status_code == 422


@pytest.mark.parametrize("payload", [{"grade": 4}, {"term_id": 1}, {"term_id": 0, "grade": 4}, {"term_id": 1, "grade": "good"}])
def test_invalid_review_payload_returns_422(client, clock, payload):
    assert client.post("/api/srs/review", json=payload).status_code == 422


def test_review_unknown_term_returns_404(client, clock):
    response = client.post("/api/srs/review", json={"term_id": 999_999, "grade": 4})
    assert response.status_code == 404
    assert "não encontrado" in response.json()["detail"]


def test_database_failure_returns_500(client, clock, monkeypatch):
    def broken(*_args, **_kwargs):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(srs_service, "get_due_cards", broken)
    monkeypatch.setattr(srs_service, "review_card", broken)

    assert client.get("/api/srs/due").status_code == 500
    assert client.post("/api/srs/review", json={"term_id": 1, "grade": 4}).status_code == 500


def test_next_review_date_is_serialised_as_utc(client, clock):
    body = client.post("/api/srs/review", json={"term_id": 1, "grade": 4}).json()
    assert body["next_review_date"].endswith(("Z", "+00:00"))
