# -*- coding: utf-8 -*-
"""Capture UI screenshots for review (development helper)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import settings  # noqa: E402
import tray  # noqa: E402
from app_window import (MainWindow, PAGE_ABOUT, PAGE_HISTORY, PAGE_HOME,  # noqa: E402
                        PAGE_ICONS, PAGE_TRAY)
from theme import BASE_QSS, app_font, light_palette  # noqa: E402

# Screenshots represent a normal desktop where the shell accepts tray icons.
tray.probe_notification_area = lambda: (True, 0)

OUT = os.path.join(ROOT, "refs")
os.makedirs(OUT, exist_ok=True)


def render_window(window: MainWindow) -> QPixmap:
    dpr = window.devicePixelRatioF()
    pixmap = QPixmap(round(window.width() * dpr),
                     round(window.height() * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    window.render(painter, QPoint(0, 0))
    painter.end()
    return pixmap


def backdrop(pixmap: QPixmap) -> QPixmap:
    pixmap.setDevicePixelRatio(1.0)
    canvas = QPixmap(pixmap.size())
    gradient = QLinearGradient(0, 0, pixmap.width(), pixmap.height())
    gradient.setColorAt(0.0, QColor("#9ccbf9"))
    gradient.setColorAt(0.5, QColor("#5d9ef0"))
    gradient.setColorAt(1.0, QColor("#2f6fdc"))
    painter = QPainter(canvas)
    painter.fillRect(canvas.rect(), gradient)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return canvas


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(app_font(13))
    app.setStyleSheet(BASE_QSS)
    app.setPalette(light_palette())
    config = settings.Settings()
    config.window_size = [1280, 990]
    config.window_pos = None
    config.window_maximized = False
    config.close_to_tray = True
    config.fill_color = "#3ec173"
    window = MainWindow(config, demo=True, use_tray=True)
    window.show()
    window.start()

    def shoot() -> None:
        window.history_page.set_bucket("day")
        for name, index in (("page_home", PAGE_HOME),
                            ("page_icons", PAGE_ICONS),
                            ("page_tray", PAGE_TRAY),
                            ("page_history", PAGE_HISTORY),
                            ("page_about", PAGE_ABOUT)):
            window.go_to(index)
            app.processEvents()
            canvas = backdrop(render_window(window))
            path = os.path.join(OUT, f"{name}.png")
            canvas.save(path)
            print("saved", path, canvas.width(), canvas.height())
        window.go_to(PAGE_HOME)
        app.processEvents()
        backdrop(render_window(window)).save(os.path.join(OUT, "screenshot.png"))
        window.quit_app()

    QTimer.singleShot(900, shoot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
