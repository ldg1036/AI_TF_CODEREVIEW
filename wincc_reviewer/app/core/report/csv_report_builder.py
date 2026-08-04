"""
CSV 리포트 내보내기 모듈 (utf-8-sig 인코딩 준수).

ReviewReport 객체를 utf-8-sig 인코딩의 CSV 파일로 내보냅니다.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from app.core.models import ReviewReport

logger = logging.getLogger(__name__)


class CSVReportBuilder:
    """CSV 리뷰 리포트 생성기."""

    @classmethod
    def export_csv(cls, report: ReviewReport, output_path: Path) -> Path:
        """
        ReviewReport 객체를 utf-8-sig 인코딩 CSV 파일로 내보냅니다.

        Args:
            report: 통합 리뷰 리포트
            output_path: 저장할 CSV 파일 경로

        Returns:
            저장된 파일 경로
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            # 헤더 작성
            writer.writerow(["Status", "Severity", "RuleID", "File", "Line", "Message", "AIAnalysis"])

            # 1. 파싱 에러 표기
            for err in report.errors:
                writer.writerow([
                    str(err.status.value if hasattr(err.status, "value") else err.status),
                    "Error",
                    "PARSE_ERROR",
                    err.file,
                    "",
                    err.error_message or "파싱 실패 사유 미기재",
                    "",
                ])

            # 2. 위반 사항 표기
            for v in report.violations:
                line_str = str(v.line_start) if v.line_start is not None else ""
                writer.writerow([
                    str(v.status.value if hasattr(v.status, "value") else v.status),
                    str(v.severity.value if hasattr(v.severity, "value") else v.severity),
                    v.rule_id,
                    v.file_id,
                    line_str,
                    v.message,
                    v.ai_analysis,
                ])

            # 3. 체크리스트 적용성 매핑 정보 표기 (TRD §6 추적성)
            if hasattr(report, "checklist_applicability") and report.checklist_applicability:
                for ca in report.checklist_applicability:
                    mode_str = str(ca.automation_mode.value if hasattr(ca.automation_mode, "value") else ca.automation_mode)
                    req_rules = ", ".join(ca.required_rule_ids) if ca.required_rule_ids else "-"
                    res_rules = ", ".join(ca.resolved_rule_ids) if ca.resolved_rule_ids else "-"
                    msg = f"Checklist Item: {ca.checklist_item} (Mode: {mode_str}, Resolved Rules: {res_rules})"
                    writer.writerow([
                        str(ca.status),
                        "ChecklistMapping",
                        "CHECKLIST_TRACEABILITY",
                        ca.checklist_item,
                        "",
                        msg,
                        f"RequiredRules: {req_rules}",
                    ])

        logger.info("CSV 리포트 내보내기 완료: %s", path)
        return path
