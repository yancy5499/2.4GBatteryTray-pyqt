"""Shared local/CI packaging entry point. Requires Python 3.12 on Windows for EXE."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
APP = "2.4GBatteryTray"
SOURCE_FILES = (
    "README.md", "BUILD.md", "LICENSE", "requirements.txt", "build.bat",
    "2.4GBatteryTray.spec", "release-readme.txt", ".gitignore", ".gitattributes",
)
SOURCE_DIRS = ("src", "assets", "tools", "tests", ".github")


def source_files(root: Path = ROOT):
    """Package an explicit source tree, including current uncommitted edits.

    Never walk the repository root: virtualenvs, output and personal runtime
    data must not enter a source distribution, even when they are tracked.
    """
    for name in SOURCE_FILES:
        path = root / name
        if path.is_file():
            yield path
    for name in SOURCE_DIRS:
        for path in sorted((root / name).rglob("*")):
            relative = path.relative_to(root)
            if (path.is_file() and not path.is_symlink()
                    and "__pycache__" not in relative.parts
                    and path.suffix.lower() not in {".pyc", ".pyo", ".log", ".sqlite3"}):
                yield path


def build_source() -> Path:
    target = RELEASE / f"{APP}-source.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, f"{APP}-source/{path.relative_to(ROOT).as_posix()}")
    return target


def build_exe() -> Path:
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise RuntimeError("The win64 bundle requires 64-bit Windows Python.")
    if importlib.util.find_spec("PyInstaller") is None:
        raise RuntimeError("Missing build dependencies. Run build.bat all --install-deps")
    # Foreign tools on PATH can provide incompatible DLLs with system names
    # (for example Poppler's icuuc.dll). Restrict dependency discovery to this
    # Python, its Qt distribution and Windows; do not change the user's PATH.
    qt = importlib.util.find_spec("PyQt6")
    if qt is None:
        raise RuntimeError("PyQt6 is missing; install requirements.txt first.")
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    search = [Path(sys.executable).parent, Path(sys.base_prefix),
              Path(sys.base_prefix) / "DLLs", Path(qt.origin).parent / "Qt6" / "bin",
              windows / "System32", windows]
    env = dict(os.environ, PATH=os.pathsep.join(map(str, search)))
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(RELEASE), "--workpath", str(ROOT / "build" / "pyinstaller"),
        str(ROOT / "2.4GBatteryTray.spec"),
    ], cwd=ROOT, env=env, check=True)
    folder = RELEASE / APP
    if not (folder / f"{APP}.exe").is_file():
        raise RuntimeError("PyInstaller did not produce the expected executable.")
    shutil.copy2(ROOT / "release-readme.txt", folder / "README.txt")
    target = RELEASE / f"{APP}-win64.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            # A previous portable build may contain user settings and history.
            # Only package the executable, bundled dependencies and release README.
            relative = path.relative_to(folder)
            if path.is_file() and (relative.parts[0] == "_internal"
                                  or relative.as_posix() in {f"{APP}.exe", "README.txt"}):
                archive.write(path, f"{APP}/{relative.as_posix()}")
    return target


def write_checksums() -> None:
    lines = []
    for name in (f"{APP}-win64.zip", f"{APP}-source.zip"):
        path = RELEASE / name
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            lines.append(f"{digest}  {name}\n")
    (RELEASE / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", choices=("all", "exe", "source"), default="all")
    parser.add_argument("--install-deps", action="store_true",
                        help="Install requirements into the current Python before building")
    args = parser.parse_args()
    try:
        if args.install_deps:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                            str(ROOT / "requirements.txt")], check=True)
        RELEASE.mkdir(exist_ok=True)
        if args.target in ("all", "exe"):
            print(f"Built: {build_exe()}", flush=True)
        if args.target in ("all", "source"):
            print(f"Built: {build_source()}", flush=True)
        write_checksums()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
