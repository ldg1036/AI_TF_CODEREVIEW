"""
ReportBuilder 유닛 테스트 (TRD §5.7, TRD §6 & 09_구현착수_패키지_계약.md §4 기준).

검증 항목:
1. 정상 파일 + 파싱 실패 파일 혼합 시 errors 섹션 및 violations 섹션 분리 검증 (DoD)
2. export_json 파일 생성 및 UTF-8 JSON 직렬화 검증
3. schemas/review_report.json JSON 스키마 필드 준수 검증
"""

from __future__ import annotations

import json
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
from app.core.report.report_builder import ReportBuilder


class TestReportBuilder:
    """ReportBuilder 유닛 테스트."""

    @pytest.fixture
    def sample_data(self) -> tuple[list[ParsedFile], list[Violation]]:
        """정상 파일, 파싱 실패 파일, 위반 목록 샘플 데이터."""
        parsed_ok1 = ParsedFile(
            file_path=Path("src/main.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="src/main.ctl"),
            content="void main() {}",
        )

        parsed_ok2 = ParsedFile(
            file_path=Path("src/panel.pnl"),
            file_type="pnl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="src/panel.pnl"),
            content="shape Btn1 {}",
        )

        parsed_failed = ParsedFile(
            file_path=Path("src/bad.xml"),
            file_type="xml",
            parse_status=ParseStatus(
                status=ParseStatusType.PARSE_FAILED,
                file="src/bad.xml",
                error_message="XML 구문 오류 (Syntax Error)",
            ),
            content="",
        )

        violation1 = Violation(
            violation_id="V-CTL-001",
            rule_id="CTL-RES-001",
            file_id="src/main.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.CRITICAL,
            message="dpConnect 대응 dpDisconnect 누락",
        )

        violation2 = Violation(
            violation_id="V-MANUAL-001",
            rule_id="MANUAL-001",
            file_id="src/panel.pnl",
            status=ViolationStatus.MANUAL_REVIEW,
            severity=SeverityLevel.INFO,
            message="[MANUAL_REVIEW] Try-catch 수동 검토 필요",
        )

        return [parsed_ok1, parsed_ok2, parsed_failed], [violation1, violation2]

    def test_build_report_with_errors_section(self, sample_data: tuple[list[ParsedFile], list[Violation]]):
        """parse_failed 파일이 errors 섹션에 독립적으로 분리되는지 검증 (DoD)."""
        parsed_files, violations = sample_data

        report = ReportBuilder.build_report(
            run_id="run-20260802-001",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        assert report.run_id == "run-20260802-001"
        assert report.rule_source == "server.xlsx"
        assert len(report.files) == 3

        # Violations 검증
        assert len(report.violations) == 2

        # Errors 섹션 독립 수집 검증 (DoD)
        assert len(report.errors) == 1
        err = report.errors[0]
        assert err.status == ParseStatusType.PARSE_FAILED
        assert err.file == "src/bad.xml"
        assert err.error_message == "XML 구문 오류 (Syntax Error)"

        # Metrics 검증
        assert report.metrics.file_count == 3
        assert report.metrics.violation_count == 2

    def test_export_json(self, sample_data: tuple[list[ParsedFile], list[Violation]], tmp_path: Path):
        """JSON 리포트 내보내기 및 구조 검증."""
        parsed_files, violations = sample_data
        report = ReportBuilder.build_report(
            run_id="run-test",
            rule_source="client.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        out_json = tmp_path / "report_output.json"
        saved_path = ReportBuilder.export_json(report, out_json)

        assert saved_path.exists()

        with open(saved_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["schema_version"] == "1.0.0"
        assert data["run_id"] == "run-test"
        assert len(data["files"]) == 3
        assert len(data["violations"]) == 2
        assert len(data["errors"]) == 1

        # Error 필드 구조 확인
        error_item = data["errors"][0]
        assert error_item["status"] == "parse_failed"
        assert error_item["file"] == "src/bad.xml"
        assert error_item["error_message"] == "XML 구문 오류 (Syntax Error)"

    def test_json_schema_contract(self, sample_data: tuple[list[ParsedFile], list[Violation]], schemas_dir: Path):
        """09_구현착수_패키지_계약.md §4 ReviewReport 필수 필드 검증."""
        parsed_files, violations = sample_data
        report = ReportBuilder.build_report(
            run_id="run-contract",
            rule_source="server.xlsx",
            parsed_files=parsed_files,
            violations=violations,
        )

        report_dict = ReportBuilder.to_dict(report)

        # required: schema_version, run_id, rule_source, files, violations, errors, metrics
        required_keys = ["schema_version", "run_id", "rule_source", "files", "violations", "errors", "metrics"]
        for key in required_keys:
            assert key in report_dict, f"ReviewReport 필수 필드 누락: {key}"
