"""ANSH AI Setup & Installer Builder.
Developed by Anshu Dubey (https://devanshu.page.gd).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"


def check_dependencies():
    print("[Setup Builder] Checking PyInstaller...")
    try:
        import PyInstaller
        print("[Setup Builder] PyInstaller is available.")
    except ImportError:
        print("[Setup Builder] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def build_pyinstaller_exe():
    """Build ANSH AI standalone executable."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    icon_path = BASE_DIR / "config" / "ansh.ico"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=ANSH_AI",
        f"--icon={icon_path}",
        "--add-data=config;config",
        "--add-data=core;core",
        "--add-data=outputs;outputs",
        "--add-data=PRODUCT_KEYS.txt;.",
        "--add-data=DOCUMENTATION.md;.",
        str(BASE_DIR / "main.py"),
    ]
    print(f"[Setup Builder] Running PyInstaller command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(BASE_DIR), check=False)
    if res.returncode == 0:
        print("[Setup Builder] ANSH AI application built successfully in dist/ANSH_AI!")
    else:
        print(f"[Setup Builder] PyInstaller exited with code {res.returncode}")


def compile_inno_setup():
    """If Inno Setup compiler (ISCC) is available, compile installer.iss into setup.exe."""
    iscc_paths = [
        shutil.which("iscc"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    iscc = next((p for p in iscc_paths if p and Path(p).exists()), None)
    if iscc:
        print(f"[Setup Builder] Found Inno Setup compiler: {iscc}")
        iss_path = BASE_DIR / "installer" / "installer.iss"
        res = subprocess.run([iscc, str(iss_path)], cwd=str(BASE_DIR / "installer"), check=False)
        if res.returncode == 0:
            print(f"[Setup Builder] Setup installer generated at dist/ANSH_AI_Setup_v2.0.0.exe!")
        else:
            print("[Setup Builder] Inno Setup compilation failed.")
    else:
        print("[Setup Builder] Inno Setup compiler (ISCC) not found on PATH. installer.iss is ready for compilation.")


def main():
    print("==================================================================")
    print("           ANSH AI - SETUP & INSTALLER BUILDER")
    print("               Developed by Anshu Dubey")
    print("==================================================================")
    check_dependencies()
    compile_inno_setup()
    print("[Setup Builder] Done!")


if __name__ == "__main__":
    main()
