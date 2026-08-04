"""
WinCC OA 코드 리뷰 자동화 도구 — AI 허위 경보(False Positive) 필터링 단위 테스트.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.ai.false_positive_filter import FalsePositiveFilter
from app.core.models import ParseStatus, ParseStatusType, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile


class TestFalsePositiveFilter:
    """FalsePositiveFilter 실증 테스트 스위트."""

    def test_safe_annotation_detected(self):
        """1. 명시적 안전 주석(@safe / IGNORE_RULE) 존재 시 오탐(False Positive) 판정 검증."""
        violation = Violation(
            violation_id="V-001",
            rule_id="CTL_SEC_001",
            file_id="sample.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.HIGH,
            message="위험한 호출",
            snippet="dpSet('tag', 1); // @safe: 테스트 인가",
        )

        conf, fp_prob, is_fp, reason = FalsePositiveFilter.analyze_domain_context(violation)
        assert conf == 0.05
        assert fp_prob == 0.95
        assert is_fp is True
        assert "[도메인 안전 예외]" in reason

    def test_safe_wrapper_function_detected(self):
        """2. SCADA 안전 래퍼 함수(safeDpSet 등) 호출 시 허위 경보 분류 검증."""
        violation = Violation(
            violation_id="V-002",
            rule_id="CTL_PRF_001",
            file_id="sample.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.MEDIUM,
            message="DP 설정",
            snippet="safeDpSet('tag1', 100);",
        )

        conf, fp_prob, is_fp, reason = FalsePositiveFilter.analyze_domain_context(violation)
        assert is_fp is True
        assert fp_prob >= 0.80
        assert "[SCADA 안전 래퍼]" in reason

    def test_error_recovery_handler_in_callback(self):
        """3. 콜백 위반 구문에 예외/오류 복구 구문 동반 시 안전 맥락 분류 검증."""
        violation = Violation(
            violation_id="V-003",
            rule_id="CTL_CALLBACK_ERR",
            file_id="cb.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.HIGH,
            message="콜백 에러",
            snippet="void cb() { dpGet(a, b); if (getLastError() != 0) return; }",
        )

        conf, fp_prob, is_fp, reason = FalsePositiveFilter.analyze_domain_context(violation)
        assert is_fp is True
        assert "[오류 복구 핸들러]" in reason

    def test_true_positive_violation(self):
        """4. 보호 로직이나 주석이 없는 위반 구문의 진성 위반(True Positive) 판정 검증."""
        violation = Violation(
            violation_id="V-004",
            rule_id="CTL_ERR_001",
            file_id="unsafe.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.CRITICAL,
            message="미처리 DB 쿼리",
            snippet="dbExecute('DROP TABLE users;');",
        )

        conf, fp_prob, is_fp, reason = FalsePositiveFilter.analyze_domain_context(violation)
        assert conf == 0.95
        assert fp_prob == 0.05
        assert is_fp is False
        assert "[진성 위반 검증]" in reason

    def test_filter_violations_batch(self):
        """5. filter_violations 일괄 처리 및 Violation 객체 속성 바인딩 검증."""
        v1 = Violation(
            violation_id="V-001",
            rule_id="CTL_SEC_001",
            file_id="sample.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.HIGH,
            message="위험한 호출",
            snippet="dpSet('tag', 1); // IGNORE_RULE",
        )
        v2 = Violation(
            violation_id="V-002",
            rule_id="CTL_ERR_001",
            file_id="sample.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.CRITICAL,
            message="미처리 쿼리",
            snippet="dbExecute('SELECT *;');",
        )

        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="sample.ctl"),
            original_sha256="123",
            detected_encoding="utf-8",
            newline_style="\n",
            content="dpSet('tag', 1); // IGNORE_RULE\ndbExecute('SELECT *;');",
        )

        results = FalsePositiveFilter.filter_violations([v1, v2], {"sample.ctl": parsed})
        assert len(results) == 2

        assert results[0].is_false_positive is True
        assert results[0].confidence_score == 0.05

        assert results[1].is_false_positive is False
        assert results[1].confidence_score == 0.95
