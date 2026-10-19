# -*- coding: utf-8 -*-
"""Design tokens for the PyQt6 rewrite.

The whole UI is a light "WinUI 3 / Fluent" surface: soft blue gradient glass,
white cards, one blue accent and the device fill colour used by the icon set.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPalette
from PyQt6.QtCore import QPointF, QRectF, Qt

APP_NAME = "2.4G 电量助手"
APP_NAME_EN = "2.4G Battery Tray"
APP_VERSION = "2.0.0"
APP_TAGLINE = "监控 2.4G 无线设备电量 · 简单 · 直观 · 始终在线"
FONT_FAMILY = "Microsoft YaHei UI"
FONT_FALLBACK = "Microsoft YaHei"

# -- surfaces -------------------------------------------------------------
BG_TOP = "#f5faff"
BG_BOTTOM = "#e6f1fe"
SHELL_BORDER = "#d8e6f7"
CARD = "#ffffff"
CARD_BORDER = "#e5edf8"
CARD_SOFT = "#f8fbff"
CARD_SOFT_BORDER = "#e8f0fa"
DIVIDER = "#e9f0f9"

# -- text -----------------------------------------------------------------
TEXT = "#17243a"
TEXT_SOFT = "#52657c"
MUTED = "#8798ab"
FAINT = "#a8b7c8"

# -- accent ---------------------------------------------------------------
ACCENT = "#2f7df6"
ACCENT_DEEP = "#1f66d8"
ACCENT_SOFT = "#dbe9fd"
ACCENT_TINT = "#eef5ff"
ACCENT_LINE = "#bcd7fb"

# -- semantic -------------------------------------------------------------
GREEN = "#2ebd6b"
GREEN_SOFT = "#e9f8f0"
AMBER = "#f2a93b"
RED = "#ef5350"
DARK = "#1b2536"
GLYPH = "#1c2637"
GLYPH_SOFT = "#ffffff"

# -- icon palette ---------------------------------------------------------
PALETTE = [
    ("默认绿", "#3ec173"),
    ("蓝色", "#2f7df6"),
    ("琥珀色", "#f7b93c"),
    ("红色", "#f25b66"),
    ("紫色", "#9361f7"),
    ("青色", "#22c4d4"),
    ("粉色", "#ef74a9"),
]
DEFAULT_FILL = PALETTE[0][1]


def qc(value: str | QColor, alpha: int | None = None) -> QColor:
    color = QColor(value) if isinstance(value, str) else QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def app_font(px: int, weight: QFont.Weight = QFont.Weight.Normal,
             family: str = FONT_FAMILY) -> QFont:
    font = QFont(family)
    font.setPixelSize(max(1, int(px)))
    font.setWeight(weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def light_palette() -> QPalette:
    """A light palette for native popups/dialogs (menus, message boxes).

    The translucent frameless window can leave child popups with a black
    inherited palette on Windows; an explicit application palette keeps
    every non-custom-painted surface light.
    """
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, qc("#f5faff"))
    palette.setColor(QPalette.ColorRole.WindowText, qc(TEXT))
    palette.setColor(QPalette.ColorRole.Base, qc("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, qc("#f5f9ff"))
    palette.setColor(QPalette.ColorRole.Text, qc(TEXT))
    palette.setColor(QPalette.ColorRole.Button, qc("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, qc(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, qc("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, qc("#1b2536"))
    palette.setColor(QPalette.ColorRole.ToolTipText, qc("#f4f8fd"))
    palette.setColor(QPalette.ColorRole.Highlight, qc(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, qc("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, qc(MUTED))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
                     qc(FAINT))
    palette.setColor(QPalette.ColorGroup.Disabled,
                     QPalette.ColorRole.WindowText, qc(FAINT))
    palette.setColor(QPalette.ColorGroup.Disabled,
                     QPalette.ColorRole.ButtonText, qc(FAINT))
    return palette


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def blend(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        round(lerp(c1.red(), c2.red(), t)),
        round(lerp(c1.green(), c2.green(), t)),
        round(lerp(c1.blue(), c2.blue(), t)),
        round(lerp(c1.alpha(), c2.alpha(), t)),
    )


def soft_tint(color: QColor, alpha: int = 22) -> QColor:
    """A very light tint of ``color`` on white, for preview panels."""
    white = QColor("#ffffff")
    mixed = blend(white, color, alpha / 100.0)
    mixed.setAlpha(255)
    return mixed


def paint_shell(painter: QPainter, rect: QRectF, radius: float) -> None:
    """Paint the frosted light-blue window surface with a subtle glow."""
    painter.save()
    clip = QRectF(rect)
    from PyQt6.QtGui import QPainterPath
    path = QPainterPath()
    path.addRoundedRect(clip, radius, radius)
    painter.setClipPath(path)
    painter.setPen(Qt.PenStyle.NoPen)

    gradient = QLinearGradient(clip.topLeft(), clip.bottomRight())
    gradient.setColorAt(0.0, qc(BG_TOP))
    gradient.setColorAt(0.55, qc("#eef7ff"))
    gradient.setColorAt(1.0, qc(BG_BOTTOM))
    painter.fillPath(path, gradient)

    # Soft white glow in the upper left, like the reference's glass panel.
    from PyQt6.QtGui import QRadialGradient
    glow = QRadialGradient(QPointF(clip.left() + clip.width() * 0.18,
                                   clip.top() + clip.height() * 0.02),
                           clip.width() * 0.75)
    glow.setColorAt(0.0, QColor(255, 255, 255, 235))
    glow.setColorAt(0.55, QColor(255, 255, 255, 90))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillPath(path, glow)

    # Faint blue bloom in the lower right corner.
    bloom = QRadialGradient(QPointF(clip.right() - clip.width() * 0.08,
                                    clip.bottom() + clip.height() * 0.05),
                            clip.width() * 0.55)
    bloom.setColorAt(0.0, QColor(147, 197, 253, 90))
    bloom.setColorAt(1.0, QColor(147, 197, 253, 0))
    painter.fillPath(path, bloom)
    painter.restore()

    painter.save()
    painter.setPen(qc(SHELL_BORDER))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(clip.adjusted(0.5, 0.5, -0.5, -0.5),
                            radius, radius)
    painter.restore()


BASE_QSS = """
QWidget {
    color: %(text)s;
    font-family: "%(family)s";
}
QLabel { background: transparent; }
QFrame#card {
    background: #ffffff;
    border: 1px solid %(card_border)s;
    border-radius: 14px;
}
QFrame#softCard {
    background: #f8fbff;
    border: 1px solid %(card_soft_border)s;
    border-radius: 12px;
}
QFrame#deviceCard {
    background: #ffffff;
    border: 1px solid %(card_border)s;
    border-radius: 14px;
}
QFrame#deviceCard:hover { border: 1px solid #cfe2fb; }
QToolTip {
    background: #1b2536;
    color: #f4f8fd;
    border: none;
    padding: 6px 9px;
    border-radius: 6px;
    font-size: 12px;
}
QMenu {
    background: #ffffff;
    border: 1px solid %(card_border)s;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 30px 7px 14px;
    border-radius: 6px;
    color: #253449;
    font-size: 12px;
}
QMenu::item:selected { background: %(accent_tint)s; color: %(accent_deep)s; }
QMenu::item:disabled { color: %(faint)s; }
QMenu::separator { height: 1px; background: %(divider)s; margin: 5px 10px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QWidget#pageBody { background: transparent; }
QStackedWidget { background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 2px 0 2px 0;
}
QScrollBar::handle:vertical {
    background: #cbd9ea; border-radius: 3px; min-height: 36px;
}
QScrollBar::handle:vertical:hover { background: #b3c8e2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }
""" % {
    "text": TEXT,
    "family": FONT_FAMILY,
    "card_border": CARD_BORDER,
    "card_soft_border": CARD_SOFT_BORDER,
    "accent_tint": ACCENT_TINT,
    "accent_deep": ACCENT_DEEP,
    "faint": FAINT,
    "divider": DIVIDER,
}
