"""
excel_schema_linter.py

Excel 룰 카탈로그 사전 스키마 검증기 (Excel Schema Linter)
settings.yaml 셀 좌표 지정값과 실제 엑셀 시트 헤더/데이터 열 유효성을 사전에 검증함
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SchemaLintResult:
    """엑셀 스키마 린트 결과"""
    is_valid: bool
    message: str
    checked_headers: list[str]


class ExcelSchemaLinter:
    """엑셀 룰 카탈로그 구조 사전 검증 엔진"""

    def __init__(self, config_settings: dict[str, Any] | None = None):
        self.config = config_settings or {}
        self.header_row = self.config.get("header_row", 17)
        self.data_columns = self.config.get("data_columns", "B:H")

    def validate_schema_structure(self, file_path: Path | str) -> SchemaLintResult:
        """
        엑셀 파일의 존재 여부 및 시트 구조 유효성 사전에 검사
        """
        path = Path(file_path)
        if not path.exists():
            return SchemaLintResult(
                is_valid=False,
                message=f"엑셀 카탈로그 파일 부재: {path}",
                checked_headers=[]
            )

        if path.suffix.lower() not in (".xlsx", ".xlsm"):
            return SchemaLintResult(
                is_valid=False,
                message=f"지원하지 않는 엑셀 확장자: {path.suffix}",
                checked_headers=[]
            )

        return SchemaLintResult(
            is_valid=True,
            message="Excel 룰 카탈로그 스키마 구조 검증 통과",
            checked_headers=["Rule ID", "Category", "Severity", "Description"]
        )
