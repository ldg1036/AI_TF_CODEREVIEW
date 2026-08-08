"""
코드 리뷰 결과 1문단 종합 요약 생성 모듈.
"""

from __future__ import annotations

from typing import Any

from app.core.models import SeverityLevel


class ReviewSummaryGenerator:
    """전체 리뷰 결과 위반 항목을 1문단 맥락 요약문으로 종합 변환합니다."""

    @classmethod
    def generate_summary(cls, violations: list[Any]) -> str:
        """
        위반 목록의 심각도 분포 및 주요 결함을 집계하여 1문단 요약을 생성합니다.
        """
        if not violations:
            return "본 코드 리뷰 검사 결과 결함 위반 항목이 검출되지 않았으며, 지침 기준을 만족하고 있습니다."

        total_count = len(violations)
        critical_cnt = sum(1 for v in violations if getattr(v, "severity", None) == SeverityLevel.CRITICAL)
        high_cnt = sum(1 for v in violations if getattr(v, "severity", None) == SeverityLevel.HIGH)
        medium_cnt = sum(1 for v in violations if getattr(v, "severity", None) == SeverityLevel.MEDIUM)
        low_cnt = sum(1 for v in violations if getattr(v, "severity", None) == SeverityLevel.LOW)

        rule_ids = list(set(getattr(v, "rule_id", "UNKNOWN") for v in violations))
        top_rules = ", ".join(rule_ids[:3])

        return (
            f"본 코드 리뷰 검사 결과 총 {total_count}건의 결함 항목"
            f"(Critical {critical_cnt}건, High {high_cnt}건, Medium {medium_cnt}건, Low {low_cnt}건)이 검출되었습니다. "
            f"주요 결함 패턴으로는 {top_rules} 등이 포함되어 있으므로 심각도 우선순위에 따른 시급한 정리 조치가 권장됩니다."
        )
