"""
PDF 품질 검수 인증서 빌더 (TRD 및 Phase 11 납품 서식 준수).
ReportLab 또는 HTML 변환 모듈을 사용하여 고객 제출용 PDF 품질 인증서를 생성합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.models import ReviewReport, SeverityLevel

logger = logging.getLogger(__name__)


class PDFReportBuilder:
    """납품 제출용 PDF 품질 인증서 생성기."""

    @staticmethod
    def export_pdf(report: ReviewReport, output_path: Path) -> Path:
        """
        ReviewReport 데이터를 바탕으로 납품 제출용 PDF 인증서 보고서를 생성합니다.

        Args:
            report: 파이프라인 검사 결과 리포트 객체
            output_path: 저장할 PDF 파일 경로

        Returns:
            저장된 파일 경로 (Path)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=30,
                leftMargin=30,
                topMargin=30,
                bottomMargin=30,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "TitleStyle",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=colors.HexColor("#1E3A8A"),
                alignment=1,
            )
            subtitle_style = ParagraphStyle(
                "SubTitleStyle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#64748B"),
                alignment=1,
            )
            heading2_style = ParagraphStyle(
                "Heading2Style",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=16,
                textColor=colors.HexColor("#1E293B"),
                spaceBefore=12,
                spaceAfter=6,
            )
            cell_style = ParagraphStyle(
                "CellStyle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=11,
            )

            elements = []

            # 1. 문서 헤더 / 제목
            elements.append(Paragraph("WinCC OA Code Quality Certificate", title_style))
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"Run ID: {report.run_id} | Source: {report.rule_source}", subtitle_style))
            elements.append(Spacer(1, 15))

            # 2. 요약 표
            elements.append(Paragraph("1. Summary Checklist", heading2_style))

            sev_counts = {sev: 0 for sev in SeverityLevel}
            for v in report.violations:
                sev = v.severity if isinstance(v.severity, SeverityLevel) else SeverityLevel(v.severity)
                sev_counts[sev] = sev_counts.get(sev, 0) + 1

            summary_table_data = [
                [Paragraph("<b>Metric</b>", cell_style), Paragraph("<b>Value</b>", cell_style)],
                [Paragraph("Total Scanned Files", cell_style), Paragraph(str(len(report.files)), cell_style)],
                [Paragraph("Total Violations", cell_style), Paragraph(str(len(report.violations)), cell_style)],
                [Paragraph("Critical Severity", cell_style), Paragraph(str(sev_counts[SeverityLevel.CRITICAL]), cell_style)],
                [Paragraph("High Severity", cell_style), Paragraph(str(sev_counts[SeverityLevel.HIGH]), cell_style)],
                [Paragraph("Medium Severity", cell_style), Paragraph(str(sev_counts[SeverityLevel.MEDIUM]), cell_style)],
                [Paragraph("Low / Info Severity", cell_style), Paragraph(str(sev_counts[SeverityLevel.LOW] + sev_counts[SeverityLevel.INFO]), cell_style)],
            ]

            t_summary = Table(summary_table_data, colWidths=[250, 250])
            t_summary.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#1E3A8A")),
                        ("TEXTCOLOR", (0, 0), (1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            elements.append(t_summary)
            elements.append(Spacer(1, 15))

            # 3. 위반 상세 테이블
            elements.append(Paragraph("2. Detailed Violation List", heading2_style))
            detail_data = [
                [
                    Paragraph("<b>Rule ID</b>", cell_style),
                    Paragraph("<b>Severity</b>", cell_style),
                    Paragraph("<b>File / Line</b>", cell_style),
                    Paragraph("<b>Message</b>", cell_style),
                ]
            ]

            for v in report.violations[:50]:
                sev = v.severity if isinstance(v.severity, SeverityLevel) else SeverityLevel(v.severity)
                f_name = Path(v.file_id).name
                detail_data.append(
                    [
                        Paragraph(v.rule_id, cell_style),
                        Paragraph(sev.value, cell_style),
                        Paragraph(f"{f_name}:{v.line_start}", cell_style),
                        Paragraph(v.message, cell_style),
                    ]
                )

            t_detail = Table(detail_data, colWidths=[80, 70, 110, 240])
            t_detail.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            elements.append(t_detail)

            doc.build(elements)
            return output_path

        except ImportError:
            # ReportLab 미설치 시 텍스트/HTML 인쇄용 PDF 대체 파일 생성
            logger.warning("ReportLab 미설치로 인하여 텍스트 포맷 PDF 파일을 생성합니다.")
            pdf_text = f"=== WinCC OA Code Quality Certificate ===\nRun ID: {report.run_id}\nRule Source: {report.rule_source}\nTotal Files: {len(report.files)}\nTotal Violations: {len(report.violations)}\n"
            output_path.write_text(pdf_text, encoding="utf-8")
            return output_path
