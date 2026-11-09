"""Repository and persistence tests against a real (in-memory or temp-file) SQLite database."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ShortCodeConflictError
from app.database.base import Base
from app.database.connection import build_engine
from app.models.url import URL, utcnow
from app.repositories.url_repository import URLRepository


def test_record_is_inserted(db_session):
    repository = URLRepository(db_session)

    record = repository.create("https://example.com/a", "abc1234")

    assert record.id is not None
    assert db_session.execute(select(func.count()).select_from(URL)).scalar_one() == 1


def test_record_can_be_retrieved(db_session):
    repository = URLRepository(db_session)
    repository.create("https://example.com/a", "abc1234")

    found = repository.get_by_short_code("abc1234")

    assert found is not None
    assert found.original_url == "https://example.com/a"
    assert found.short_code == "abc1234"


def test_missing_record_returns_none(db_session):
    assert URLRepository(db_session).get_by_short_code("nope1234") is None


def test_short_code_exists(db_session):
    repository = URLRepository(db_session)
    repository.create("https://example.com/a", "abc1234")

    assert repository.short_code_exists("abc1234") is True
    assert repository.short_code_exists("zzz9999") is False


def test_repository_rejects_duplicate_short_code(db_session):
    repository = URLRepository(db_session)
    repository.create("https://example.com/a", "abc1234")

    with pytest.raises(ShortCodeConflictError):
        repository.create("https://example.com/b", "abc1234")


def test_session_is_usable_after_a_rolled_back_conflict(db_session):
    repository = URLRepository(db_session)
    repository.create("https://example.com/a", "abc1234")
    with pytest.raises(ShortCodeConflictError):
        repository.create("https://example.com/b", "abc1234")

    repository.create("https://example.com/c", "other12")

    assert db_session.execute(select(func.count()).select_from(URL)).scalar_one() == 2


def test_database_enforces_unique_short_code_even_without_the_repository(db_session):
    db_session.add(URL(original_url="https://a.example", short_code="same123", created_at=utcnow()))
    db_session.commit()

    db_session.add(URL(original_url="https://b.example", short_code="same123", created_at=utcnow()))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_short_codes_are_case_sensitive_in_the_database(db_session):
    repository = URLRepository(db_session)
    repository.create("https://example.com/a", "AbCdEfG")
    repository.create("https://example.com/b", "abcdefg")

    assert repository.get_by_short_code("AbCdEfG").original_url == "https://example.com/a"
    assert repository.get_by_short_code("abcdefg").original_url == "https://example.com/b"


def test_required_columns_are_not_nullable():
    table = Base.metadata.tables["urls"]

    assert table.c.original_url.nullable is False
    assert table.c.short_code.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is True


def test_short_code_has_a_unique_index(engine):
    indexes = inspect(engine).get_indexes("urls")

    assert any(index["unique"] and index["column_names"] == ["short_code"] for index in indexes)


def test_timestamps_round_trip_as_aware_utc(db_session):
    repository = URLRepository(db_session)
    original_created_at = repository.create("https://example.com/a", "abc1234").created_at
    db_session.expire_all()  # force a real reload from the database

    reloaded = repository.get_by_short_code("abc1234")

    assert reloaded.created_at.tzinfo is not None
    assert reloaded.created_at.utcoffset() == timedelta(0)
    assert reloaded.created_at == original_created_at
    assert reloaded.updated_at is None


def test_naive_datetimes_are_refused(db_session):
    db_session.add(
        URL(original_url="https://a.example", short_code="naive12", created_at=datetime.now())
    )
    with pytest.raises((StatementError, ValueError)):
        db_session.commit()
    db_session.rollback()


def test_records_survive_an_application_restart(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'short_url.db'}"

    first_engine = build_engine(database_url)
    Base.metadata.create_all(bind=first_engine)
    with sessionmaker(bind=first_engine, expire_on_commit=False)() as session:
        URLRepository(session).create("https://example.com/persisted", "keep123")
    first_engine.dispose()  # simulates the application shutting down

    second_engine = build_engine(database_url)
    Base.metadata.create_all(bind=second_engine)  # what init_db() does on start-up
    with sessionmaker(bind=second_engine, expire_on_commit=False)() as session:
        found = URLRepository(session).get_by_short_code("keep123")
    second_engine.dispose()

    assert found is not None
    assert found.original_url == "https://example.com/persisted"
