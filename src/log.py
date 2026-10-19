# -*- coding: utf-8 -*-
"""Tiny append-only log used for diagnosing startup / HID problems."""

from __future__ import annotations

import os
import time
import traceback

import settings


def log(message: str) -> None:
    try:
        path = os.path.join(settings.data_dir(), "app.log")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def log_exception(prefix: str = "") -> None:
    log((prefix + "\n" if prefix else "") + traceback.format_exc())
