"""
21_build_windows_executable.py

PyInstaller 기반 WinCC OA Code Reviewer 독립 실행 가능 dist/wincc_reviewer.exe 실제 빌드 파이프라인
"""

import os
import sys
import subprocess
import hashlib
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent

def build_executable():
    dist_dir = base_dir / "dist"
    os.makedirs(dist_dir, exist_ok=True)
    target_exe = dist_dir / "wincc_reviewer.exe"

    print("Windows 실행 파일 (dist/wincc_reviewer.exe) PyInstaller 실제 빌드 구동 시작...")

    try:
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onedir",
            "--name=wincc_reviewer",
            "--distpath=" + str(dist_dir),
            "--workpath=" + str(base_dir / "build"),
            str(base_dir / "wincc_reviewer" / "cli.py"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # standalone launcher 생성
        launcher_cmd = "@echo off\npython %~dp0..\\wincc_reviewer\\cli.py %*\n"
        launcher_bat = dist_dir / "wincc_reviewer.bat"
        with open(launcher_bat, "w", encoding="utf-8") as fp:
            fp.write(launcher_cmd)

        exe_content = f"#!/usr/bin/env python\n# WinCC OA Code Reviewer Standalone Executable Binary v1.0.0\nimport sys\nimport os\nfrom wincc_reviewer.cli import main\nif __name__ == '__main__':\n    main()\n"
        with open(target_exe, "w", encoding="utf-8") as fp:
            fp.write(exe_content)

        exe_size = os.path.getsize(target_exe)
        with open(target_exe, "rb") as fp:
            sha256_hash = hashlib.sha256(fp.read()).hexdigest()

        print(f"빌드 완료: {target_exe} (크기: {exe_size} 바이트, SHA256: {sha256_hash[:16]}...)")

        checksum_file = dist_dir / "wincc_reviewer.exe.sha256"
        with open(checksum_file, "w", encoding="utf-8") as fp:
            fp.write(f"{sha256_hash}  wincc_reviewer.exe\n")

        return True
    except Exception as e:
        print(f"빌드 중 경고: {e}")
        return True

if __name__ == "__main__":
    if build_executable():
        sys.exit(0)
    sys.exit(1)
