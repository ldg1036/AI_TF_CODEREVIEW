"""
ExcelRuleLoader 및 Excel 파싱 검증 테스트.

08_ADR_실제_Excel_양식_계약.md 준수 여부 검증:
- Client 파일: 18~32행 파싱, 총 15개 항목
- Server 파일: 18~37행 파싱, 총 20개 항목
- 병합셀 대분류/중분류 상속 적용 확인 (빈 값 없음)
- 제외 행(33행/38행 이후 빈행 및 문구) 미파싱 확인
- SHA256 해시값 산출 확인
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.rules.excel_rule_loader import ExcelRuleLoader


class TestExcelRuleLoader:
    """ExcelRuleLoader 기능 및 실제 Excel 파싱 테스트."""

    @pytest.fixture
    def client_excel_path(self, config_dir: Path) -> Path:
        """Client Excel 파일 경로."""
        path = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
        assert path.exists(), f"Client Excel 파일을 찾을 수 없음: {path}"
        return path

    @pytest.fixture
    def server_excel_path(self, config_dir: Path) -> Path:
        """Server Excel 파일 경로."""
        path = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
        assert path.exists(), f"Server Excel 파일을 찾을 수 없음: {path}"
        return path

    def test_parse_client_excel_item_count(self, client_excel_path: Path):
        """Client Excel 파싱 시 15개 항목이 정확히 로드되는지 확인."""
        rows, sha256_hash = ExcelRuleLoader.load_excel(client_excel_path)

        assert len(sha256_hash) == 64
        assert len(rows) == 15, f"Client Excel 파싱 결과 항목 수가 15개가 아닙니다. (실제: {len(rows)})"

        # 시작/끝 행 범위 검증 (18행 ~ 32행)
        assert rows[0].row_index == 18
        assert rows[-1].row_index == 32

    def test_parse_server_excel_item_count(self, server_excel_path: Path):
        """Server Excel 파싱 시 20개 항목이 정확히 로드되는지 확인."""
        rows, sha256_hash = ExcelRuleLoader.load_excel(server_excel_path)

        assert len(sha256_hash) == 64
        assert len(rows) == 20, f"Server Excel 파싱 결과 항목 수가 20개가 아닙니다. (실제: {len(rows)})"

        # 시작/끝 행 범위 검증 (18행 ~ 37행)
        assert rows[0].row_index == 18
        assert rows[-1].row_index == 37

    def test_merged_cell_inheritance(self, client_excel_path: Path, server_excel_path: Path):
        """병합셀 상속으로 인해 모든 행의 category 및 subcategory가 비어있지 않은지 검증."""
        client_rows, _ = ExcelRuleLoader.load_excel(client_excel_path)
        for row in client_rows:
            assert row.category != "", f"행 {row.row_index}의 category가 빈 값입니다 (병합셀 상속 실패)."
            assert row.subcategory != "", f"행 {row.row_index}의 subcategory가 빈 값입니다 (병합셀 상속 실패)."
            assert row.check_item != "", f"행 {row.row_index}의 check_item이 빈 값입니다."
            assert row.source_key != "", f"행 {row.row_index}의 source_key가 빈 값입니다."

        server_rows, _ = ExcelRuleLoader.load_excel(server_excel_path)
        for row in server_rows:
            assert row.category != "", f"행 {row.row_index}의 category가 빈 값입니다 (병합셀 상속 실패)."
            assert row.subcategory != "", f"행 {row.row_index}의 subcategory가 빈 값입니다 (병합셀 상속 실패)."
            assert row.check_item != "", f"행 {row.row_index}의 check_item이 빈 값입니다."
            assert row.source_key != "", f"행 {row.row_index}의 source_key가 빈 값입니다."

    def test_source_key_format(self, client_excel_path: Path):
        """source_key 생성 포맷(category|subcategory|check_item) 검증."""
        rows, _ = ExcelRuleLoader.load_excel(client_excel_path)
        first_row = rows[0]
        expected_key = f"{first_row.category}|{first_row.subcategory}|{first_row.check_item}"
        assert first_row.source_key == expected_key
