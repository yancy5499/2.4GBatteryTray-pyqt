# -*- coding: utf-8 -*-
r"""Battery readers for 2.4G USB receivers.

This workspace has two reversed devices.

3554:FA09 "2.4G Wireless Receiver" (Redragon K618 / Yunzii X75 Pro keyboard):

    report id 0x13, 20-byte input/output reports
    request : 13 05 00 ... checksum
    response: 13 05 01 00 0a ... checksum
    event   : 13 0a 01 00 04 05 <level> <status> ... checksum

The last byte of every packet is an 8-bit additive checksum of all preceding
bytes.  Command 0x05 makes the receiver emit a 0x0A status event; byte 6 of
that event is the battery percentage (0-100).

258A:0136 / 258A:0138 MCHOSE 2.4G mouse receiver:

    Feature Report 0x09, 520 bytes
    request : 09 13 44 01 ... 58
    push    : 09 0a 05 <level> 00 00 00 00

The 0x44/0x01 command is the same config-read command MCHOSE HUB sends in
C:\MCHOSE\Log.txt; the receiver then pushes battery byte 3 (0-100).

Readers for the devices documented by the reference project are included too:
  * ATK / VXE 373B:1216 (report id 0x08, 64-byte output report)
  * VXE / Scyrox / VGN 3554 dongles (17-byte report id 0x08)
  * DARKRIM SHADOW 3654:6901 (Jieli TLV protocol)
  * standard HID battery usages and Logitech HID++ 2.0 as fallbacks

No third-party packages are required.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import hid_win
from hid_win import HidDevice, HidError, HidInterface


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------
@dataclass
class BatteryReading:
    ok: bool
    level: Optional[int] = None
    source: str = ""
    detail: str = ""
    status: Optional[int] = None
    charging: Optional[bool] = None
    voltage_mv: Optional[int] = None
    raw: bytes = b""
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Known devices / labels
# ---------------------------------------------------------------------------
KNOWN_DEVICES = {
    (0x3554, 0xFA09): "Redragon / Yunzii 2.4G 键盘接收器（Compx）",
    (0x3554, 0xF505): "VGN / VXE 4K Dongle",
    (0x3554, 0xF58A): "VXE 1K Dongle",
    (0x3554, 0xF5F6): "Scyrox V6（有线）",
    (0x3554, 0xF5F7): "Scyrox V6（2.4G）",
    (0x373B, 0x1216): "ATK / VXE 无线鼠标",
    (0x3654, 0x6901): "DARKRIM SHADOW 耳机",
    (0x046D, 0xC52B): "Logitech Unifying Receiver",
    (0x046D, 0xC534): "Logitech Bolt Receiver",
    (0x046D, 0xC548): "Logitech USB Receiver",
    (0x258A, 0x0136): "MCHOSE G3 无线鼠标（258A:0136）",
    (0x258A, 0x0138): "MCHOSE 2.4G 无线鼠标（258A:0138）",
}

# Interfaces that are never 2.4G receivers.
IGNORED_VIDS = {0x0000, 0x045E, 0x093A, 0x8087}


@dataclass
class DeviceGroup:
    key: str
    interfaces: list[HidInterface]

    @property
    def vid(self) -> int:
        return self.interfaces[0].vid

    @property
    def pid(self) -> int:
        return self.interfaces[0].pid

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04X}:{self.pid:04X}"

    @property
    def name(self) -> str:
        known = KNOWN_DEVICES.get((self.vid, self.pid))
        if known:
            return known
        for iface in self.interfaces:
            if iface.product and "HID" not in iface.product:
                return iface.product
        return f"USB HID 设备 {self.vid_pid}"

    @property
    def product(self) -> str:
        for iface in self.interfaces:
            if iface.product:
                return iface.product
        return ""

    def find(self, usage_page: int, usage: int = 0x0002,
             min_output: int = 0) -> Optional[HidInterface]:
        for iface in self.interfaces:
            if (iface.usage_page == usage_page
                    and (usage == 0 or iface.usage == usage)
                    and iface.output_len >= min_output):
                return iface
        return None


def group_interfaces(items: list[HidInterface]) -> list[DeviceGroup]:
    groups: dict[str, DeviceGroup] = {}
    for item in items:
        groups.setdefault(item.group, DeviceGroup(item.group, [])).interfaces.append(item)
    return list(groups.values())


def is_candidate(group: DeviceGroup) -> bool:
    if (group.vid, group.pid) in KNOWN_DEVICES:
        return True
    if group.vid in IGNORED_VIDS:
        return False
    if group.vid == 0x046D:          # any Logitech device may speak HID++
        return True
    text = " ".join((i.product + " " + i.manufacturer).lower()
                    for i in group.interfaces)
    if any(word in text for word in ("2.4g", "wireless", "receiver", "dongle")):
        return True
    return any(i.is_vendor_page and (i.output_len or i.feature_len)
               for i in group.interfaces)


def discover_groups(include_all: bool = False) -> list[DeviceGroup]:
    groups = group_interfaces(hid_win.enumerate_hid())
    if include_all:
        return groups
    candidates = [g for g in groups if is_candidate(g)]
    candidates.sort(key=lambda g: (g.vid != 0x3554, g.vid_pid, g.name))
    return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scale(value: int, logical_max: int) -> int:
    if logical_max and logical_max > 100:
        if logical_max == 255 and value > 100:
            value = round(value * 100 / 255)
        else:
            value = round(value * 100 / logical_max)
    elif value > 100:
        value = round(value * 100 / 255)
    return max(0, min(100, int(value)))


def _read_until(dev: HidDevice, seconds: float) -> list[bytes]:
    out: list[bytes] = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        r = dev.read_input(timeout_ms=150)
        if r:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# 3554:FA09 Redragon / Yunzii 2.4G keyboard receiver
# ---------------------------------------------------------------------------
REDRAGON_REPORT_ID = 0x13
REDRAGON_CMD_STATUS = 0x05


def _redragon_packet(cmd: int, size: int, params: bytes = b"") -> bytes:
    body = bytearray(size)
    body[0] = REDRAGON_REPORT_ID
    body[1] = cmd
    body[2:2 + len(params)] = params
    body[-1] = sum(body[:-1]) & 0xFF
    return bytes(body)


def _valid_redragon(report: bytes) -> bool:
    return (len(report) >= 8 and report[0] == REDRAGON_REPORT_ID
            and (sum(report[:-1]) & 0xFF) == report[-1])


def read_redragon_2g(iface: HidInterface, debug: bool = False,
                     fast: bool = False) -> Optional[BatteryReading]:
    """Read the keyboard battery through the 0x13 vendor protocol."""
    if iface.output_len < 8:
        return None
    size = iface.output_len or 20
    debug_reports: list[bytes] = []
    attempts = 2 if fast else 3
    read_seconds = 0.7 if fast else 0.9

    for attempt in range(attempts):
        try:
            with HidDevice(iface.path, write=True) as dev:
                dev.drain()
                request = _redragon_packet(REDRAGON_CMD_STATUS, size)
                dev.write_output(request)
                reports = _read_until(dev, read_seconds)
                debug_reports.extend(reports)

                for report in reports:
                    if debug:
                        print("    raw <-", report.hex(" "))
                    if not _valid_redragon(report):
                        continue
                    if report[1] != 0x0A:
                        continue
                    # 13 0a 01 00 04 05 <level> <status> ...
                    if len(report) < 8 or report[4] != 0x04:
                        continue
                    level = report[6]
                    if not 0 <= level <= 100:
                        continue
                    return BatteryReading(
                        ok=True,
                        level=level,
                        status=report[7],
                        charging=None,
                        source="3554:FA09 厂商协议（cmd 0x05 -> event 0x0A）",
                        detail=(f"第 {attempt + 1} 次查询收到 0x0A 事件，"
                                f"第 6 字节为电量；状态字节=0x{report[7]:02X}"),
                        raw=report,
                        extra={"request": request.hex(" "), "reports": debug_reports},
                    )
        except HidError as e:
            return BatteryReading(
                ok=False, source="3554:FA09 厂商协议",
                detail=f"打开/读写失败：{e}（请关闭厂商驱动软件后重试）",
            )
        time.sleep(0.12)
    return BatteryReading(
        ok=False, source="3554:FA09 厂商协议",
        detail=("接收器没有回复 0x0A 电量事件。按一下键盘按键（或切换键盘电源）"
                "唤醒后再试；如果键盘已关机，也会读不到。"),
    )


# ---------------------------------------------------------------------------
# MCHOSE 258A:0136 / 258A:0138 2.4G mouse receiver
# ---------------------------------------------------------------------------
# MCHOSE HUB writes a 0x13 0x44 0x01 command through HID feature report 0x09
# (520 bytes).  The receiver then pushes an 8-byte input report:
#
#     09 0a 05 1f 00 00 00 00
#              ^^ battery = 0x1f = 31%
#
# The packet layout and the 0x44 command were confirmed from
# C:\MCHOSE\Log.txt ("Send :13 44 01 ..." / "Grab :13 44 0a ...").
MCHOSE_REPORT_ID = 0x09
MCHOSE_CMD = 0x44
MCHOSE_SUB_READ = 0x01


def _mchose_packet(size: int) -> bytes:
    body = bytearray(size)
    body[0] = MCHOSE_REPORT_ID
    payload = bytearray(20)
    payload[0] = 0x13
    payload[1] = MCHOSE_CMD
    payload[2] = MCHOSE_SUB_READ
    payload[19] = sum(payload[:19]) & 0xFF
    body[1:21] = payload
    return bytes(body)


def read_mchose_258a(iface: HidInterface, debug: bool = False,
                     fast: bool = False) -> Optional[BatteryReading]:
    """Read the wireless mouse battery through the MCHOSE 0x13 vendor protocol."""
    if iface.feature_len < 520 or iface.input_len < 4:
        return None
    size = iface.feature_len
    request = _mchose_packet(size)
    raw_reports: list[bytes] = []
    attempts = 3 if fast else 8
    read_seconds = 0.8 if fast else 1.2

    for attempt in range(attempts):
        try:
            with HidDevice(iface.path, write=True) as dev:
                dev.drain()
                dev.set_feature_report(request)
                # Reading the feature report completes the transaction on
                # this receiver; the battery status is then pushed on the
                # interrupt IN endpoint.  Without this GET, the 0x0A event
                # is often not delivered.
                time.sleep(0.05)
                try:
                    dev.get_feature_report(MCHOSE_REPORT_ID, size)
                except HidError:
                    pass
                for report in _read_until(dev, read_seconds):
                    raw_reports.append(report)
                    if debug:
                        print("    raw <-", report.hex(" "))
                    if (len(report) >= 4 and report[0] == MCHOSE_REPORT_ID
                            and report[1] == 0x0A and report[2] == 0x05):
                        level = report[3]
                        if 0 <= level <= 100:
                            return BatteryReading(
                                ok=True, level=level,
                                source="MCHOSE 258A 厂商协议"
                                       "（0x44 查询 -> 0x0A 电量事件）",
                                detail=(f"第 {attempt + 1} 次查询收到 "
                                        f"09 0A 05 {level:02X}，"
                                        f"第 3 字节为电量；"
                                        f"MCHOSE HUB 的 Log.txt 使用同一 0x44 查询"),
                                raw=report,
                                extra={"request": request.hex(" "),
                                       "reports": raw_reports},
                            )
        except HidError as e:
            return BatteryReading(
                ok=False, source="MCHOSE 258A 厂商协议",
                detail=f"打开/读写失败：{e}（请关闭 MCHOSE HUB 后重试）",
            )
        time.sleep(0.2)

    return BatteryReading(
        ok=False, source="MCHOSE 258A 厂商协议",
        detail=("接收器没有推送 0x0A 电量事件。移动一下鼠标唤醒后再试；"
                "如果鼠标已关机，也会读不到。"),
    )


# ---------------------------------------------------------------------------
# Scyrox / VXE / VGN 17-byte protocol (report id 0x08)
# ---------------------------------------------------------------------------
def _scyrox_packet(cmd: int) -> bytes:
    body = bytearray(17)
    body[0] = 0x08
    body[1] = cmd
    body[16] = (0x55 - sum(body[:16])) & 0xFF
    return bytes(body)


def _scyrox_transact(dev: HidDevice, cmd: int, seconds: float = 0.8) -> Optional[bytes]:
    dev.drain()
    dev.write_output(_scyrox_packet(cmd))
    for report in _read_until(dev, seconds):
        if (len(report) >= 17 and report[0] == 0x08 and report[1] == cmd
                and (sum(report) & 0xFF) == 0x55):
            return report
    return None


def read_scyrox_17(iface: HidInterface, debug: bool = False) -> Optional[BatteryReading]:
    if iface.output_len != 17:
        return None
    try:
        with HidDevice(iface.path, write=True) as dev:
            online = _scyrox_transact(dev, 3)
            if online is None:
                return None
            if debug:
                print("    raw online <-", online.hex(" "))
            if len(online) < 7 or online[6] != 1:
                return BatteryReading(
                    ok=False, source="VXE / Scyrox 17 字节协议",
                    detail="接收器没有报告设备在线（设备可能休眠，按一下键/动一下鼠标）",
                    raw=online,
                )
            battery = _scyrox_transact(dev, 4)
            if battery is None:
                return None
            if debug:
                print("    raw battery <-", battery.hex(" "))
            if len(battery) < 10 or not 0 <= battery[6] <= 100:
                return None
            voltage = (battery[8] << 8) | battery[9]
            return BatteryReading(
                ok=True, level=battery[6], charging=battery[7] == 1,
                voltage_mv=voltage if 2000 <= voltage <= 5000 else None,
                source="VXE / Scyrox 17 字节协议（cmd 3/4）",
                detail=f"在线回复 byte6={online[6]}；电量字节=0x{battery[6]:02X}",
                raw=battery,
            )
    except HidError as e:
        return BatteryReading(ok=False, source="VXE / Scyrox 17 字节协议",
                              detail=f"打开/读写失败：{e}")


# ---------------------------------------------------------------------------
# ATK / VXE 64-byte protocol (report id 0x08)
# ---------------------------------------------------------------------------
def read_atk_64(iface: HidInterface, debug: bool = False) -> Optional[BatteryReading]:
    if iface.output_len < 32:
        return None
    size = iface.output_len or 64
    payload = [0x7D, 0x72, 0x02, 0x00, 0x01, 0x07, 0x01]
    body = bytes([0x08] + payload + [0] * (size - 1 - len(payload)))
    last: Optional[bytes] = None
    try:
        with HidDevice(iface.path, write=True) as dev:
            for _ in range(3):
                dev.drain()
                dev.write_output(body)
                for report in _read_until(dev, 0.7):
                    last = report
                    if debug:
                        print("    raw <-", report.hex(" "))
                    if (len(report) >= 8 and report[1] == 0x72
                            and report[5] == 0x07 and 0 <= report[7] <= 100):
                        return BatteryReading(
                            ok=True, level=report[7],
                            source="ATK / VXE 64 字节协议（cmd 0x72）",
                            detail="回复 byte1=0x72、byte5=0x07，电量取 byte7",
                            raw=report,
                        )
                time.sleep(0.12)
    except HidError as e:
        return BatteryReading(ok=False, source="ATK / VXE 64 字节协议",
                              detail=f"打开/读写失败：{e}")
    if last is not None:
        return BatteryReading(
            ok=False, source="ATK / VXE 64 字节协议",
            detail="收到了回复，但没有匹配到 0x72/0x07 电量报文",
            raw=last,
        )
    return None


# ---------------------------------------------------------------------------
# DARKRIM SHADOW (Jieli) TLV protocol
# ---------------------------------------------------------------------------
def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _darkrim_frame(seq: int, payload: bytes) -> bytes:
    frame = bytearray(65)
    frame[0] = 0x00
    frame[1] = 0xFE
    frame[2] = seq & 0xFF
    frame[3] = 0x10          # dongle side
    frame[4] = 0x00
    frame[5] = 0x02
    frame[6] = 0x00
    frame[7] = 0x00
    frame[8] = len(payload) & 0xFF
    frame[9] = (len(payload) >> 8) & 0xFF
    frame[10:10 + len(payload)] = payload
    crc = crc16_ccitt(bytes(frame[1:10 + len(payload)]))
    frame[10 + len(payload)] = (crc >> 8) & 0xFF
    frame[11 + len(payload)] = crc & 0xFF
    return bytes(frame)


def _darkrim_tlvs(payload: bytes) -> list[tuple[int, bytes]]:
    out = []
    i = 0
    while i + 2 <= len(payload):
        t, ln = payload[i], payload[i + 1]
        value = payload[i + 2:i + 2 + ln]
        if len(value) < ln:
            break
        out.append((t, value))
        i += 2 + ln
    return out


def read_darkrim(iface: HidInterface, debug: bool = False) -> Optional[BatteryReading]:
    if iface.output_len != 65:
        return None
    try:
        with HidDevice(iface.path, write=True) as dev:
            dev.drain()
            dev.write_output(_darkrim_frame(0, bytes([0x01, 0x00])))
            for report in _read_until(dev, 0.8):
                if debug:
                    print("    raw <-", report.hex(" "))
                if len(report) < 12 or report[1] != 0xFE:
                    continue
                ln = report[8] | (report[9] << 8)
                if 10 + ln + 2 > len(report):
                    continue
                payload = report[10:10 + ln]
                crc = (report[10 + ln] << 8) | report[11 + ln]
                if crc != crc16_ccitt(report[1:10 + ln]):
                    continue
                for t, value in _darkrim_tlvs(payload):
                    if t == 0x01 and value and 0 <= value[0] <= 100:
                        return BatteryReading(
                            ok=True, level=value[0],
                            source="DARKRIM SHADOW TLV 协议",
                            detail="TLV 0x01 的第一个字节为电量",
                            raw=report,
                        )
    except HidError as e:
        return BatteryReading(ok=False, source="DARKRIM SHADOW TLV 协议",
                              detail=f"打开/读写失败：{e}")
    return None


# ---------------------------------------------------------------------------
# Standard HID battery usage
# ---------------------------------------------------------------------------
def read_standard_battery(interfaces: list[HidInterface],
                          debug: bool = False) -> Optional[BatteryReading]:
    for iface in interfaces:
        caps = hid_win.battery_feature_caps(iface)
        if not caps:
            continue
        try:
            with HidDevice(iface.path, write=False) as dev:
                for cap, label in caps:
                    try:
                        report = dev.get_feature_report(cap.ReportID, iface.feature_len)
                    except HidError:
                        continue
                    value = dev.usage_value(hid_win.HidP_Feature, report, cap)
                    if value is None:
                        continue
                    if debug:
                        print("    raw <-", report.hex(" "))
                    return BatteryReading(
                        ok=True, level=_scale(value, cap.LogicalMax),
                        source=f"标准 HID 电量字段（{label}）",
                        detail=(f"UsagePage=0x{cap.UsagePage:04X} "
                                f"Usage=0x{cap.u.NotRange.Usage:04X} "
                                f"ReportID=0x{cap.ReportID:02X} 原始值={value}"),
                        raw=report,
                    )
        except HidError:
            continue
    return None


# ---------------------------------------------------------------------------
# Logitech HID++ 2.0
# ---------------------------------------------------------------------------
_HIDPP_NAMES = {
    0: "discharging", 1: "charging", 2: "charging", 3: "full",
    4: "charging", 5: "invalid", 6: "temperature error", 7: "charging error",
}


def _hidpp_call(dev: HidDevice, rid: int, index: int, feature_index: int,
                function: int, params: list[int]) -> Optional[bytes]:
    length = dev.caps.OutputReportByteLength
    body = [rid, index, feature_index, ((function & 0x0F) << 4) | 0x01] + params
    body = (body + [0] * length)[:length]
    try:
        dev.drain()
        dev.write_output(bytes(body))
    except HidError:
        return None
    for report in _read_until(dev, 0.3):
        if (len(report) >= 4 and report[0] == rid and report[1] == index
                and report[2] == feature_index
                and ((report[3] >> 4) & 0x0F) == function):
            return report
    return None


def _hidpp_feature_index(dev: HidDevice, rid: int, index: int,
                         feature_id: int) -> Optional[int]:
    reply = _hidpp_call(dev, rid, index, 0x00, 0x00,
                        [feature_id >> 8, feature_id & 0xFF])
    if not reply or len(reply) < 5:
        return None
    if reply[3] & 0x80:
        return None
    for pos in (6, 4, 5):
        if len(reply) > pos and reply[pos]:
            return reply[pos]
    return None


def _hidpp_probe(dev: HidDevice, rid: int, iface: HidInterface) -> Optional[BatteryReading]:
    for index in (0xFF, 1, 2, 3, 4, 5, 6):
        fidx = _hidpp_feature_index(dev, rid, index, 0x1000)
        if fidx:
            reply = _hidpp_call(dev, rid, index, fidx, 0x00, [])
            if reply and len(reply) >= 7 and not (reply[3] & 0x80):
                level = reply[4]
                status = reply[6]
                if 0 <= level <= 100:
                    return BatteryReading(
                        ok=True, level=level, status=status,
                        charging=status in (1, 2, 4),
                        source="Logitech HID++ 2.0（0x1000）",
                        detail=f"设备索引 {index}，状态={_HIDPP_NAMES.get(status, status)}",
                        raw=reply,
                    )
        fidx = _hidpp_feature_index(dev, rid, index, 0x1004)
        if fidx:
            reply = _hidpp_call(dev, rid, index, fidx, 0x00, [])
            if reply and len(reply) >= 6 and not (reply[3] & 0x80):
                level = reply[4]
                status = reply[5]
                if 0 <= level <= 100:
                    return BatteryReading(
                        ok=True, level=level, status=status,
                        charging=status in (1, 2, 4),
                        source="Logitech HID++ 2.0（0x1004）",
                        detail=f"设备索引 {index}，状态={_HIDPP_NAMES.get(status, status)}",
                        raw=reply,
                    )
    return None


def read_logitech(iface: HidInterface, debug: bool = False) -> Optional[BatteryReading]:
    if iface.output_len < 7:
        return None
    try:
        with HidDevice(iface.path, write=True) as dev:
            for rid in (0x11, 0x10):
                if dev.caps.OutputReportByteLength < (20 if rid == 0x11 else 7):
                    continue
                result = _hidpp_probe(dev, rid, iface)
                if result:
                    if debug and result.raw:
                        print("    raw <-", result.raw.hex(" "))
                    return result
    except HidError as e:
        return BatteryReading(ok=False, source="Logitech HID++",
                              detail=f"打开/读写失败：{e}")
    return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
def read_group(group: DeviceGroup, debug: bool = False,
               fast: bool = False) -> BatteryReading:
    """Try every applicable strategy for one physical device."""
    fallback: Optional[BatteryReading] = None

    # 1) Known vendor protocols.
    if group.vid == 0x3554 and group.pid == 0xFA09:
        iface = group.find(0xFF02, 0, 16)
        if iface:
            result = read_redragon_2g(iface, debug=debug, fast=fast)
            if result and result.ok:
                return result
            fallback = result

    if group.vid == 0x258A:
        iface = next((i for i in group.interfaces
                      if i.usage_page == 0xFF02 and i.feature_len >= 520), None)
        if iface:
            result = read_mchose_258a(iface, debug=debug, fast=fast)
            if result and result.ok:
                return result
            fallback = fallback or result

    if group.vid == 0x3654:
        iface = group.find(0xFF02, 0, 65)
        if iface:
            result = read_darkrim(iface, debug=debug)
            if result and result.ok:
                return result
            fallback = fallback or result

    if group.vid == 0x373B:
        iface = group.find(0xFF05, 0, 32)
        if iface:
            result = read_atk_64(iface, debug=debug)
            if result and result.ok:
                return result
            fallback = fallback or result
        iface = group.find(0xFF02, 0, 16)
        if iface:
            result = read_scyrox_17(iface, debug=debug)
            if result and result.ok:
                return result
            fallback = fallback or result

    if group.vid == 0x3554 and group.pid != 0xFA09:
        iface = group.find(0xFF02, 0, 17)
        if iface:
            result = read_scyrox_17(iface, debug=debug)
            if result and result.ok:
                return result
            fallback = fallback or result

    if group.vid == 0x046D:
        for iface in group.interfaces:
            if iface.output_len:
                result = read_logitech(iface, debug=debug)
                if result and result.ok:
                    return result
                fallback = fallback or result

    # 2) Standard HID battery usage (works for many headsets/mice).
    result = read_standard_battery(group.interfaces, debug=debug)
    if result and result.ok:
        return result

    # 3) ATK protocol on any vendor interface as a last resort.
    if group.vid in (0x373B, 0x3554):
        for iface in group.interfaces:
            if iface.output_len >= 32 and iface.is_vendor_page:
                result = read_atk_64(iface, debug=debug)
                if result and result.ok:
                    return result

    return fallback or BatteryReading(
        ok=False, source="未匹配到协议",
        detail="设备存在，但没有识别出电量读取方式（可运行 --list 查看接口）",
    )


def read_all(include_all: bool = False, debug: bool = False,
             fast: bool = False) -> list[tuple[DeviceGroup, BatteryReading]]:
    results = []
    for group in discover_groups(include_all=include_all):
        results.append((group, read_group(group, debug=debug, fast=fast)))
    return results
