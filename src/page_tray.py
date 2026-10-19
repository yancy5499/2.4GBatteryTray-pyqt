# -*- coding: utf-8 -*-
"""System tray / polling settings page."""

from __future__ import annotations

import os
from typing import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import settings as settings_module
import icons
from model import DeviceView
from theme import AMBER, DEFAULT_FILL, GREEN, MUTED, RED, TEXT, TEXT_SOFT
from widgets import (Card, ChipButton, GlyphView, LineIcon, PageHeader,
                     PillButton, ScrollPage, SettingRow, StatusPill,
                     ToggleSwitch, hline, label)

INTERVAL_LABELS = {
    value: settings_module.format_interval(value)
    for value in settings_module.INTERVAL_CHOICES
}
SCAN_DURATION_LABELS = {
    value: f"{value} 秒"
    for value in settings_module.SCAN_DURATION_CHOICES
}


def _card_title(text: str) -> QWidget:
    return label(text, 15, QFont.Weight.Bold, TEXT)


class TrayPage(ScrollPage):
    interval_changed = pyqtSignal(int)
    scan_duration_changed = pyqtSignal(int)
    refresh_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    close_to_tray_changed = pyqtSignal(bool)
    autostart_changed = pyqtSignal(bool)
    open_data_dir_requested = pyqtSignal()

    def __init__(self, interval: int, scan_duration: int,
                 close_to_tray: bool,
                 autostart: bool, color: str = DEFAULT_FILL,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._devices: list[DeviceView] = []
        self._rows: list[QWidget] = []

        self.vbox.addWidget(PageHeader(
            "系统托盘",
            "控制自动扫描频率、单次扫描时长、窗口行为与开机启动；"
            "托盘图标不可用时窗口会保持显示。"))

        # -- refresh ---------------------------------------------------
        refresh_card = Card()
        refresh_layout = QVBoxLayout(refresh_card)
        refresh_layout.setContentsMargins(22, 16, 22, 14)
        refresh_layout.setSpacing(12)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(label("自动扫描间隔", 13.5, QFont.Weight.Medium, TEXT))
        titles.addWidget(label("每隔这段时间自动开始一次扫描（最短 3 分钟）",
                               11, QFont.Weight.Normal, MUTED))
        interval_row.addLayout(titles, 1)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self._chips: dict[int, ChipButton] = {}
        for value in settings_module.INTERVAL_CHOICES:
            chip = ChipButton(INTERVAL_LABELS.get(
                value, settings_module.format_interval(value)))
            chip.setChecked(value == interval)
            chip.clicked.connect(
                lambda _checked=False, v=value: self._select_interval(v))
            chips.addWidget(chip)
            self._chips[value] = chip
        interval_row.addLayout(chips)
        refresh_layout.addLayout(interval_row)

        refresh_layout.addWidget(hline())

        duration_row = QHBoxLayout()
        duration_row.setSpacing(16)
        duration_titles = QVBoxLayout()
        duration_titles.setSpacing(3)
        duration_titles.addWidget(label("单次扫描时长", 13.5,
                                        QFont.Weight.Medium, TEXT))
        duration_titles.addWidget(label("每次扫描持续 10–60 秒，期间持续读取",
                                        11, QFont.Weight.Normal, MUTED))
        duration_row.addLayout(duration_titles, 1)
        duration_chips = QHBoxLayout()
        duration_chips.setSpacing(6)
        self._duration_chips: dict[int, ChipButton] = {}
        for value in settings_module.SCAN_DURATION_CHOICES:
            chip = ChipButton(SCAN_DURATION_LABELS.get(value, f"{value} 秒"))
            chip.setChecked(value == scan_duration)
            chip.clicked.connect(
                lambda _checked=False, v=value: self._select_duration(v))
            duration_chips.addWidget(chip)
            self._duration_chips[value] = chip
        duration_row.addLayout(duration_chips)
        refresh_layout.addLayout(duration_row)

        refresh_layout.addWidget(hline())

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.status_dot = LineIcon("dot", 12, GREEN)
        status_row.addWidget(self.status_dot)
        self.status_label = label("正在检测设备…", 11.5, QFont.Weight.Normal,
                                  MUTED)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        self.refresh_btn = PillButton("立即扫描", "primary", icon="search",
                                      height=32)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        status_row.addWidget(self.refresh_btn)
        refresh_layout.addLayout(status_row)
        self.vbox.addWidget(refresh_card)

        # -- behaviour -------------------------------------------------
        behaviour_card = Card()
        behaviour = QVBoxLayout(behaviour_card)
        behaviour.setContentsMargins(22, 16, 22, 10)
        behaviour.setSpacing(0)
        behaviour_header = QHBoxLayout()
        behaviour_header.setSpacing(8)
        behaviour_header.addWidget(_card_title("托盘行为"), 1)
        self.taskbar_btn = PillButton("打开任务栏设置", "ghost", icon="monitor",
                                      height=28, font_size=10.5)
        self.taskbar_btn.clicked.connect(self._open_taskbar_settings)
        behaviour_header.addWidget(self.taskbar_btn, 0,
                                   Qt.AlignmentFlag.AlignVCenter)
        behaviour.addLayout(behaviour_header)
        behaviour.addSpacing(4)

        self.close_switch = ToggleSwitch(close_to_tray)
        self.close_switch.toggled.connect(self.close_to_tray_changed.emit)
        behaviour.addWidget(SettingRow(
            "关闭窗口时最小化到托盘",
            "关闭按钮只隐藏窗口，程序继续在后台读取电量",
            self.close_switch))
        behaviour.addWidget(hline())

        self.autostart_switch = ToggleSwitch(autostart)
        self.autostart_switch.toggled.connect(self.autostart_changed.emit)
        behaviour.addWidget(SettingRow(
            "开机自启",
            "登录 Windows 后自动以最小化方式启动，写入 HKCU\\Run",
            self.autostart_switch))
        behaviour.addWidget(hline())

        self.tray_hint = label("系统托盘不可用时会自动保持窗口显示。", 10.5,
                               QFont.Weight.Normal, MUTED, wrap=True)
        behaviour.addWidget(self.tray_hint)
        self.vbox.addWidget(behaviour_card)

        # -- tray icons ------------------------------------------------
        icons_card = Card()
        icons_layout = QVBoxLayout(icons_card)
        icons_layout.setContentsMargins(22, 16, 22, 14)
        icons_layout.setSpacing(2)
        icons_header = QHBoxLayout()
        icons_header.addWidget(_card_title("托盘图标"), 1)
        icons_header.addWidget(label("可在设备卡片 ··· 中单独开关", 10.5,
                                     QFont.Weight.Normal, MUTED))
        icons_layout.addLayout(icons_header)
        icons_layout.addSpacing(4)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        icons_layout.addLayout(self.rows_layout)
        self.empty_hint = label("尚未检测到设备。", 11, QFont.Weight.Normal,
                                MUTED)
        icons_layout.addWidget(self.empty_hint)
        icons_hint = label(
            "Windows 会把新图标收进溢出区（^）；未读取到电量的设备默认不显示。",
            10.5, QFont.Weight.Normal, MUTED, wrap=True)
        icons_layout.addWidget(icons_hint)
        icons_layout.addSpacing(2)
        self.vbox.addWidget(icons_card)

        # -- data ------------------------------------------------------
        data_card = Card()
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(22, 16, 22, 14)
        data_layout.setSpacing(8)
        data_layout.addWidget(_card_title("数据与维护"))
        self.path_label = label(settings_module.settings_path(), 10.5,
                                QFont.Weight.Normal, MUTED, wrap=True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        data_layout.addWidget(self.path_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        open_dir = PillButton("打开数据目录", "ghost", icon="link", height=32,
                              font_size=11.5)
        open_dir.clicked.connect(self.open_data_dir_requested.emit)
        buttons.addWidget(open_dir)
        detect = PillButton("重新检测设备", "ghost", icon="refresh", height=32,
                            font_size=11.5)
        detect.clicked.connect(self.refresh_requested.emit)
        buttons.addWidget(detect)
        buttons.addStretch(1)
        data_layout.addLayout(buttons)
        self.vbox.addWidget(data_card)

        # -- actions ---------------------------------------------------
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(label("需要彻底退出时使用“退出程序”，托盘图标会一并移除。",
                                10.5, QFont.Weight.Normal, MUTED), 1)
        self.hide_btn = PillButton("隐藏到托盘", "ghost", height=34,
                                   icon="minimize")
        self.hide_btn.clicked.connect(self.hide_requested.emit)
        actions.addWidget(self.hide_btn)
        quit_btn = PillButton("退出程序", "danger", height=34)
        quit_btn.clicked.connect(self.quit_requested.emit)
        actions.addWidget(quit_btn)
        self.vbox.addLayout(actions)
        self.vbox.addStretch(1)

        self.set_devices([])

    # -- public API ---------------------------------------------------
    def _select_interval(self, value: int) -> None:
        self.set_interval(value)
        self.interval_changed.emit(value)

    def set_interval(self, interval: int) -> None:
        for value, chip in self._chips.items():
            chip.setChecked(value == interval)

    def _select_duration(self, value: int) -> None:
        self.set_scan_duration(value)
        self.scan_duration_changed.emit(value)

    def set_scan_duration(self, duration: int) -> None:
        for value, chip in self._duration_chips.items():
            chip.setChecked(value == duration)

    def set_autostart(self, enabled: bool) -> None:
        self.autostart_switch.blockSignals(True)
        self.autostart_switch.setChecked(enabled)
        self.autostart_switch.blockSignals(False)

    def set_close_to_tray(self, enabled: bool) -> None:
        self.close_switch.blockSignals(True)
        self.close_switch.setChecked(enabled)
        self.close_switch.blockSignals(False)

    def set_tray_available(self, available: bool, reason: str = "") -> None:
        self.hide_btn.setEnabled(available)
        self.close_switch.setEnabled(available)
        self.taskbar_btn.setVisible(available)
        if available:
            self.tray_hint.setText("系统托盘不可用时会自动保持窗口显示。")
            self.tray_hint.setStyleSheet(
                f"color: {MUTED}; background: transparent;")
        else:
            detail = f"：{reason}" if reason else ""
            self.tray_hint.setText(
                f"当前环境无法创建系统托盘图标{detail}。关闭窗口将直接退出程序。")
            self.tray_hint.setStyleSheet(
                f"color: {AMBER}; background: transparent;")

    def _open_taskbar_settings(self) -> None:
        try:
            os.startfile("ms-settings:taskbar")  # noqa: S606
        except Exception:
            pass

    def set_busy(self, busy: bool) -> None:
        self.refresh_btn.setEnabled(not busy)
        if busy:
            self.set_status("正在读取电量…", "busy")

    def set_status(self, text: str, tone: str = "idle") -> None:
        self.status_label.setText(text)
        color = {"ok": GREEN, "error": RED, "busy": AMBER}.get(tone, MUTED)
        self.status_dot.set_color(color)
        text_color = color if tone in ("error", "busy") else MUTED
        self.status_label.setStyleSheet(
            f"color: {text_color}; background: transparent;")

    def set_devices(self, devices: Iterable[DeviceView],
                    color: str | None = None,
                    visible_keys: set[str] | None = None) -> None:
        if color is not None:
            self._color = color
        self._devices = list(devices)
        if visible_keys is None:
            visible_keys = {d.stable_key for d in self._devices
                            if d.level is not None}
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        for index, device in enumerate(self._devices[:6]):
            if index:
                line = hline()
                self.rows_layout.addWidget(line)
                self._rows.append(line)
            row = _DeviceRow(device, self._color,
                             device.stable_key in visible_keys)
            self.rows_layout.addWidget(row)
            self._rows.append(row)
        self.empty_hint.setVisible(not self._devices)

    def refresh_colors(self, color: str | None = None) -> None:
        if color is not None:
            self._color = color
        for row in self._rows:
            if isinstance(row, _DeviceRow):
                row.refresh_colors(self._color)

    def set_color(self, color: str) -> None:
        self.refresh_colors(color)


class _DeviceRow(QWidget):
    def __init__(self, device: DeviceView, color: str,
                 visible: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._device = device
        self._color = color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 7, 0, 7)
        layout.setSpacing(11)
        self.glyph = GlyphView(device.kind, device.level, color, side=30,
                               warning_colors=True)
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignVCenter)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        name = label(device.name, 12.5, QFont.Weight.Medium, TEXT)
        name.setToolTip(device.tooltip)
        texts.addWidget(name)
        secondary = f"{device.vid_pid} · {device.kind_label}"
        if not visible:
            secondary += " · 托盘已隐藏"
        texts.addWidget(label(secondary, 10, QFont.Weight.Normal, MUTED))
        layout.addLayout(texts, 1)

        self.percent = label(device.percent_text, 13, QFont.Weight.Bold,
                             TEXT_SOFT)
        pct_color = icons.level_color(device.level, TEXT_SOFT)
        self.percent.setStyleSheet(
            f"color: {pct_color.name()}; background: transparent;")
        layout.addWidget(self.percent, 0, Qt.AlignmentFlag.AlignVCenter)
        self.pill = StatusPill(device.status_text, device.status_tone)
        layout.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setToolTip(device.tooltip)

    def refresh_colors(self, color: str | None = None) -> None:
        if color is not None:
            self._color = color
        self.glyph.set_data(color=self._color)
        self.glyph.update()
        pct_color = icons.level_color(self._device.level, TEXT_SOFT)
        self.percent.setStyleSheet(
            f"color: {pct_color.name()}; background: transparent;")
        self.pill.update()

    def set_color(self, color: str) -> None:
        self.refresh_colors(color)
