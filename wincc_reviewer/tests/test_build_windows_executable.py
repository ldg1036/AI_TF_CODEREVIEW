"""
test_build_windows_executable.py

build_windows_executable 빌드 파이프라인 유닛 테스트 (R2 호출부 증명)
"""

from __future__ import annotations

import importlib


class TestBuildWindowsExecutable:
    """Windows 바이너리 빌드 파이프라인 검증"""

    def test_build_windows_executable_execution(self):
        mod = importlib.import_module("scripts.21_build_windows_executable")
        res = mod.build_windows_executable()
        assert res is not None
        assert "executable" in res
        assert len(res["checksum"]) == 64
