# -*- coding: utf-8 -*-
"""Frameless main window: title bar, sidebar, pages and app state."""

from __future__ import annotations

import math
import os
import time
from typing import Optional

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
                             QMessageBox, QStackedWidget, QVBoxLayout, QWidget)

import icons
import settings as settings_module
import single_instance
from log import log, log_exception
from model import DeviceView, demo_devices
from page_about import AboutPage
from page_history import HistoryPage
from page_home import HomePage
from page_icons import IconSettingsPage
from page_tray import TrayPage
from poller import BatteryPoller
from theme import (AMBER, APP_NAME, APP_TAGLINE, DIVIDER, FAINT, GREEN, MUTED,
                   RED, TEXT, paint_shell)
from tray import TrayController
from widgets import (AppLogo, Card, IconButton, LineIcon, NavButton,
                     WindowButton, label)

SHADOW = 18
RADIUS = 20
SIDEBAR_WIDTH = 208
PAGE_HOME, PAGE_ICONS, PAGE_TRAY, PAGE_HISTORY, PAGE_ABOUT = range(5)
SEARCH_SECONDS = 60
SEARCH_INTERVAL = 2


class ResizeHandle(QWidget):
    """Invisible edge grip using the native resize loop."""

    def __init__(self, window: QWidget, edges: Qt.Edge,
                 cursor: Qt.CursorShape):
        super().__init__(window)
        self._edges = edges
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemResize(self._edges)
            event.accept()
            return
        super().mousePressEvent(event)


class TitleBar(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self._window = window
        self._press_global = None
        self._drag_ready = False
        self.setFixedHeight(78)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 16, 0)
        layout.setSpacing(0)
        self.logo = AppLogo(40)
        layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(14)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(2)
        texts.addStretch(1)
        self.title = label(APP_NAME, 20, QFont.Weight.Bold, TEXT)
        self.subtitle = label(APP_TAGLINE, 11, QFont.Weight.Normal, MUTED)
        for widget in (self.title, self.subtitle):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                                True)
        texts.addWidget(self.title)
        texts.addWidget(self.subtitle)
        texts.addStretch(1)
        layout.addLayout(texts)
        layout.addStretch(1)

        self.min_button = WindowButton("minimize")
        self.max_button = WindowButton("maximize")
        self.close_button = WindowButton("close")
        self.min_button.setToolTip("最小化")
        self.max_button.setToolTip("最大化 / 还原")
        self.close_button.setToolTip("关闭到托盘")
        self.min_button.clicked.connect(window.showMinimized)
        self.max_button.clicked.connect(window.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        for button in (self.min_button, self.max_button, self.close_button):
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._drag_ready = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if (self._drag_ready and self._press_global is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            moved = (event.globalPosition().toPoint()
                     - self._press_global).manhattanLength()
            if moved >= QApplication.startDragDistance():
                self._drag_ready = False
                handle = self.window().windowHandle()
                if handle is not None:
                    handle.startSystemMove()
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_ready = False
        self._press_global = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_ready = False
            self._window.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MainWindow(QWidget):
    def __init__(self, config: settings_module.Settings | None = None,
                 demo: bool = False, use_tray: bool = True,
                 start_minimized: bool = False):
        super().__init__()
        self.settings = config or settings_module.Settings()
        self.demo = demo
        self.use_tray = use_tray
        self.start_minimized = start_minimized
        self.color = self.settings.fill_color
        self.warn_color = self.settings.warn_color
        self.low_color = self.settings.low_color
        icons.set_warning_colors(self.warn_color, self.low_color)
        self.devices: list[DeviceView] = []
        self._quitting = False
        self._busy = False
        self._demo_loaded = False
        self._last_update = ""
        self._hide_hint_shown = False
        self._poller: Optional[BatteryPoller] = None
        self._handles: list[ResizeHandle] = []
        self._search_active = False
        self._search_deadline = 0.0
        self._search_shown_sec = -1
        self._search_last_demo = 0.0
        self._search_duration = 60
        self._search_started = 0.0
        self._search_timer = QTimer(self)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._on_search_tick)
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.start_search)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.setWindowFlags(Qt.WindowType.Window
                            | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(1040, 720)
        self.resize(1280, 990)

        self._build_ui()
        self._build_resize_handles()
        self._restore_geometry()

        self.tray = TrayController(self)
        self.tray_available = bool(self.tray.available) and use_tray
        self.tray.show_requested.connect(self.show_window)
        self.tray.refresh_requested.connect(self.refresh)
        self.tray.settings_requested.connect(
            lambda: (self.show_window(), self.go_to(PAGE_TRAY)))
        self.tray.quit_requested.connect(self.quit_app)
        self.tray.autostart_toggled.connect(self._on_tray_autostart)

        self._connect_pages()
        self.home_page.set_colors(self.color, self.warn_color, self.low_color)
        self.icon_page.set_colors(self.color, self.warn_color, self.low_color)
        self.tray_page.refresh_colors(self.color)
        self.tray_page.set_tray_available(self.tray_available,
                                          getattr(self.tray, "error", ""))
        if not self.tray_available:
            self.side_tray_warning.show()
        self.tray_page.set_interval(self.settings.interval)
        self.tray_page.set_autostart(settings_module.is_autostart_enabled())
        self._update_interval_labels()
        self._set_side_status("正在检测设备…", "busy")
        self.tray.set_startup_checked(settings_module.is_autostart_enabled())

        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh)
        self.setWindowIcon(icons.app_icon())

        single_instance.drop_stale_marker()
        self._activation_timer = QTimer(self)
        self._activation_timer.setInterval(450)
        self._activation_timer.timeout.connect(self._check_activation)
        self._activation_timer.start()

    def _check_activation(self) -> None:
        if self._quitting:
            return
        if single_instance.consume_show_request():
            self.show_window()

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(SHADOW, SHADOW, SHADOW, SHADOW)
        self._root_layout.setSpacing(0)

        self.shell = QWidget(self)
        self.shell.setObjectName("shell")
        self._root_layout.addWidget(self.shell)
        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        shell_layout.addWidget(self.title_bar)

        body = QWidget(self.shell)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        body_layout.addWidget(self._build_sidebar(), 0)

        divider_wrap = QWidget(body)
        divider_wrap.setFixedWidth(1)
        divider_layout = QVBoxLayout(divider_wrap)
        divider_layout.setContentsMargins(0, 16, 0, 16)
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background: {DIVIDER}; border: none;")
        divider_layout.addWidget(divider)
        body_layout.addWidget(divider_wrap, 0)

        content = QWidget(body)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 8, 14, 16)
        content_layout.setSpacing(0)
        self.pages = QStackedWidget(content)
        self.pages.setStyleSheet("background: transparent;")
        content_layout.addWidget(self.pages)
        body_layout.addWidget(content, 1)

        self.home_page = HomePage(self.color)
        self.icon_page = IconSettingsPage(self.color)
        self.tray_page = TrayPage(self.settings.interval,
                                  self.settings.scan_duration,
                                  self.settings.close_to_tray,
                                  settings_module.is_autostart_enabled(),
                                  self.color)
        self.history_page = HistoryPage()
        self.about_page = AboutPage()
        for page in (self.home_page, self.icon_page, self.tray_page,
                     self.history_page, self.about_page):
            self.pages.addWidget(page)

        shell_layout.addWidget(body, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget(self.shell)
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 6, 14, 18)
        layout.setSpacing(6)
        layout.addSpacing(16)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[NavButton] = []
        for index, (icon, text) in enumerate((
                ("home", "首页"), ("gear", "图标设置"),
                ("monitor", "系统托盘"), ("history", "电量历史"),
                ("info", "关于"))):
            button = NavButton(icon, text)
            button.setChecked(index == 0)
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            layout.addWidget(button)
        self.nav_group.idClicked.connect(self._on_nav)
        layout.addStretch(1)

        status_card = Card(soft=True)
        status_card.setFixedWidth(SIDEBAR_WIDTH - 28)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 11, 14, 12)
        status_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.side_dot = LineIcon("dot", 10, AMBER)
        top_row.addWidget(self.side_dot)
        self.side_title = label("正在监控", 11.5, QFont.Weight.DemiBold, TEXT)
        top_row.addWidget(self.side_title)
        top_row.addStretch(1)
        self.side_refresh = IconButton("refresh", 22, 13, MUTED,
                                       tooltip="立即刷新")
        self.side_refresh.clicked.connect(self.refresh)
        top_row.addWidget(self.side_refresh)
        status_layout.addLayout(top_row)

        self.side_status = label("正在读取设备…", 10, QFont.Weight.Normal,
                                 MUTED, wrap=True)
        status_layout.addWidget(self.side_status)
        self.side_interval = label(
            f"每 {settings_module.format_interval(self.settings.interval)} 自动扫描",
            9.5, QFont.Weight.Normal, FAINT)
        status_layout.addWidget(self.side_interval)
        self.side_tray_warning = label("托盘不可用：关闭窗口将退出程序", 9.5,
                                       QFont.Weight.Normal, RED, wrap=True)
        self.side_tray_warning.hide()
        status_layout.addWidget(self.side_tray_warning)
        layout.addWidget(status_card)
        return sidebar

    def _build_resize_handles(self) -> None:
        edges = Qt.Edge
        specs = (
            (edges.TopEdge, Qt.CursorShape.SizeVerCursor),
            (edges.BottomEdge, Qt.CursorShape.SizeVerCursor),
            (edges.LeftEdge, Qt.CursorShape.SizeHorCursor),
            (edges.RightEdge, Qt.CursorShape.SizeHorCursor),
            (edges.TopEdge | edges.LeftEdge, Qt.CursorShape.SizeFDiagCursor),
            (edges.TopEdge | edges.RightEdge, Qt.CursorShape.SizeBDiagCursor),
            (edges.BottomEdge | edges.LeftEdge, Qt.CursorShape.SizeBDiagCursor),
            (edges.BottomEdge | edges.RightEdge, Qt.CursorShape.SizeFDiagCursor),
        )
        for edge, cursor in specs:
            self._handles.append(ResizeHandle(self, edge, cursor))
        self._layout_handles()

    def _layout_handles(self) -> None:
        if not self._handles:
            return
        if self.isMaximized():
            for handle in self._handles:
                handle.hide()
            return
        width, height = self.width(), self.height()
        band = SHADOW + 5
        corner = SHADOW + 7
        rects = [
            QRect(corner, 0, max(0, width - 2 * corner), band),
            QRect(corner, height - band, max(0, width - 2 * corner), band),
            QRect(0, corner, band, max(0, height - 2 * corner)),
            QRect(width - band, corner, band, max(0, height - 2 * corner)),
            QRect(0, 0, corner, corner),
            QRect(width - corner, 0, corner, corner),
            QRect(0, height - corner, corner, corner),
            QRect(width - corner, height - corner, corner, corner),
        ]
        for handle, rect in zip(self._handles, rects):
            handle.setGeometry(rect)
            handle.raise_()
            handle.show()

    # ------------------------------------------------------------------
    # connections / state
    # ------------------------------------------------------------------
    def _connect_pages(self) -> None:
        self.home_page.colors_changed.connect(self.set_colors)
        self.home_page.refresh_requested.connect(self.refresh)
        self.home_page.settings_requested.connect(lambda: self.go_to(PAGE_ICONS))
        self.home_page.tray_requested.connect(lambda: self.go_to(PAGE_TRAY))
        self.home_page.copy_requested.connect(self.copy_device)
        self.home_page.visibility_toggled.connect(
            self._on_tray_visibility_toggled)
        self.home_page.search_toggle_requested.connect(self.toggle_search)
        self.home_page.history_requested.connect(self.open_device_history)

        self.icon_page.colors_changed.connect(self.set_colors)

        self.tray_page.interval_changed.connect(self.set_interval)
        self.tray_page.scan_duration_changed.connect(self.set_scan_duration)
        self.tray_page.refresh_requested.connect(self.start_search)
        self.tray_page.hide_requested.connect(self.hide_to_tray)
        self.tray_page.quit_requested.connect(self.quit_app)
        self.tray_page.close_to_tray_changed.connect(self.set_close_to_tray)
        self.tray_page.autostart_changed.connect(self.set_autostart)
        self.tray_page.open_data_dir_requested.connect(self.open_data_dir)

    def start(self) -> None:
        log("window start")
        if self.start_minimized and self.tray_available:
            pass
        elif self.settings.window_maximized:
            self.showMaximized()
        else:
            self.show()
        if self.demo:
            QTimer.singleShot(120, self._load_demo)
        else:
            self._poller = BatteryPoller(self.settings.interval, self)
            self._poller.results.connect(self._on_results)
            self._poller.failed.connect(self._on_failed)
            self._poller.started_read.connect(self._on_read_started)
            self._poller.start()
        self._refresh_tray()
        QTimer.singleShot(400, self.start_search)

    def _load_demo(self) -> None:
        self._demo_loaded = True
        self._on_results(demo_devices())

    def _on_nav(self, index: int) -> None:
        if 0 <= index < self.pages.count():
            if index == PAGE_HISTORY:
                # A normal click on "电量历史" always shows every device.
                self.history_page.show_all()
            self.pages.setCurrentIndex(index)

    def open_device_history(self, device: DeviceView) -> None:
        self.go_to(PAGE_HISTORY)
        self.history_page.focus_device(device)

    def go_to(self, index: int) -> None:
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)
        self._on_nav(index)

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if self._quitting:
            return
        if self.demo:
            self._set_busy(True)
            QTimer.singleShot(180, lambda: self._on_results(demo_devices()))
            return
        if self._poller is None:
            return
        self._set_busy(True)
        self._poller.refresh_now()

    def _on_read_started(self) -> None:
        if not self._quitting:
            self._set_busy(True)

    def _on_results(self, devices: list[DeviceView]) -> None:
        if self._quitting:
            return
        self.devices = list(devices)
        self._apply_devices()
        now = time.strftime("%H:%M:%S")
        self._last_update = now
        self._refresh_status_text()
        self.home_page.set_busy(False)
        self.tray_page.set_busy(False)
        interval_text = (f"每 {SEARCH_INTERVAL} 秒扫描（搜索中）"
                         if self._search_active
                         else f"每 {settings_module.format_interval(self.settings.interval)} 自动扫描")
        self.tray_page.set_status(
            f"上次更新 {now} · {interval_text}", "ok")
        self._set_busy(False)
        if not self._search_active:
            self._set_side_status(f"上次更新 {now}", "ok")
        self.side_interval.setText(
            f"搜索中 · 每 {SEARCH_INTERVAL} 秒扫描"
            if self._search_active
            else f"每 {settings_module.format_interval(self.settings.interval)} 自动扫描")
        self._refresh_tray()
        if self.pages.currentWidget() is self.history_page:
            self.history_page.reload(throttled=True)

    def _refresh_status_text(self) -> None:
        prefix = "演示模式 · " if self.demo else ""
        count = len(self.devices)
        if self._search_active:
            remaining = max(0, int(math.ceil(
                self._search_deadline - time.monotonic())))
            if count:
                text = (f"{prefix}监听中 · 剩余 {remaining} 秒 · "
                        f"已找到 {count} 台设备")
            else:
                text = f"{prefix}监听中 · 剩余 {remaining} 秒 · 正在扫描…"
            self.home_page.set_status(text)
            return
        if count:
            text = (f"{prefix}{count} 台设备 · 托盘 "
                    f"{len(self._tray_devices())} 台 · 已更新 "
                    f"{self._last_update}")
        else:
            text = f"{prefix}未检测到设备 · 已更新 {self._last_update}"
        self.home_page.set_status(text)

    # -- device search -------------------------------------------------
    def toggle_search(self) -> None:
        if self._search_active:
            self._stop_search(manual=True)
        else:
            self.start_search()

    def start_search(self) -> None:
        if self._quitting or self._search_active:
            return
        duration = max(10, min(60, int(self.settings.scan_duration)))
        self._search_duration = duration
        self._auto_timer.stop()
        self._search_active = True
        self._search_started = time.monotonic()
        self._search_deadline = self._search_started + duration
        self._search_shown_sec = duration
        self._search_last_demo = 0.0
        self._search_timer.start()
        if not self.demo and self._poller is not None:
            self._poller.set_interval(SEARCH_INTERVAL)
        self.home_page.set_search_state(True, duration, 0, duration)
        self._set_side_status(f"正在搜索设备… 剩余 {duration} 秒", "busy")
        self.side_title.setText("正在搜索")
        self.side_interval.setText(f"搜索中 · 每 {SEARCH_INTERVAL} 秒扫描")
        self._refresh_status_text()
        log(f"search start ({duration}s, {SEARCH_INTERVAL}s interval)")
        self.refresh()

    def _on_search_tick(self) -> None:
        if self._quitting or not self._search_active:
            return
        now = time.monotonic()
        remaining_float = max(0.0, self._search_deadline - now)
        remaining = int(math.ceil(remaining_float))
        duration = self._search_duration
        self.home_page.set_search_state(True, remaining, len(self.devices),
                                        duration)
        if self.demo and now - self._search_last_demo >= 1.8:
            self._search_last_demo = now
            self._on_results(demo_devices())
        if remaining != self._search_shown_sec:
            self._search_shown_sec = remaining
            self._set_side_status(
                f"正在搜索设备… 剩余 {remaining} 秒", "busy")
            self.side_title.setText("正在搜索")
            self._refresh_status_text()
        if remaining_float <= 0:
            self._finish_search()

    def _finish_search(self) -> None:
        found = len(self.devices)
        self._end_search("搜索完成 · " + (
            f"找到 {found} 台设备" if found else "未检测到设备"), "ok")

    def _stop_search(self, manual: bool = False) -> None:
        message = "已停止搜索"
        if self.devices:
            message += f" · 已找到 {len(self.devices)} 台设备"
        self._end_search(message, "ok")

    def _end_search(self, message: str, tone: str) -> None:
        if not self._search_active:
            return
        self._search_active = False
        self._search_timer.stop()
        self._search_shown_sec = -1
        if not self.demo and self._poller is not None:
            self._poller.set_interval(self.settings.interval)
        self.home_page.set_search_state(False, 0)
        self._set_side_status(message, tone)
        self._refresh_status_text()
        self.side_interval.setText(
            f"每 {settings_module.format_interval(self.settings.interval)} 自动扫描")
        log("search end: " + message)
        elapsed = max(0.0, time.monotonic() - self._search_started)
        self._schedule_auto_scan(
            max(5.0, float(self.settings.interval) - elapsed))

    def _schedule_auto_scan(self, delay: float | None = None) -> None:
        if self._quitting:
            return
        if delay is None:
            delay = float(max(10, int(self.settings.interval)))
        delay = max(1.0, delay)
        self._auto_timer.start(int(delay * 1000))
        log(f"next auto scan in {delay:.0f}s")

    def _on_failed(self, message: str) -> None:
        if self._quitting:
            return
        log("read failed: " + message)
        self._set_busy(False)
        self.home_page.set_status(f"读取失败：{message}", "error")
        self.tray_page.set_status(f"读取失败：{message}", "error")
        self._set_side_status("读取失败", "error")

    def _is_tray_visible(self, device: DeviceView) -> bool:
        """Level-less devices are hidden unless the user opted them in."""
        explicit = self.settings.tray_visibility.get(device.stable_key)
        if explicit is not None:
            return bool(explicit)
        return device.level is not None

    def _visible_keys(self) -> set[str]:
        return {device.stable_key for device in self.devices
                if self._is_tray_visible(device)}

    def _tray_devices(self) -> list[DeviceView]:
        return [device for device in self.devices
                if self._is_tray_visible(device)]

    def _refresh_tray(self) -> None:
        if not self.use_tray:
            return
        visible = self._tray_devices()
        ok = self.tray.update_devices(visible, self.color)
        log(f"tray icons: {len(visible)}/{len(self.devices)} visible")
        if not ok:
            self.tray_available = False
            self.tray_page.set_tray_available(
                False, getattr(self.tray, "error", ""))
            self.side_tray_warning.show()
        elif not self.tray_available:
            self.tray_available = True
            self.tray_page.set_tray_available(True)
            self.side_tray_warning.hide()

    def _on_tray_visibility_toggled(self, device: DeviceView,
                                    visible: bool) -> None:
        self.settings.tray_visibility[device.stable_key] = bool(visible)
        self.settings.save()
        keys = self._visible_keys()
        self.home_page.set_tray_visibility(keys)
        self.tray_page.set_devices(self.devices, self.color, keys)
        self._refresh_tray()
        self._refresh_status_text()
        action = "已显示在托盘" if visible else "已从托盘隐藏"
        self._set_side_status(f"{device.kind_label}{action}", "ok")

    def _apply_devices(self) -> None:
        visible = self._visible_keys()
        self.home_page.set_devices(self.devices, visible)
        self.tray_page.set_devices(self.devices, self.color, visible)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.home_page.set_busy(busy)
        self.tray_page.set_busy(busy)
        if busy and not self._search_active:
            self._set_side_status("正在读取电量…", "busy")

    def _set_side_status(self, text: str, tone: str = "idle") -> None:
        self.side_status.setText(text)
        color = {"ok": GREEN, "error": RED, "busy": AMBER}.get(tone, MUTED)
        self.side_dot.set_color(color)
        self.side_title.setText({
            "ok": "正在监控", "error": "读取异常", "busy": "正在刷新",
        }.get(tone, "正在监控"))

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    def set_colors(self, normal: str, warn: str, low: str) -> None:
        values = []
        for value in (normal, warn, low):
            color = QColor(value)
            if not color.isValid():
                return
            values.append(color.name())
        normal, warn, low = values
        self.color = normal
        self.warn_color = warn
        self.low_color = low
        self.settings.fill_color = normal
        self.settings.warn_color = warn
        self.settings.low_color = low
        self.settings.save()
        icons.set_warning_colors(warn, low)
        icons.clear_device_icon_cache()
        self.home_page.set_colors(normal, warn, low)
        self.icon_page.set_colors(normal, warn, low)
        self.tray_page.refresh_colors(normal)
        self._refresh_tray()

    def set_color(self, color: str) -> None:
        self.set_colors(color, self.warn_color, self.low_color)

    def set_interval(self, seconds: int) -> None:
        seconds = max(180, min(10800, int(seconds)))
        seconds = settings_module.normalize_auto_interval(seconds)
        self.settings.interval = seconds
        self.settings.save()
        self.tray_page.set_interval(seconds)
        if self._poller is not None and not self._search_active:
            self._poller.set_interval(seconds)
        self._update_interval_labels()
        if not self._search_active:
            self._schedule_auto_scan()

    def set_scan_duration(self, seconds: int) -> None:
        seconds = max(10, min(60, int(seconds)))
        self.settings.scan_duration = seconds
        self.settings.save()
        self.tray_page.set_scan_duration(seconds)
        self._set_side_status(f"单次扫描时长：{seconds} 秒", "ok")

    def _update_interval_labels(self) -> None:
        if self._search_active:
            self.side_interval.setText(
                f"搜索中 · 每 {SEARCH_INTERVAL} 秒扫描")
        else:
            self.side_interval.setText(
                f"每 {settings_module.format_interval(self.settings.interval)} 自动扫描")
        self.tray_page.set_status(
            f"每 {settings_module.format_interval(self.settings.interval)} 自动扫描 · "
            f"单次 {self.settings.scan_duration} 秒", "idle")

    def set_close_to_tray(self, enabled: bool) -> None:
        self.settings.close_to_tray = bool(enabled)
        self.settings.save()

    def set_autostart(self, enabled: bool) -> None:
        if not settings_module.set_autostart(bool(enabled)):
            self.tray_page.set_autostart(not enabled)
            self.tray.set_startup_checked(not enabled)
            QMessageBox.warning(
                self, "开机自启",
                "无法写入启动项（HKCU\\Software\\Microsoft\\Windows\\"
                "CurrentVersion\\Run），请检查权限后重试。")
            return
        self.tray.set_startup_checked(bool(enabled))
        self.tray_page.set_autostart(bool(enabled))
        self._set_side_status("已开启开机自启" if enabled else "已关闭开机自启",
                              "ok")

    def _on_tray_autostart(self, enabled: bool) -> None:
        self.set_autostart(enabled)

    def open_data_dir(self) -> None:
        try:
            os.startfile(settings_module.appdata_dir())  # noqa: S606
        except Exception:
            log_exception("open data dir failed")
            QMessageBox.warning(self, "打开目录", "无法打开数据目录。")

    def copy_device(self, device: DeviceView) -> None:
        text = "\n".join((
            device.name,
            device.vid_pid,
            f"{device.kind_label} {device.percent_text}",
            device.detail_text,
        ))
        QApplication.clipboard().setText(text)
        self._set_side_status("已复制设备信息", "ok")
        QTimer.singleShot(2200, lambda: self._set_side_status(
            "上次更新 " + time.strftime("%H:%M:%S"), "ok"))

    # ------------------------------------------------------------------
    # window
    # ------------------------------------------------------------------
    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_frame()
        super().changeEvent(event)

    def _sync_frame(self) -> None:
        maximized = self.isMaximized()
        margin = 0 if maximized else SHADOW
        self._root_layout.setContentsMargins(margin, margin, margin, margin)
        self.title_bar.max_button.set_icon(
            "restore" if maximized else "maximize")
        self._layout_handles()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_handles()

    def show_window(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self) -> None:
        if not self.tray_available:
            QMessageBox.warning(
                self, "托盘不可用",
                "当前环境无法创建系统托盘图标，窗口将保持显示。")
            return
        self.hide()
        if not self._hide_hint_shown:
            self._hide_hint_shown = True
            self.tray.show_message("2.4G 电量助手",
                                   "已最小化到托盘，继续在后台监控设备电量。")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._quitting:
            self._save_geometry()
            event.accept()
            return
        if self.settings.close_to_tray and self.tray_available:
            event.ignore()
            self.hide_to_tray()
            return
        event.ignore()
        QTimer.singleShot(0, self.quit_app)

    def quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        log("quit requested")
        self._search_timer.stop()
        self._auto_timer.stop()
        self._search_active = False
        self._save_geometry()
        self._stop_poller()
        try:
            self.tray.shutdown()
        except Exception:
            log_exception("tray shutdown failed")
        self.close()
        QApplication.quit()

    def _stop_poller(self) -> None:
        if self._poller is None:
            return
        self._poller.stop()
        if not self._poller.wait(400):
            # The HID read cannot be interrupted; detach the daemon thread so
            # it does not keep the UI alive or get destroyed mid-read.
            log("poller still reading; detaching for fast exit")
            self._poller.setParent(None)
        self._poller = None

    # ------------------------------------------------------------------
    # geometry
    # ------------------------------------------------------------------
    def _restore_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        available = (screen.availableGeometry() if screen is not None
                     else QRect(0, 0, 1280, 940))
        size = self.settings.window_size
        width = min(max(1040, int(size[0])),
                    max(1040, available.width()))
        height = min(max(720, int(size[1])),
                     max(720, available.height()))
        self.resize(width, height)
        if self.settings.window_pos:
            point = QPoint(int(self.settings.window_pos[0]),
                           int(self.settings.window_pos[1]))
            if not available.intersects(QRect(point, QSize(width, height))):
                point = QPoint(available.center().x() - width // 2,
                               available.center().y() - height // 2)
        else:
            point = QPoint(available.center().x() - width // 2,
                           available.center().y() - height // 2)
        self.move(point)
        if self.settings.window_maximized:
            self.setWindowState(Qt.WindowState.WindowMaximized)

    def _save_geometry(self) -> None:
        try:
            if self.isMaximized() or self.isFullScreen():
                normal = self.normalGeometry()
                self.settings.window_maximized = True
            else:
                normal = self.geometry()
                self.settings.window_maximized = False
            self.settings.window_size = [max(1040, normal.width()),
                                         max(720, normal.height())]
            self.settings.window_pos = [normal.x(), normal.y()]
            self.settings.save()
        except Exception:
            log_exception("save geometry failed")

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.isMaximized():
            rect = self.rect()
            paint_shell(painter, rect, 0)
            return
        rect = self.rect().adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)
        for step in range(14, 0, -1):
            alpha = 3 + int(8 * (1 - step / 14.0) ** 1.4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(24, 62, 112, alpha))
            painter.drawRoundedRect(
                rect.adjusted(-step, -step + 3, step, step + 4),
                RADIUS + step, RADIUS + step)
        paint_shell(painter, rect, RADIUS)
