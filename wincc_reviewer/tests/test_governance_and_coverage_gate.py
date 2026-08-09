"""
WinCC OA 코드 리뷰 자동화 도구 — 거버넌스 및 커버리지 무결성 CI 회귀 게이트.
12번 개발 문서 IMP 10 및 IMP 11 명세에 따라 CODEOWNERS 거버넌스 파일과 커버리지 주장 무결성을 실시간 자동 검증합니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from scripts.verify_coverage_claim import verify_coverage_claim


class TestGovernanceAndCoverageGate:
    """IMP 10, IMP 11 거버넌스 및 커버리지 자동 검증 수트."""

    def test_codeowners_file_exists_and_valid(self) -> None:
        """거버넌스 강제를 위한 .github/CODEOWNERS 파일 존재 및 필수 작성 상태를 검증합니다 (IMP 11)."""
        codeowners_path = base_dir / ".github" / "CODEOWNERS"
        assert codeowners_path.exists(), ".github/CODEOWNERS 거버넌스 파일이 존재해야 합니다."

        content = codeowners_path.read_text(encoding="utf-8")
        assert "@ldg1036" in content, "지정된 승인 소유자(@ldg1036)가 명시되어야 합니다."
        assert "wincc_reviewer/app/core/rules/" in content, "핵심 룰 엔진 경로 보호가 설정되어야 합니다."

    def test_coverage_claim_integrity_gate(self) -> None:
        """등록된 체커 수와 자동화 커버리지 주장 무결성을 실시간 검증합니다 (IMP 10)."""
        is_valid = verify_coverage_claim()
        assert is_valid is True, "자동화 커버리지 주장 무결성 검증을 통과해야 합니다."

    def test_real_world_fp_log_structure(self) -> None:
        """IMP 09 실물 SCADA 오탐 구조화 로그 파일 존재를 검증합니다."""
        fp_log_path = base_dir / "secondary_data" / "real_world_fp_log.csv"
        assert fp_log_path.exists(), "secondary_data/real_world_fp_log.csv 구조화 로그가 존재해야 합니다."
