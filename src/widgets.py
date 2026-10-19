# -*- coding: utf-8 -*-
"""Reusable Fluent-style widgets for the PyQt6 UI."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation, QRectF,
                          QSize, Qt, pyqtProperty, pyqtSignal)
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QLinearGradient,
                         QPainter, QPen)
from PyQt6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel,
                             QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

import icons
import ui_icons
from theme import (ACCENT, ACCENT_DEEP, ACCENT_LINE, ACCENT_SOFT, ACCENT_TINT,
                   AMBER, DEFAULT_FILL, DIVIDER, FAINT, GREEN, MUTED, RED,
                   TEXT, TEXT_SOFT, app_font, blend, qc)

_SENTINEL = object()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def label(text: str = "", size: int = 13, weight: QFont.Weight = QFont.Weight.Normal,
          color: str = TEXT, wrap: bool = False, parent: QWidget | None = None) -> QLabel:
    widget = QLabel(text, parent)
    widget.setFont(app_font(size, weight))
    widget.setStyleSheet(f"color: {color}; background: transparent;")
    widget.setWordWrap(wrap)
    return widget


def hline(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {DIVIDER}; border: none;")
    return line


def vbox(margins=(0, 0, 0, 0), spacing: int = 0,
         parent: QWidget | None = None) -> QVBoxLayout:
    layout = QVBoxLayout(parent) if parent is not None else QVBoxLayout()
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def hbox(margins=(0, 0, 0, 0), spacing: int = 0,
         parent: QWidget | None = None) -> QHBoxLayout:
    layout = QHBoxLayout(parent) if parent is not None else QHBoxLayout()
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, soft: bool = False,
                 object_name: str | None = None):
        super().__init__(parent)
        self.setObjectName(object_name or ("softCard" if soft else "card"))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class ScrollPage(QScrollArea):
    """A transparent, vertically scrolling page."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.viewport().setAutoFillBackground(False)
        self.body = QWidget()
        self.body.setObjectName("pageBody")
        self.body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.vbox = QVBoxLayout(self.body)
        self.vbox.setContentsMargins(0, 0, 8, 12)
        self.vbox.setSpacing(16)
        self.setWidget(self.body)

    def add(self, widget: QWidget, stretch: int = 0) -> None:
        self.vbox.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self.vbox.addStretch(1)


# ---------------------------------------------------------------------------
# labels / icons
# ---------------------------------------------------------------------------
class LineIcon(QWidget):
    def __init__(self, name: str, size: int = 20, color: str = TEXT_SOFT,
                 stroke: float | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self._color = color
        self._stroke = stroke
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_color(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ui_icons.draw_ui_icon(painter, self._name, QRectF(self.rect()),
                              self._color, self._stroke)


class AppLogo(QWidget):
    def __init__(self, side: int = 40, parent: QWidget | None = None):
        super().__init__(parent)
        self._side = side
        self.setFixedSize(side, side)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        icons.paint_app_icon(painter, QRectF(self.rect()))


class GlyphView(QWidget):
    """Paints one device battery glyph."""

    def __init__(self, kind: str = "mouse", level: Optional[int] = None,
                 color: str = DEFAULT_FILL, side: int = 100, wave: bool = False,
                 tile: bool = False, warning_colors: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._kind = icons.normalize_kind(kind)
        self._level = level
        self._color = color
        self._wave = wave
        self._tile = tile
        self._warning_colors = warning_colors
        self.setFixedSize(side, side)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_data(self, kind: str | None = None, level=_SENTINEL,
                 color: str | None = None) -> None:
        changed = False
        if kind is not None:
            kind = icons.normalize_kind(kind)
            if kind != self._kind:
                self._kind = kind
                changed = True
        if level is not _SENTINEL and level != self._level:
            self._level = level
            changed = True
        if color is not None and color != self._color:
            self._color = color
            changed = True
        if changed:
            self.update()
        # Global warning colours can change without touching this widget's
        # data; callers use set_data() after such changes to force a repaint.
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = (icons.level_color(self._level, self._color)
                 if self._warning_colors else self._color)
        icons.paint_device(painter, QRectF(self.rect()), self._kind,
                           self._level, color, self._wave,
                           tile=self._tile)


class StatusPill(QWidget):
    """Small "connected" pill with a coloured dot."""

    _TONES = {
        "ok": ("#f1f4f8", GREEN),
        "warn": ("#fff6e6", AMBER),
        "error": ("#fdecec", RED),
        "muted": ("#f3f5f9", "#b8c4d2"),
    }

    def __init__(self, text: str = "已连接", tone: str = "ok",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._tone = tone
        self.setFont(app_font(11))
        self.setFixedHeight(25)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_status(self, text: str, tone: str) -> None:
        if (text, tone) != (self._text, self._tone):
            self._text, self._tone = text, tone
            self.updateGeometry()
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetricsF(self.font())
        return QSize(int(metrics.horizontalAdvance(self._text)) + 42, 25)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        if self._tone == "warn":
            dot_color = icons.warning_color()
            bg = blend(QColor("#ffffff"), dot_color, 0.12)
        elif self._tone == "error":
            dot_color = icons.low_color()
            bg = blend(QColor("#ffffff"), dot_color, 0.12)
        else:
            bg, dot_color = self._TONES.get(self._tone, self._TONES["muted"])
            dot_color = qc(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qc(bg) if isinstance(bg, str) else QColor(bg))
        painter.drawRoundedRect(rect, 12.5, 12.5)
        painter.setBrush(dot_color)
        painter.drawEllipse(QPointF(14.0, rect.center().y()), 3.5, 3.5)
        painter.setPen(qc(TEXT_SOFT))
        painter.setFont(self.font())
        painter.drawText(rect.adjusted(24, 0, -11, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self._text)


class TrayMini(QWidget):
    """Icon + percentage used by the tray preview panel."""

    clicked = pyqtSignal()

    def __init__(self, kind: str, level: Optional[int], color: str,
                 width: int = 84, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._level = level
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.glyph = GlyphView(kind, level, color, side=40, tile=True,
                               warning_colors=True)
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        self.caption = label(f"{level}%" if level is not None else "--",
                             10.5, QFont.Weight.Normal, TEXT_SOFT)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.caption)
        self._set_caption_color(level)

    def _set_caption_color(self, level: Optional[int]) -> None:
        color = icons.level_color(level, TEXT_SOFT)
        self.caption.setStyleSheet(f"color: {color.name()}; background: transparent;")

    def refresh_colors(self) -> None:
        self._set_caption_color(self._level)
        self.glyph.update()

    def set_data(self, kind: str, level: Optional[int], color: str) -> None:
        self._level = level
        self.glyph.set_data(kind, level, color)
        self.caption.setText(f"{level}%" if level is not None else "--")
        self._set_caption_color(level)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class PreviewItem(QWidget):
    """Larger icon + percentage + name used by the colour preview strip."""

    def __init__(self, kind: str, level: Optional[int], color: str,
                 caption: Optional[str] = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(96)
        self._level = level
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.glyph = GlyphView(kind, level, color, side=50, tile=True,
                               warning_colors=True)
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        self.percent = label(f"{level}%" if level is not None else "--",
                             12, QFont.Weight.DemiBold, TEXT)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.percent)
        self.caption = label(caption or "", 11, QFont.Weight.Normal, MUTED)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.caption)
        self._set_percent_color(level)

    def _set_percent_color(self, level: Optional[int]) -> None:
        color = icons.level_color(level, TEXT)
        self.percent.setStyleSheet(f"color: {color.name()}; background: transparent;")

    def refresh_colors(self) -> None:
        self._set_percent_color(self._level)
        self.glyph.update()

    def set_data(self, kind: str, level: Optional[int], color: str,
                 caption: str | None = None) -> None:
        self._level = level
        self.glyph.set_data(kind, level, color)
        self.percent.setText(f"{level}%" if level is not None else "--")
        self._set_percent_color(level)
        if caption is not None:
            self.caption.setText(caption)


# ---------------------------------------------------------------------------
# buttons
# ---------------------------------------------------------------------------
class ThinProgress(QWidget):
    """Small rounded progress bar used by the search countdown."""

    def __init__(self, width: int = 118, height: int = 4,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._value = 0.0

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        radius = rect.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qc("#e7f0fb"))
        painter.drawRoundedRect(rect, radius, radius)
        if self._value > 0:
            fill = QRectF(rect.x(), rect.y(), rect.width() * self._value,
                          rect.height())
            painter.setBrush(qc(ACCENT))
            painter.drawRoundedRect(fill, radius, radius)


class PillButton(QAbstractButton):
    VARIANTS = {
        "primary": (ACCENT, None, "#ffffff", "#3a88f8", "#1f66d8"),
        "ghost": ("#ffffff", "#dfe9f6", TEXT_SOFT, "#f5f9ff", "#eef5ff"),
        "soft": (ACCENT_TINT, None, ACCENT_DEEP, "#e2efff", "#d7e8ff"),
        "subtle": ("transparent", None, ACCENT_DEEP, ACCENT_TINT, ACCENT_SOFT),
        "danger": ("#ffffff", "#f3dada", "#d94a4a", "#fff6f6", "#ffecec"),
    }

    def __init__(self, text: str, variant: str = "ghost",
                 icon: str | None = None, height: int = 34,
                 font_size: float = 12.5, radius: float = 10,
                 parent: QWidget | None = None, padding: int = 16):
        super().__init__(parent)
        self.setText(text)
        self._variant = variant
        self._icon = icon
        self._radius = radius
        self._padding = padding
        self._font_size = font_size
        self.setFont(app_font(font_size, QFont.Weight.Medium))
        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if variant == "subtle":
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self.updateGeometry()
        self.update()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetricsF(self.font())
        width = metrics.horizontalAdvance(self.text()) + self._padding * 2
        if self._icon:
            width += 16 + 7
        return QSize(int(width), self.height())

    def _colors(self):
        bg, border, fg, hover, pressed = self.VARIANTS.get(
            self._variant, self.VARIANTS["ghost"])
        if self.isDown():
            bg = pressed
        elif self.underMouse() and self.isEnabled():
            bg = hover
        if not self.isEnabled():
            fg = FAINT
        return bg, border, fg

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg, border, fg = self._colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if bg != "transparent":
            painter.setPen(qc(border) if border else Qt.PenStyle.NoPen)
            painter.setBrush(qc(bg))
            painter.drawRoundedRect(rect, self._radius, self._radius)
        painter.setPen(qc(fg))
        painter.setFont(self.font())
        metrics = QFontMetricsF(self.font())
        text_width = metrics.horizontalAdvance(self.text())
        icon_width = (16 + 7) if self._icon else 0
        content = icon_width + text_width
        start = rect.center().x() - content / 2.0
        if self._icon:
            ui_icons.draw_ui_icon(painter, self._icon,
                                  QRectF(start, rect.center().y() - 8, 16, 16),
                                  fg, 1.9)
            start += icon_width
        painter.drawText(QRectF(start, rect.y(), text_width + 2, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.text())


class IconButton(QAbstractButton):
    def __init__(self, icon: str, size: int = 28, icon_size: int = 16,
                 color: str = TEXT_SOFT, hover_bg: str = ACCENT_TINT,
                 radius: int = 8, tooltip: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._icon = icon
        self._icon_size = icon_size
        self._color = color
        self._hover_bg = hover_bg
        self._radius = radius
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if tooltip:
            self.setToolTip(tooltip)

    def set_icon(self, name: str) -> None:
        self._icon = name
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        if self.underMouse() and self.isEnabled():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qc("#e9f3ff" if self._hover_bg == ACCENT_TINT else self._hover_bg))
            painter.drawRoundedRect(rect, self._radius, self._radius)
        size = self._icon_size
        icon_rect = QRectF((rect.width() - size) / 2,
                           (rect.height() - size) / 2, size, size)
        painter.setOpacity(1.0 if self.isEnabled() else 0.45)
        ui_icons.draw_ui_icon(painter, self._icon, icon_rect, self._color, 1.9)


class WindowButton(IconButton):
    def __init__(self, kind: str, parent: QWidget | None = None):
        super().__init__(kind, size=42, icon_size=16, color="#3f5065",
                         hover_bg="#e6f0fc", radius=8, parent=parent)
        self._kind = kind
        self.setFixedSize(42, 30)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        hover = self.underMouse()
        pressed = self.isDown()
        color = "#3f5065"
        if hover:
            bg = "#e81123" if self._kind == "close" else "#e6f0fc"
            if pressed:
                bg = "#c50f1f" if self._kind == "close" else "#d8e7f9"
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qc(bg))
            painter.drawRoundedRect(rect, 8, 8)
            if self._kind == "close":
                color = "#ffffff"
        icon_rect = QRectF((rect.width() - 16) / 2, (rect.height() - 16) / 2,
                           16, 16)
        ui_icons.draw_ui_icon(painter, self._icon, icon_rect, color, 1.8)


class NavButton(QAbstractButton):
    def __init__(self, icon: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon = icon
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFont(app_font(14, QFont.Weight.Medium))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        checked = self.isChecked()
        hover = self.underMouse() and not checked

        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qc(ACCENT))
            painter.drawRoundedRect(QRectF(1, rect.height() / 2 - 11, 3, 22),
                                    1.5, 1.5)

        pill = QRectF(10, 0, rect.width() - 10, rect.height())
        if checked or hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qc(ACCENT_SOFT if checked else "#eef5ff"))
            painter.drawRoundedRect(pill, 10, 10)

        color = ACCENT_DEEP if checked else TEXT_SOFT
        ui_icons.draw_ui_icon(painter, self._icon,
                              QRectF(24, rect.height() / 2 - 10, 20, 20),
                              color, 2.0)
        painter.setPen(qc(color))
        painter.setFont(self.font())
        painter.drawText(QRectF(54, 0, rect.width() - 62, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.text())


class ChipButton(QAbstractButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFont(app_font(11.5, QFont.Weight.Medium))
        self.setFixedHeight(30)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetricsF(self.font())
        return QSize(int(metrics.horizontalAdvance(self.text())) + 26, 30)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        checked = self.isChecked()
        hover = self.underMouse()
        if checked:
            painter.setPen(qc(ACCENT_LINE))
            painter.setBrush(qc(ACCENT_TINT))
        elif hover:
            painter.setPen(qc("#e3edf9"))
            painter.setBrush(qc("#f6faff"))
        else:
            painter.setPen(qc("#e7eef8"))
            painter.setBrush(qc("#ffffff"))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setPen(qc(ACCENT_DEEP if checked else TEXT_SOFT))
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._position = 1.0 if checked else 0.0
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._anim = QPropertyAnimation(self, b"position", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    @pyqtProperty(float)
    def position(self) -> float:
        return self._position

    @position.setter
    def position(self, value: float) -> None:
        self._position = value
        self.update()

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._position = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._position)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        track = blend(QColor("#d5e2f2"), qc(ACCENT), self._position)
        if not self.isEnabled():
            track = QColor("#e1e8f1")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        x = 3 + self._position * (self.width() - 24)
        painter.setBrush(QColor(0, 0, 0, 26))
        painter.drawEllipse(QRectF(x, 4.5, 18, 18))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, 3, 18, 18))


class ColorStateChip(QAbstractButton):
    """Small selectable chip showing one of the three level colours."""

    def __init__(self, text: str, color: QColor | str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setText(text)
        self._color = QColor(color)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(26)
        self.setFont(app_font(10.5, QFont.Weight.Medium))

    def set_color(self, color: QColor | str) -> None:
        self._color = QColor(color)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetricsF(self.font())
        return QSize(int(metrics.horizontalAdvance(self.text())) + 42, 26)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        checked = self.isChecked()
        hover = self.underMouse()
        if checked:
            painter.setPen(qc(ACCENT_LINE))
            painter.setBrush(qc(ACCENT_TINT))
        elif hover:
            painter.setPen(qc("#e1ecf9"))
            painter.setBrush(qc("#f7fbff"))
        else:
            painter.setPen(qc("#e6eef8"))
            painter.setBrush(qc("#ffffff"))
        painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(QPen(QColor(18, 32, 48, 28), 1))
        painter.setBrush(self._color)
        painter.drawEllipse(QPointF(12.0, rect.center().y()), 4.3, 4.3)

        painter.setPen(qc(ACCENT_DEEP if checked else TEXT_SOFT))
        painter.setFont(self.font())
        painter.drawText(QRectF(21, rect.y(), rect.width() - 23, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter |
                         Qt.AlignmentFlag.AlignLeft, self.text())


class SwatchButton(QAbstractButton):
    def __init__(self, color: QColor | None, caption: str,
                 custom: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = QColor(color) if color is not None else QColor("#ffffff")
        self._caption = caption
        self._custom = custom
        self._selected = False
        self.setFixedHeight(92)
        self.setMinimumWidth(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(caption)
        self.setFont(app_font(12))

    @property
    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        area = QRectF(self.rect()).adjusted(6, 8, -6, -2)
        swatch = QRectF(area.x(), area.y(), area.width(), 50)

        if self._selected:
            painter.setPen(QPen(qc(ACCENT), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(swatch.adjusted(-3.4, -3.4, 3.4, 3.4), 12, 12)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawRoundedRect(swatch.adjusted(-1.3, -1.3, 1.3, 1.3), 10, 10)

        if self._custom:
            painter.setPen(qc("#dfe8f4"))
            painter.setBrush(QColor("#ffffff"))
            painter.drawRoundedRect(swatch, 9, 9)
            wheel = icons.color_wheel(22)
            painter.drawPixmap(
                QPointF(swatch.center().x() - 11, swatch.center().y() - 11),
                wheel)
        else:
            lighter = blend(self._color, QColor("#ffffff"), 0.18)
            darker = blend(self._color, QColor("#000000"), 0.06)
            gradient = QLinearGradient(swatch.topLeft(), swatch.bottomLeft())
            gradient.setColorAt(0.0, lighter)
            gradient.setColorAt(1.0, darker)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(swatch, 9, 9)

        if self._selected:
            center = swatch.center()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(18, 26, 40, 165))
            painter.drawEllipse(center, 13, 13)
            ui_icons.draw_ui_icon(painter, "check",
                                  QRectF(center.x() - 7, center.y() - 7, 14, 14),
                                  "#ffffff", 2.4)

        if self.underMouse() and not self._selected:
            painter.setPen(QPen(QColor(47, 125, 246, 90), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(swatch.adjusted(-1, -1, 1, 1), 10, 10)

        painter.setPen(qc(TEXT if self._selected else TEXT_SOFT))
        painter.setFont(self.font())
        caption_rect = QRectF(0, 64, self.width(), 22)
        painter.drawText(caption_rect, Qt.AlignmentFlag.AlignHCenter |
                         Qt.AlignmentFlag.AlignVCenter, self._caption)


# ---------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------
class SettingRow(QWidget):
    """Title + description on the left, a control on the right."""

    def __init__(self, title: str, subtitle: str, control: QWidget,
                 icon: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._control = control
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 9, 0, 9)
        layout.setSpacing(14)
        if icon:
            icon_widget = LineIcon(icon, 20, TEXT_SOFT)
            layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignTop)
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(3)
        text_box.addWidget(label(title, 13, QFont.Weight.Medium, TEXT))
        hint = label(subtitle, 11, QFont.Weight.Normal, MUTED, wrap=True)
        text_box.addWidget(hint)
        layout.addLayout(text_box, 1)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        if isinstance(control, ToggleSwitch):
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (event.button() == Qt.MouseButton.LeftButton
                and isinstance(self._control, ToggleSwitch)
                and self._control.isEnabled()):
            self._control.toggle()
        super().mouseReleaseEvent(event)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(4)
        layout.addWidget(label(title, 24, QFont.Weight.Bold, TEXT))
        layout.addWidget(label(subtitle, 12, QFont.Weight.Normal, MUTED, wrap=True))


class SectionTitle(QWidget):
    def __init__(self, title: str, right: QWidget | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(label(title, 18, QFont.Weight.Bold, TEXT))
        layout.addStretch(1)
        if right is not None:
            layout.addWidget(right, 0, Qt.AlignmentFlag.AlignVCenter)
