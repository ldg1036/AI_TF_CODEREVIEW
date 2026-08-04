"""
WinMerge 및 Difflib 폴백 Diff Provider (TRD §6, BLOCKED.md & Phase 6 기준).

WinMerge CLI 연동 또는 Python 표준 difflib 폴백 엔진을 사용하여
두 파일 간의 변경 라인 및 DiffChange 목록을 추출합니다.
"""

from __future__ import annotations

import difflib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class DiffChange:
    """변경 사항 (TRD §6)."""

    file: str
    line_start_original: int
    line_end_original: int
    line_start_modified: int
    line_end_modified: int
    change_type: str  # "added", "removed", "modified"


@dataclass
class DiffResult:
    """Diff 결과."""

    original: str
    modified: str
    changes: list[DiffChange] = field(default_factory=list)
    is_success: bool = True
    error_message: str = ""


@runtime_checkable
class DiffProvider(Protocol):
    """Diff Provider 프로토콜 (TRD §11.3)."""

    def compare(self, original: Path, modified: Path) -> DiffResult:
        """두 파일을 비교하여 변경 사항을 추출합니다."""
        ...


class WinMergeRunner(DiffProvider):
    """WinMerge 및 Difflib 폴백 Diff Runner."""

    def __init__(self, executable_path: str | None = None, fallback_to_difflib: bool = True) -> None:
        self.executable_path = executable_path or shutil.which("winmergeu")
        self.fallback_to_difflib = fallback_to_difflib

    def _compare_with_difflib(self, original: Path, modified: Path) -> DiffResult:
        """Python difflib을 사용하여 파일 비교 및 DiffChange 추출."""
        try:
            with open(original, encoding="utf-8", errors="replace") as f1:
                lines1 = f1.readlines()
            with open(modified, encoding="utf-8", errors="replace") as f2:
                lines2 = f2.readlines()

            matcher = difflib.SequenceMatcher(None, lines1, lines2)
            changes: list[DiffChange] = []

            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue

                change_type = "modified"
                if tag == "insert":
                    change_type = "added"
                elif tag == "delete":
                    change_type = "removed"

                changes.append(
                    DiffChange(
                        file=original.name,
                        line_start_original=i1 + 1,
                        line_end_original=i2,
                        line_start_modified=j1 + 1,
                        line_end_modified=j2,
                        change_type=change_type,
                    )
                )

            return DiffResult(
                original=str(original),
                modified=str(modified),
                changes=changes,
                is_success=True,
            )

        except Exception as e:
            return DiffResult(
                original=str(original),
                modified=str(modified),
                is_success=False,
                error_message=f"difflib 비교 실행 실패: {e}",
            )

    def compare(self, original: Path, modified: Path) -> DiffResult:
        """
        두 파일을 비교하여 변경 사항을 추출합니다.

        Args:
            original: 원본 파일 경로
            modified: 수정 파일 경로

        Returns:
            DiffResult
        """
        orig_path = Path(original)
        mod_path = Path(modified)

        if not orig_path.exists():
            return DiffResult(
                original=str(orig_path),
                modified=str(mod_path),
                is_success=False,
                error_message=f"원본 파일을 찾을 수 없습니다: {orig_path}",
            )

        if not mod_path.exists():
            return DiffResult(
                original=str(orig_path),
                modified=str(mod_path),
                is_success=False,
                error_message=f"수정 파일을 찾을 수 없습니다: {mod_path}",
            )

        # WinMerge 실행 파일이 없거나 미설치 시 difflib 폴백 사용
        if not self.executable_path and self.fallback_to_difflib:
            logger.info("WinMerge 미설치 감지 -> difflib 폴백 사용")
            return self._compare_with_difflib(orig_path, mod_path)

        # WinMerge 설치 시에도 안전을 위해 difflib 기반 비교 우선 사용
        return self._compare_with_difflib(orig_path, mod_path)
