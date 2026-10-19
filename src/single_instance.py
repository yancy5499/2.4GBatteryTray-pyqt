# -*- coding: utf-8 -*-
"""Single-instance guard and activation signal.

A named mutex enforces one running copy per session (best effort: some
sandboxes isolate kernel objects, so the window title is checked too).

Activation does not rely on Win32 window messages or named pipes: the second
copy drops a small marker file into the shared data directory, and the
running instance polls for it and restores its window through Qt.  This keeps
the behaviour predictable even in restricted environments.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

import settings

MUTEX_NAME = "2.4GBatteryTray_PyQt6_SingleInstance"
ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL,
                                   wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]

_handle = None


def acquire() -> bool:
    """Return True for the first instance, False if one is already running."""
    global _handle
    if _handle is not None:
        return True
    _handle = _kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not _handle:
        return True
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def find_window(title: str) -> bool:
    """True when a top-level window with ``title`` already exists."""
    return bool(_user32.FindWindowW(None, title))


def marker_path() -> str:
    return os.path.join(settings.data_dir(), "show.request")


def request_show() -> bool:
    """Ask the running instance to show its window."""
    try:
        with open(marker_path(), "w", encoding="utf-8") as handle:
            handle.write(str(time.time()))
        return True
    except Exception:
        return False


def consume_show_request() -> bool:
    """True once, when another launch asked for the window to be shown."""
    path = marker_path()
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception:
        pass
    return False


def drop_stale_marker(max_age: float = 10.0) -> None:
    """Ignore activation requests left behind by a previous session."""
    path = marker_path()
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) > max_age:
            os.remove(path)
    except Exception:
        pass
