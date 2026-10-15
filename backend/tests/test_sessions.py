"""Refresh-token sessions (services/sessions.py): rotation, replay detection, expiry, logout.

Uses a throwaway in-memory SQLite database with just the two tables involved."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import RefreshToken, User
from services import sessions
from services.sessions import SessionError


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    User.__table__.create(engine)
    RefreshToken.__table__.create(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(
            User(full_name="Test Patient", email="phase0-test-x@test.com", hashed_password="x", role="PATIENT",
                 phone="0300 1", is_active=True)
        )  # fmt: skip
        session.commit()
        yield session


def sign_in(db):
    user = db.query(User).one()
    pair = sessions.start_session(db, user)
    db.commit()
    return user, pair


def test_only_a_hash_of_the_refresh_token_is_stored(db):
    _, (_, refresh) = sign_in(db)
    row = db.query(RefreshToken).one()
    assert row.token_hash != refresh and refresh not in row.token_hash and len(row.token_hash) == 64


def test_refreshing_rotates_the_token_and_keeps_the_family(db):
    user, (_, first) = sign_in(db)
    same_user, access, second = sessions.refresh_session(db, first)
    assert same_user.id == user.id and access and second != first
    rows = db.query(RefreshToken).order_by(RefreshToken.id).all()
    assert rows[0].revoked_at is not None and rows[1].revoked_at is None
    assert rows[0].family_id == rows[1].family_id


def test_a_used_token_presented_again_revokes_the_whole_session(db):
    _, (_, first) = sign_in(db)
    _, _, second = sessions.refresh_session(db, first)
    long_ago = datetime.now(UTC) - timedelta(seconds=sessions.GRACE_SECONDS + 1)
    db.query(RefreshToken).filter(RefreshToken.revoked_at.is_not(None)).update({"revoked_at": long_ago})
    db.commit()
    with pytest.raises(SessionError):
        sessions.refresh_session(db, first)  # replay of the old token: a stolen copy
    with pytest.raises(SessionError):
        sessions.refresh_session(db, second)  # the legitimate newer token is revoked too
    assert db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0


def test_unknown_and_expired_tokens_are_refused(db):
    _, (_, refresh) = sign_in(db)
    with pytest.raises(SessionError):
        sessions.refresh_session(db, "not-a-token")
    db.query(RefreshToken).update({"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    db.commit()
    with pytest.raises(SessionError):
        sessions.refresh_session(db, refresh)


def test_an_inactive_account_cannot_refresh(db):
    user, (_, refresh) = sign_in(db)
    user.is_active = False
    db.commit()
    with pytest.raises(SessionError):
        sessions.refresh_session(db, refresh)
    assert db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0


def test_logout_ends_the_session_and_ignores_unknown_tokens(db):
    _, (_, refresh) = sign_in(db)
    sessions.end_session(db, "not-a-token")
    sessions.end_session(db, refresh)
    with pytest.raises(SessionError):
        sessions.refresh_session(db, refresh)


def test_two_sign_ins_are_separate_sessions(db):
    _, (_, first) = sign_in(db)
    _, (_, other) = sign_in(db)
    sessions.end_session(db, first)
    sessions.refresh_session(db, other)  # the other device stays signed in


def test_the_access_token_is_short_lived_and_names_the_role():
    from auth import decode_access_token
    from config import Settings

    user = User(id=7, full_name="x", email="a@b.c", hashed_password="x", role="DOCTOR", phone="1")
    claims = decode_access_token(sessions.access_token_for(user))
    assert claims["sub"] == "7" and claims["role"] == "doctor"
    assert claims["exp"] - claims["iat"] == Settings().access_token_expire_minutes * 60 <= 900


def test_a_token_that_just_raced_the_rotation_is_refused_without_ending_the_session(db):
    _, (_, first) = sign_in(db)
    _, _, second = sessions.refresh_session(db, first)
    with pytest.raises(SessionError):
        sessions.refresh_session(db, first)  # the other tab's parallel call, a moment later
    sessions.refresh_session(db, second)  # the session is still alive
