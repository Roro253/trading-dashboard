"""Persistent store for composite history and breadth snapshots.

Uses stdlib sqlite3 under asyncio.to_thread so we don't add a new
async-sqlite dependency. Two stores share one DB:

- composite_history: one row per date with the raw composite score.
  Used to percentile-map today's composite into the final 0-100
  Market Quality Score.
- breadth_cache: one row per metric per date. Today used for
  ``percent_above_50d`` — the S&P-constituent-loop computation is too
  expensive to do inline, so a separate job writes and the pipeline
  reads the latest cached value.
"""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd


COLD_START_MIN_SAMPLES = 60  # need ~3 months of daily history before percentile map is meaningful


class CompositeHistoryStore(Protocol):
    async def append_composite(self, as_of: date, composite_raw: float) -> None: ...
    async def get_composite_history(self, exclude: date | None = None) -> pd.Series: ...


class BreadthCacheStore(Protocol):
    async def put_metric(self, metric: str, as_of: date, value: float) -> None: ...
    async def latest_metric(self, metric: str) -> tuple[date, float] | None: ...


SCHEMA = """
CREATE TABLE IF NOT EXISTS composite_history (
    as_of TEXT PRIMARY KEY,
    composite_raw REAL NOT NULL,
    written_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS breadth_cache (
    metric TEXT NOT NULL,
    as_of TEXT NOT NULL,
    value REAL NOT NULL,
    written_at TEXT NOT NULL,
    PRIMARY KEY (metric, as_of)
);

CREATE INDEX IF NOT EXISTS idx_breadth_metric ON breadth_cache(metric, as_of DESC);
"""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SqliteStore:
    """Composite history + breadth cache in one SQLite file. Thread-safe
    because each operation opens its own short-lived connection."""

    path: Path | str

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None)  # autocommit
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as c:
            c.executescript(SCHEMA)

    # --- composite history -------------------------------------------

    async def append_composite(self, as_of: date, composite_raw: float) -> None:
        await asyncio.to_thread(self._append_composite_sync, as_of, composite_raw)

    def _append_composite_sync(self, as_of: date, composite_raw: float) -> None:
        with self._connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO composite_history(as_of, composite_raw, written_at) VALUES (?, ?, ?)",
                (as_of.isoformat(), float(composite_raw), _utcnow_iso()),
            )

    async def get_composite_history(self, exclude: date | None = None) -> pd.Series:
        return await asyncio.to_thread(self._get_composite_history_sync, exclude)

    def _get_composite_history_sync(self, exclude: date | None) -> pd.Series:
        with self._connect() as c:
            rows = c.execute(
                "SELECT as_of, composite_raw FROM composite_history ORDER BY as_of"
            ).fetchall()
        if not rows:
            return pd.Series(dtype=float, name="composite_raw")
        idx = pd.to_datetime([r["as_of"] for r in rows])
        vals = [r["composite_raw"] for r in rows]
        s = pd.Series(vals, index=idx, name="composite_raw", dtype="float64")
        if exclude is not None:
            s = s[s.index != pd.Timestamp(exclude)]
        return s

    # --- breadth cache -----------------------------------------------

    async def put_metric(self, metric: str, as_of: date, value: float) -> None:
        await asyncio.to_thread(self._put_metric_sync, metric, as_of, value)

    def _put_metric_sync(self, metric: str, as_of: date, value: float) -> None:
        with self._connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO breadth_cache(metric, as_of, value, written_at) VALUES (?, ?, ?, ?)",
                (metric, as_of.isoformat(), float(value), _utcnow_iso()),
            )

    async def latest_metric(self, metric: str) -> tuple[date, float] | None:
        return await asyncio.to_thread(self._latest_metric_sync, metric)

    def _latest_metric_sync(self, metric: str) -> tuple[date, float] | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT as_of, value FROM breadth_cache WHERE metric = ? ORDER BY as_of DESC LIMIT 1",
                (metric,),
            ).fetchone()
        if row is None:
            return None
        return (date.fromisoformat(row["as_of"]), float(row["value"]))

    async def metric_history(self, metric: str) -> pd.Series:
        return await asyncio.to_thread(self._metric_history_sync, metric)

    def _metric_history_sync(self, metric: str) -> pd.Series:
        with self._connect() as c:
            rows = c.execute(
                "SELECT as_of, value FROM breadth_cache WHERE metric = ? ORDER BY as_of",
                (metric,),
            ).fetchall()
        if not rows:
            return pd.Series(dtype=float, name=metric)
        idx = pd.to_datetime([r["as_of"] for r in rows])
        return pd.Series([r["value"] for r in rows], index=idx, name=metric, dtype="float64")


@dataclass
class InMemoryStore:
    """No-persistence store for tests. Same surface as SqliteStore."""

    composite: dict[date, float] = None  # type: ignore[assignment]
    metrics: dict[str, dict[date, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.composite is None:
            self.composite = {}
        if self.metrics is None:
            self.metrics = {}

    async def append_composite(self, as_of: date, composite_raw: float) -> None:
        self.composite[as_of] = float(composite_raw)

    async def get_composite_history(self, exclude: date | None = None) -> pd.Series:
        if not self.composite:
            return pd.Series(dtype=float, name="composite_raw")
        items = sorted(self.composite.items())
        idx = pd.to_datetime([d for d, _ in items])
        vals = [v for _, v in items]
        s = pd.Series(vals, index=idx, name="composite_raw", dtype="float64")
        if exclude is not None:
            s = s[s.index != pd.Timestamp(exclude)]
        return s

    async def put_metric(self, metric: str, as_of: date, value: float) -> None:
        self.metrics.setdefault(metric, {})[as_of] = float(value)

    async def latest_metric(self, metric: str) -> tuple[date, float] | None:
        m = self.metrics.get(metric)
        if not m:
            return None
        d = max(m)
        return (d, m[d])

    async def metric_history(self, metric: str) -> pd.Series:
        m = self.metrics.get(metric) or {}
        if not m:
            return pd.Series(dtype=float, name=metric)
        items = sorted(m.items())
        idx = pd.to_datetime([d for d, _ in items])
        return pd.Series([v for _, v in items], index=idx, name=metric, dtype="float64")
