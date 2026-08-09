"""
WinCC OA 코드 리뷰 자동화 도구 — 기술 부채 핫스팟 히트맵 & 품질 트렌드 리포트 단위 테스트 (TRD Phase 16).
"""

from __future__ import annotations

from app.core.models import (
    Metrics,
    ReviewReport,
    SeverityLevel,
    Violation,
    ViolationStatus,
)
from app.core.report.hotspot_calculator import HotspotCalculator
from app.core.report.html_report_builder import HTMLReportBuilder


class TestHotspotCalculatorAndTrendReport:
    """기술 부채 핫스팟 점수 산출 및 HTML 릴리스 트렌드 렌더링 검증."""

    def test_hotspot_calculator_weights_and_sorting(self):
        violations = [
            Violation(
                violation_id="v1",
                rule_id="CTL_001",
                file_id="scripts/high_risk.ctl",
                line_start=10,
                severity=SeverityLevel.CRITICAL,
                message="Critical bug",
                status=ViolationStatus.FAIL,
            ),
            Violation(
                violation_id="v2",
                rule_id="CTL_002",
                file_id="scripts/high_risk.ctl",
                line_start=20,
                severity=SeverityLevel.HIGH,
                message="High bug",
                status=ViolationStatus.FAIL,
            ),
            Violation(
                violation_id="v3",
                rule_id="CTL_003",
                file_id="scripts/low_risk.ctl",
                line_start=15,
                severity=SeverityLevel.LOW,
                message="Low issue",
                status=ViolationStatus.FAIL,
            ),
        ]

        summary = HotspotCalculator.calculate(violations, limit=5)
        assert summary.total_score == 16.0  # CRITICAL(10.0) + HIGH(5.0) + LOW(1.0)
        assert len(summary.top_hotspots) == 2

        # 첫 번째 핫스팟은 high_risk.ctl (15.0점)
        top1 = summary.top_hotspots[0]
        assert top1.file_id == "scripts/high_risk.ctl"
        assert top1.hotspot_score == 15.0
        assert top1.critical_count == 1
        assert top1.high_count == 1

        # 두 번째 핫스팟은 low_risk.ctl (1.0점)
        top2 = summary.top_hotspots[1]
        assert top2.file_id == "scripts/low_risk.ctl"
        assert top2.hotspot_score == 1.0

    def test_html_report_renders_hotspot_and_trend(self):
        violations = [
            Violation(
                violation_id="v4",
                rule_id="CTL_001",
                file_id="scripts/core.ctl",
                line_start=10,
                severity=SeverityLevel.CRITICAL,
                message="Critical issue in loop",
                status=ViolationStatus.FAIL,
            )
        ]

        report = ReviewReport(
            schema_version="1.0.0",
            run_id="run-hotspot-001",
            rule_source="test_rules",
            files=["scripts/core.ctl"],
            violations=violations,
            errors=[],
            metrics=Metrics(
                file_count=1,
                violation_count=1,
                timings_ms={"total": 50},
            ),
            trend_summary={
                "has_previous": True,
                "new_count": 3,
                "resolved_count": 2,
                "unchanged_count": 1,
            },
        )


        html_text = HTMLReportBuilder.render_html(report)

        # 1. 핫스팟 히트맵 렌더링 검증
        assert "🔥 기술 부채 핫스팟 히트맵 (Technical Debt Hotspot Map)" in html_text
        assert "Hotspot Score: 10.0" in html_text
        assert "filterByFile('scripts/core.ctl')" in html_text

        # 2. 릴리스 품질 트렌드 대시보드 렌더링 검증
        assert "📈 릴리스 품질 트렌드 및 퇴보(Regression) 분석" in html_text
        assert "신규 유입 결함 (New)" in html_text
        assert "해결된 결함 (Fixed)" in html_text
