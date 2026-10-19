# -*- coding: utf-8 -*-
"""Bounded rotating log used for diagnosing startup / HID problems."""

from __future__ import annotations

import os
import traceback
import logging
import threading
from logging.handlers import RotatingFileHandler

import settings

_lock = threading.Lock()
_logger = None


def log(message: str) -> None:
    global _logger
    try:
        with _lock:
            if _logger is None:
                handler = RotatingFileHandler(
                    os.path.join(settings.data_dir(), "app.log"),
                    maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
                handler.setFormatter(logging.Formatter(
                    "%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
                _logger = logging.Logger("battery-tray", logging.INFO)
                _logger.addHandler(handler)
            _logger.info(message)
    except Exception:
        pass


def log_exception(prefix: str = "") -> None:
    log((prefix + "\n" if prefix else "") + traceback.format_exc())
