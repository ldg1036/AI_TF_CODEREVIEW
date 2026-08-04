"""
통합 리포트 생성기 (TRD §5.7, TRD §6 & 09_구현착수_패키지_계약.md §4 기준).

파싱 결과, 룰 위반 목록, 파싱 실패 에러(Errors 섹션), 실행 지표(Metrics)를
하나의 ReviewReport 모델로 통합하고 JSON 리포트로 출력합니다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app import __version__
from app.core.models import Metrics, ParseStatus, ParseStatusType, ReviewReport, Violation
from app.core.parser.base_parser import ParsedFile


class ReportEncoder(json.JSONEncoder):
    """ReviewReport JSON 직렬화용 커스텀 엔코더."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, Path):
            return str(obj)
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)


class ReportBuilder:
    """통합 리뷰 리포트 생성기."""

    SCHEMA_VERSION = "1.0.0"

    @classmethod
    def build_report(
        cls,
        run_id: str,
        rule_source: str,
        parsed_files: list[ParsedFile],
        violations: list[Violation],
        metrics: Metrics | None = None,
        ruleset_version: str = "1.0.0",
        ruleset_source_sha256: str = "",
    ) -> ReviewReport:
        """
        리뷰 파이프라인 결과를 ReviewReport 모델로 통합합니다.

        Errors 섹션 분리 규격:
            parse_status.status == parse_failed 인 파일은
            violations에 섞이지 않고 errors 목록에 수집됩니다.

        Args:
            run_id: 파이프라인 실행 식별자
            rule_source: 사용된 Excel 룰 원천 파일명/경로
            parsed_files: 파싱된 파일 IR 목록
            violations: 검출된 위반 사항 목록
            metrics: 실행 지표 (None일 경우 자동 생성)
            ruleset_version: 룰셋 버전
            ruleset_source_sha256: Excel 원천 SHA256

        Returns:
            ReviewReport
        """
        file_paths = [str(p.file_path) for p in parsed_files]

        # 파싱 실패 파일들을 errors 섹션으로 별도 분류 (DoD)
        errors: list[ParseStatus] = [
            p.parse_status
            for p in parsed_files
            if p.parse_status.status == ParseStatusType.PARSE_FAILED
        ]

        if metrics is None:
            metrics = Metrics()

        metrics.file_count = len(parsed_files)
        metrics.violation_count = len(violations)

        now_utc = datetime.now(timezone.utc)

        return ReviewReport(
            schema_version=cls.SCHEMA_VERSION,
            run_id=run_id,
            rule_source=rule_source,
            files=file_paths,
            violations=violations,
            errors=errors,
            metrics=metrics,
            ruleset_version=ruleset_version,
            ruleset_source_sha256=ruleset_source_sha256,
            app_version=__version__,
            generated_at=now_utc,
        )

    @classmethod
    def to_dict(cls, report: ReviewReport) -> dict[str, Any]:
        """ReviewReport 객체를 JSON 직렬화 가능한 dict로 변환합니다."""
        raw_json = json.dumps(report, cls=ReportEncoder, ensure_ascii=False)
        return json.loads(raw_json)

    @classmethod
    def export_json(cls, report: ReviewReport, output_path: Path) -> Path:
        """
        ReviewReport 객체를 JSON 파일로 내보냅니다 (utf-8 인코딩).

        Args:
            report: 통합 리뷰 리포트 객체
            output_path: 저장할 JSON 파일 경로

        Returns:
            저장된 파일 경로
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        report_dict = cls.to_dict(report)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        return path
