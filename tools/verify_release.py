"""Validate both release archives, checksums, and the extracted Windows EXE."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from build import APP, RELEASE


def main():
    checksums = dict(line.split("  ", 1)[::-1] for line in
                     (RELEASE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines())
    for suffix in ("win64", "source"):
        name = f"{APP}-{suffix}.zip"
        path = RELEASE / name
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == checksums[name], name
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None, name
            names = set(archive.namelist())
            if suffix == "source":
                prefix = f"{APP}-source/"
                for required in ("build.bat", "BUILD.md", "tools/build.py", "src/main.py",
                                 "2.4GBatteryTray.spec", "requirements.txt", ".github/workflows/ci.yml"):
                    assert prefix + required in names, required
                for entry in names:
                    parts = Path(entry).parts
                    assert not {".venv", ".git", "release", "build", "log", "__pycache__"}.intersection(parts), entry
                    assert Path(entry).name not in {"settings.json", "app.log", "show.request"}, entry
            else:
                assert f"{APP}/{APP}.exe" in names
                assert any(entry.startswith(f"{APP}/_internal/") for entry in names)
                assert f"{APP}/README.txt" in names
                with tempfile.TemporaryDirectory() as directory:
                    archive.extractall(directory)
                    folder = Path(directory) / APP
                    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
                    subprocess.run([str(folder / f"{APP}.exe"), "--tray-selftest"],
                                   cwd=folder, env=env, check=True, timeout=30)
        print(f"Verified: {name}")


if __name__ == "__main__":
    main()
