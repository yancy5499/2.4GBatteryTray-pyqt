# -*- coding: utf-8 -*-
"""Generate assets/app.ico, app.png and the tray-icon design sheet."""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PyQt6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import icons  # noqa: E402
import ui_icons  # noqa: E402
from app_icon_svg import APP_ICON_SVG  # noqa: E402
from model import KIND_META  # noqa: E402
from theme import ACCENT, app_font  # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)

FILL = "#2f7df6"
TEXT = "#17243a"
MUTED = "#7d8fa5"
BORDER = "#e6edf7"


def font(px: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return app_font(int(px), weight)


def text(painter: QPainter, rect: QRectF, value: str, px: float,
         color: str = TEXT, weight: QFont.Weight = QFont.Weight.Normal,
         align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) -> None:
    painter.setFont(font(px, weight))
    painter.setPen(QColor(color))
    painter.drawText(rect, align, value)


def rounded_card(painter: QPainter, rect: QRectF, radius: float = 18,
                 color: str = "#ffffff", border: str = BORDER) -> None:
    painter.setPen(QPen(QColor(border), 1))
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


def draw_kind_card(painter: QPainter, rect: QRectF, kind: str) -> None:
    rounded_card(painter, rect)
    title, subtitle = KIND_META[kind]
    x = rect.x() + 28
    text(painter, QRectF(x, rect.y() + 22, 300, 32), title, 23,
         weight=QFont.Weight.Bold)
    text(painter, QRectF(x, rect.y() + 56, 420, 22), subtitle, 12.5, MUTED)

    top = rect.y() + 92
    for index, level in enumerate((100, 50, 20)):
        column = QRectF(x + index * 166, top, 150, 180)
        fill = icons.level_color(level, FILL)
        icons.paint_device(painter, QRectF(column.x() + 15, column.y(), 120, 120),
                           kind, level, fill)
        text(painter, QRectF(column.x(), column.y() + 128, 150, 26),
             f"{level}%", 13, TEXT, QFont.Weight.Medium,
             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    line_y = top + 166
    painter.setPen(QPen(QColor("#eef2f8"), 1))
    painter.drawLine(QPointF(rect.x() + 24, line_y),
                     QPointF(rect.right() - 24, line_y))

    text(painter, QRectF(x, line_y + 10, 320, 24),
         "托盘尺寸预览（16–24px，圆角方块）", 11.5, MUTED)
    for index, size in enumerate((24, 20, 16)):
        px = rect.right() - 150 + index * 46
        icons.paint_device(painter, QRectF(px, line_y + 14, size, size), kind,
                           50, icons.level_color(50, FILL), tile=True)
        text(painter, QRectF(px - 8, line_y + 42, size + 16, 18),
             f"{size}px", 9, MUTED,
             align=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)


def make_sheet(path: str) -> None:
    width, height = 1448, 1060
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#f7f9fd"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    text(painter, QRectF(56, 40, 780, 52), "托盘图标设计方案", 38, TEXT,
         QFont.Weight.Bold)
    text(painter, QRectF(58, 96, 900, 28),
         "高于 50% 使用主色，低于 50% 变黄，低于 20% 变红；"
         "保留设备原有形态，符合 WinUI 3 风格。",
         15, MUTED)

    badge = QRectF(width - 280, 46, 224, 62)
    text(painter, QRectF(badge.x(), badge.y(), badge.width(), 26),
         "设备电量托盘图标", 13, TEXT, QFont.Weight.Medium,
         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    text(painter, QRectF(badge.x(), badge.y() + 24, badge.width(), 20),
         "DESIGN CONCEPT", 10, MUTED,
         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    painter.setPen(QPen(QColor(ACCENT), 3))
    painter.drawLine(QPointF(badge.right() - 4, badge.bottom() + 2),
                     QPointF(badge.right() - 60, badge.bottom() + 2))

    card_w, card_h = 652, 366
    positions = [(56, 150), (740, 150), (56, 536), (740, 536)]
    for (x, y), kind in zip(positions, ("mouse", "keyboard", "headset", "gamepad")):
        draw_kind_card(painter, QRectF(x, y, card_w, card_h), kind)

    footer_y = 938
    painter.setPen(QPen(QColor("#e6edf7"), 1))
    painter.drawLine(QPointF(56, footer_y), QPointF(width - 56, footer_y))
    features = [
        ("monitor", "WinUI 3 风格", "现代、系统化的视觉语言"),
        ("palette", "统一的设计语言", "一致的线宽、圆角与填充"),
        ("maximize", "小尺寸高可读", "16–24px 托盘场景优化"),
        ("check", "保持设备特征", "不牺牲设备原有形态"),
    ]
    for index, (icon, title, subtitle) in enumerate(features):
        x = 56 + index * 346
        ui_icons.draw_ui_icon(painter, icon, QRectF(x, footer_y + 24, 22, 22),
                              ACCENT, 2.0)
        text(painter, QRectF(x + 32, footer_y + 21, 260, 28), title, 14.5,
             TEXT, QFont.Weight.DemiBold)
        text(painter, QRectF(x + 32, footer_y + 50, 300, 22), subtitle, 11.5,
             MUTED)
    painter.end()
    image.save(path)


def make_app_assets() -> None:
    with open(os.path.join(ASSETS, "app-icon.svg"), "w", encoding="utf-8") as fh:
        fh.write(APP_ICON_SVG)
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icons.app_pixmap(size).save(
            os.path.join(tempfile.gettempdir(), f"batterytray_{size}.png"))
    icons.app_pixmap(256).save(os.path.join(ASSETS, "app.png"))
    try:
        from PIL import Image
        base = Image.open(os.path.join(tempfile.gettempdir(),
                                       "batterytray_256.png")).convert("RGBA")
        base.save(os.path.join(ASSETS, "app.ico"),
                  sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                         (48, 48), (64, 64), (128, 128), (256, 256)])
        print("wrote app.ico with Pillow")
    except Exception as exc:  # pragma: no cover - fallback only
        print("Pillow unavailable, using Qt ICO writer:", exc)
        image = QImage(os.path.join(ASSETS, "app.png"))
        image.save(os.path.join(ASSETS, "app.ico"), "ICO")


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841  (needed for fonts/pixmaps)
    make_app_assets()
    make_sheet(os.path.join(ASSETS, "tray-preview.png"))
    print("assets written to", ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
