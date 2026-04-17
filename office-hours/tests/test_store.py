"""SQLite + in-memory store tests."""
from __future__ import annotations

from datetime import date

import pytest

from store import InMemoryStore, SqliteStore


@pytest.mark.asyncio
async def test_sqlite_composite_round_trips(tmp_path):
    store = SqliteStore(path=tmp_path / "test.db")
    await store.append_composite(date(2026, 4, 15), 55.5)
    await store.append_composite(date(2026, 4, 16), 62.0)

    history = await store.get_composite_history()
    assert list(history.values) == [55.5, 62.0]


@pytest.mark.asyncio
async def test_sqlite_composite_append_replaces_same_date(tmp_path):
    store = SqliteStore(path=tmp_path / "test.db")
    await store.append_composite(date(2026, 4, 15), 55.5)
    await store.append_composite(date(2026, 4, 15), 60.0)  # same date, update

    history = await store.get_composite_history()
    assert len(history) == 1
    assert history.iloc[0] == 60.0


@pytest.mark.asyncio
async def test_sqlite_composite_exclude_filters_current_date(tmp_path):
    store = SqliteStore(path=tmp_path / "test.db")
    await store.append_composite(date(2026, 4, 15), 55.5)
    await store.append_composite(date(2026, 4, 16), 62.0)

    history = await store.get_composite_history(exclude=date(2026, 4, 16))
    assert list(history.values) == [55.5]


@pytest.mark.asyncio
async def test_sqlite_breadth_latest_metric(tmp_path):
    store = SqliteStore(path=tmp_path / "test.db")
    await store.put_metric("percent_above_50d", date(2026, 4, 14), 45.0)
    await store.put_metric("percent_above_50d", date(2026, 4, 15), 52.0)

    latest = await store.latest_metric("percent_above_50d")
    assert latest == (date(2026, 4, 15), 52.0)


@pytest.mark.asyncio
async def test_sqlite_breadth_metric_history_sorted(tmp_path):
    store = SqliteStore(path=tmp_path / "test.db")
    await store.put_metric("percent_above_50d", date(2026, 4, 16), 52.0)
    await store.put_metric("percent_above_50d", date(2026, 4, 15), 48.0)
    await store.put_metric("percent_above_50d", date(2026, 4, 14), 45.0)

    hist = await store.metric_history("percent_above_50d")
    assert list(hist.values) == [45.0, 48.0, 52.0]


@pytest.mark.asyncio
async def test_sqlite_latest_metric_missing_returns_none(tmp_path):
    store = SqliteStore(path=tmp_path / "test.db")
    assert await store.latest_metric("nonexistent") is None


@pytest.mark.asyncio
async def test_sqlite_persists_across_instances(tmp_path):
    path = tmp_path / "test.db"
    s1 = SqliteStore(path=path)
    await s1.append_composite(date(2026, 4, 15), 55.5)

    s2 = SqliteStore(path=path)
    hist = await s2.get_composite_history()
    assert list(hist.values) == [55.5]


# --- InMemoryStore ------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_store_matches_sqlite_surface():
    store = InMemoryStore()
    await store.append_composite(date(2026, 4, 15), 55.5)
    await store.put_metric("m", date(2026, 4, 15), 42.0)

    hist = await store.get_composite_history()
    assert list(hist.values) == [55.5]

    latest = await store.latest_metric("m")
    assert latest == (date(2026, 4, 15), 42.0)
