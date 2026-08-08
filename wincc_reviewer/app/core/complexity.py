"""
함수 및 스크립트 단위 순환 복잡도(Cyclomatic Complexity) 및 구조적 품질 지표 분석 모듈.
"""

from __future__ import annotations

import re
from typing import Any


class ComplexityAnalyzer:
    """스크립트 코드의 순환 복잡도, 중첩 깊이 및 라인 수 지표를 계산합니다."""

    BRANCH_KEYWORDS = [
        r"\bif\b",
        r"\belse\s+if\b",
        r"\bwhile\b",
        r"\bfor\b",
        r"\bswitch\b",
        r"\bcase\b",
        r"\bcatch\b",
        r"&&",
        r"\|\|",
    ]

    @classmethod
    def calculate_cyclomatic_complexity(cls, code: str) -> int:
        """
        코드 스니펫 또는 전체 파일의 순환 복잡도(기본값 1 + 분기문 수)를 산출합니다.
        """
        if not code:
            return 1

        complexity = 1
        for pattern in cls.BRANCH_KEYWORDS:
            matches = re.findall(pattern, code)
            complexity += len(matches)

        return complexity

    @classmethod
    def calculate_max_nesting_depth(cls, code: str) -> int:
        """
        중괄호 분기 기준 최대 중첩 깊이를 계산합니다.
        """
        if not code:
            return 0

        max_depth = 0
        current_depth = 0
        for char in code:
            if char == "{":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == "}":
                if current_depth > 0:
                    current_depth -= 1

        return max_depth

    @classmethod
    def analyze(cls, code: str) -> dict[str, Any]:
        """
        순환 복잡도, 중첩 깊이, 라인 수 지표를 요약하여 반환합니다.
        """
        lines = code.splitlines() if code else []
        total_lines = len(lines)
        cyclomatic = cls.calculate_cyclomatic_complexity(code)
        max_depth = cls.calculate_max_nesting_depth(code)

        return {
            "total_lines": total_lines,
            "cyclomatic_complexity": cyclomatic,
            "max_nesting_depth": max_depth,
            "is_high_complexity": cyclomatic >= 15 or max_depth >= 5,
        }
