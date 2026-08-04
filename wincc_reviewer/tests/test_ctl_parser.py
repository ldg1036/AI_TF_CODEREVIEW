"""
CTLParser 유닛 테스트 (TRD §5.1 & Phase 1 기준).

검증 항목:
1. CTL 파일 정상 파싱 (함수, 전역변수, 주석 추출)
2. CP949 / UTF-8 인코딩 감지 및 디코딩 검증
3. 존재하지 않는 파일 또는 에러 발생 시 예외 없이 parse_failed 반환 (DoD)
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.models import ParseStatusType
from app.core.parser.ctl_parser import CTLParser


class TestCTLParser:
    """CTLParser 유닛 테스트."""

    def test_parse_valid_ctl_script(self, tmp_path: Path):
        """정상 CTL 스크립트 파일 파싱 테스트."""
        ctl_code = """// WinCC OA Test Script
int g_counter = 0;
string g_serverIp = "127.0.0.1";

void main()
{
    dpConnect("cbTemp", "Sys1:Tank.Temp");
}

int calculateSum(int a, int b)
{
    return a + b;
}
"""
        sample_file = tmp_path / "sample_script.ctl"
        sample_file.write_text(ctl_code, encoding="utf-8")

        parser = CTLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "ctl"
        assert parsed.original_sha256 != ""
        assert parsed.detected_encoding in ["utf-8", "utf-8-sig"]

        metadata = parsed.metadata
        functions = metadata["functions"]
        global_vars = metadata["global_variables"]

        # 함수 추출 검증
        func_names = [f["name"] for f in functions]
        assert "main" in func_names
        assert "calculateSum" in func_names

        # 전역변수 추출 검증
        var_names = [v["name"] for v in global_vars]
        assert "g_counter" in var_names
        assert "g_serverIp" in var_names

        # 주석 검증
        assert 1 in metadata["comment_lines"]

    def test_parse_encoding_cp949(self, tmp_path: Path):
        """CP949(EUC-KR) 인코딩 파일 디코딩 및 파싱 검증."""
        ctl_code_cp949 = """// 한글 주석 테스트
int g_카운터 = 10;

void 메인함수()
{
    // 처리 로직
}
"""
        sample_file = tmp_path / "sample_cp949.ctl"
        with open(sample_file, "wb") as f:
            f.write(ctl_code_cp949.encode("cp949"))

        parser = CTLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.detected_encoding in ["cp949", "euc-kr"]
        assert "한글 주석 테스트" in parsed.content

    def test_parse_non_existent_file(self):
        """존재하지 않는 파일에 대해 예외 없이 parse_failed 반환 검증."""
        parser = CTLParser()
        parsed = parser.parse(Path("non_existent_file_12345.ctl"))

        assert parsed.parse_status.status == ParseStatusType.PARSE_FAILED
        assert parsed.parse_status.error_message is not None
        assert "찾을 수 없습니다" in parsed.parse_status.error_message
