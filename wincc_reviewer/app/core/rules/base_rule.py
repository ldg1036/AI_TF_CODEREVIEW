"""
WinCC OA 코드 리뷰 자동화 도구 — 룰 체커 기본 인터페이스.

TRD §11.3의 최소 인터페이스 계약:
    class RuleChecker(Protocol):
        def check(self, parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]: ...

TRD §5.2:
    BaseRule 추상클래스: check(ir) -> list[Violation]
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.models import RuleDefinition, Violation
from app.core.parser.base_parser import ParsedFile


@runtime_checkable
class RuleChecker(Protocol):
    """룰 체커 프로토콜 (TRD §11.3)."""

    def check(self, parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
        """
        파싱된 파일에 대해 룰을 적용하여 위반 사항을 검출합니다.

        parse_status.status == parse_failed 인 IR은
        룰 검사를 건너뛰고 빈 Violation 목록만 반환합니다.

        Args:
            parsed: 파싱된 파일 IR
            rule: 적용할 룰 정의

        Returns:
            검출된 위반 사항 목록
        """
        ...
