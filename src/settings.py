# -*- coding: utf-8 -*-
"""Settings persistence, data paths and Windows startup registration."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import winreg
from typing import Any

from theme import AMBER, DEFAULT_FILL, RED

APP_NAME = "2.4G 电量助手"
APP_ID = "2.4GBatteryTray"
APP_VERSION = "2.0.0"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

INTERVAL_CHOICES = (180, 600, 1800, 3600, 10800)  # 3m / 10m / 30m / 1h / 3h
SCAN_DURATION_CHOICES = (10, 15, 20, 30, 45, 60)


def format_interval(seconds: int) -> str:
    seconds = int(seconds)
    if seconds >= 3600:
        hours = seconds / 3600
        return (f"{int(hours)} 小时" if abs(hours - round(hours)) < 1e-6
                else f"{hours:.1f} 小时")
    if seconds >= 60:
        return f"{seconds // 60} 分钟"
    return f"{seconds} 秒"


def normalize_auto_interval(seconds: int) -> int:
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return INTERVAL_CHOICES[0]
    for choice in INTERVAL_CHOICES:
        if value <= choice:
            return choice
    return INTERVAL_CHOICES[-1]


def app_dir() -> str:
    """Directory of the running program (next to the exe / the project root)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_data_dir_cache: str | None = None


def data_dir() -> str:
    """Portable data directory: the program's own folder first.

    For the packaged app this is the folder containing the exe, so settings,
    logs and the activation marker travel with the portable build.  If that
    folder is read-only (for example under Program Files), fall back to
    %APPDATA%, %LOCALAPPDATA% and finally the temp directory.
    """
    global _data_dir_cache
    if _data_dir_cache is not None:
        return _data_dir_cache
    candidates = [app_dir()]
    for base in (os.environ.get("APPDATA"),
                 os.environ.get("LOCALAPPDATA"),
                 tempfile.gettempdir()):
        if base:
            candidates.append(os.path.join(base, APP_ID))
    chosen = None
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".write-test")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            chosen = path
            break
        except Exception:
            continue
    _data_dir_cache = chosen or tempfile.gettempdir()
    return _data_dir_cache


def appdata_dir() -> str:
    """Backwards-compatible alias used by the log and activation helpers."""
    return data_dir()


def settings_path() -> str:
    return os.path.join(data_dir(), "settings.json")


DEFAULTS: dict[str, Any] = {
    "interval": 180,
    "scan_duration": 60,
    "close_to_tray": True,
    "fill_color": DEFAULT_FILL,
    "warn_color": AMBER,
    "low_color": RED,
    "window_size": [1280, 990],
    "window_pos": None,
    "window_maximized": False,
    "tray_visibility": {},
}


class Settings:
    def __init__(self) -> None:
        self.interval = int(DEFAULTS["interval"])
        self.scan_duration = int(DEFAULTS["scan_duration"])
        self.close_to_tray = bool(DEFAULTS["close_to_tray"])
        self.fill_color = str(DEFAULTS["fill_color"])
        self.warn_color = str(DEFAULTS["warn_color"])
        self.low_color = str(DEFAULTS["low_color"])
        self.window_size = list(DEFAULTS["window_size"])
        self.window_pos = None
        self.window_maximized = False
        self.tray_visibility: dict[str, bool] = {}
        self.load()

    def load(self) -> None:
        try:
            with open(settings_path(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return
        try:
            self.interval = normalize_auto_interval(
                int(data.get("interval", self.interval)))
        except Exception:
            pass
        try:
            self.scan_duration = max(
                10, min(60, int(data.get("scan_duration", self.scan_duration))))
        except Exception:
            pass
        self.close_to_tray = bool(data.get("close_to_tray", self.close_to_tray))
        color = str(data.get("fill_color", self.fill_color))
        if _valid_color(color):
            self.fill_color = color.lower()
        warn = str(data.get("warn_color", self.warn_color))
        if _valid_color(warn):
            self.warn_color = warn.lower()
        low = str(data.get("low_color", self.low_color))
        if _valid_color(low):
            self.low_color = low.lower()
        size = data.get("window_size")
        if isinstance(size, list) and len(size) == 2:
            try:
                self.window_size = [max(900, int(size[0])),
                                    max(620, int(size[1]))]
            except Exception:
                pass
        pos = data.get("window_pos")
        if isinstance(pos, list) and len(pos) == 2:
            try:
                self.window_pos = [int(pos[0]), int(pos[1])]
            except Exception:
                self.window_pos = None
        self.window_maximized = bool(data.get("window_maximized", False))
        visibility = data.get("tray_visibility")
        if isinstance(visibility, dict):
            self.tray_visibility = {
                str(key): bool(value)
                for key, value in visibility.items()
                if isinstance(value, (bool, int))
            }

    def save(self) -> None:
        try:
            with open(settings_path(), "w", encoding="utf-8") as fh:
                json.dump({
                    "interval": int(self.interval),
                    "scan_duration": int(self.scan_duration),
                    "close_to_tray": bool(self.close_to_tray),
                    "fill_color": self.fill_color,
                    "warn_color": self.warn_color,
                    "low_color": self.low_color,
                    "window_size": [int(v) for v in self.window_size],
                    "window_pos": ([int(v) for v in self.window_pos]
                                   if self.window_pos else None),
                    "window_maximized": bool(self.window_maximized),
                    "tray_visibility": {
                        str(key): bool(value)
                        for key, value in self.tray_visibility.items()
                    },
                }, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass


def _valid_color(value: str) -> bool:
    try:
        value = value.strip().lstrip("#")
        return len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value)
    except Exception:
        return False


def _pythonw() -> str:
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        candidate = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(candidate):
            return candidate
    return exe


def startup_command() -> str:
    """Command written to HKCU\\...\\Run."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
    return f'"{_pythonw()}" "{script}" --minimized'


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_ID)
            return bool(value)
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ,
                                  startup_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_ID)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
