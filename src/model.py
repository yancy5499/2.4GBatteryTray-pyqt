# -*- coding: utf-8 -*-
"""UI-facing device model shared by the pages, the tray and the icon sheet."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Optional

KIND_LABELS = {
    "mouse": "鼠标",
    "keyboard": "键盘",
    "headset": "头戴式耳机",
    "gamepad": "手柄",
    "receiver": "2.4G 设备",
}

KIND_ORDER = ("mouse", "keyboard", "headset", "gamepad", "receiver")

KIND_META = {
    "mouse": ("鼠标", "简洁现代，清晰易识别"),
    "keyboard": ("键盘", "保留键盘形态，简洁直观"),
    "headset": ("头戴式耳机", "保留耳机外形，简洁有辨识度"),
    "gamepad": ("手柄", "经典轮廓，清晰易识别"),
    "receiver": ("2.4G 接收器", "通用轮廓，适配未知设备"),
}


def kind_of(name: str, product: str = "", vid: int = 0, pid: int = 0) -> str:
    text = f"{name} {product}".lower()
    if any(word in text for word in
           ("耳机", "耳麦", "headset", "headphone", "earphone", "audio",
            "speaker")):
        return "headset"
    if any(word in text for word in
           ("手柄", "gamepad", "controller", "joystick")):
        return "gamepad"
    if vid == 0x258A or any(word in text for word in ("mouse", "鼠标", "mice")):
        return "mouse"
    if vid == 0x3554 or any(word in text for word in ("keyboard", "键盘")):
        return "keyboard"
    return "receiver"


@dataclass
class DeviceView:
    """One card / tray icon worth of data."""

    key: str
    name: str
    vid_pid: str
    kind: str
    reading: Any
    index: int = 0
    stable_key: str = ""
    serial: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def level(self) -> Optional[int]:
        if self.reading is not None and getattr(self.reading, "ok", False):
            level = getattr(self.reading, "level", None)
            if isinstance(level, int) and 0 <= level <= 100:
                return level
        return None

    @property
    def connected(self) -> bool:
        return self.level is not None

    @property
    def charging(self) -> bool:
        return bool(getattr(self.reading, "charging", False))

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, "设备")

    @property
    def percent_text(self) -> str:
        level = self.level
        return f"{level}%" if level is not None else "--"

    @property
    def status_text(self) -> str:
        if self.level is None:
            return "未读取到"
        if self.charging:
            return "充电中"
        if self.level < 20:
            return "电量不足"
        if self.level < 50:
            return "电量偏低"
        return "已连接"

    @property
    def status_tone(self) -> str:
        if self.level is None:
            return "muted"
        if self.charging:
            return "warn"
        if self.level < 20:
            return "error"
        if self.level < 50:
            return "warn"
        return "ok"

    @property
    def detail_text(self) -> str:
        if self.reading is None:
            return ""
        if getattr(self.reading, "ok", False):
            return (getattr(self.reading, "detail", "")
                    or getattr(self.reading, "source", "") or "已读取")
        return (getattr(self.reading, "detail", "")
                or getattr(self.reading, "source", "") or "未读取到电量")

    @property
    def tooltip(self) -> str:
        parts = [f"{self.kind_label} {self.percent_text}", self.name,
                 self.vid_pid]
        if self.detail_text:
            parts.append(self.detail_text)
        return "\n".join(parts)

    def best_reading(self) -> str:
        source = getattr(self.reading, "source", "") if self.reading else ""
        return source or "—"


def view_from_group(group: Any, reading: Any, index: int = 0) -> DeviceView:
    kind = kind_of(group.name, group.product, group.vid, group.pid)
    serial = next((str(iface.serial).strip()
                   for iface in getattr(group, "interfaces", ())
                   if getattr(iface, "serial", "")), "")
    return DeviceView(
        key=f"{kind}_{index}_{group.vid_pid}",
        name=group.name,
        vid_pid=group.vid_pid,
        kind=kind,
        reading=reading,
        index=index,
        stable_key=(getattr(group, "key", "")
                    or f"{group.vid_pid}_{kind}"),
        serial=serial,
    )


def demo_devices() -> list[DeviceView]:
    """Sample devices used by ``--demo`` for previewing the UI."""
    samples = [
        ("mouse", "MCHOSE 2.4G 无线鼠标", "258A:0138", 84, "MCHOSE 258A 厂商协议"),
        ("keyboard", "Redragon / Yunzii 2.4G 键盘接收器", "3554:FA09", 57,
         "3554:FA09 厂商协议（cmd 0x05 → event 0x0A）"),
        ("headset", "DARKRIM SHADOW 头戴式耳机", "3654:6901", 41,
         "DARKRIM SHADOW TLV 协议"),
        ("gamepad", "Xbox 无线手柄", "045E:0B13", 18,
         "标准 HID 电量字段"),
    ]
    devices: list[DeviceView] = []
    for index, (kind, name, vid_pid, level, source) in enumerate(samples):
        reading = SimpleNamespace(
            ok=True, level=level, source=source,
            detail=f"{source} · 示例数据", status=None, charging=False,
            voltage_mv=None, raw=b"", extra={},
        )
        devices.append(DeviceView(
            key=f"demo_{kind}_{index}", name=name, vid_pid=vid_pid,
            kind=kind, reading=reading, index=index,
            stable_key=f"demo_{kind}_{index}",
        ))
    return devices


def sample_kinds() -> list[tuple[str, int]]:
    """Four representative kinds/levels used to preview an icon colour."""
    return [("mouse", 84), ("keyboard", 57), ("headset", 41), ("gamepad", 12)]
