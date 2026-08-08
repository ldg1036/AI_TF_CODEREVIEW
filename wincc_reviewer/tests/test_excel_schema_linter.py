"""
test_excel_schema_linter.py

ExcelSchemaLinter 린터 모듈 유닛 테스트 (R2 호출부 증명)
"""

from __future__ import annotations

from pathlib import Path
from app.core.rules.excel_schema_linter import ExcelSchemaLinter


class TestExcelSchemaLinter:
    """ExcelSchemaLinter 사전 스키마 검증 기능 테스트"""

    def test_non_existent_file(self, tmp_path: Path):
        linter = ExcelSchemaLinter()
        result = linter.validate_schema_structure(tmp_path / "missing.xlsx")
        assert result.is_valid is False
        assert "부재" in result.message

    def test_invalid_extension(self, tmp_path: Path):
        invalid_file = tmp_path / "catalog.txt"
        invalid_file.write_text("dummy", encoding="utf-8")
        linter = ExcelSchemaLinter()
        result = linter.validate_schema_structure(invalid_file)
        assert result.is_valid is False
        assert "지원하지 않는" in result.message

    def test_valid_file_extension(self, tmp_path: Path):
        valid_file = tmp_path / "catalog.xlsx"
        valid_file.write_text("dummy", encoding="utf-8")
        linter = ExcelSchemaLinter(config_settings={"header_row": 17, "data_columns": "B:H"})
        result = linter.validate_schema_structure(valid_file)
        assert result.is_valid is True
        assert len(result.checked_headers) > 0
