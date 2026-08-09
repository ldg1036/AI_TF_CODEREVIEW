"""
WinMergeRunner 및 DiffProvider 유닛 테스트 (TRD §6 & Phase 6 기준).

검증 항목:
1. difflib 폴백 차분 비교 및 DiffChange 목록 생성
2. 존재하지 않는 파일에 대해 is_success=False 및 error_message 반환
"""

from __future__ import annotations

from pathlib import Path

from app.core.diff.winmerge_runner import WinMergeRunner


class TestDiffProvider:
    """DiffProvider 유닛 테스트."""

    def test_diff_provider_changes(self, tmp_path: Path):
        """두 파일 간의 변경 사항(DiffChange) 산출 검증."""
        file1 = tmp_path / "orig.ctl"
        file1.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

        file2 = tmp_path / "mod.ctl"
        file2.write_text("line 1\nline 2 MODIFIED\nline 3\nline 4 ADDED\n", encoding="utf-8")

        runner = WinMergeRunner()
        res = runner.compare(file1, file2)

        assert res.is_success is True
        assert len(res.changes) >= 1

        types = [c.change_type for c in res.changes]
        assert "modified" in types or "added" in types

    def test_diff_provider_file_not_found(self, tmp_path: Path):
        """존재하지 않는 파일에 대한 안전 에러 반환 검증."""
        file1 = tmp_path / "exist.ctl"
        file1.write_text("hello", encoding="utf-8")

        file2 = tmp_path / "non_existent.ctl"

        runner = WinMergeRunner()
        res = runner.compare(file1, file2)

        assert res.is_success is False
        assert "찾을 수 없습니다" in res.error_message
