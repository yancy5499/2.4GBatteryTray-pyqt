# -*- coding: utf-8 -*-
"""Probe whether this desktop allows adding a notification-area icon.

``QSystemTrayIcon.isSystemTrayAvailable()`` can return True even when the
shell rejects ``Shell_NotifyIcon`` (for example in restricted/remote or
sandboxed sessions).  Qt does not expose that failure, so this module adds
and immediately removes one throw-away icon and returns the Win32 result.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

WM_APP = 0x8000
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_STATE = 0x00000008
NIS_HIDDEN = 0x00000001
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
IDI_APPLICATION = 32512
TRAY_CALLBACK = WM_APP + 1

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


_kernel32.GetModuleHandleW.restype = wintypes.HMODULE
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_user32.RegisterClassW.restype = wintypes.ATOM
_user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
_user32.UnregisterClassW.restype = wintypes.BOOL
_user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                   wintypes.WPARAM, wintypes.LPARAM]
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.LoadIconW.restype = wintypes.HANDLE
_user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
_shell32.Shell_NotifyIconW.restype = wintypes.BOOL
_shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                       ctypes.POINTER(NOTIFYICONDATAW)]


def probe_notification_area() -> tuple[bool, int]:
    """Return ``(allowed, win32_error)`` for a throw-away tray icon."""
    class_name = f"BatteryTrayProbe_{os.getpid()}"
    hinst = _kernel32.GetModuleHandleW(None)
    proc = WNDPROC(lambda hwnd, msg, wparam, lparam:
                   _user32.DefWindowProcW(hwnd, msg, wparam, lparam))

    wc = WNDCLASSW()
    wc.lpfnWndProc = proc
    wc.hInstance = hinst
    wc.lpszClassName = class_name
    if not _user32.RegisterClassW(ctypes.byref(wc)):
        # Cannot create our probe window: do not disable the real tray.
        return True, 0

    hwnd = _user32.CreateWindowExW(0, class_name, "probe", 0, 0, 0, 0, 0,
                                   None, None, hinst, None)
    if not hwnd:
        _user32.UnregisterClassW(class_name, hinst)
        return True, 0

    hicon = _user32.LoadIconW(None, wintypes.LPCWSTR(IDI_APPLICATION))
    if not hicon:
        _user32.DestroyWindow(hwnd)
        _user32.UnregisterClassW(class_name, hinst)
        return True, 0

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_STATE
    nid.dwState = NIS_HIDDEN
    nid.dwStateMask = NIS_HIDDEN
    nid.uCallbackMessage = TRAY_CALLBACK
    nid.hIcon = hicon
    nid.szTip = "2.4G 电量助手 · 托盘检测"

    allowed = bool(_shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
    error = 0 if allowed else ctypes.get_last_error()
    if allowed:
        _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    _user32.DestroyWindow(hwnd)
    _user32.UnregisterClassW(class_name, hinst)
    # Keep the callback alive until the window is destroyed.
    del proc
    return allowed, error
