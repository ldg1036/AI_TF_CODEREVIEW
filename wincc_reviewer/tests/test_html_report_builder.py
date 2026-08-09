"""
HTMLReportBuilder 유닛 테스트 (TRD §5.7, TRD §7 & 05_개발로드맵 Phase 7 기준).

검증 항목:
1. 파싱 실패 파일 포함 시 Errors 섹션 HTML 독립 표기 검증 (DoD)
2. export_html 단일 HTML 파일 생성 검증
3. 외부 CDN(http/https) 의존성 0개 검증 (사내망 환경 고려)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.models import (
    ParseStatus,
    ParseStatusType,
    SeverityLevel,
    Violation,
    ViolationStatus,
)
from app.core.parser.base_parser import ParsedFile
from app.core.report.html_report_builder import HTMLReportBuilder
from app.core.report.report_builder import ReportBuilder


class TestHTMLReportBuilder:
    """HTMLReportBuilder 유닛 테스트."""

    @pytest.fixture
    def report_data(self) -> tuple[list[ParsedFile], list[Violation]]:
        parsed_ok = ParsedFile(
            file_path=Path("src/main.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="src/main.ctl"),
            content="void main() {}",
        )

        parsed_err = ParsedFile(
            file_path=Path("src/broken.pnl"),
            file_type="pnl",
            parse_status=ParseStatus(
                status=ParseStatusType.PARSE_FAILED,
                file="src/broken.pnl",
                error_message="PNL 구문 파싱 실패",
            ),
            content="",
        )

        violation = Violation(
            violation_id="V-001",
            rule_id="CTL-RES-001",
            file_id="src/main.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.CRITICAL,
            message="dpConnect 대응 dpDisconnect 누락",
            line_start=10,
            snippet="dpConnect('cbTemp', 'dpe');",
        )

        return [parsed_ok, parsed_err], [violation]

    def test_render_html_with_errors_section(self, report_data: tuple[list[ParsedFile], list[Violation]]):
        """파싱 실패 파일이 HTML Errors 섹션에 독립 표기되는지 검증 (DoD)."""
        parsed_files, violations = report_data
        report = ReportBuilder.build_report(
            run_id="run-html-001",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        html_text = HTMLReportBuilder.render_html(report)

        assert "<html" in html_text
        assert "run-html-001" in html_text
        assert "Parsing Errors (1)" in html_text
        assert "src/broken.pnl" in html_text
        assert "PNL 구문 파싱 실패" in html_text
        assert "CTL-RES-001" in html_text

    def test_export_html_file(self, report_data: tuple[list[ParsedFile], list[Violation]], tmp_path: Path):
        """export_html 파일 내보내기 검증."""
        parsed_files, violations = report_data
        report = ReportBuilder.build_report(
            run_id="run-html-file",
            rule_source="client.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        out_html = tmp_path / "review_report.html"
        saved_path = HTMLReportBuilder.export_html(report, out_html)

        assert saved_path.exists()
        content = saved_path.read_text(encoding="utf-8")
        assert "</html>" in content

    def test_render_html_no_external_cdns(self, report_data: tuple[list[ParsedFile], list[Violation]]):
        """외부 CDN(http://, https://) 의존성이 없는지 검증."""
        parsed_files, violations = report_data
        report = ReportBuilder.build_report(
            run_id="run-cdn-check",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        html_text = HTMLReportBuilder.render_html(report)

        assert "http://" not in html_text
        assert "https://" not in html_text

    def test_render_html_with_checklist_applicability(self, report_data: tuple[list[ParsedFile], list[Violation]]):
        """checklist_applicability 정보가 HTML 보고서 내 추적성 테이블로 렌더링되는지 검증."""
        from app.core.models import AutomationMode, ChecklistApplicability

        parsed_files, violations = report_data
        report = ReportBuilder.build_report(
            run_id="run-ca-001",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        ca_item = ChecklistApplicability(
            checklist_item="Server-Res-Check-01",
            automation_mode=AutomationMode.AUTO_FULL,
            required_rule_ids=["CTL-RES-001"],
            resolved_rule_ids=["CTL-RES-001"],
            missing_rule_ids=[],
            status="resolved",
        )
        report.checklist_applicability = [ca_item]

        html_text = HTMLReportBuilder.render_html(report)

        assert "Checklist Applicability & Traceability Table (1)" in html_text
        assert "Server-Res-Check-01" in html_text
        assert "resolved" in html_text

    def test_render_html_with_interactive_filter_bar(self, report_data: tuple[list[ParsedFile], list[Violation]]):
        """HTML 보고서에 실시간 심각도/상태 필터 및 텍스트 검색 컨트롤 바가 렌더링되는지 검증."""
        parsed_files, violations = report_data
        report = ReportBuilder.build_report(
            run_id="run-filter-001",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        html_text = HTMLReportBuilder.render_html(report)

        assert "filter-bar" in html_text
        assert "filterViolations('SEV', 'CRITICAL')" in html_text
        assert "searchViolations()" in html_text
        assert 'class="v-row"' in html_text

    def test_render_html_with_side_by_side_diff(self, report_data: tuple[list[ParsedFile], list[Violation]]):
        """HTML 보고서에 좌우 대조 Diff(Side-by-Side Code Viewer) 영역이 렌더링되는지 검증."""
        parsed_files, violations = report_data
        if violations:
            violations[0].snippet = "dpGet('System1:Valve.val', x);"
            violations[0].ai_analysis = "```\ndpGet('System1:Valve.val', x);\nif (rc != 0) return;\n```"

        report = ReportBuilder.build_report(
            run_id="run-sbs-001",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        html_text = HTMLReportBuilder.render_html(report)

        assert "diff-sbs-box" in html_text
        assert "좌우 대조 Diff (Side-by-Side Code Viewer)" in html_text
        assert "[- 원본 스니펫 (Original)]" in html_text
        assert "[+ 안전 대안 코드 (Safe Code)]" in html_text



