# -*- coding: utf-8 -*-
"""Per-device battery history stored as CSV files under ``<data>/log``.

Every successful poll appends one row per device (timestamp, level, ...).
The history page aggregates those rows into hourly or daily buckets.
"""

from __future__ import annotations

import csv
import re
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
_last_written: dict[str, tuple[int, int]] = {}


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


def consolidate() -> None:
    """Merge per-detection / serial-suffixed CSVs into one file per model."""
    directory = log_dir(create=False)
    if not directory.is_dir():
        return
    groups: dict[str, list[Path]] = {}
    for path in sorted(directory.glob("*.csv")):
        parts = path.stem.split("-")
        if len(parts) < 3:
            continue
        canonical = "-".join(parts[:3]) + ".csv"
        groups.setdefault(canonical, []).append(path)
    for canonical_name, files in groups.items():
        if len(files) == 1 and files[0].name == canonical_name:
            continue
        canonical = directory / canonical_name
        merged: dict[tuple[str, str], dict] = {}
        for path in files:
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as fh:
                    for row in csv.DictReader(fh):
                        key = (str(row.get("epoch") or row.get("timestamp") or ""),
                               str(row.get("level") or ""))
                        merged.setdefault(key, row)
            except Exception as exc:
                log(f"history consolidate read failed: {path}: {exc}")
        if not merged:
            continue
        ordered = sorted(
            merged.values(),
            key=lambda row: (int(float(row.get("epoch") or 0)),
                             int(float(row.get("level") or 0))))
        try:
            with canonical.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=HEADER,
                                        extrasaction="ignore")
                writer.writeheader()
                for row in ordered:
                    writer.writerow({field: row.get(field, "")
                                     for field in HEADER})
        except Exception as exc:
            log(f"history consolidate write failed: {canonical}: {exc}")
            continue
        for path in files:
            if path != canonical:
                try:
                    path.unlink()
                except OSError:
                    pass
        log(f"history consolidated {len(files)} file(s) -> {canonical.name}")


def append_readings(devices: Iterable[DeviceView]) -> None:
    """Append one row for every device that produced a valid level."""
    now = datetime.now()
    stamp = now.isoformat(timespec="seconds")
    epoch = int(now.timestamp())
    for device in devices:
        level = device.level
        if level is None:
            continue
        try:
            path = file_for(device)
        except Exception as exc:
            log(f"history directory failed: {exc}")
            continue
        previous = _last_written.get(str(path))
        if previous == (epoch, level):
            continue
        _last_written[str(path)] = (epoch, level)
        is_new = not path.exists()
        try:
            mode = "w" if is_new else "a"
            encoding = "utf-8-sig" if is_new else "utf-8"
            with path.open(mode, encoding=encoding, newline="") as fh:
                writer = csv.writer(fh)
                if is_new:
                    writer.writerow(HEADER)
                writer.writerow([
                    stamp, epoch, device.name, device.kind, device.vid_pid,
                    int(level), int(device.charging),
                    getattr(device.reading, "source", "") or "",
                    getattr(device, "serial", "") or "",
                ])
        except Exception as exc:
            log(f"history write failed: {path}: {exc}")


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
    except (TypeError, ValueError):
        raw = row.get("timestamp") or ""
        try:
            return int(datetime.fromisoformat(raw).timestamp())
        except (TypeError, ValueError):
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
    for path in sorted(directory.glob("*.csv")):
        sums = [0.0] * len(starts)
        counts = [0] * len(starts)
        name = ""
        kind = ""
        vid_pid = ""
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    epoch = _epoch_of(row)
                    if epoch < start_epoch or epoch >= end_epoch:
                        continue
                    try:
                        level = int(float(row.get("level") or ""))
                    except (TypeError, ValueError):
                        continue
                    if not 0 <= level <= 100:
                        continue
                    index = int((epoch - start_epoch) // step)
                    if not 0 <= index < len(starts):
                        continue
                    sums[index] += level
                    counts[index] += 1
                    name = row.get("device_name") or name
                    kind = row.get("kind") or kind
                    vid_pid = row.get("vid_pid") or vid_pid
        except Exception as exc:
            log(f"history read failed: {path}: {exc}")
            continue
        total = sum(counts)
        if not total:
            continue
        points: list[tuple[float, Optional[float]]] = []
        latest: Optional[int] = None
        for index, start in enumerate(starts):
            if counts[index]:
                value = sums[index] / counts[index]
                points.append((start.timestamp(), value))
                latest = int(round(value))
            else:
                points.append((start.timestamp(), None))
        candidates.append(HistorySeries(
            key=path.stem,
            name=name or path.stem,
            kind=kind,
            vid_pid=vid_pid,
            color=SERIES_COLORS[0],
            points=points,
            latest=latest,
            count=total,
        ))

    candidates.sort(key=lambda item: (item.name.lower(), item.vid_pid))
    if len(candidates) > MAX_SERIES:
        data.truncated = len(candidates) - MAX_SERIES
        candidates = candidates[:MAX_SERIES]
    for index, series in enumerate(candidates):
        series.color = SERIES_COLORS[index % len(SERIES_COLORS)]
    data.series = candidates
    return data
