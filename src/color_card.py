# -*- coding: utf-8 -*-
"""Shared editor for the three battery reminder colours.

The palette edits one of three states at a time (normal / low / critical),
while all three colours stay visible in the state chips and the preview.
"""

from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QButtonGroup, QColorDialog, QFrame, QHBoxLayout,
                             QSizePolicy, QVBoxLayout, QWidget)

from model import DeviceView, KIND_LABELS, sample_kinds
from theme import AMBER, DEFAULT_FILL, MUTED, PALETTE, RED, TEXT, soft_tint
from widgets import (Card, ColorStateChip, LineIcon, PillButton, PreviewItem,
                     SwatchButton, label)

STATE_META = (
    ("normal", "正常", "高于或等于 50%"),
    ("warn", "偏低", "低于 50%"),
    ("low", "不足", "低于 20%"),
)


class TintPanel(QFrame):
    """A soft rounded panel tinted with the normal fill colour."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._color = QColor(DEFAULT_FILL)

    def set_tint(self, color: QColor) -> None:
        self._color = QColor(color)
        self._apply()

    def _apply(self) -> None:
        bg = soft_tint(self._color, 16).name()
        border = soft_tint(self._color, 34).name()
        self.setStyleSheet(
            f"QFrame#previewPanel {{ background: {bg}; "
            f"border: 1px solid {border}; border-radius: 12px; }}")


class ColorSettingsCard(Card):
    """Palette row + live preview strip for all three reminder colours."""

    colors_changed = pyqtSignal(str, str, str)

    def __init__(self, color: str = DEFAULT_FILL,
                 show_preview: bool = True,
                 warn: str = AMBER, low: str = RED,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._colors = {
            "normal": str(color).lower(),
            "warn": str(warn).lower(),
            "low": str(low).lower(),
        }
        self._state = "normal"
        self._show_preview = show_preview
        self._devices: list[DeviceView] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(9)

        # -- header -----------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(12)
        palette_icon = LineIcon("palette", 24, "#2b3a4f", 1.8)
        header.addWidget(palette_icon, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(label("图标填充颜色", 15.5, QFont.Weight.Bold, TEXT))
        titles.addWidget(label(
            "分别设置正常、偏低、不足三种提醒色；点击状态切换要编辑的颜色",
            11.5, color=MUTED, wrap=True))
        header.addLayout(titles, 1)

        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        chips = QHBoxLayout()
        chips.setSpacing(4)
        self._chips: dict[str, ColorStateChip] = {}
        for state, text, hint in STATE_META:
            chip = ColorStateChip(text, self._colors[state])
            chip.setToolTip(f"{text}：{hint}")
            self._chip_group.addButton(chip)
            chip.clicked.connect(
                lambda _checked=False, s=state: self._select_state(s))
            chips.addWidget(chip)
            self._chips[state] = chip
        self._chips["normal"].setChecked(True)
        header.addLayout(chips, 0)
        header.addSpacing(4)

        self.restore_btn = PillButton("恢复默认", "ghost", icon="refresh",
                                      height=32, font_size=11.5)
        self.restore_btn.clicked.connect(self._restore)
        header.addWidget(self.restore_btn, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        # -- swatches ---------------------------------------------------
        self.swatches: list[SwatchButton] = []
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(8)
        for caption, value in PALETTE:
            swatch = SwatchButton(QColor(value), caption)
            swatch.clicked.connect(
                lambda _checked=False, c=value: self._pick(c))
            swatch_row.addWidget(swatch, 1)
            self.swatches.append(swatch)
        self.custom_swatch = SwatchButton(None, "自定义…", custom=True)
        self.custom_swatch.clicked.connect(self._pick_custom)
        swatch_row.addWidget(self.custom_swatch, 1)
        self.swatches.append(self.custom_swatch)
        outer.addLayout(swatch_row)

        # -- preview ----------------------------------------------------
        self.preview = TintPanel()
        preview_layout = QVBoxLayout(self.preview)
        preview_layout.setContentsMargins(16, 9, 16, 10)
        preview_layout.setSpacing(6)

        preview_header = QHBoxLayout()
        preview_header.setSpacing(8)
        preview_header.addWidget(label("效果预览", 12.5, QFont.Weight.Bold,
                                       TEXT))
        preview_header.addWidget(label(
            "正常色用于 ≥50%，偏低/不足使用上方设置的提醒色",
            11, color=MUTED))
        preview_header.addStretch(1)
        preview_layout.addLayout(preview_header)

        self.items_row = QHBoxLayout()
        self.items_row.setSpacing(0)
        self._preview_items: list[PreviewItem] = []
        self._dividers: list[QFrame] = []
        for index in range(4):
            item = PreviewItem("mouse", 100, self._colors["normal"])
            self.items_row.addWidget(item, 1)
            self._preview_items.append(item)
            if index < 3:
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setSizePolicy(QSizePolicy.Policy.Fixed,
                                      QSizePolicy.Policy.Expanding)
                self.items_row.addWidget(divider, 0)
                self._dividers.append(divider)
        preview_layout.addLayout(self.items_row)
        self.preview.setVisible(show_preview)
        outer.addWidget(self.preview)

        self.set_colors(self._colors["normal"], self._colors["warn"],
                        self._colors["low"], emit=False)
        self.set_devices([])

    # -- public -------------------------------------------------------
    def set_colors(self, normal: str, warn: str, low: str,
                   emit: bool = False) -> None:
        self._colors = {
            "normal": str(normal).lower(),
            "warn": str(warn).lower(),
            "low": str(low).lower(),
        }
        for state, chip in self._chips.items():
            chip.set_color(self._colors[state])
        self._chips[self._state].setChecked(True)
        self._update_swatches()
        self._update_preview()
        if emit:
            self._emit()

    def set_color(self, color: str, emit: bool = False) -> None:
        """Compatibility wrapper: update the normal colour only."""
        self.set_colors(color, self._colors["warn"], self._colors["low"],
                        emit=emit)

    @property
    def color(self) -> str:
        return self._colors["normal"]

    @property
    def warn_color(self) -> str:
        return self._colors["warn"]

    @property
    def low_color(self) -> str:
        return self._colors["low"]

    def set_devices(self, devices: Iterable[DeviceView]) -> None:
        self._devices = list(devices)[:4]
        if self._devices:
            for index, item in enumerate(self._preview_items):
                if index < len(self._devices):
                    device = self._devices[index]
                    item.set_data(device.kind, device.level,
                                  self._colors["normal"],
                                  KIND_LABELS.get(device.kind, "设备"))
                    item.setVisible(True)
                else:
                    item.setVisible(False)
        else:
            for index, item in enumerate(self._preview_items):
                kind, level = sample_kinds()[index]
                item.set_data(kind, level, self._colors["normal"],
                              KIND_LABELS.get(kind, "设备"))
                item.setVisible(True)
        counts = sum(1 for item in self._preview_items if not item.isHidden())
        for index, divider in enumerate(self._dividers):
            divider.setVisible(index < counts - 1)

    def set_show_preview(self, show: bool) -> None:
        self._show_preview = show
        self.preview.setVisible(show)

    # -- internals ----------------------------------------------------
    def _select_state(self, state: str) -> None:
        self._state = state
        self._chips[state].setChecked(True)
        self._update_swatches()

    def _update_swatches(self) -> None:
        color = self._colors[self._state]
        presets = {value.lower() for _caption, value in PALETTE}
        for swatch in self.swatches:
            if swatch is self.custom_swatch:
                swatch.set_selected(color not in presets)
            else:
                swatch.set_selected(swatch.color.name().lower() == color)

    def _update_preview(self) -> None:
        normal = QColor(self._colors["normal"])
        self.preview.set_tint(normal)
        for item in self._preview_items:
            item.glyph.set_data(color=self._colors["normal"])
            item.refresh_colors()
        divider_color = soft_tint(normal, 42).name()
        for divider in self._dividers:
            divider.setStyleSheet(f"background: {divider_color}; border: none;")

    def _emit(self) -> None:
        self.colors_changed.emit(self._colors["normal"],
                                 self._colors["warn"],
                                 self._colors["low"])

    # -- actions ------------------------------------------------------
    def _pick(self, color: str) -> None:
        self._colors[self._state] = str(color).lower()
        self._chips[self._state].set_color(color)
        self._update_swatches()
        self._update_preview()
        self._emit()

    def _pick_custom(self) -> None:
        current = self._colors[self._state]
        chosen = QColorDialog.getColor(QColor(current), self,
                                       "自定义提醒颜色")
        if chosen.isValid():
            self._pick(chosen.name())

    def _restore(self) -> None:
        self._state = "normal"
        self._chips["normal"].setChecked(True)
        self.set_colors(DEFAULT_FILL, AMBER, RED, emit=True)
