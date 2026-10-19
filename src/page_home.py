# -*- coding: utf-8 -*-
"""Home page: hero, tray preview, device cards and the colour card."""

from __future__ import annotations

import math
from typing import Iterable

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QMenu,
                             QSizePolicy, QVBoxLayout, QWidget)

from color_card import ColorSettingsCard
from model import DeviceView
from theme import ACCENT_DEEP, DEFAULT_FILL, DIVIDER, MUTED, TEXT, TEXT_SOFT
from widgets import (Card, GlyphView, IconButton, PillButton, ScrollPage,
                     SectionTitle, StatusPill, ThinProgress, TrayMini, label)

import icons

CARD_HEIGHT = 300
GRID_GAP = 14
MIN_CARD_WIDTH = 196


class DeviceCard(QFrame):
    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    copy_requested = pyqtSignal(object)
    history_requested = pyqtSignal(object)
    visibility_toggled = pyqtSignal(object, bool)

    def __init__(self, device: DeviceView, color: str,
                 tray_visible: bool = True,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("deviceCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(CARD_HEIGHT)
        self.setMinimumWidth(MIN_CARD_WIDTH)
        self.setMaximumWidth(380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self._device = device
        self._tray_visible = tray_visible

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 13)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch(1)
        self.more_btn = IconButton("more", size=26, icon_size=18,
                                   color="#7f8fa3",
                                   tooltip="设备操作")
        self.more_btn.clicked.connect(self._show_menu)
        top.addWidget(self.more_btn, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top)

        self.glyph = GlyphView(device.kind, device.level, color, side=148,
                               wave=True, warning_colors=True)
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(2)

        self.percent = label(device.percent_text, 30, QFont.Weight.Bold, TEXT)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.percent)
        layout.addSpacing(1)

        self.kind_label = label(device.kind_label, 14, QFont.Weight.Normal,
                                TEXT_SOFT)
        self.kind_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.kind_label)
        layout.addSpacing(11)

        self.pill = StatusPill(device.status_text, device.status_tone)
        layout.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignHCenter)

        self.setToolTip(device.tooltip)
        self._apply(device, color)

    def _apply(self, device: DeviceView, color: str) -> None:
        self._device = device
        self.glyph.set_data(device.kind, device.level, color)
        self.percent.setText(device.percent_text)
        pct_color = icons.level_color(
            device.level, TEXT_SOFT if device.level is None else TEXT)
        self.percent.setStyleSheet(
            f"color: {pct_color.name()}; background: transparent;")
        self.kind_label.setText(device.kind_label)
        self.pill.set_status(device.status_text, device.status_tone)
        self.pill.update()
        self.setToolTip(device.tooltip)

    def update_device(self, device: DeviceView, color: str,
                      tray_visible: bool | None = None) -> None:
        if tray_visible is not None:
            self._tray_visible = tray_visible
        self._apply(device, color)

    def set_tray_visible(self, visible: bool) -> None:
        self._tray_visible = bool(visible)

    def _toggle_tray_visibility(self) -> None:
        self._tray_visible = not self._tray_visible
        self.visibility_toggled.emit(self._device, self._tray_visible)

    def _show_menu(self) -> None:
        # The popup is deliberately parentless: a QMenu parented to a widget
        # inside the translucent window inherits that widget's black "Window"
        # palette and renders as a black rectangle.
        menu = QMenu()
        header = menu.addAction(f"{self._device.kind_label} {self._device.percent_text}")
        header.setEnabled(False)
        menu.addSeparator()
        tray_label = "从托盘隐藏" if self._tray_visible else "在托盘显示"
        tray_action = menu.addAction(tray_label)
        tray_action.triggered.connect(self._toggle_tray_visibility)
        menu.addSeparator()
        history = menu.addAction("查看电量记录")
        refresh = menu.addAction("立即刷新")
        copy = menu.addAction("复制设备信息")
        menu.addSeparator()
        settings = menu.addAction("打开图标设置")
        history.triggered.connect(
            lambda: self.history_requested.emit(self._device))
        refresh.triggered.connect(self.refresh_requested.emit)
        copy.triggered.connect(lambda: self.copy_requested.emit(self._device))
        settings.triggered.connect(self.settings_requested.emit)
        pos = self.more_btn.mapToGlobal(QPoint(0, self.more_btn.height() + 2))
        menu.exec(pos)
        menu.deleteLater()


class DeviceGrid(QWidget):
    """Responsive 1-4 column grid of device cards."""

    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    copy_requested = pyqtSignal(object)
    history_requested = pyqtSignal(object)
    visibility_toggled = pyqtSignal(object, bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cards: list[DeviceCard] = []
        self._devices: list[DeviceView] = []
        self._visible_keys: set[str] = set()
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(GRID_GAP)
        self._grid.setVerticalSpacing(GRID_GAP)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_devices(self, devices: Iterable[DeviceView], color: str,
                    visible_keys: set[str] | None = None) -> None:
        devices = list(devices)
        if visible_keys is None:
            visible_keys = {d.stable_key for d in devices
                            if d.level is not None}
        self._visible_keys = set(visible_keys)
        if [d.key for d in devices] == [d.key for d in self._devices]:
            self._devices = devices
            for card, device in zip(self._cards, devices):
                card.update_device(device, color,
                                   device.stable_key in self._visible_keys)
            return
        self._devices = devices
        for card in self._cards:
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        for device in devices:
            card = DeviceCard(device, color,
                              tray_visible=device.stable_key in self._visible_keys)
            card.refresh_requested.connect(self.refresh_requested.emit)
            card.settings_requested.connect(self.settings_requested.emit)
            card.copy_requested.connect(self.copy_requested.emit)
            card.history_requested.connect(self.history_requested.emit)
            card.visibility_toggled.connect(self.visibility_toggled.emit)
            self._cards.append(card)
        self._columns = 0
        self._reflow()

    def set_color(self, color: str) -> None:
        for card, device in zip(self._cards, self._devices):
            card.update_device(device, color)

    def set_tray_visibility(self, visible_keys: set[str]) -> None:
        self._visible_keys = set(visible_keys)
        for card, device in zip(self._cards, self._devices):
            card.set_tray_visible(device.stable_key in self._visible_keys)

    def _calc_columns(self) -> int:
        if not self._cards:
            return 0
        width = max(self.width(), self.parentWidget().width()
                    if self.parentWidget() else 0)
        if width <= 0:
            return min(4, len(self._cards))
        columns = max(1, (width + GRID_GAP) // (MIN_CARD_WIDTH + GRID_GAP))
        return int(min(4, columns, len(self._cards)))

    def _reflow(self) -> None:
        columns = self._calc_columns()
        if columns == self._columns and self._grid.count() == len(self._cards):
            return
        self._columns = columns
        while self._grid.count():
            self._grid.takeAt(0)
        for index in range(4):
            self._grid.setColumnStretch(index, 1 if index < columns else 0)
        for index, card in enumerate(self._cards):
            row, col = divmod(index, max(1, columns))
            self._grid.addWidget(card, row, col)
        rows = math.ceil(len(self._cards) / max(1, columns)) if self._cards else 0
        self.setFixedHeight(rows * CARD_HEIGHT + max(0, rows - 1) * GRID_GAP
                            if rows else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reflow()


class TrayPreviewPanel(Card):
    """The frosted "tray icon preview" box in the hero card."""

    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(soft=True, parent=parent)
        self.setMinimumWidth(370)
        self.setMaximumWidth(464)
        self.setFixedHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 11, 10, 11)
        layout.setSpacing(8)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(2)
        body.addWidget(label("托盘图标预览", 11.5, QFont.Weight.Normal, MUTED))
        self.minis_row = QHBoxLayout()
        self.minis_row.setContentsMargins(0, 0, 0, 0)
        self.minis_row.setSpacing(4)
        self.minis_row.addStretch(1)
        body.addLayout(self.minis_row, 1)
        layout.addLayout(body, 1)

        self.separator = QFrame()
        self.separator.setFixedWidth(1)
        self.separator.setStyleSheet(f"background: {DIVIDER}; border: none;")
        layout.addWidget(self.separator, 0)
        self.chevron = IconButton("chevron-down", size=28, icon_size=16,
                                  color="#8595a9",
                                  tooltip="查看全部设备")
        self.chevron.clicked.connect(self._show_menu)
        layout.addWidget(self.chevron, 0, Qt.AlignmentFlag.AlignVCenter)

        self._minis: list[TrayMini] = []
        self._devices: list[DeviceView] = []
        self._empty = label("等待设备连接…", 11, QFont.Weight.Normal, MUTED)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.minis_row.insertWidget(0, self._empty)

    def set_empty_hint(self, text: str) -> None:
        self._empty.setText(text)

    def set_devices(self, devices: Iterable[DeviceView], color: str) -> None:
        devices = list(devices)
        show = devices[:4]
        self._devices = devices
        if len(show) != len(self._minis):
            for mini in self._minis:
                self.minis_row.removeWidget(mini)
                mini.deleteLater()
            self._minis.clear()
            for index in range(len(show)):
                mini = TrayMini("mouse", None, color)
                mini.clicked.connect(self._show_menu)
                self.minis_row.insertWidget(index + 1, mini, 0)
                self._minis.append(mini)
        for mini, device in zip(self._minis, show):
            mini.set_data(device.kind, device.level, color)
            mini.setToolTip(device.tooltip)
        self._empty.setVisible(not show)
        self.chevron.setEnabled(bool(devices))
        self._apply_mini_visibility()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(464, 118)

    def _apply_mini_visibility(self) -> None:
        limit = 4 if self.width() >= 425 else 3
        for index, mini in enumerate(self._minis):
            mini.setVisible(index < limit)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_mini_visibility()

    def set_color(self, color: str) -> None:
        for mini, device in zip(self._minis, self._devices):
            mini.set_data(device.kind, device.level, color)

    def _show_menu(self) -> None:
        menu = QMenu()
        if self._devices:
            for device in self._devices:
                action = menu.addAction(
                    f"{device.kind_label}   {device.percent_text}   {device.name}")
                action.setEnabled(False)
            menu.addSeparator()
        settings = menu.addAction("打开系统托盘设置")
        settings.triggered.connect(self.settings_requested.emit)
        menu.exec(self.chevron.mapToGlobal(
            QPoint(self.chevron.width(), self.chevron.height())))
        menu.deleteLater()


class EmptyDevicesCard(Card):
    search_toggle_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(4)
        glyph = GlyphView("receiver", None, "#b9c9da", side=72)
        layout.addWidget(glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(2)
        title = label("未检测到 2.4G 设备", 15, QFont.Weight.Bold, TEXT)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        hint = label("插入键盘 / 鼠标接收器，或唤醒设备后点击“搜索设备”。",
                     11.5, QFont.Weight.Normal, MUTED)
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(hint)
        layout.addSpacing(8)
        row = QHBoxLayout()
        row.addStretch(1)
        self.search_btn = PillButton("搜索设备", "primary", icon="search",
                                     height=32)
        self._search_active = False
        self.search_btn.clicked.connect(self.search_toggle_requested.emit)
        row.addWidget(self.search_btn)
        settings = PillButton("图标设置", "ghost", height=32)
        settings.clicked.connect(self.settings_requested.emit)
        row.addWidget(settings)
        row.addStretch(1)
        layout.addLayout(row)

    def set_search_state(self, active: bool) -> None:
        if active == self._search_active:
            return
        self._search_active = active
        self.search_btn.setText("停止搜索" if active else "搜索设备")
        self.search_btn.set_icon(None if active else "search")
        self.search_btn.set_variant("ghost" if active else "primary")


class HeroCard(Card):
    settings_requested = pyqtSignal()
    search_toggle_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(162)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 18, 20, 18)
        layout.setSpacing(20)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(9)
        texts.addStretch(1)
        texts.addWidget(label("设备电量状态", 24, QFont.Weight.Bold, TEXT))
        texts.addWidget(label(
            "实时查看 2.4G 无线设备的电量，图标将在系统托盘中显示",
            12, QFont.Weight.Normal, MUTED, wrap=True))

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(9)
        self.search_btn = PillButton("搜索设备", "soft", icon="search",
                                     height=30, font_size=11.5)
        self.search_btn.clicked.connect(self.search_toggle_requested.emit)
        self._search_active = False
        search_row.addWidget(self.search_btn)
        self.search_hint = label("持续监听 10–60 秒", 10, color=MUTED)
        search_row.addWidget(self.search_hint)
        self.search_countdown = label("", 10.5, QFont.Weight.DemiBold,
                                      ACCENT_DEEP)
        self.search_countdown.hide()
        search_row.addWidget(self.search_countdown)
        self.search_progress = ThinProgress(112, 4)
        self.search_progress.hide()
        search_row.addWidget(self.search_progress)
        search_row.addStretch(1)
        texts.addLayout(search_row)
        texts.addStretch(1)
        layout.addLayout(texts, 1)

        self.preview = TrayPreviewPanel()
        self.preview.settings_requested.connect(self.settings_requested.emit)
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_search_state(self, active: bool, remaining: int = 60,
                         found: int = 0, duration: int = 60) -> None:
        if active:
            if not self._search_active:
                self._search_active = True
                self.search_btn.setText("停止搜索")
                self.search_btn.set_icon(None)
                self.search_btn.set_variant("ghost")
                self.search_hint.hide()
                self.search_countdown.show()
                self.search_progress.show()
            seconds = max(0, int(remaining))
            minutes, secs = divmod(seconds, 60)
            self.search_countdown.setText(
                f"监听中 · 剩余 {minutes:02d}:{secs:02d}")
            self.search_progress.set_value(
                max(0.0, min(float(duration), seconds)) / max(1.0, float(duration)))
        else:
            if self._search_active:
                self._search_active = False
                self.search_btn.setText("搜索设备")
                self.search_btn.set_icon("search")
                self.search_btn.set_variant("soft")
                self.search_hint.show()
                self.search_countdown.hide()
                self.search_progress.hide()


class HomePage(ScrollPage):
    colors_changed = pyqtSignal(str, str, str)
    refresh_requested = pyqtSignal()
    search_toggle_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    tray_requested = pyqtSignal()
    copy_requested = pyqtSignal(object)
    history_requested = pyqtSignal(object)
    visibility_toggled = pyqtSignal(object, bool)

    def __init__(self, color: str = DEFAULT_FILL,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._devices: list[DeviceView] = []
        self._visible_keys: set[str] = set()
        self.vbox.setSpacing(14)

        self.hero = HeroCard()
        self.hero.settings_requested.connect(self.tray_requested.emit)
        self.hero.search_toggle_requested.connect(
            self.search_toggle_requested.emit)
        self.vbox.addWidget(self.hero)

        self.status_label = label("正在检测设备…", 11.5, QFont.Weight.Normal,
                                  MUTED)
        self.section = SectionTitle("已连接的设备", right=self.status_label)
        self.vbox.addWidget(self.section)

        self.grid = DeviceGrid()
        self.grid.refresh_requested.connect(self.refresh_requested.emit)
        self.grid.settings_requested.connect(self.settings_requested.emit)
        self.grid.copy_requested.connect(self.copy_requested.emit)
        self.grid.history_requested.connect(self.history_requested.emit)
        self.grid.visibility_toggled.connect(self.visibility_toggled.emit)
        self.vbox.addWidget(self.grid)

        self.empty = EmptyDevicesCard()
        self.empty.search_toggle_requested.connect(
            self.search_toggle_requested.emit)
        self.empty.settings_requested.connect(self.settings_requested.emit)
        self.vbox.addWidget(self.empty)
        self.empty.hide()

        self.color_card = ColorSettingsCard(color, show_preview=True)
        self.color_card.colors_changed.connect(self.colors_changed.emit)
        self.vbox.addWidget(self.color_card)
        self.vbox.addStretch(1)

    def set_colors(self, normal: str, warn: str, low: str) -> None:
        self._color = normal
        self.grid.set_color(normal)
        self.hero.preview.set_color(normal)
        self.color_card.set_colors(normal, warn, low)

    def set_color(self, color: str) -> None:
        self.set_colors(color, self.color_card.warn_color,
                        self.color_card.low_color)

    def set_search_state(self, active: bool, remaining: int = 60,
                         found: int = 0, duration: int = 60) -> None:
        self.hero.set_search_state(active, remaining, found, duration)
        self.empty.set_search_state(active)

    def set_devices(self, devices: Iterable[DeviceView],
                    visible_keys: set[str] | None = None) -> None:
        devices = list(devices)
        if visible_keys is None:
            visible_keys = {d.stable_key for d in devices
                            if d.level is not None}
        self._devices = devices
        self._visible_keys = set(visible_keys)
        self.grid.set_devices(devices, self._color, self._visible_keys)
        self.grid.setVisible(bool(devices))
        self.empty.setVisible(not devices)
        visible = [d for d in devices if d.stable_key in self._visible_keys]
        self.hero.preview.set_empty_hint(
            "托盘图标已隐藏" if devices and not visible else "等待设备连接…")
        self.hero.preview.set_devices(visible, self._color)
        self.color_card.set_devices(devices)

    def set_tray_visibility(self, visible_keys: set[str]) -> None:
        self._visible_keys = set(visible_keys)
        self.grid.set_tray_visibility(self._visible_keys)
        visible = [d for d in self._devices
                   if d.stable_key in self._visible_keys]
        self.hero.preview.set_empty_hint(
            "托盘图标已隐藏" if self._devices and not visible
            else "等待设备连接…")
        self.hero.preview.set_devices(visible, self._color)

    def set_status(self, text: str, tone: str = "muted") -> None:
        self.status_label.setText(text)
        color = "#d9544d" if tone == "error" else MUTED
        self.status_label.setStyleSheet(f"color: {color}; background: transparent;")

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.set_status("正在读取电量…")
        self.empty.setEnabled(not busy)
