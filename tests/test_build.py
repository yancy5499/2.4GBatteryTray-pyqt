import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build


class BuildTests(unittest.TestCase):
    def test_source_archive_excludes_runtime_data_and_build_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("src/main.py", "src/__pycache__/main.pyc", "assets/app.ico",
                         "tools/build.py", ".github/workflows/ci.yml", "tests/test_build.py",
                         "BUILD.md", "build.bat", "requirements.txt", ".gitignore",
                         "settings.json", "app.log", "log/device.csv", "log/history.sqlite3",
                         ".venv/Lib/secret.py", "release/old.zip", ".git/config"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")
            expected = {"src/main.py", "assets/app.ico", "tools/build.py",
                        ".github/workflows/ci.yml", "tests/test_build.py", "BUILD.md",
                        "build.bat", "requirements.txt", ".gitignore"}
            self.assertEqual({p.relative_to(root).as_posix() for p in build.source_files(root)}, expected)
            with patch.object(build, "ROOT", root), patch.object(build, "RELEASE", root / "release"), \
                    patch.object(build, "source_files", new=lambda: (root / p for p in sorted(expected))):
                archive = build.build_source()
                build.write_checksums()
                with zipfile.ZipFile(archive) as zipped:
                    self.assertIsNone(zipped.testzip())
                    self.assertEqual(set(zipped.namelist()),
                                     {f"{build.APP}-source/{p}" for p in expected})
                with archive.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                self.assertEqual((root / "release/SHA256SUMS.txt").read_text(encoding="utf-8"),
                                 f"{digest}  {archive.name}\n")


if __name__ == "__main__":
    unittest.main()
