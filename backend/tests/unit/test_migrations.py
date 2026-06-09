"""Lightweight SQLite migrations (app/database.py).

Regression guard for the *"no such column: app_settings.memory_enabled"* startup
crash: when a column is added to a model, an existing DB created by an older
build must be upgraded in place by ``_apply_lightweight_migrations`` —
``create_all`` only creates missing *tables*, it never alters existing ones.
This path isn't exercised by the normal test suite (which recreates every table
fresh per test), so it gets its own test.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.unit


async def _columns(conn, table: str) -> set[str]:
    res = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in res.fetchall()}


async def test_migration_adds_memory_enabled_to_existing_db(tmp_path):
    from app.database import _apply_lightweight_migrations

    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")
    try:
        # Simulate an app_settings table from an older build — no memory_enabled.
        async with eng.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE app_settings ("
                "id VARCHAR(36) PRIMARY KEY, llm_provider VARCHAR(50), "
                "llm_model VARCHAR(100), default_jd_intensity INTEGER)"
            ))
            await conn.execute(text(
                "INSERT INTO app_settings (id, llm_provider) VALUES ('1', 'google')"
            ))
            assert "memory_enabled" not in await _columns(conn, "app_settings")

        # This is what init_db() runs right after create_all.
        async with eng.begin() as conn:
            await _apply_lightweight_migrations(conn)
            cols = await _columns(conn, "app_settings")

        assert "memory_enabled" in cols  # the column the crash was about
    finally:
        await eng.dispose()


async def test_migrations_are_idempotent(tmp_path):
    """Re-running migrations must be a no-op, not a 'duplicate column' error —
    every ALTER is guarded by a PRAGMA column check."""
    from app.database import _apply_lightweight_migrations

    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")
    try:
        async with eng.begin() as conn:
            await conn.execute(text("CREATE TABLE app_settings (id VARCHAR(36) PRIMARY KEY)"))
        async with eng.begin() as conn:
            await _apply_lightweight_migrations(conn)
        async with eng.begin() as conn:
            await _apply_lightweight_migrations(conn)  # second pass — no error
            cols = await _columns(conn, "app_settings")
        assert "memory_enabled" in cols
    finally:
        await eng.dispose()
