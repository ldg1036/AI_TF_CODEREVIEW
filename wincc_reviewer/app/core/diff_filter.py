"""
git diff 기반 변경 라인 파서 및 필터링 모듈.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class GitDiffFilter:
    """git diff 결과 텍스트를 파싱하여 변경된 라인 영역만 선별하는 필터."""

    @classmethod
    def parse_unified_diff(cls, diff_text: str) -> dict[str, set[int]]:
        """
        Unified diff 텍스트를 파싱하여 파일 상대 경로별 변경된 라인 번호 집합을 반환합니다.
        Returns:
            dict[file_path_str, set[line_numbers]]
        """
        result: dict[str, set[int]] = {}
        current_file: str | None = None
        current_line: int = 0

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                if current_file not in result:
                    result[current_file] = set()
            elif line.startswith("@@"):
                # 예: @@ -10,5 +12,8 @@
                match = re.search(r"\+(\d+)(?:,(\d+))?", line)
                if match:
                    current_line = int(match.group(1))
            elif current_file:
                if line.startswith("+") and not line.startswith("+++"):
                    result[current_file].add(current_line)
                    current_line += 1
                elif line.startswith(" "):
                    current_line += 1

        return result

    @classmethod
    def filter_violations(cls, violations: list[Any], diff_map: dict[str, set[int]]) -> list[Any]:
        """
        전체 위반 목록 중 git diff 변경 라인 영역에 존재하는 위반만 필터링합니다.
        """
        if not diff_map:
            return violations

        filtered = []
        for v in violations:
            file_path = str(getattr(v, "file_path", ""))
            line_no = int(getattr(v, "line_number", 0))

            # 상대 경로 또는 파일명 매칭 탐색
            matched = False
            for diff_path, lines in diff_map.items():
                if file_path.endswith(diff_path) or diff_path.endswith(file_path) or Path(file_path).name == Path(diff_path).name:
                    if line_no in lines or line_no == 0:
                        matched = True
                        break

            if matched:
                filtered.append(v)

        return filtered
