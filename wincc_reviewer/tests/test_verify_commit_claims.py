"""
verify_commit_message_claims.py 유닛 테스트 수트.
과장 표현 및 SSOT 수치 불일치 커밋이 실제로 차단되는지 검증합니다.
"""

from __future__ import annotations

import pytest
from scripts.verify_commit_message_claims import verify_commit_message


class TestVerifyCommitClaims:
    def test_valid_commit_message_passes(self) -> None:
        """정상적인 수치 및 설명이 명시된 커밋 메시지 통과 검증."""
        msg = "feat: 커버리지 85.8% 달성 (SSOT: single_source_metrics.json, 33개 체커 완료)"
        is_valid, errors = verify_commit_message(msg)
        assert is_valid is True
        assert len(errors) == 0

    def test_exaggerated_forbidden_term_rejected(self) -> None:
        """SSOT 수치 병기 없이 과장 표현 사용 시 커밋 거부 검증."""
        msg = "feat: 코드 결함 완전히 해소 완료"
        is_valid, errors = verify_commit_message(msg)
        assert is_valid is False
        assert any("금지된 과장 표현" in err for err in errors)

    def test_mismatched_coverage_percentage_rejected(self) -> None:
        """SSOT 실측값(85.8%)과 불일치하는 100% 커버리지 주장 시 커밋 거부 검증."""
        msg = "feat: 자동화 커버리지 100% 완수 및 35개 체커 완료"
        is_valid, errors = verify_commit_message(msg)
        assert is_valid is False
        assert any("수치 주장 불일치" in err or "과장 표현" in err for err in errors)

    def test_mismatched_checker_count_rejected(self) -> None:
        """SSOT 실측 체커 수(35개)와 불일치하는 체커 주장 시 커밋 거부 검증."""
        msg = "feat: 신규 50개 체커 등록 완료 (SSOT: single_source_metrics.json)"
        is_valid, errors = verify_commit_message(msg)
        assert is_valid is False
        assert any("체커 개수 불일치" in err for err in errors)
