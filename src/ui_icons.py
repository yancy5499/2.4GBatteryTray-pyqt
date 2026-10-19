# -*- coding: utf-8 -*-
"""Thin line icons drawn with QPainter on a 24x24 design grid."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPen,
                         QPixmap)

from theme import qc

GRID = 24.0

NAMES = {
    "home", "gear", "monitor", "info", "palette", "refresh", "chevron-down",
    "chevron-up", "check", "more", "close", "minimize", "maximize", "restore",
    "bolt", "link", "usb", "dot", "wave", "battery", "startup", "copy",
    "pin", "sun", "plug", "search", "history", "folder",
}


def _pen(color: QColor, width: float = 2.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _gear(painter: QPainter, color: QColor) -> None:
    center = QPointF(12, 12)
    painter.setPen(_pen(color, 3.0))
    for i in range(8):
        angle = math.radians(i * 45 + 22.5)
        inner = QPointF(center.x() + math.cos(angle) * 6.2,
                        center.y() - math.sin(angle) * 6.2)
        outer = QPointF(center.x() + math.cos(angle) * 8.9,
                        center.y() - math.sin(angle) * 8.9)
        painter.drawLine(inner, outer)
    painter.setPen(_pen(color, 2.3))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center, 6.2, 6.2)
    painter.drawEllipse(center, 2.3, 2.3)


def _palette(painter: QPainter, color: QColor) -> None:
    path = QPainterPath()
    path.moveTo(12.0, 3.4)
    path.cubicTo(7.1, 3.4, 3.4, 7.0, 3.4, 11.8)
    path.cubicTo(3.4, 16.6, 7.1, 20.4, 12.0, 20.4)
    path.cubicTo(13.6, 20.4, 14.7, 19.6, 14.7, 18.3)
    path.cubicTo(14.7, 17.2, 13.7, 16.5, 13.7, 15.3)
    path.cubicTo(13.7, 14.1, 14.7, 13.3, 15.9, 13.3)
    path.lineTo(17.9, 13.3)
    path.cubicTo(19.6, 13.3, 20.6, 12.4, 20.6, 10.9)
    path.cubicTo(20.6, 6.3, 16.9, 3.4, 12.0, 3.4)
    path.closeSubpath()
    painter.setPen(_pen(color, 1.9))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    for x, y, r in ((7.6, 7.6, 1.15), (10.4, 6.2, 1.1), (13.2, 6.9, 1.1),
                    (15.9, 9.2, 1.05), (7.2, 11.6, 1.1), (6.9, 15.0, 1.0)):
        painter.drawEllipse(QPointF(x, y), r, r)


def _refresh(painter: QPainter, color: QColor) -> None:
    rect = QRectF(4.4, 4.4, 15.2, 15.2)
    painter.setPen(_pen(color, 2.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.arcMoveTo(rect, 65)
    path.arcTo(rect, 65, 290)
    painter.drawPath(path)
    angle = math.radians(65)
    tip = QPointF(12 + 7.6 * math.cos(angle), 12 - 7.6 * math.sin(angle))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    arrow = QPainterPath()
    arrow.moveTo(tip.x() + 1.9, tip.y() + 0.1)
    arrow.lineTo(tip.x() - 1.9, tip.y() - 2.4)
    arrow.lineTo(tip.x() - 2.1, tip.y() + 2.2)
    arrow.closeSubpath()
    painter.drawPath(arrow)


def draw_ui_icon(painter: QPainter, name: str, rect: QRectF,
                 color: QColor | str, width: float | None = None) -> None:
    """Draw ``name`` fitted into ``rect`` (square)."""
    color = qc(color) if isinstance(color, str) else color
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scale = min(rect.width(), rect.height()) / GRID
    painter.translate(rect.x() + (rect.width() - GRID * scale) / 2.0,
                      rect.y() + (rect.height() - GRID * scale) / 2.0)
    painter.scale(scale, scale)
    w = width if width is not None else 2.0

    if name == "home":
        pen = _pen(color, w)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        roof = QPainterPath()
        roof.moveTo(3.8, 10.4)
        roof.lineTo(10.9, 4.0)
        roof.quadTo(12.0, 3.1, 13.1, 4.0)
        roof.lineTo(20.2, 10.4)
        painter.drawPath(roof)
        walls = QPainterPath()
        walls.moveTo(5.6, 9.2)
        walls.lineTo(5.6, 18.6)
        walls.quadTo(5.6, 20.3, 7.3, 20.3)
        walls.lineTo(16.7, 20.3)
        walls.quadTo(18.4, 20.3, 18.4, 18.6)
        walls.lineTo(18.4, 9.2)
        painter.drawPath(walls)
        door = QPainterPath()
        door.moveTo(9.7, 20.3)
        door.lineTo(9.7, 15.3)
        door.quadTo(9.7, 14.2, 10.8, 14.2)
        door.lineTo(13.2, 14.2)
        door.quadTo(14.3, 14.2, 14.3, 15.3)
        door.lineTo(14.3, 20.3)
        painter.drawPath(door)
    elif name == "gear":
        _gear(painter, color)
    elif name == "monitor":
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(2.9, 3.9, 18.2, 12.4), 2.4, 2.4)
        painter.drawLine(QPointF(12, 16.3), QPointF(12, 19.3))
        painter.drawLine(QPointF(8.3, 20.2), QPointF(15.7, 20.2))
    elif name == "info":
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(12, 12), 8.9, 8.9)
        painter.setPen(_pen(color, w + 0.2))
        painter.drawLine(QPointF(12, 11.1), QPointF(12, 16.7))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(12, 7.8), 1.15, 1.15)
    elif name == "palette":
        _palette(painter, color)
    elif name == "refresh":
        _refresh(painter, color)
    elif name in ("chevron-down", "chevron-up"):
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        if name == "chevron-down":
            path.moveTo(6.5, 9.3)
            path.lineTo(12.0, 14.7)
            path.lineTo(17.5, 9.3)
        else:
            path.moveTo(6.5, 14.7)
            path.lineTo(12.0, 9.3)
            path.lineTo(17.5, 14.7)
        painter.drawPath(path)
    elif name == "check":
        painter.setPen(_pen(color, w + 0.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(5.2, 12.4)
        path.lineTo(9.9, 17.1)
        path.lineTo(18.8, 7.2)
        painter.drawPath(path)
    elif name == "more":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        for x in (5.9, 12.0, 18.1):
            painter.drawEllipse(QPointF(x, 12.0), 1.35, 1.35)
    elif name == "close":
        painter.setPen(_pen(color, w))
        painter.drawLine(QPointF(6.4, 6.4), QPointF(17.6, 17.6))
        painter.drawLine(QPointF(17.6, 6.4), QPointF(6.4, 17.6))
    elif name == "minimize":
        painter.setPen(_pen(color, max(w - 0.2, 1.2)))
        painter.drawLine(QPointF(5.8, 12.0), QPointF(18.2, 12.0))
    elif name == "maximize":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(5.4, 5.4, 13.2, 13.2), 1.4, 1.4)
    elif name == "restore":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(4.6, 7.3, 11.3, 11.3), 1.3, 1.3)
        back = QPainterPath()
        back.moveTo(7.7, 7.1)
        back.lineTo(7.7, 5.3)
        back.quadTo(7.7, 4.5, 8.5, 4.5)
        back.lineTo(18.6, 4.5)
        back.quadTo(19.4, 4.5, 19.4, 5.3)
        back.lineTo(19.4, 15.4)
        back.quadTo(19.4, 16.2, 18.6, 16.2)
        back.lineTo(16.0, 16.2)
        painter.drawPath(back)
    elif name == "bolt":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        path = QPainterPath()
        path.moveTo(13.6, 2.4)
        path.lineTo(6.2, 13.6)
        path.lineTo(11.3, 13.6)
        path.lineTo(10.4, 21.6)
        path.lineTo(17.8, 10.4)
        path.lineTo(12.7, 10.4)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "link":
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(9.8, 8.4)
        path.lineTo(8.4, 8.4)
        path.cubicTo(5.9, 8.4, 4.0, 10.3, 4.0, 12.7)
        path.cubicTo(4.0, 15.1, 5.9, 16.9, 8.3, 16.9)
        path.lineTo(9.6, 16.9)
        path.moveTo(14.2, 8.4)
        path.lineTo(15.7, 8.4)
        path.cubicTo(18.1, 8.4, 20.0, 10.3, 20.0, 12.7)
        path.cubicTo(20.0, 15.1, 18.1, 16.9, 15.6, 16.9)
        path.lineTo(14.4, 16.9)
        path.moveTo(8.2, 12.7)
        path.lineTo(15.8, 12.7)
        painter.drawPath(path)
    elif name == "usb":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(4.5, 3.5, 15.0, 17.0), 3.0, 3.0)
        painter.drawLine(QPointF(12, 7.0), QPointF(12, 15.0))
        painter.drawLine(QPointF(8.5, 11.0), QPointF(12, 7.0))
        painter.drawLine(QPointF(15.5, 11.0), QPointF(12, 7.0))
    elif name == "battery":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(2.8, 7.4, 16.6, 9.2), 2.2, 2.2)
        painter.drawLine(QPointF(21.0, 10.2), QPointF(21.0, 13.8))
    elif name == "startup":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(3.4, 3.4, 17.2, 17.2))
        painter.drawLine(QPointF(12, 7.4), QPointF(12, 12.0))
        painter.drawLine(QPointF(12, 12.0), QPointF(15.4, 13.8))
    elif name == "copy":
        painter.setPen(_pen(color, w - 0.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(8.2, 8.2, 11.4, 11.4), 2.0, 2.0)
        path = QPainterPath()
        path.moveTo(15.8, 8.0)
        path.lineTo(15.8, 6.4)
        path.quadTo(15.8, 4.4, 13.8, 4.4)
        path.lineTo(6.4, 4.4)
        path.quadTo(4.4, 4.4, 4.4, 6.4)
        path.lineTo(4.4, 13.8)
        path.quadTo(4.4, 15.8, 6.4, 15.8)
        path.lineTo(8.0, 15.8)
        painter.drawPath(path)
    elif name == "search":
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(4.2, 4.2, 11.4, 11.4))
        painter.drawLine(QPointF(14.2, 14.2), QPointF(20.2, 20.2))
    elif name == "history":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(3.6, 4.2), QPointF(3.6, 20.4))
        painter.drawLine(QPointF(3.6, 20.4), QPointF(20.4, 20.4))
        path = QPainterPath()
        path.moveTo(6.8, 15.8)
        path.lineTo(10.6, 11.6)
        path.lineTo(13.8, 14.4)
        path.lineTo(19.8, 6.6)
        painter.drawPath(path)
    elif name == "folder":
        painter.setPen(_pen(color, w - 0.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(3.2, 7.4)
        path.lineTo(9.0, 7.4)
        path.lineTo(11.0, 9.6)
        path.lineTo(20.8, 9.6)
        path.lineTo(20.8, 19.2)
        path.lineTo(3.2, 19.2)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "dot":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(12, 12), 4.0, 4.0)
    elif name == "wave":
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for r in (3.2, 6.4, 9.6):
            path = QPainterPath()
            path.arcMoveTo(QRectF(12 - r, 12 - r, r * 2, r * 2), 55)
            path.arcTo(QRectF(12 - r, 12 - r, r * 2, r * 2), 55, 70)
            painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(12, 12), 1.4, 1.4)
    else:
        painter.setPen(_pen(color, w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    painter.restore()


def ui_pixmap(name: str, size: int, color: QColor | str,
              dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(max(1, int(round(size * dpr))),
                 max(1, int(round(size * dpr))))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    draw_ui_icon(painter, name, QRectF(0, 0, size * dpr, size * dpr), color)
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm
