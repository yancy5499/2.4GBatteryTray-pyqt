# -*- coding: utf-8 -*-
"""2.4G Battery Tray — PyQt6 entry point."""

from __future__ import annotations

import argparse
import signal
import sys
import traceback

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox

import icons
import settings
import single_instance
from app_window import MainWindow
from log import log
from model import demo_devices
from theme import (APP_NAME, APP_VERSION, BASE_QSS, app_font, light_palette)
from tray import TrayController


def _install_excepthook() -> None:
    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            # Ctrl+C in a console run is a normal way to stop the app.
            log("interrupted (KeyboardInterrupt)")
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log("unhandled exception:\n" + text)
        try:
            QMessageBox.critical(None, APP_NAME,
                                 f"发生未处理的错误：\n{exc}")
        except Exception:
            pass
    sys.excepthook = _hook


def _create_app(argv: list[str]) -> QApplication:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("2.4GBatteryTray")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(icons.app_icon())
    app.setFont(app_font(13))
    app.setPalette(light_palette())
    app.setStyleSheet(BASE_QSS)
    return app


def _run_selftest() -> int:
    app = _create_app(sys.argv)
    tray = TrayController()
    print(f"tray available: {tray.available}")
    tray.update_devices(demo_devices(), "#2f7df6")
    QTimer.singleShot(2500, app.quit)
    app.exec()
    tray.shutdown()
    print("tray selftest finished")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--minimized", action="store_true",
                        help="启动后直接隐藏到托盘")
    parser.add_argument("--demo", action="store_true",
                        help="使用示例设备数据预览界面（不读取 HID）")
    parser.add_argument("--no-tray", action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--tray-selftest", action="store_true",
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.tray_selftest:
        return _run_selftest()

    log(f"main start v{APP_VERSION} demo={args.demo} tray={not args.no_tray}")
    app = _create_app(sys.argv)
    _install_excepthook()

    if single_instance.find_window(APP_NAME) or not single_instance.acquire():
        log("another instance is already running")
        single_instance.request_show()
        return 0

    config = settings.Settings()
    window = MainWindow(config, demo=args.demo,
                        use_tray=not args.no_tray,
                        start_minimized=args.minimized)

    def _on_sigint(_signum, _frame) -> None:
        log("SIGINT received")
        QTimer.singleShot(0, window.quit_app)

    signal.signal(signal.SIGINT, _on_sigint)
    window.start()
    try:
        return app.exec()
    except KeyboardInterrupt:
        log("KeyboardInterrupt in event loop")
        return 0
    finally:
        window.quit_app()


if __name__ == "__main__":
    raise SystemExit(main())
