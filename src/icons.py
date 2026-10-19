# -*- coding: utf-8 -*-
"""Device glyphs and application icon, painted with QPainter.

The tray icon concept (see ``assets/tray-preview.png``):

* the device keeps its real outline, drawn with one thick dark stroke;
* the battery level is the amount of coloured "liquid" inside the outline;
* one fill colour is shared by every device, so a tray full of dongles still
  reads as one visual family at 16-24 px.

All shapes are designed on a 64x64 grid and scaled, so the same code renders
a 16 px tray icon and a 110 px card illustration.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional

from PyQt6.QtCore import QByteArray, QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QIcon,
                         QLinearGradient, QPainter, QPainterPath, QPen,
                         QPixmap, QRadialGradient)
from PyQt6.QtSvg import QSvgRenderer

import app_icon_svg
from theme import AMBER, GLYPH, RED, qc

GRID = 64.0
STROKE = 4.2
DETAIL = QColor(GLYPH)
PAPER = QColor("#ffffff")
KINDS = ("mouse", "keyboard", "headset", "gamepad", "receiver")

_WARN_COLOR = QColor(AMBER)
_LOW_COLOR = QColor(RED)


def set_warning_colors(warn: QColor | str, low: QColor | str) -> None:
    """Set the user-configured colours for 20–49% and below 20%."""
    global _WARN_COLOR, _LOW_COLOR
    warn_color = qc(warn)
    low_color = qc(low)
    if warn_color.isValid():
        _WARN_COLOR = warn_color
    if low_color.isValid():
        _LOW_COLOR = low_color


def warning_color() -> QColor:
    return QColor(_WARN_COLOR)


def low_color() -> QColor:
    return QColor(_LOW_COLOR)


def level_color(level: Optional[int], base: QColor | str) -> QColor:
    """Warning colour convention: <20% low, <50% warning, else the base."""
    base_color = qc(base) if isinstance(base, str) else QColor(base)
    if level is None:
        return base_color
    if level < 20:
        return QColor(_LOW_COLOR)
    if level < 50:
        return QColor(_WARN_COLOR)
    return base_color


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def _mouse_paths() -> tuple[list[QPainterPath], list[QRectF]]:
    body = QPainterPath()
    body.addRoundedRect(QRectF(19.0, 7.0, 26.0, 47.5), 13.0, 13.0)
    return [body], [body.boundingRect()]


def _keyboard_paths() -> tuple[list[QPainterPath], list[QRectF]]:
    body = QPainterPath()
    body.addRoundedRect(QRectF(5.0, 18.0, 54.0, 30.0), 7.0, 7.0)
    return [body], [body.boundingRect()]


def _headset_paths() -> tuple[list[QPainterPath], list[QRectF]]:
    left = QPainterPath()
    left.addRoundedRect(QRectF(5.0, 26.0, 19.5, 28.0), 6.5, 6.5)
    right = QPainterPath()
    right.addRoundedRect(QRectF(39.5, 26.0, 19.5, 28.0), 6.5, 6.5)
    return [left, right], [QRectF(5.0, 8.5, 54.0, 45.5)]


def _gamepad_paths() -> tuple[list[QPainterPath], list[QRectF]]:
    path = QPainterPath()
    path.moveTo(11.0, 32.0)
    path.cubicTo(11.0, 23.4, 15.2, 19.2, 22.6, 19.2)
    path.cubicTo(27.2, 19.2, 29.6, 22.0, 32.0, 22.0)
    path.cubicTo(34.4, 22.0, 36.8, 19.2, 41.4, 19.2)
    path.cubicTo(48.8, 19.2, 53.0, 23.4, 53.0, 32.0)
    path.cubicTo(54.4, 39.6, 56.6, 46.6, 53.6, 51.6)
    path.cubicTo(50.8, 56.4, 44.2, 57.6, 40.4, 53.2)
    path.cubicTo(37.2, 49.4, 35.4, 45.8, 32.0, 45.8)
    path.cubicTo(28.6, 45.8, 26.8, 49.4, 23.6, 53.2)
    path.cubicTo(19.8, 57.6, 13.2, 56.4, 10.4, 51.6)
    path.cubicTo(7.4, 46.6, 9.6, 39.6, 11.0, 32.0)
    path.closeSubpath()
    return [path], [path.boundingRect()]


def _receiver_paths() -> tuple[list[QPainterPath], list[QRectF]]:
    body = QPainterPath()
    body.addRoundedRect(QRectF(21.0, 22.0, 22.0, 28.0), 5.5, 5.5)
    return [body], [body.boundingRect()]


_PATH_BUILDERS = {
    "mouse": _mouse_paths,
    "keyboard": _keyboard_paths,
    "headset": _headset_paths,
    "gamepad": _gamepad_paths,
    "receiver": _receiver_paths,
}


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------
def _liquid(painter: QPainter, clip: QPainterPath, bounds: QRectF,
            level: Optional[int], color: QColor, wave: bool) -> None:
    if level is None:
        return
    level = max(0, min(100, int(level)))
    if level <= 0:
        return
    ratio = level / 100.0
    top = bounds.bottom() - bounds.height() * ratio
    fill = QPainterPath()
    if wave and ratio < 0.985:
        steps = 48
        amp = 1.15
        fill.moveTo(bounds.left() - 3, top)
        for i in range(steps + 1):
            x = bounds.left() - 3 + (bounds.width() + 6) * i / steps
            y = top + amp * math.sin(i / steps * math.pi * 2.0 + 0.45)
            fill.lineTo(x, y)
        fill.lineTo(bounds.right() + 3, bounds.bottom() + 4)
        fill.lineTo(bounds.left() - 3, bounds.bottom() + 4)
        fill.closeSubpath()
    else:
        fill.addRect(QRectF(bounds.left() - 3, top,
                            bounds.width() + 6, bounds.height() + 4))
    painter.save()
    painter.setClipPath(clip)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawPath(fill)
    painter.restore()


def _stroke(painter: QPainter, path: QPainterPath, width: float = STROKE,
            color: QColor = DETAIL) -> None:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)


def _draw_mouse(painter: QPainter, level, color, wave, stroke) -> None:
    paths, bounds = _mouse_paths()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PAPER))
    painter.drawPath(paths[0])
    _liquid(painter, paths[0], bounds[0], level, color, wave)
    _stroke(painter, paths[0], stroke)
    wheel = QPainterPath()
    wheel.addRoundedRect(QRectF(29.6, 12.0, 4.8, 15.6), 2.4, 2.4)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(DETAIL))
    painter.drawPath(wheel)


def _draw_keyboard(painter: QPainter, level, color, wave, stroke) -> None:
    paths, bounds = _keyboard_paths()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PAPER))
    painter.drawPath(paths[0])
    _liquid(painter, paths[0], bounds[0], level, color, wave)
    _stroke(painter, paths[0], stroke)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(DETAIL))
    key_w, key_h, gap = 5.2, 5.0, 2.0
    rows = ((5, 14.4, 22.8), (6, 10.4, 30.6))
    for count, start_x, y in rows:
        for i in range(count):
            x = start_x + i * (key_w + gap)
            painter.drawRoundedRect(QRectF(x, y, key_w, key_h), 1.3, 1.3)
    painter.drawRoundedRect(QRectF(23.4, 38.4, 17.2, 5.0), 1.5, 1.5)


def _draw_headset(painter: QPainter, level, color, wave, stroke) -> None:
    paths, bounds = _headset_paths()
    # Hollow head band: the annular band is filled with the battery colour so
    # the connecting part shows the same colour as the ear cups.
    outer = QRectF(10.5, 8.5, 43.0, 39.0)
    inner = QRectF(19.0, 17.0, 26.0, 24.0)
    band = QPainterPath()
    band.arcMoveTo(outer, 180)
    band.arcTo(outer, 180, -180)
    band.lineTo(inner.right(), inner.center().y())
    band.arcTo(inner, 0, 180)
    band.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PAPER))
    painter.drawPath(band)
    # Fill the whole headset from one shared liquid level: the cups and the
    # hollow head band are clipped against the overall icon height.
    _liquid(painter, band, bounds[0], level, color, wave)
    _stroke(painter, band, 3.4)

    for path in paths:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(PAPER))
        painter.drawPath(path)
        _liquid(painter, path, bounds[0], level, color, wave)
        _stroke(painter, path, stroke)


def _draw_gamepad(painter: QPainter, level, color, wave, stroke) -> None:
    paths, bounds = _gamepad_paths()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PAPER))
    painter.drawPath(paths[0])
    _liquid(painter, paths[0], bounds[0], level, color, wave)
    _stroke(painter, paths[0], stroke)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(DETAIL))
    painter.drawRoundedRect(QRectF(16.2, 31.1, 11.0, 2.9), 1.3, 1.3)
    painter.drawRoundedRect(QRectF(20.25, 27.0, 2.9, 11.0), 1.3, 1.3)
    for dx, dy in ((0, -4.4), (4.4, 0), (-4.4, 0), (0, 4.4)):
        painter.drawEllipse(QPointF(41.0 + dx, 34.0 + dy), 1.95, 1.95)


def _draw_receiver(painter: QPainter, level, color, wave, stroke) -> None:
    paths, bounds = _receiver_paths()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PAPER))
    painter.drawPath(paths[0])
    _liquid(painter, paths[0], bounds[0], level, color, wave)
    _stroke(painter, paths[0], stroke)
    # USB connector on top
    connector = QPainterPath()
    connector.addRoundedRect(QRectF(27.0, 12.5, 10.0, 11.0), 2.4, 2.4)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PAPER))
    painter.drawPath(connector)
    _stroke(painter, connector, stroke * 0.82)
    painter.setPen(QPen(DETAIL, 2.4))
    painter.drawLine(QPointF(30.4, 17.0), QPointF(30.4, 19.4))
    painter.drawLine(QPointF(33.6, 17.0), QPointF(33.6, 19.4))
    # tiny status LED
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(color)))
    painter.drawEllipse(QPointF(32.0, 43.0), 2.0, 2.0)


_DRAWERS = {
    "mouse": _draw_mouse,
    "keyboard": _draw_keyboard,
    "headset": _draw_headset,
    "gamepad": _draw_gamepad,
    "receiver": _draw_receiver,
}


def normalize_kind(kind: str) -> str:
    return kind if kind in _DRAWERS else "receiver"


TILE_BORDER = QColor("#c7dcf5")


def _paint_tile(painter: QPainter) -> None:
    """Light blue rounded-square backdrop used by tray icons."""
    rect = QRectF(1.6, 1.6, 60.8, 60.8)
    path = QPainterPath()
    path.addRoundedRect(rect, 14.2, 14.2)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#ffffff"))
    gradient.setColorAt(0.55, QColor("#f4faff"))
    gradient.setColorAt(1.0, QColor("#e3f1ff"))
    painter.setPen(QPen(TILE_BORDER, 1.8))
    painter.setBrush(QBrush(gradient))
    painter.drawPath(path)


def paint_device(painter: QPainter, box: QRectF, kind: str,
                 level: Optional[int], color: QColor | str,
                 wave: bool = False, stroke: float = STROKE,
                 tile: bool = False) -> None:
    """Paint one battery glyph into ``box`` (square).

    With ``tile=True`` the glyph sits on a white rounded square, which is the
    look used by the Windows notification area and the in-app tray previews.
    """
    color = qc(color) if isinstance(color, str) else color
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scale = min(box.width(), box.height()) / GRID
    painter.translate(box.x() + (box.width() - GRID * scale) / 2.0,
                      box.y() + (box.height() - GRID * scale) / 2.0)
    painter.scale(scale, scale)

    drawer = _DRAWERS[normalize_kind(kind)]
    if tile:
        _paint_tile(painter)
        painter.save()
        painter.translate(1.8, 1.8)
        painter.scale(60.4 / GRID, 60.4 / GRID)
        drawer(painter, level, color, wave, stroke)
        painter.restore()
    else:
        drawer(painter, level, color, wave, stroke)
    painter.restore()


def device_pixmap(kind: str, level: Optional[int], color: QColor | str,
                  size: int, wave: bool = False, tile: bool = False) -> QPixmap:
    """Crisp pixmap for labels, tray icons and ICO export."""
    size = max(1, int(size))
    supersample = 8 if size <= 24 else (4 if size <= 48 else 2)
    big = QPixmap(size * supersample, size * supersample)
    big.fill(Qt.GlobalColor.transparent)
    painter = QPainter(big)
    paint_device(painter, QRectF(0, 0, size * supersample,
                                 size * supersample), kind, level, color, wave,
                 tile=tile)
    painter.end()
    if supersample > 1:
        big = big.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    big.setDevicePixelRatio(1.0)
    return big


@lru_cache(maxsize=32)
def device_icon(kind: str, level: Optional[int], color: str) -> QIcon:
    icon = QIcon()
    fill = level_color(level, color).name()
    for size in (16, 20, 24, 28, 32, 40, 48, 64):
        icon.addPixmap(device_pixmap(kind, level, fill, size, tile=True))
    return icon


def clear_device_icon_cache() -> None:
    device_icon.cache_clear()


# ---------------------------------------------------------------------------
# application icon (SVG)
# ---------------------------------------------------------------------------
_app_renderer: QSvgRenderer | None = None


def _app_svg_renderer() -> QSvgRenderer | None:
    global _app_renderer
    if _app_renderer is None:
        try:
            _app_renderer = QSvgRenderer(
                QByteArray(app_icon_svg.APP_ICON_SVG.encode("utf-8")))
        except Exception:
            _app_renderer = QSvgRenderer()
    return _app_renderer if _app_renderer.isValid() else None


def _paint_app_icon_fallback(painter: QPainter, box: QRectF) -> None:
    """Minimal blue/white USB receiver used only if QtSvg is unavailable."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scale = min(box.width(), box.height()) / GRID
    painter.translate(box.x() + (box.width() - GRID * scale) / 2.0,
                      box.y() + (box.height() - GRID * scale) / 2.0)
    painter.scale(scale, scale)

    tile = QPainterPath()
    tile.addRoundedRect(QRectF(2, 2, 60, 60), 15, 15)
    gradient = QLinearGradient(2, 2, 62, 62)
    gradient.setColorAt(0.0, QColor("#5aa8ff"))
    gradient.setColorAt(0.55, QColor("#2f7df6"))
    gradient.setColorAt(1.0, QColor("#1a5fd6"))
    painter.fillPath(tile, gradient)

    white = QColor("#ffffff")
    blue = QColor("#2f7df6")
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(white)
    painter.drawRoundedRect(QRectF(25, 8, 14, 16), 3, 3)
    painter.drawRoundedRect(QRectF(22, 21, 20, 34), 6, 6)
    painter.setBrush(blue)
    painter.drawRoundedRect(QRectF(24, 30, 16, 12), 3.5, 3.5)
    font = QFont("Segoe UI")
    font.setPixelSize(6)
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(white)
    painter.drawText(QRectF(22, 30, 20, 12),
                     Qt.AlignmentFlag.AlignCenter, "2.4G")
    painter.restore()


def paint_app_icon(painter: QPainter, box: QRectF) -> None:
    renderer = _app_svg_renderer()
    if renderer is not None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, box)
        painter.restore()
        return
    _paint_app_icon_fallback(painter, box)


def app_pixmap(size: int) -> QPixmap:
    size = max(1, int(size))
    ss = 4 if size <= 192 else 2
    big = QPixmap(size * ss, size * ss)
    big.fill(Qt.GlobalColor.transparent)
    painter = QPainter(big)
    paint_app_icon(painter, QRectF(0, 0, size * ss, size * ss))
    painter.end()
    if ss > 1:
        big = big.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    big.setDevicePixelRatio(1.0)
    return big


@lru_cache(maxsize=2)
def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size))
    return icon


def color_wheel(size: int) -> QPixmap:
    px = max(8, int(size))
    pm = QPixmap(px * 4, px * 4)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(2, 2, px * 4 - 4, px * 4 - 4)
    cone = QConicalGradient(rect.center(), 0)
    for i in range(13):
        hue = i * 30
        cone.setColorAt(i / 12.0, QColor.fromHsv(hue % 360, 235, 250))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(cone))
    painter.drawEllipse(rect)
    sheen = QRadialGradient(QPointF(rect.center().x(), rect.top() + rect.height() * 0.24),
                            rect.width() * 0.55)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 120))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(sheen))
    painter.drawEllipse(rect)
    painter.end()
    pm = pm.scaled(px, px, Qt.AspectRatioMode.IgnoreAspectRatio,
                   Qt.TransformationMode.SmoothTransformation)
    pm.setDevicePixelRatio(1.0)
    return pm
