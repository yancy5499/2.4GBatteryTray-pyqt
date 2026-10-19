# -*- coding: utf-8 -*-
"""Windows notification-area integration via QSystemTrayIcon.

One tray icon is created per detected device, matching the design concept:
the tooltip carries the exact percentage and the device name, while the
icon shows the device silhouette filled to the battery level.
"""

from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

import icons
import settings
from log import log
from model import DeviceView
from theme import app_font
from tray_probe import probe_notification_area


class TrayController(QObject):
    show_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    autostart_toggled = pyqtSignal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.available = bool(QSystemTrayIcon.isSystemTrayAvailable())
        self.error = ""
        if self.available:
            allowed, error = probe_notification_area()
            if not allowed:
                self.available = False
                self.error = ("系统拒绝访问（Win32 5）" if error == 5
                              else f"Shell_NotifyIcon 失败（Win32 {error}）")
                log("tray unavailable: " + self.error)
        self._icons: dict[str, dict] = {}
        self._generic: dict | None = None
        self._startup = settings.is_autostart_enabled()
        self._visibility_checked = False
        log(f"tray available={self.available}")

    # -- public -------------------------------------------------------
    def update_devices(self, devices: Iterable[DeviceView], color: str) -> bool:
        if not self.available:
            return False
        devices = list(devices)[:6]
        keep: list[str] = []
        for device in devices:
            entry = self._icons.get(device.key)
            if entry is None:
                entry = self._create(device)
                self._icons[device.key] = entry
            entry["device"] = device
            entry["icon"].setIcon(
                icons.device_icon(device.kind, device.level, color))
            entry["icon"].setToolTip(
                f"{device.kind_label} {device.percent_text} · {device.name}"[:126])
            entry["header"].setText(
                f"{device.kind_label} {device.percent_text}")
            entry["icon"].show()
            keep.append(device.key)
        for key in list(self._icons):
            if key not in keep:
                self._destroy(self._icons.pop(key))
        if devices:
            self._hide_generic()
        else:
            self._show_generic()
        if not self._visibility_checked:
            self._visibility_checked = True
            QTimer.singleShot(1200, self._check_visibility)
        return True

    def set_startup_checked(self, checked: bool) -> None:
        self._startup = bool(checked)
        for action in self._startup_actions():
            action.blockSignals(True)
            action.setChecked(self._startup)
            action.blockSignals(False)

    def show_message(self, title: str, text: str) -> None:
        if self.available:
            icon = self._generic["icon"] if self._generic else next(
                (entry["icon"] for entry in self._icons.values()), None)
            if icon is not None:
                icon.showMessage(title, text,
                                 QSystemTrayIcon.MessageIcon.Information, 4000)

    def _check_visibility(self) -> None:
        """Hint once when Windows put the new icons in the overflow area."""
        if not self.available or not self._icons:
            return
        if not all(entry["icon"].geometry().isNull()
                   for entry in self._icons.values()):
            return
        log("tray icons exist but the shell keeps them hidden")
        self.show_message(
            "托盘图标已添加",
            "如果任务栏没有显示图标，请点击任务栏的 ^ 溢出区查看，"
            "或在“设置 → 个性化 → 任务栏 → 其他系统托盘图标”中开启。")

    def shutdown(self) -> None:
        for entry in list(self._icons.values()):
            self._destroy(entry)
        self._icons.clear()
        if self._generic:
            self._destroy(self._generic)
            self._generic = None

    # -- icon/menu ----------------------------------------------------
    def _startup_actions(self) -> list[QAction]:
        actions = [entry["startup"] for entry in self._icons.values()]
        if self._generic:
            actions.append(self._generic["startup"])
        return actions

    def _make_menu(self, header_text: str) -> tuple[QMenu, QAction, QAction]:
        menu = QMenu()
        menu.setFont(app_font(12))
        header = menu.addAction(header_text)
        header.setEnabled(False)
        font = header.font()
        font.setWeight(QFont.Weight.DemiBold)
        header.setFont(font)
        menu.addSeparator()

        show_action = menu.addAction("打开主界面")
        show_action.triggered.connect(self.show_requested.emit)
        refresh_action = menu.addAction("立即刷新")
        refresh_action.triggered.connect(self.refresh_requested.emit)
        menu.addSeparator()

        startup = menu.addAction("开机自启")
        startup.setCheckable(True)
        startup.setChecked(self._startup)
        startup.toggled.connect(self._on_startup_action)
        icon_settings = menu.addAction("图标设置")
        icon_settings.triggered.connect(self.settings_requested.emit)
        menu.addSeparator()

        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(
            lambda: QTimer.singleShot(0, self.quit_requested.emit))
        return menu, header, startup

    def _create(self, device: DeviceView) -> dict:
        icon = QSystemTrayIcon(self)
        icon.setIcon(icons.device_icon(device.kind, device.level, "#2f7df6"))
        menu, header, startup = self._make_menu(
            f"{device.kind_label} {device.percent_text}")
        icon.setContextMenu(menu)
        icon.activated.connect(self._on_activated)
        icon.show()
        return {"icon": icon, "menu": menu, "header": header,
                "startup": startup, "device": device}

    def _create_generic(self) -> dict:
        icon = QSystemTrayIcon(self)
        icon.setIcon(icons.app_icon())
        menu, header, startup = self._make_menu("2.4G 电量助手")
        icon.setContextMenu(menu)
        icon.activated.connect(self._on_activated)
        icon.setToolTip("2.4G 电量助手")
        return {"icon": icon, "menu": menu, "header": header,
                "startup": startup, "device": None}

    def _show_generic(self) -> None:
        if self._generic is None:
            self._generic = self._create_generic()
        self._generic["icon"].setIcon(icons.app_icon())
        self._generic["header"].setText("2.4G 电量助手")
        self._generic["icon"].setToolTip("2.4G 电量助手 · 无设备图标")
        self._generic["icon"].show()

    def _hide_generic(self) -> None:
        if self._generic:
            self._generic["icon"].hide()

    @staticmethod
    def _destroy(entry: dict) -> None:
        try:
            entry["icon"].hide()
            entry["icon"].setContextMenu(None)
            entry["icon"].deleteLater()
            entry["menu"].deleteLater()
        except Exception:
            pass

    # -- events -------------------------------------------------------
    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.refresh_requested.emit()

    def _on_startup_action(self, checked: bool) -> None:
        self._startup = bool(checked)
        for action in self._startup_actions():
            action.blockSignals(True)
            action.setChecked(self._startup)
            action.blockSignals(False)
        self.autostart_toggled.emit(self._startup)
