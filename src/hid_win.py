# -*- coding: utf-8 -*-
"""Windows HID access layer built on ctypes (no third-party dependencies).

Only setupapi.dll / hid.dll / kernel32.dll are used, so any official Python
3.9+ installation can run this file without pip install.

Provided:
  * enumerate every present HID interface (VID/PID, usage page, report sizes)
  * read/write Feature and Output reports
  * asynchronous Input report reads with a timeout
  * read a value declared in the HID report descriptor
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional

if sys.platform != "win32":
    raise RuntimeError("hid_win.py only supports Windows")

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
OPEN_EXISTING = 3
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
HIDP_STATUS_SUCCESS = 0x00110000
HidP_Input = 0
HidP_Output = 1
HidP_Feature = 2

# Standard HID usages that mean "battery level".
BATTERY_USAGES = {
    (0x0006, 0x0020): "Battery Strength (Generic Device Controls)",
    (0x000D, 0x003B): "Battery Strength (Digitizer)",
    (0x0085, 0x0001): "Absolute State of Charge (Battery System)",
    (0x0085, 0x0065): "Battery Level (Battery System)",
    (0x0085, 0x0066): "Relative State of Charge (Battery System)",
}

# Top-level collections owned by Windows. They can only be opened with
# dwDesiredAccess=0; reading Feature reports still works.
SYSTEM_RESERVED_USAGES = {
    (0x0001, 0x0001), (0x0001, 0x0002),
    (0x0001, 0x0006), (0x0001, 0x0007),
    (0x000D, 0x0001), (0x000D, 0x0002),
    (0x000D, 0x0004), (0x000D, 0x0005),
}


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("DevicePath", ctypes.c_wchar * 1),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


class _RANGE(ctypes.Structure):
    _fields_ = [("UsageMin", wintypes.USHORT), ("UsageMax", wintypes.USHORT)]


class _NOT_RANGE(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("Reserved1", wintypes.USHORT),
        ("StringIndex", wintypes.USHORT),
        ("Reserved2", wintypes.USHORT),
        ("DesignatorIndex", wintypes.USHORT),
        ("Reserved3", wintypes.USHORT),
        ("DataIndex", wintypes.USHORT),
        ("Reserved4", wintypes.USHORT),
    ]


class _USAGE_UNION(ctypes.Union):
    _fields_ = [("Range", _RANGE), ("NotRange", _NOT_RANGE)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wintypes.USHORT),
        ("ReportID", ctypes.c_ubyte),
        ("IsAlias", ctypes.c_ubyte),
        ("BitField", wintypes.USHORT),
        ("LinkCollection", wintypes.USHORT),
        ("LinkUsage", wintypes.USHORT),
        ("LinkUsagePage", wintypes.USHORT),
        ("IsRange", ctypes.c_ubyte),
        ("IsStringRange", ctypes.c_ubyte),
        ("IsDesignatorRange", ctypes.c_ubyte),
        ("IsAbsolute", ctypes.c_ubyte),
        ("HasNull", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ubyte),
        ("BitSize", wintypes.USHORT),
        ("ReportCount", wintypes.USHORT),
        ("Reserved2", wintypes.USHORT * 5),
        ("UnitsExp", wintypes.ULONG),
        ("Units", wintypes.ULONG),
        ("LogicalMin", wintypes.LONG),
        ("LogicalMax", wintypes.LONG),
        ("PhysicalMin", wintypes.LONG),
        ("PhysicalMax", wintypes.LONG),
        ("u", _USAGE_UNION),
    ]


# ---------------------------------------------------------------------------
# DLL prototypes
# ---------------------------------------------------------------------------
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD,
]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
    wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.WriteFile.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
kernel32.CreateEventW.restype = ctypes.c_void_p
kernel32.CreateEventW.argtypes = [
    ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR,
]
kernel32.ResetEvent.restype = wintypes.BOOL
kernel32.ResetEvent.argtypes = [ctypes.c_void_p]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
kernel32.GetOverlappedResult.restype = wintypes.BOOL
kernel32.GetOverlappedResult.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
]
kernel32.CancelIoEx.restype = wintypes.BOOL
kernel32.CancelIoEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.restype = wintypes.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.restype = ctypes.c_long
hid.HidP_GetValueCaps.argtypes = [
    ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(wintypes.USHORT), ctypes.c_void_p,
]
hid.HidP_GetUsageValue.restype = ctypes.c_long
hid.HidP_GetUsageValue.argtypes = [
    ctypes.c_int, wintypes.USHORT, wintypes.USHORT, wintypes.USHORT,
    ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG,
]
hid.HidD_GetFeature.restype = wintypes.BOOL
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetFeature.restype = wintypes.BOOL
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetOutputReport.restype = wintypes.BOOL
hid.HidD_SetOutputReport.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG]
for _name in ("HidD_GetProductString", "HidD_GetManufacturerString",
              "HidD_GetSerialNumberString"):
    _fn = getattr(hid, _name)
    _fn.restype = wintypes.BOOL
    _fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG]

HID_GUID = GUID(
    0x4D1E55B2, 0xF16F, 0x11CF,
    (ctypes.c_ubyte * 8)(0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30),
)


def _wide_string(fn, handle, size: int = 512) -> str:
    buf = ctypes.create_string_buffer(size)
    try:
        if not fn(handle, buf, size):
            return ""
    except Exception:
        return ""
    return buf.raw.decode("utf-16-le", errors="ignore").split("\x00")[0].strip()


def _parse_vid_pid(path: str) -> tuple[int, int]:
    low = path.lower()
    vid = pid = 0
    if "vid_" in low:
        try:
            vid = int(low.split("vid_", 1)[1][:4], 16)
        except ValueError:
            pass
    if "pid_" in low:
        try:
            pid = int(low.split("pid_", 1)[1][:4], 16)
        except ValueError:
            pass
    return vid, pid


def physical_group_key(path: str) -> str:
    """Return a key shared by all HID collections of one USB device."""
    parts = path.split("#")
    if len(parts) < 2:
        return path
    keep = []
    for part in parts[1].split("&"):
        low = part.lower()
        if low.startswith("col") or low.startswith("mi_"):
            continue
        keep.append(part)
    return "&".join(keep) or parts[1]


@dataclass
class HidInterface:
    path: str
    vid: int
    pid: int
    version: int = 0
    usage_page: int = 0
    usage: int = 0
    input_len: int = 0
    output_len: int = 0
    feature_len: int = 0
    product: str = ""
    manufacturer: str = ""
    serial: str = ""
    num_feature_value_caps: int = 0
    num_input_value_caps: int = 0
    error: str = ""
    group: str = ""

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04X}:{self.pid:04X}"

    @property
    def usage_text(self) -> str:
        return f"0x{self.usage_page:04X}:0x{self.usage:04X}"

    @property
    def is_vendor_page(self) -> bool:
        return self.usage_page >= 0xFF00

    @property
    def is_system_reserved(self) -> bool:
        return (self.usage_page, self.usage) in SYSTEM_RESERVED_USAGES

    @property
    def name(self) -> str:
        if self.product:
            return self.product
        if self.manufacturer:
            return f"{self.manufacturer} HID device"
        return "HID device (no product string)"

    def summary(self) -> str:
        return (f"{self.vid_pid} usage={self.usage_text} "
                f"in/out/feature={self.input_len}/{self.output_len}/{self.feature_len}")


def enumerate_hid() -> list[HidInterface]:
    """Enumerate all present HID interfaces."""
    result: list[HidInterface] = []
    hdev = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(HID_GUID), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        raise OSError(f"SetupDiGetClassDevsW failed, err={ctypes.get_last_error()}")
    try:
        index = 0
        while True:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                    hdev, None, ctypes.byref(HID_GUID), index, ctypes.byref(iface)):
                break
            index += 1

            need = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(iface), None, 0, ctypes.byref(need), None)
            if not need.value:
                continue
            buf = ctypes.create_string_buffer(need.value)
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = (
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                    hdev, ctypes.byref(iface), buf, need.value, None, None):
                continue
            path = ctypes.cast(ctypes.addressof(buf) + 4, ctypes.c_wchar_p).value or ""
            if not path:
                continue
            result.append(_probe_interface(path))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return result


def _probe_interface(path: str) -> HidInterface:
    vid, pid = _parse_vid_pid(path)
    item = HidInterface(path=path, vid=vid, pid=pid, group=physical_group_key(path))
    handle = kernel32.CreateFileW(
        path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if not handle or handle == INVALID_HANDLE_VALUE:
        item.error = f"CreateFileW(err={ctypes.get_last_error()})"
        return item
    try:
        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
        if hid.HidD_GetAttributes(handle, ctypes.byref(attrs)):
            item.vid = attrs.VendorID
            item.pid = attrs.ProductID
            item.version = attrs.VersionNumber
        item.product = _wide_string(hid.HidD_GetProductString, handle)
        item.manufacturer = _wide_string(hid.HidD_GetManufacturerString, handle)
        item.serial = _wide_string(hid.HidD_GetSerialNumberString, handle)

        preparsed = ctypes.c_void_p()
        if hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)) and preparsed:
            try:
                caps = HIDP_CAPS()
                if hid.HidP_GetCaps(preparsed, ctypes.byref(caps)) == HIDP_STATUS_SUCCESS:
                    item.usage_page = caps.UsagePage
                    item.usage = caps.Usage
                    item.input_len = caps.InputReportByteLength
                    item.output_len = caps.OutputReportByteLength
                    item.feature_len = caps.FeatureReportByteLength
                    item.num_feature_value_caps = caps.NumberFeatureValueCaps
                    item.num_input_value_caps = caps.NumberInputValueCaps
            finally:
                hid.HidD_FreePreparsedData(preparsed)
    finally:
        kernel32.CloseHandle(handle)
    return item


class HidError(OSError):
    pass


class HidDevice:
    """An open HID interface."""

    def __init__(self, path: str, write: bool = False):
        self.path = path
        access = (GENERIC_READ | GENERIC_WRITE) if write else 0
        handle = kernel32.CreateFileW(
            path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
            OPEN_EXISTING, 0, None)
        self.write_access = bool(write)
        if (not handle or handle == INVALID_HANDLE_VALUE) and write:
            handle = kernel32.CreateFileW(
                path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                OPEN_EXISTING, 0, None)
            self.write_access = False
        if not handle or handle == INVALID_HANDLE_VALUE:
            raise HidError(f"CreateFileW failed (err={ctypes.get_last_error()})",
                           ctypes.get_last_error())
        self.handle = handle
        self._preparsed = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(self.handle, ctypes.byref(self._preparsed)):
            self._preparsed = ctypes.c_void_p()
        self._caps: Optional[HIDP_CAPS] = None
        self._read_handle: Optional[int] = None
        self._read_event: Optional[int] = None

    def close(self) -> None:
        if getattr(self, "handle", None):
            if self._read_handle:
                kernel32.CancelIoEx(self._read_handle, None)
                kernel32.CloseHandle(self._read_handle)
                self._read_handle = None
            if self._read_event:
                kernel32.CloseHandle(self._read_event)
                self._read_event = None
            if self._preparsed:
                hid.HidD_FreePreparsedData(self._preparsed)
                self._preparsed = ctypes.c_void_p()
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def caps(self) -> HIDP_CAPS:
        if self._caps is None:
            caps = HIDP_CAPS()
            if not self._preparsed:
                raise HidError("no preparsed data")
            if hid.HidP_GetCaps(self._preparsed, ctypes.byref(caps)) != HIDP_STATUS_SUCCESS:
                raise HidError("HidP_GetCaps failed")
            self._caps = caps
        return self._caps

    def value_caps(self, report_type: int = HidP_Feature) -> list[HIDP_VALUE_CAPS]:
        if not self._preparsed:
            return []
        length = wintypes.USHORT(0)
        hid.HidP_GetValueCaps(report_type, None, ctypes.byref(length), self._preparsed)
        if not length.value:
            return []
        arr = (HIDP_VALUE_CAPS * length.value)()
        status = hid.HidP_GetValueCaps(
            report_type, ctypes.byref(arr), ctypes.byref(length), self._preparsed)
        if status != HIDP_STATUS_SUCCESS:
            return []
        return [arr[i] for i in range(length.value)]

    def get_feature_report(self, report_id: int, length: Optional[int] = None) -> bytes:
        if length is None:
            length = self.caps.FeatureReportByteLength or 64
        buf = ctypes.create_string_buffer(length)
        buf[0] = bytes([report_id & 0xFF])
        if not hid.HidD_GetFeature(self.handle, buf, length):
            raise HidError(f"HidD_GetFeature(0x{report_id:02X}) failed "
                           f"(err={ctypes.get_last_error()})")
        return buf.raw

    def set_feature_report(self, data: bytes) -> None:
        if not self.write_access:
            raise HidError("handle has no write access")
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        if not hid.HidD_SetFeature(self.handle, buf, len(data)):
            raise HidError(f"HidD_SetFeature failed (err={ctypes.get_last_error()})")

    def write_output(self, data: bytes, use_hidd: bool = True) -> None:
        if not self.write_access:
            raise HidError("handle has no write access")
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        if use_hidd:
            if hid.HidD_SetOutputReport(self.handle, buf, len(data)):
                return
        written = wintypes.DWORD(0)
        if not kernel32.WriteFile(
                self.handle, buf, len(data), ctypes.byref(written), None):
            raise HidError(f"WriteFile failed (err={ctypes.get_last_error()})")

    def read_input(self, timeout_ms: int = 250,
                   length: Optional[int] = None) -> Optional[bytes]:
        if not self.caps.InputReportByteLength:
            return None
        if not self._open_reader():
            return None
        if length is None:
            length = self.caps.InputReportByteLength
        buf = ctypes.create_string_buffer(length)
        ov = OVERLAPPED()
        ov.hEvent = self._read_event
        read = wintypes.DWORD(0)
        kernel32.ResetEvent(self._read_event)
        ok = kernel32.ReadFile(
            self._read_handle, buf, length, ctypes.byref(read), ctypes.byref(ov))
        if ok:
            return buf.raw[: read.value]
        if ctypes.get_last_error() != ERROR_IO_PENDING:
            return None

        deadline = time.monotonic() + max(timeout_ms, 1) / 1000.0
        while True:
            remain = deadline - time.monotonic()
            if remain <= 0:
                self._cancel_read(ov)
                return None
            wait = int(min(remain, 0.2) * 1000) or 1
            r = kernel32.WaitForSingleObject(self._read_event, wait)
            if r == WAIT_OBJECT_0:
                done = wintypes.DWORD(0)
                if kernel32.GetOverlappedResult(
                        self._read_handle, ctypes.byref(ov), ctypes.byref(done), False):
                    return buf.raw[: done.value]
                return None

    def _cancel_read(self, ov: OVERLAPPED) -> None:
        kernel32.CancelIoEx(self._read_handle, ctypes.byref(ov))
        kernel32.WaitForSingleObject(self._read_event, 200)
        done = wintypes.DWORD(0)
        kernel32.GetOverlappedResult(
            self._read_handle, ctypes.byref(ov), ctypes.byref(done), False)

    def _open_reader(self) -> bool:
        if self._read_handle:
            return True
        handle = kernel32.CreateFileW(
            self.path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
        if not handle or handle == INVALID_HANDLE_VALUE:
            return False
        event = kernel32.CreateEventW(None, True, False, None)
        if not event:
            kernel32.CloseHandle(handle)
            return False
        self._read_handle = handle
        self._read_event = event
        return True

    def drain(self) -> None:
        if not self.caps.InputReportByteLength:
            return
        for _ in range(64):
            if self.read_input(timeout_ms=8) is None:
                return

    def usage_value(self, report_type: int, report: bytes,
                    cap: HIDP_VALUE_CAPS) -> Optional[int]:
        if not self._preparsed:
            return None
        value = wintypes.ULONG(0)
        status = hid.HidP_GetUsageValue(
            report_type, cap.UsagePage, cap.LinkCollection,
            cap.u.NotRange.Usage, ctypes.byref(value), self._preparsed,
            ctypes.create_string_buffer(bytes(report), len(report)), len(report))
        if status != HIDP_STATUS_SUCCESS:
            return None
        return int(value.value)


def battery_feature_caps(iface: HidInterface) -> list[tuple[HIDP_VALUE_CAPS, str]]:
    """Feature-report value caps that represent battery level."""
    if not iface.feature_len:
        return []
    out: list[tuple[HIDP_VALUE_CAPS, str]] = []
    try:
        with HidDevice(iface.path, write=False) as dev:
            for cap in dev.value_caps(HidP_Feature):
                key = (cap.UsagePage, cap.u.NotRange.Usage)
                if key in BATTERY_USAGES:
                    out.append((cap, BATTERY_USAGES[key]))
    except HidError:
        return []
    return out


__all__ = [
    "HidInterface", "HidDevice", "HidError", "enumerate_hid",
    "HIDP_VALUE_CAPS", "HIDP_CAPS", "HidP_Input", "HidP_Output", "HidP_Feature",
    "BATTERY_USAGES", "SYSTEM_RESERVED_USAGES", "physical_group_key",
    "battery_feature_caps",
]
