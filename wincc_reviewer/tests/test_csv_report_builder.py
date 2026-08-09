"""
CSVReportBuilder 유닛 테스트 (utf-8-sig 인코딩 검증).
"""

from __future__ import annotations

import codecs
from pathlib import Path

from app.core.models import SeverityLevel, Violation, ViolationStatus
from app.core.report.csv_report_builder import CSVReportBuilder
from app.core.report.report_builder import ReportBuilder


class TestCSVReportBuilder:
    """CSVReportBuilder 유닛 테스트."""

    def test_export_csv_utf8_sig(self, tmp_path: Path):
        """CSV export 및 utf-8-sig 인코딩 검증."""
        violation = Violation(
            violation_id="V-001",
            rule_id="CTL-RES-001",
            file_id="src/main.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.HIGH,
            message="한글 테스트 메시지",
        )
        report = ReportBuilder.build_report(
            run_id="run-csv-test",
            rule_source="server.xlsx",
            parsed_files=[],
            violations=[violation],
        )

        out_csv = tmp_path / "report.csv"
        saved = CSVReportBuilder.export_csv(report, out_csv)

        assert saved.exists()
        raw_bytes = saved.read_bytes()
        assert raw_bytes.startswith(codecs.BOM_UTF8)

        text = saved.read_text(encoding="utf-8-sig")
        assert "CTL-RES-001" in text
        assert "한글 테스트 메시지" in text

    def test_export_csv_with_checklist_applicability(self, tmp_path: Path):
        """CSV export 시 checklist_applicability 내역이 포함되는지 검증."""
        from app.core.models import AutomationMode, ChecklistApplicability

        report = ReportBuilder.build_report(
            run_id="run-csv-ca",
            rule_source="client.xlsx",
            parsed_files=[],
            violations=[],
        )

        ca_item = ChecklistApplicability(
            checklist_item="Client-Check-01",
            automation_mode=AutomationMode.AUTO_FULL,
            required_rule_ids=["CTL-RES-001"],
            resolved_rule_ids=["CTL-RES-001"],
            status="resolved",
        )
        report.checklist_applicability = [ca_item]

        out_csv = tmp_path / "report_ca.csv"
        saved = CSVReportBuilder.export_csv(report, out_csv)

        text = saved.read_text(encoding="utf-8-sig")
        assert "CHECKLIST_TRACEABILITY" in text
        assert "Client-Check-01" in text

