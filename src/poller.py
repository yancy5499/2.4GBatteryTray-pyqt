# -*- coding: utf-8 -*-
"""Background battery polling.

A daemon Python thread is used instead of QThread: HID reads can block for
several seconds when a device is asleep, and a QThread would either delay
application exit or have to be terminated (which can crash inside ctypes).
The daemon thread is abandoned at process exit; Qt signals are queued to
the UI thread as usual.
"""

from __future__ import annotations

import threading
import traceback

from PyQt6.QtCore import QObject, pyqtSignal

import battery
from log import log
from model import DeviceView, view_from_group


class BatteryPoller(QObject):
    """Reads every 2.4G receiver in the background, without blocking the UI."""

    results = pyqtSignal(object)
    failed = pyqtSignal(str)
    started_read = pyqtSignal()

    def __init__(self, interval: int = 30, parent=None):
        super().__init__(parent)
        self._interval = max(1, min(300, int(interval)))
        self._wake = threading.Event()
        self._stop = False
        self._skip_read = False
        self._started = False
        self._thread = threading.Thread(target=self._loop, name="battery-poller",
                                        daemon=True)

    # -- control ------------------------------------------------------
    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def isRunning(self) -> bool:  # noqa: N802
        return self._thread.is_alive()

    def wait(self, milliseconds: int) -> bool:
        self._thread.join(max(0, milliseconds) / 1000.0)
        return not self._thread.is_alive()

    def refresh_now(self) -> None:
        self._wake.set()

    def set_interval(self, seconds: int) -> None:
        self._interval = max(1, min(300, int(seconds)))
        self._skip_read = True
        self._wake.set()

    def stop(self) -> None:
        self._stop = True
        self._wake.set()

    # -- loop ---------------------------------------------------------
    def _loop(self) -> None:
        log("poller start")
        while not self._stop:
            self._wake.clear()
            if not self._skip_read:
                self._read_once()
            self._skip_read = False
            if self._stop:
                break
            self._wake.wait(self._interval)
        log("poller stop")

    def _read_once(self) -> None:
        self.started_read.emit()
        try:
            results = battery.read_all(fast=True)
        except Exception as exc:
            log("battery read failed: " + traceback.format_exc())
            self.failed.emit(str(exc))
            return
        devices: list[DeviceView] = []
        for index, (group, reading) in enumerate(results):
            devices.append(view_from_group(group, reading, index))
        log("battery read: " + ", ".join(
            f"{d.vid_pid}={d.percent_text}" for d in devices))
        if not self._stop:
            self.results.emit(devices)
