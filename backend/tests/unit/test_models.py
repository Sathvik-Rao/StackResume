"""SQLAlchemy model defaults + cascade behaviour."""
from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.unit


async def test_session_defaults(db_session):
    from app.models import Session

    s = Session()
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    assert s.id and len(s.id) == 36
    assert s.title == "New Resume"
    assert s.is_favorite is False
    assert s.created_at is not None


async def test_message_cascade_delete(db_session):
    from app.models import Session, Message

    s = Session(title="parent")
    db_session.add(s)
    await db_session.commit()

    m = Message(session_id=s.id, role="user", content="hi", status="complete")
    db_session.add(m)
    await db_session.commit()

    await db_session.delete(s)
    await db_session.commit()

    res = await db_session.execute(select(Message).where(Message.session_id == s.id))
    assert res.scalar_one_or_none() is None


async def test_app_settings_single_row_pattern(db_session):
    """The app stores a single row — make sure default UUIDs don't collide."""
    from app.models import AppSettings

    row1 = AppSettings()
    db_session.add(row1)
    await db_session.commit()
    row2 = AppSettings()
    db_session.add(row2)
    await db_session.commit()
    assert row1.id != row2.id
