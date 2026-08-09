"""
WinCC OA 코드 리뷰 자동화 도구 — AST 파서 및 정적 체커 고도화 유닛 테스트.
11번 지침서 R2(호출부 증명) 및 R4(독립 재실행 원칙)에 따라 오탐 FP 감소 및 주석/태그 정밀 검수를 검증합니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from app.core.input_normalization.service import NormalizationService
from app.core.models import CheckerType, RuleDefinition, ViolationStatus
from app.core.rules.rule_engine import RuleEngine


class TestASTCheckerEnhancements:
    """AST 파서 및 체커 FP 노이즈 감축 고도화 유닛 테스트."""

    def test_manual_review_rule_does_not_flag_unmatched_lines(self, tmp_path: Path) -> None:
        """키워드가 존재하지 않는 파일에 대해 MANUAL_REVIEW 오탐 FP가 발생하지 않음을 검증합니다."""
        sample = tmp_path / "clean_sample.ctl"
        sample.write_text(
            """
            void main() {
                int count = 10;
                DebugN("Processing...", count);
            }
            """,
            encoding="utf-8",
        )

        parsed = NormalizationService.normalize_and_parse(sample)
        rule = RuleDefinition(
            rule_id="MANUAL-001",
            source_key="SRC-MANUAL-001",
            file_types=[".ctl"],
            rule_version="1.0",
            category="Maintainability",
            severity="Info",
            check_item="active 동작 구문 수동 검토",
            condition="MANUAL_REVIEW",
            message="active 동작 구문 검토 필요",
            enabled=True,
            checker_type=CheckerType.MANUAL,
        )

        violations = RuleEngine.execute_rule(parsed, rule)
        assert len(violations) == 0, "키워드가 없는 소스 파일에 대해 오탐 위반이 등록되지 않아야 합니다."

    def test_manual_review_rule_flags_matching_keyword_lines(self, tmp_path: Path) -> None:
        """이중화 active 조치가 누락된 제어 로직에 대해 1건의 수동 검토 위반이 탐지되는지 검증합니다."""
        sample = tmp_path / "active_sample.ctl"
        sample.write_text(
            """
            void main() {
                dpConnect("workCB", "System1:Tag.status");
            }
            """,
            encoding="utf-8",
        )

        parsed = NormalizationService.normalize_and_parse(sample)
        rule = RuleDefinition(
            rule_id="MANUAL-001",
            source_key="SRC-MANUAL-001",
            file_types=[".ctl"],
            rule_version="1.0",
            category="Maintainability",
            severity="Info",
            check_item="active 동작 구문 수동 검토",
            condition="MANUAL_REVIEW",
            message="active 동작 구문 검토 필요",
            enabled=True,
            checker_type=CheckerType.MANUAL,
        )

        violations = RuleEngine.execute_rule(parsed, rule)
        assert len(violations) == 1, "active 조치가 누락된 제어 코드 라인에 대해 1건의 수동 검토 위반이 등록되어야 합니다."
        assert violations[0].status == ViolationStatus.MANUAL_REVIEW
