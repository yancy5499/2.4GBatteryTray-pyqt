"""Headless UI refresh and real HID enumeration soak; run from the project venv.

Does not send vendor commands or modify the user settings/history.
"""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys, gc, ctypes, tracemalloc, tempfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QWidget
import settings, history, hid_win, log
from main import _create_app
from app_window import MainWindow
from model import demo_devices

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
def handles():
    count = ctypes.c_ulong()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(count))
    return count.value

(ROOT / '.tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as directory, patch('settings.data_dir', new=lambda: str(Path(directory).resolve())):
    app = _create_app(['soak'])
    window = MainWindow(settings.Settings(), demo=True, use_tray=False)
    try:
        tracemalloc.start()
        snapshots = []
        for i in range(1200):
            devices = demo_devices() if i % 10 else []
            history.append_readings(devices)
            window._on_results(devices)
            window.history_page.reload()
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if i in (199, 699, 1199):
                gc.collect()
                snapshots.append((i+1, tracemalloc.get_traced_memory()[0], handles(), len(window.findChildren(QWidget))))
        print('UI cycles, Python bytes, handles, widgets:', snapshots)
        assert snapshots[-1][3] == snapshots[0][3]
        assert snapshots[-1][2] <= snapshots[0][2] + 5
        assert snapshots[-1][1] - snapshots[0][1] < 512 * 1024
    finally:
        window.quit_app()
        if log._logger:
            for handler in log._logger.handlers:
                handler.close()
            log._logger = None

baseline = handles()
counts = []
for i in range(100):
    interfaces = hid_win.enumerate_hid()
    if i in (0, 49, 99):
        counts.append((i+1, len(interfaces), handles()))
print('HID enumeration cycles, interfaces, handles:', counts, 'baseline:', baseline)
assert counts[-1][2] <= counts[0][2] + 2
