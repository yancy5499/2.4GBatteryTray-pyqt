"""Run with: .venv/Scripts/python -m unittest discover -s tests -v."""
import csv
import ctypes
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import hid_win
import history
import log
from model import demo_devices


class RuntimeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = patch("settings.data_dir", return_value=self.temp.name)
        self.directory.start()

    def tearDown(self):
        if log._logger:
            for handler in log._logger.handlers:
                handler.close()
            log._logger = None
        self.directory.stop()
        self.temp.cleanup()

    def test_cancel_waits_for_completion_and_retains_request(self):
        device = object.__new__(hid_win.HidDevice)
        device._read_handle = 123
        ov = hid_win.OVERLAPPED()
        calls = []
        kernel = Mock()
        kernel.CancelIoEx.side_effect = lambda *args: calls.append("cancel")

        def completed(handle, request, transferred, wait):
            self.assertEqual(handle, 123)
            self.assertEqual(ctypes.addressof(request._obj), ctypes.addressof(ov))
            self.assertTrue(wait)  # FALSE would permit ERROR_IO_INCOMPLETE.
            calls.append("completed")
            return False  # ERROR_OPERATION_ABORTED is normal after cancellation.

        kernel.GetOverlappedResult.side_effect = completed
        with patch.object(hid_win, "kernel32", kernel):
            device._cancel_read(ov)
        self.assertEqual(calls, ["cancel", "completed"])
        kernel.WaitForSingleObject.assert_not_called()

    def test_history_migration_retention_and_restart(self):
        path = history.log_dir() / "keyboard-3554-FA09-oldserial.csv"
        now = int(datetime.now().timestamp())
        rows = [(now, "80"), (now, "80"),
                (now - 100 * 86400, "50"), (now, "invalid"), (now, "inf")]
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=history.HEADER)
            writer.writeheader()
            for epoch, level in rows:
                writer.writerow(dict(epoch=epoch, level=level,
                                     device_name="Keyboard", kind="keyboard",
                                     vid_pid="3554:FA09"))
        original = path.read_bytes()
        history.consolidate()
        history.consolidate()
        data = history.load_history()
        self.assertEqual(len(data.series), 1)
        self.assertEqual(data.series[0].key, "keyboard-3554-FA09")
        self.assertEqual(data.total_rows, 1)
        self.assertEqual(data.series[0].latest, 80)
        self.assertEqual(path.read_bytes(), original)
        # A write error must not mark a partial file as imported.
        with patch.object(history, "_epoch_of", side_effect=OSError("interrupted")):
            path.write_bytes(original + b"\n")
            history.consolidate()
        history.consolidate()
        self.assertEqual(history.load_history().total_rows, 1)

    def test_history_writes_deduplicate_and_limit_series(self):
        devices = demo_devices()
        history.append_readings(devices)
        history.append_readings(devices)
        self.assertEqual(history.load_history().total_rows, len(devices))
        with history.closing(history._connect()) as db, db:
            old = int((datetime.now() - timedelta(days=100)).timestamp())
            db.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?)",
                       ("expired", old, 10, "old", "mouse", "0000:0000", 0, "", ""))
            for index in range(12):
                db.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?)",
                           (str(index), int(datetime.now().timestamp()), 50,
                            str(index), "mouse", "0000:0000", 0, "", ""))
        history.append_readings([])
        with history.closing(history._connect()) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM readings WHERE device='expired'").fetchone()[0], 0)
        data = history.load_history("day")
        self.assertEqual(len(data.series), history.MAX_SERIES)
        self.assertEqual(data.truncated, len(devices) + 12 - history.MAX_SERIES)

    def test_log_rotation_is_bounded(self):
        log.log("initialize")
        handler = log._logger.handlers[0]
        handler.maxBytes = 1024
        # Logging normally swallows filesystem failures; fail this test on one.
        with patch.object(handler, "handleError", side_effect=AssertionError("rotation failed")):
            for _ in range(12):
                log.log("x" * 600)
        paths = list(Path(self.temp.name).glob("app.log*"))
        self.assertEqual(len(paths), 4)
        self.assertLess(sum(path.stat().st_size for path in paths), 4096)

    def test_history_reader_does_not_wait_for_import_writer(self):
        history.append_readings(demo_devices())
        with history.closing(history._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM readings")
            # WAL readers see the previous committed snapshot while migration
            # or retention is writing, rather than waiting on the GUI thread.
            self.assertEqual(history.load_history().total_rows, len(demo_devices()))
            db.rollback()


if __name__ == "__main__":
    unittest.main()
