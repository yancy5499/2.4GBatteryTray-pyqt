# -*- coding: utf-8 -*-
"""Indexed 90-day battery history under ``<data>/log/history.sqlite3``.

Legacy CSV files are imported in the poller and preserved as archives.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import settings as settings_module
from log import log
from model import DeviceView

HEADER = ["timestamp", "epoch", "device_name", "kind", "vid_pid",
          "level", "charging", "source", "serial"]

SERIES_COLORS = (
    "#2f7df6", "#22b573", "#f2a93b", "#ef5350",
    "#8b5cf6", "#14b8a6", "#ec4899", "#64748b",
)

MAX_SERIES = 8
RETENTION_DAYS = 90


@dataclass
class HistorySeries:
    key: str
    name: str
    kind: str
    vid_pid: str
    color: str
    points: list[tuple[float, Optional[float]]] = field(default_factory=list)
    latest: Optional[int] = None
    count: int = 0


@dataclass
class HistoryData:
    bucket: str
    range_label: str
    starts: list[datetime] = field(default_factory=list)
    series: list[HistorySeries] = field(default_factory=list)
    truncated: int = 0

    @property
    def total_rows(self) -> int:
        return sum(item.count for item in self.series)


def log_dir(create: bool = True) -> Path:
    path = Path(settings_module.data_dir()) / "log"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", value).strip("-")
    return cleaned[:32] or fallback


def file_stem(device: DeviceView) -> str:
    """Deterministic file name: one CSV per kind + VID/PID.

    The serial is intentionally not part of the file name: some receivers
    expose it intermittently, and a changing serial must not create a new
    file for the same device.
    """
    kind = _safe_part(device.kind, "device")
    vid = _safe_part(device.vid_pid.replace(":", "-"), "0000")
    return f"{kind}-{vid}"


def file_for(device: DeviceView) -> Path:
    return log_dir() / f"{file_stem(device)}.csv"


def _connect(timeout: float = 5) -> sqlite3.Connection:
    connection = sqlite3.connect(log_dir() / "history.sqlite3", timeout=timeout)
    try:
        # Readers can display existing history during a long legacy import.
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA cache_size=-2048")
        connection.execute("""CREATE TABLE IF NOT EXISTS readings (
        device TEXT NOT NULL, epoch INTEGER NOT NULL, level INTEGER NOT NULL,
        name TEXT, kind TEXT, vid_pid TEXT, charging INTEGER, source TEXT,
        serial TEXT, PRIMARY KEY(device, epoch, level))""")
        connection.execute("CREATE INDEX IF NOT EXISTS readings_epoch ON readings(epoch)")
        connection.execute("""CREATE TABLE IF NOT EXISTS imports (
        path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER)""")
    except Exception:
        connection.close()
        raise
    return connection


def consolidate() -> None:
    """Stream legacy CSVs into SQLite; retain originals as user archives.

    A transaction per file makes interrupted imports safe to retry. File
    signatures avoid re-reading unchanged archives on subsequent starts.
    """
    try:
        with closing(_connect()) as db:
            cutoff = int((datetime.now() - timedelta(days=RETENTION_DAYS)).timestamp())
            for path in sorted(log_dir().glob("*.csv")):
                stat = path.stat()
                signature = (path.name, stat.st_size, stat.st_mtime_ns)
                if db.execute("SELECT 1 FROM imports WHERE path=? AND size=? AND mtime=?",
                              signature).fetchone():
                    continue
                parts = path.stem.split("-")
                if len(parts) < 3:
                    continue
                key = "-".join(parts[:3])
                try:
                    with db, path.open("r", encoding="utf-8-sig", newline="") as fh:
                        for row in csv.DictReader(fh):
                            epoch = _epoch_of(row)
                            try:
                                level = int(float(row.get("level") or ""))
                            except (ValueError, TypeError, OverflowError):
                                continue
                            if epoch < cutoff or not 0 <= level <= 100:
                                continue
                            db.execute("INSERT OR IGNORE INTO readings VALUES (?,?,?,?,?,?,?,?,?)",
                                       (key, epoch, level, row.get("device_name", ""),
                                        row.get("kind", ""), row.get("vid_pid", ""),
                                        int(row.get("charging") == "1"),
                                        row.get("source", ""), row.get("serial", "")))
                        db.execute("INSERT OR REPLACE INTO imports VALUES (?,?,?)", signature)
                except Exception as exc:
                    log(f"history import failed: {path}: {exc}")
            with db:
                db.execute("DELETE FROM readings WHERE epoch < ?", (cutoff,))
    except Exception as exc:
        log(f"history initialization failed: {exc}")


def append_readings(devices: Iterable[DeviceView]) -> None:
    """Store bounded history; SQLite reuses pages freed by retention cleanup."""
    now = int(datetime.now().timestamp())
    try:
        with closing(_connect()) as db, db:
            for device in devices:
                if device.level is None:
                    continue
                db.execute("INSERT OR IGNORE INTO readings VALUES (?,?,?,?,?,?,?,?,?)",
                           (file_stem(device), now, device.level, device.name,
                            device.kind, device.vid_pid, int(device.charging),
                            getattr(device.reading, "source", "") or "",
                            device.serial or ""))
            db.execute("DELETE FROM readings WHERE epoch < ?",
                       (now - RETENTION_DAYS * 86400,))
    except Exception as exc:
        log(f"history write failed: {exc}")


def _bucket_spec(bucket: str) -> tuple[list[datetime], int, str]:
    now = datetime.now()
    if bucket == "day":
        anchor = now.replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [anchor - timedelta(days=offset)
                  for offset in range(29, -1, -1)]
        return starts, 86400, "最近一个月"
    anchor = now.replace(minute=0, second=0, microsecond=0)
    starts = [anchor - timedelta(hours=offset)
              for offset in range(23, -1, -1)]
    return starts, 3600, "最近 24 小时"


def _epoch_of(row: dict) -> int:
    raw = row.get("epoch") or ""
    try:
        return int(float(raw))
    except (TypeError, ValueError, OverflowError):
        raw = row.get("timestamp") or ""
        try:
            return int(datetime.fromisoformat(raw).timestamp())
        except (TypeError, ValueError, OverflowError):
            return 0


def load_history(bucket: str = "hour") -> HistoryData:
    starts, step, range_label = _bucket_spec(bucket)
    start_epoch = int(starts[0].timestamp())
    end_epoch = int(starts[-1].timestamp()) + step
    data = HistoryData(bucket=bucket, range_label=range_label, starts=starts)

    directory = log_dir(create=False)
    if not directory.is_dir():
        return data

    candidates: list[HistorySeries] = []
    try:
        with closing(_connect(timeout=0.05)) as db:
            # Aggregate in SQLite so Python only receives at most 30 points
            # per selected device, regardless of the number of stored polls.
            total = db.execute("""SELECT COUNT(DISTINCT device) FROM readings
                WHERE epoch >= ? AND epoch < ?""", (start_epoch, end_epoch)).fetchone()[0]
            keys = db.execute("""SELECT device, MAX(name), MAX(kind), MAX(vid_pid)
                FROM readings WHERE epoch >= ? AND epoch < ?
                GROUP BY device ORDER BY LOWER(MAX(name)), MAX(vid_pid), device LIMIT ?""",
                              (start_epoch, end_epoch, MAX_SERIES)).fetchall()
            data.truncated = max(0, total - MAX_SERIES)
            for key, name, kind, vid_pid in keys:
                rows = db.execute("""SELECT (epoch - ?) / ?, AVG(level), COUNT(*)
                    FROM readings WHERE device=? AND epoch >= ? AND epoch < ?
                    GROUP BY (epoch - ?) / ?""",
                                  (start_epoch, step, key, start_epoch, end_epoch,
                                   start_epoch, step)).fetchall()
                values = {int(index): (value, count) for index, value, count in rows}
                points = [(start.timestamp(), values.get(index, (None, 0))[0])
                          for index, start in enumerate(starts)]
                latest = next((int(round(value)) for _, value in reversed(points)
                               if value is not None), None)
                candidates.append(HistorySeries(
                    key=key, name=name or key, kind=kind, vid_pid=vid_pid,
                    color=SERIES_COLORS[len(candidates) % len(SERIES_COLORS)],
                    points=points, latest=latest,
                    count=sum(count for _, count in values.values())))
    except Exception as exc:
        log(f"history read failed: {exc}")
    data.series = candidates
    return data
