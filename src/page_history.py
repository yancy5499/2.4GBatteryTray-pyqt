# -*- coding: utf-8 -*-
"""Battery history page: a hand-drawn level-vs-time chart."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout,
                             QWidget)

import history
from theme import ACCENT, DIVIDER, FAINT, MUTED, TEXT, TEXT_SOFT, qc
from widgets import (Card, ChipButton, PageHeader, PillButton, ScrollPage,
                     label)


class BatteryChart(QWidget):
    """0-100% line chart with one line per device and gaps for missing data."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: Optional[history.HistoryData] = None
        self._empty_text = "暂无历史记录"
        self.setMinimumHeight(292)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    def set_data(self, data: history.HistoryData) -> None:
        self._data = data
        self.update()

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        data = self._data
        starts = data.starts if data else []
        left, right, top, bottom = 44.0, 16.0, 14.0, 30.0
        plot = QRectF(left, top, max(10.0, self.width() - left - right),
                      max(10.0, self.height() - top - bottom))

        painter.setFont(QFont(self.font().family(), 8))
        painter.setPen(qc(FAINT))
        for value in (0, 25, 50, 75, 100):
            y = plot.bottom() - plot.height() * value / 100.0
            painter.setPen(QPen(qc("#eaf1fa"), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(qc(FAINT))
            text_rect = QRectF(0, y - 8, left - 8, 16)
            painter.drawText(text_rect,
                             Qt.AlignmentFlag.AlignRight |
                             Qt.AlignmentFlag.AlignVCenter,
                             f"{value}%")

        if data is not None and starts:
            count = len(starts)
            every = 3 if data.bucket == "hour" else 5
            painter.setFont(QFont(self.font().family(), 8))
            for index in range(0, count, every):
                x = (plot.left() + plot.width() * index / max(1, count - 1))
                painter.setPen(QPen(qc("#dfeaf7"), 1))
                painter.drawLine(QPointF(x, plot.bottom()),
                                 QPointF(x, plot.bottom() + 4))
                painter.setPen(qc(FAINT))
                if data.bucket == "hour":
                    text = starts[index].strftime("%H:%M")
                else:
                    text = starts[index].strftime("%m-%d")
                painter.drawText(
                    QRectF(x - 26, plot.bottom() + 7, 52, 16),
                    Qt.AlignmentFlag.AlignHCenter |
                    Qt.AlignmentFlag.AlignTop, text)

        painter.setPen(QPen(qc(DIVIDER), 1.1))
        painter.drawLine(QPointF(plot.left(), plot.bottom()),
                         QPointF(plot.right(), plot.bottom()))
        painter.drawLine(QPointF(plot.left(), plot.top()),
                         QPointF(plot.left(), plot.bottom()))

        series = data.series if data else []
        if not series:
            painter.setPen(qc(MUTED))
            painter.setFont(QFont(self.font().family(), 12,
                                  QFont.Weight.Medium))
            painter.drawText(
                QRectF(plot.left(), plot.center().y() - 18, plot.width(), 24),
                Qt.AlignmentFlag.AlignHCenter, self._empty_text)
            painter.setPen(qc(FAINT))
            painter.setFont(QFont(self.font().family(), 9))
            painter.drawText(
                QRectF(plot.left(), plot.center().y() + 6, plot.width(), 20),
                Qt.AlignmentFlag.AlignHCenter,
                "搜索或监听成功后会自动写入 log/ 目录")
            return
        if not starts:
            return

        count = len(starts)
        for item in series:
            color = QColor(item.color)
            painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            previous: Optional[QPointF] = None
            for index, (_timestamp, value) in enumerate(item.points):
                if value is None:
                    continue
                x = (plot.left() + plot.width() * index /
                     max(1, count - 1))
                y = plot.bottom() - plot.height() * max(0, min(100, value)) / 100.0
                point = QPointF(x, y)
                if previous is not None:
                    painter.drawLine(previous, point)
                previous = point
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            for index, (_timestamp, value) in enumerate(item.points):
                if value is None:
                    continue
                x = (plot.left() + plot.width() * index /
                     max(1, count - 1))
                y = plot.bottom() - plot.height() * max(0, min(100, value)) / 100.0
                painter.drawEllipse(QPointF(x, y), 2.2, 2.2)


class HistoryPage(ScrollPage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._bucket = "hour"
        self._data: Optional[history.HistoryData] = None
        self._enabled: Optional[set[str]] = None
        self._filter_keys: tuple[str, ...] = ()
        self.vbox.setSpacing(14)
        self.vbox.addWidget(PageHeader(
            "电量历史",
            "根据 log/ 中每台设备独立的 CSV，查看电量随时间的变化；"
            "可切换按 1 小时或 1 天聚合。"))

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.hour_btn = PillButton("间隔按 1 小时", "soft", icon="history",
                                   height=32, font_size=11.5)
        self.day_btn = PillButton("间隔按 1 天", "ghost", icon="history",
                                  height=32, font_size=11.5)
        self.hour_btn.clicked.connect(lambda: self.set_bucket("hour"))
        self.day_btn.clicked.connect(lambda: self.set_bucket("day"))
        controls.addWidget(self.hour_btn)
        controls.addWidget(self.day_btn)
        self.range_hint = label("最近 24 小时", 11, color=MUTED)
        controls.addWidget(self.range_hint)
        controls.addStretch(1)
        self.refresh_btn = PillButton("刷新", "ghost", icon="refresh",
                                      height=32, font_size=11)
        self.refresh_btn.clicked.connect(self.reload)
        controls.addWidget(self.refresh_btn)
        self.open_btn = PillButton("打开 log 目录", "ghost", icon="folder",
                                   height=32, font_size=11)
        self.open_btn.clicked.connect(self.open_log_dir)
        controls.addWidget(self.open_btn)
        self.vbox.addLayout(controls)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.filter_label = label("显示设备", 10.5, color=MUTED)
        filter_row.addWidget(self.filter_label)
        self.filter_chips = QHBoxLayout()
        self.filter_chips.setSpacing(5)
        filter_row.addLayout(self.filter_chips)
        filter_row.addStretch(1)
        self.all_btn = PillButton("全部显示", "subtle", height=26,
                                  font_size=10.5)
        self.all_btn.clicked.connect(self.show_all)
        filter_row.addWidget(self.all_btn)
        self.vbox.addLayout(filter_row)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 12)
        card_layout.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(label("电量与时间", 14, QFont.Weight.Bold, TEXT))
        header.addStretch(1)
        self.summary = label("", 10.5, color=MUTED)
        header.addWidget(self.summary)
        card_layout.addLayout(header)

        self.legend = QHBoxLayout()
        self.legend.setSpacing(16)
        card_layout.addLayout(self.legend)
        self.chart = BatteryChart()
        card_layout.addWidget(self.chart, 1)
        self.vbox.addWidget(card, 1)

        log_path = str(history.log_dir(create=False))
        self.path_hint = label(f"记录位置：{log_path}", 10, color=FAINT,
                               wrap=True)
        self.vbox.addWidget(self.path_hint)
        self.vbox.addStretch(1)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload()

    def set_bucket(self, bucket: str) -> None:
        if bucket not in ("hour", "day"):
            return
        self._bucket = bucket
        self.hour_btn.set_variant("soft" if bucket == "hour" else "ghost")
        self.day_btn.set_variant("soft" if bucket == "day" else "ghost")
        self.range_hint.setText("最近 24 小时" if bucket == "hour"
                                else "最近一个月")
        self.reload()

    def show_all(self) -> None:
        self._enabled = None
        self.reload()

    def focus_device(self, device) -> None:
        self._enabled = {history.file_stem(device)}
        self.reload()

    def reload(self) -> None:
        self._data = history.load_history(self._bucket)
        self._rebuild_filter_chips()
        self._apply_filter()

    def _apply_filter(self) -> None:
        data = self._data
        if data is None:
            return
        if self._enabled is None:
            visible = list(data.series)
        else:
            visible = [item for item in data.series
                       if item.key in self._enabled]
        filtered = history.HistoryData(
            bucket=data.bucket,
            range_label=data.range_label,
            starts=data.starts,
            series=visible,
            truncated=data.truncated,
        )
        self.chart.set_empty_text(
            "未选择设备" if data.series and not visible else "暂无历史记录")
        self.chart.set_data(filtered)
        self._rebuild_legend(filtered)
        suffix = ""
        if data.truncated:
            suffix = f" · 仅显示前 {history.MAX_SERIES} 台"
        if visible:
            self.summary.setText(
                f"{data.range_label} · {len(visible)} 台设备 · "
                f"{filtered.total_rows} 条记录{suffix}")
        else:
            self.summary.setText(f"{data.range_label} · 暂无记录")

    def _rebuild_filter_chips(self) -> None:
        data = self._data
        series = data.series if data else []
        keys = tuple(item.key for item in series)
        if keys != self._filter_keys:
            self._filter_keys = keys
            while self.filter_chips.count():
                entry = self.filter_chips.takeAt(0)
                widget = entry.widget()
                if widget is not None:
                    widget.deleteLater()
            for item in series:
                short = item.name if len(item.name) <= 10 else item.name[:9] + "…"
                chip = ChipButton(short)
                chip.setToolTip(f"{item.name}\n{item.vid_pid}")
                checked = (self._enabled is None
                           or item.key in self._enabled)
                chip.setChecked(checked)
                chip.clicked.connect(
                    lambda state, key=item.key: self._filter_toggled(key, state))
                self.filter_chips.addWidget(chip)
        else:
            for index, item in enumerate(series):
                widget = self.filter_chips.itemAt(index)
                chip = widget.widget() if widget else None
                if isinstance(chip, ChipButton):
                    chip.setChecked(self._enabled is None
                                    or item.key in self._enabled)
        visible = bool(series)
        self.filter_label.setVisible(visible)
        self.all_btn.setVisible(visible)

    def _filter_toggled(self, key: str, checked: bool) -> None:
        data = self._data
        if data is None:
            return
        if self._enabled is None:
            self._enabled = {item.key for item in data.series}
        if checked:
            self._enabled.add(key)
        else:
            self._enabled.discard(key)
        if self._enabled == {item.key for item in data.series}:
            self._enabled = None
        self._apply_filter()

    def _rebuild_legend(self, data: history.HistoryData) -> None:
        while self.legend.count():
            item = self.legend.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for series in data.series:
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            dot = label("●", 9, color=series.color)
            row.addWidget(dot)
            name = series.name if len(series.name) <= 14 else series.name[:13] + "…"
            text = name
            if series.latest is not None:
                text += f"  {series.latest}%"
            item = label(text, 10, color=TEXT_SOFT)
            item.setToolTip(f"{series.name}\n{series.vid_pid}")
            row.addWidget(item)
            self.legend.addWidget(holder)
        self.legend.addStretch(1)

    def open_log_dir(self) -> None:
        path = history.log_dir()
        try:
            os.startfile(str(path))  # noqa: S606
        except Exception:
            pass
