# -*- coding: utf-8 -*-
"""Icon settings page, based on the tray-icon design concept sheet."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QVBoxLayout,
                             QWidget)

from color_card import ColorSettingsCard
from model import KIND_META
from theme import ACCENT, DEFAULT_FILL, DIVIDER, MUTED, TEXT, TEXT_SOFT
from widgets import (Card, GlyphView, LineIcon, PageHeader, ScrollPage, label)

PREVIEW_LEVELS = (100, 50, 20)
TRAY_SIZES = (24, 20, 16)


class FeatureItem(QWidget):
    def __init__(self, icon: str, title: str, subtitle: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(LineIcon(icon, 18, ACCENT, 1.9), 0,
                     Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label(title, 12, QFont.Weight.DemiBold, TEXT))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(label(subtitle, 10.5, QFont.Weight.Normal, MUTED))


class KindPreviewCard(Card):
    def __init__(self, kind: str, color: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._kind = kind
        self._color = color
        self.setMinimumHeight(206)
        title, description = KIND_META.get(kind, KIND_META["receiver"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 13)
        layout.setSpacing(0)

        layout.addWidget(label(title, 15, QFont.Weight.Bold, TEXT))
        layout.addWidget(label(description, 10.5, QFont.Weight.Normal, MUTED))

        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 4)
        row.setSpacing(6)
        for level in PREVIEW_LEVELS:
            column = QVBoxLayout()
            column.setSpacing(1)
            glyph = GlyphView(kind, level, color, side=74,
                              warning_colors=True)
            column.addWidget(glyph, 0, Qt.AlignmentFlag.AlignHCenter)
            caption = label(f"{level}%", 10.5, QFont.Weight.Medium, TEXT_SOFT)
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(caption)
            holder = QWidget()
            holder.setLayout(column)
            row.addWidget(holder, 1)
        layout.addLayout(row)

        layout.addSpacing(2)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {DIVIDER}; border: none;")
        layout.addWidget(line)
        layout.addSpacing(7)

        tray_row = QHBoxLayout()
        tray_row.setContentsMargins(0, 0, 2, 0)
        tray_row.setSpacing(10)
        hint = label("托盘尺寸预览（16–24px）", 10, QFont.Weight.Normal, MUTED)
        tray_row.addWidget(hint, 1)
        for size in TRAY_SIZES:
            column = QVBoxLayout()
            column.setSpacing(1)
            column.addWidget(GlyphView(kind, 50, color, side=size, tile=True), 0,
                             Qt.AlignmentFlag.AlignHCenter)
            caption = label(f"{size}px", 8.5, QFont.Weight.Normal, MUTED)
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(caption)
            holder = QWidget()
            holder.setLayout(column)
            tray_row.addWidget(holder, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(tray_row)
        layout.addStretch(1)

    def set_color(self, color: str) -> None:
        self._color = color
        for column in self.findChildren(GlyphView):
            column.set_data(color=color)


class IconSettingsPage(ScrollPage):
    colors_changed = pyqtSignal(str, str, str)

    def __init__(self, color: str = DEFAULT_FILL,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self.vbox.addWidget(PageHeader(
            "图标设置",
            "托盘图标保留设备原有形态，用统一的填充颜色表示剩余电量；"
            "托盘尺寸使用浅蓝圆角方块底，同一套轮廓覆盖 16–24px。"
            "实际托盘中低于 50% 变黄、低于 20% 变红。"))

        features = Card(soft=True)
        feature_layout = QHBoxLayout(features)
        feature_layout.setContentsMargins(20, 12, 20, 12)
        feature_layout.setSpacing(18)
        for icon, title, subtitle in (
                ("monitor", "WinUI 3 风格", "现代、系统化的视觉语言"),
                ("palette", "统一的设计语言", "一致的线宽、圆角与填充"),
                ("maximize", "小尺寸高可读", "16–24px 托盘场景优化"),
                ("check", "保持设备特征", "不牺牲设备原有形态")):
            feature_layout.addWidget(FeatureItem(icon, title, subtitle), 1)
        self.vbox.addWidget(features)

        self.kind_cards: list[KindPreviewCard] = []
        grid_holder = QWidget()
        grid = QGridLayout(grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        kinds = ("mouse", "keyboard", "headset", "gamepad")
        for index, kind in enumerate(kinds):
            card = KindPreviewCard(kind, color)
            self.kind_cards.append(card)
            grid.addWidget(card, index // 2, index % 2)
            grid.setColumnStretch(index % 2, 1)
        self.vbox.addWidget(grid_holder)

        self.color_card = ColorSettingsCard(color, show_preview=False)
        self.color_card.colors_changed.connect(self.colors_changed.emit)
        self.vbox.addWidget(self.color_card)
        self.vbox.addStretch(1)

    def set_colors(self, normal: str, warn: str, low: str) -> None:
        self._color = normal
        for card in self.kind_cards:
            card.set_color(normal)
        self.color_card.set_colors(normal, warn, low)

    def set_color(self, color: str) -> None:
        self.set_colors(color, self.color_card.warn_color,
                        self.color_card.low_color)
