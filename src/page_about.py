# -*- coding: utf-8 -*-
"""About page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from theme import (ACCENT, ACCENT_DEEP, ACCENT_TINT, CARD_BORDER, DIVIDER,
                   MUTED, TEXT, TEXT_SOFT, app_font)
from widgets import AppLogo, Card, LineIcon, PageHeader, ScrollPage, label

PROTOCOLS = [
    ("Redragon / Yunzii 2.4G 键盘接收器", "3554:FA09",
     "0x13 厂商协议，cmd 0x05 → event 0x0A"),
    ("MCHOSE 2.4G 鼠标接收器", "258A:0136 / 0138",
     "Feature Report 0x09 → 0x13 44 01"),
    ("Scyrox / VXE / VGN", "3554:F5F7 等", "17 字节 0x08 协议"),
    ("ATK / VXE 无线鼠标", "373B:1216", "64 字节 0x7D 72 协议"),
    ("DARKRIM SHADOW 耳机", "3654:6901", "Jieli TLV + CRC16"),
    ("罗技 HID++ / 标准 HID", "任意", "Feature 电量字段兜底"),
]

TIPS = [
    "设备休眠时接收器可能不回复：按一下键盘、移动鼠标后再点“搜索设备”。",
    "不需要让厂商驱动常驻；如果驱动独占了 HID，关闭后重试。",
    "托盘图标被收进溢出区（^）时，可在 Windows 任务栏设置中固定显示。",
    "程序以单实例运行，重复启动会唤起已经存在的窗口。",
]


def _bullet(text: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(9)
    dot = QLabel("•")
    dot.setFont(app_font(13, QFont.Weight.Bold))
    dot.setStyleSheet(f"color: {ACCENT}; background: transparent;")
    dot.setFixedWidth(10)
    dot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
    body = label(text, 11.5, QFont.Weight.Normal, TEXT_SOFT, wrap=True)
    layout.addWidget(body, 1)
    return row


class AboutPage(ScrollPage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.vbox.addWidget(PageHeader(
            "关于",
            "2.4G 电量助手 · 用 PyQt6 重写的托盘电量监控工具。"))

        # -- identity --------------------------------------------------
        identity = Card()
        identity_layout = QHBoxLayout(identity)
        identity_layout.setContentsMargins(24, 20, 24, 20)
        identity_layout.setSpacing(18)
        identity_layout.addWidget(AppLogo(64), 0,
                                  Qt.AlignmentFlag.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(label("2.4G 电量助手", 22, QFont.Weight.Bold, TEXT))
        badge = QLabel("v2.0.0 · PyQt6")
        badge.setFont(app_font(10.5, QFont.Weight.Medium))
        badge.setStyleSheet(
            f"color: {ACCENT_DEEP}; background: {ACCENT_TINT};"
            f"border: 1px solid {CARD_BORDER}; border-radius: 9px;"
            "padding: 3px 9px;")
        title_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        texts.addLayout(title_row)
        texts.addWidget(label("2.4G Battery Tray · 键盘 / 鼠标 / 耳机 / 手柄电量监控",
                              11.5, QFont.Weight.Normal, MUTED))
        texts.addWidget(label(
            "读取 USB 接收器的 HID 电量，为每台设备绘制一个托盘图标；"
            "关闭窗口后继续在后台刷新。", 11.5, QFont.Weight.Normal,
            TEXT_SOFT, wrap=True))
        identity_layout.addLayout(texts, 1)
        self.vbox.addWidget(identity)

        # -- two columns ----------------------------------------------
        columns = QHBoxLayout()
        columns.setSpacing(16)
        features = Card()
        features_layout = QVBoxLayout(features)
        features_layout.setContentsMargins(20, 16, 20, 16)
        features_layout.setSpacing(9)
        features_layout.addWidget(label("功能特性", 13.5, QFont.Weight.Bold,
                                        TEXT))
        for text in (
                "多设备卡片：键盘、鼠标、耳机与手柄同时显示",
                "图2 风格托盘图标：设备轮廓 + 电量填充，三档提醒色",
                "耳机头梁镂空，填充按整个耳机高度计算",
                "单次扫描 10–60 秒可调；自动扫描 3 分钟–3 小时",
                "电量历史：每台设备唯一 CSV，可逐台筛选曲线",
                "设备卡片 ... 可直接跳转到该设备的电量记录",
                "托盘菜单：打开主界面、立即刷新、开机自启、退出",
                "关闭到托盘、开机自启、单实例运行"):
            features_layout.addWidget(_bullet(text))
        features_layout.addStretch(1)
        columns.addWidget(features, 1)

        tips = Card()
        tips_layout = QVBoxLayout(tips)
        tips_layout.setContentsMargins(20, 16, 20, 16)
        tips_layout.setSpacing(9)
        tips_layout.addWidget(label("使用提示", 13.5, QFont.Weight.Bold, TEXT))
        for text in TIPS:
            tips_layout.addWidget(_bullet(text))
        tips_layout.addStretch(1)
        columns.addWidget(tips, 1)
        self.vbox.addLayout(columns)

        # -- protocols -------------------------------------------------
        protocols_card = Card()
        protocols_layout = QVBoxLayout(protocols_card)
        protocols_layout.setContentsMargins(20, 16, 20, 16)
        protocols_layout.setSpacing(6)
        protocols_layout.addWidget(label("已验证设备与协议", 13.5,
                                         QFont.Weight.Bold, TEXT))
        protocols_layout.addWidget(label(
            "协议层直接通过 HID 读取，不依赖厂商驱动或后台服务。",
            10.5, QFont.Weight.Normal, MUTED))
        protocols_layout.addSpacing(4)
        for index, (name, vid_pid, method) in enumerate(PROTOCOLS):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 5, 0, 5)
            row_layout.setSpacing(12)
            row_layout.addWidget(label(name, 11.5, QFont.Weight.Medium,
                                       TEXT), 2)
            vid = label(vid_pid, 10.5, QFont.Weight.Normal, TEXT_SOFT)
            vid.setMinimumWidth(128)
            row_layout.addWidget(vid, 1)
            row_layout.addWidget(label(method, 10.5, QFont.Weight.Normal,
                                       MUTED, wrap=True), 3)
            protocols_layout.addWidget(row)
            if index < len(PROTOCOLS) - 1:
                line = QWidget()
                line.setFixedHeight(1)
                line.setStyleSheet(f"background: {DIVIDER}; border: none;")
                protocols_layout.addWidget(line)
        self.vbox.addWidget(protocols_card)

        # -- links -----------------------------------------------------
        links_card = Card()
        links_layout = QVBoxLayout(links_card)
        links_layout.setContentsMargins(20, 16, 20, 16)
        links_layout.setSpacing(8)
        links_layout.addWidget(label("参考与致谢", 13.5, QFont.Weight.Bold,
                                     TEXT))
        links = [
            ("原 CLI 项目 / 协议来源",
             "https://github.com/yszyszysz233/2.4G-battery-viewer"),
            ("MCHOSE G98 V2 的 Feature Report 0x09 实现",
             "https://github.com/DX-Cloud/MchoseG98V2AutoLight"),
            ("MCHOSE K7 Ultra 公开协议整理",
             "https://gitlab.com/unk9201422/Mchose/-/wikis/Protocol-Specification"),
        ]
        for title, url in links:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 1, 0, 1)
            row_layout.setSpacing(9)
            row_layout.addWidget(LineIcon("link", 16, ACCENT), 0,
                                 Qt.AlignmentFlag.AlignVCenter)
            html = (f'<a href="{url}" style="color:{ACCENT_DEEP};'
                    f'text-decoration:none;">{title}</a>'
                    f'<span style="color:{MUTED};"> · {url}</span>')
            link = QLabel(html)
            link.setOpenExternalLinks(True)
            link.setFont(app_font(11.5))
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setWordWrap(True)
            link.setStyleSheet("background: transparent;")
            row_layout.addWidget(link, 1)
            links_layout.addWidget(row)
        self.vbox.addWidget(links_card)

        footer = label("MIT License · 原始 tkinter 版本重写为 PyQt6，"
                       "托盘图标采用“设备轮廓 + 电量填充”方案。",
                       10, QFont.Weight.Normal, MUTED)
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.vbox.addWidget(footer)
        self.vbox.addStretch(1)
