"""
WinCC OA 코드 리뷰 자동화 도구 — AI 룰 카탈로그 자율 최적화 루프 실증 단위 테스트 (TRD Phase 17).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.ai.rule_optimizer import RuleOptimizer
from app.main import main


class TestRuleOptimizerAndCLI:
    """오탐 피드백 학습 및 제외 키워드 자율 추천 검증."""

    def test_record_feedback_and_analyze_suggestions(self, tmp_path: Path):
        log_file = tmp_path / "test_fp_log.json"
        optimizer = RuleOptimizer(log_path=log_file)

        # 1. CTL_PRF_001에 대한 오탐 3건 기록 (공통 안전 래퍼: safeDpSet)
        optimizer.record_feedback(
            rule_id="CTL_PRF_001",
            snippet="safeDpSet(dpe, val); // domain safe wrapper",
            reason="도메인 래퍼 함수 사용으로 안전",
            file_id="scripts/mgr.ctl",
        )
        optimizer.record_feedback(
            rule_id="CTL_PRF_001",
            snippet="if (ok) { safeDpSet(dpe2, 100); }",
            reason="도메인 래퍼 함수 사용",
            file_id="scripts/mgr2.ctl",
        )
        optimizer.record_feedback(
            rule_id="CTL_PRF_001",
            snippet="safeDpSet(target, value);",
            reason="도메인 래퍼 함수",
            file_id="scripts/mgr3.ctl",
        )

        # 2. CTL_SEC_002에 대한 오탐 1건 기록 (임계치 2건 미달성)
        optimizer.record_feedback(
            rule_id="CTL_SEC_002",
            snippet="checkAuth(user);",
            reason="인증 체크됨",
            file_id="scripts/auth.ctl",
        )

        # 3. 분석 및 추천안 산출 검증 (min_fp_threshold=2)
        suggestions = optimizer.analyze_and_suggest(min_fp_threshold=2)
        assert len(suggestions) == 1

        top_sug = suggestions[0]
        assert top_sug.rule_id == "CTL_PRF_001"
        assert top_sug.total_fp_count == 3
        assert top_sug.suggested_exclude_keyword == "safeDpSet"
        assert "not_contains: \"safeDpSet\"" in top_sug.suggested_rule_condition_update

        # 4. 마크다운 리포트 렌더링 검증
        md_report = optimizer.render_markdown_report(suggestions)
        assert "# 🤖 AI 룰 카탈로그 자율 최적화 추천 리포트" in md_report
        assert "`CTL_PRF_001`" in md_report
        assert "**3건**" in md_report
        assert "`safeDpSet`" in md_report

    def test_cli_suggest_rules_option(self, capsys: pytest.CaptureFixture[str]):
        """CLI --suggest-rules 실행 시 정상 종료 및 추천 리포트 출력 검증."""
        exit_code = main(["--suggest-rules"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "AI 룰 카탈로그 자율 최적화 추천 리포트" in captured.out

    def test_is_rule_approved_for_exclusion(self, tmp_path: Path):
        approved_file = tmp_path / "approved_rules.json"
        approved_file.write_text(
            '{"approved_fp_exclusions": [{"rule_id": "CTL_AST_CFA_003"}]}',
            encoding="utf-8"
        )
        optimizer = RuleOptimizer(approved_path=approved_file)
        assert optimizer.is_rule_approved_for_exclusion("CTL_AST_CFA_003") is True
        assert optimizer.is_rule_approved_for_exclusion("UNAPPROVED_RULE") is False

