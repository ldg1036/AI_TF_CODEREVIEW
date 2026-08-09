"""
PNLParser 유닛 테스트 (TRD §5.1 & Phase 1 기준).

검증 항목:
1. XML 기반 PNL 파일 도형 및 이벤트 핸들러 파싱
2. 텍스트 기반 PNL 파일 이벤트 핸들러 폴백 파싱
3. CP949 / UTF-8 인코딩 감지 및 디코딩 검증
4. 존재하지 않는 파일 읽기 시 예외 없이 parse_failed 반환
"""

from __future__ import annotations

from pathlib import Path

from app.core.models import ParseStatusType
from app.core.parser.pnl_parser import PNLParser


class TestPNLParser:
    """PNLParser 유닛 테스트."""

    def test_parse_xml_pnl_file(self, tmp_path: Path):
        """XML 형태의 PNL 파일 파싱 테스트."""
        xml_pnl_content = """<?xml version="1.0" encoding="UTF-8"?>
<panel name="MainPanel">
    <shapes>
        <shape name="BtnSubmit" type="PUSH_BUTTON">
            <properties>
                <prop name="Text">제출</prop>
            </properties>
        </shape>
    </shapes>
    <scripts>
        <script event="Click" shape="BtnSubmit">
            dpSet("System1:Pump1.Cmd", 1);
        </script>
    </scripts>
</panel>
"""
        sample_file = tmp_path / "panel_xml.pnl"
        sample_file.write_text(xml_pnl_content, encoding="utf-8")

        parser = PNLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "pnl"
        assert parsed.metadata["is_xml_format"] is True

        shapes = parsed.metadata["shapes"]
        events = parsed.metadata["event_handlers"]

        assert len(shapes) >= 1
        assert shapes[0]["name"] == "BtnSubmit"

        assert len(events) >= 1
        assert events[0]["event_name"] == "Click"
        assert "dpSet(" in events[0]["script_body"]

    def test_parse_text_pnl_file(self, tmp_path: Path):
        """텍스트 형태의 PNL 파일 파싱 폴백 테스트."""
        text_pnl_content = """V 2
CB 1
shape Button1
Initialize()
{
    dpConnect("cbTemp", "Sys1:Tank.Temp");
}
Click()
{
    dpSet("Sys1:Tank.Cmd", 1);
}
"""
        sample_file = tmp_path / "panel_text.pnl"
        sample_file.write_text(text_pnl_content, encoding="utf-8")

        parser = PNLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "pnl"
        assert parsed.metadata["is_xml_format"] is False

        events = parsed.metadata["event_handlers"]
        event_names = [e["event_name"] for e in events]
        assert "Initialize" in event_names
        assert "Click" in event_names

    def test_parse_encoding_cp949_pnl(self, tmp_path: Path):
        """CP949 인코딩 PNL 파일 디코딩 검증."""
        cp949_pnl_content = """// 한글 패널 주석
shape 버튼_제출
Initialize()
{
    // 초기화 스크립트
}
"""
        sample_file = tmp_path / "panel_cp949.pnl"
        with open(sample_file, "wb") as f:
            f.write(cp949_pnl_content.encode("cp949"))

        parser = PNLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.detected_encoding in ["cp949", "euc-kr"]
        assert "한글 패널 주석" in parsed.metadata["raw_content"]

    def test_parse_non_existent_pnl(self):
        """존재하지 않는 파일에 대한 parse_failed 반환 검증."""
        parser = PNLParser()
        parsed = parser.parse(Path("non_existent_panel.pnl"))

        assert parsed.parse_status.status == ParseStatusType.PARSE_FAILED
        assert parsed.parse_status.error_message is not None
        assert "찾을 수 없습니다" in parsed.parse_status.error_message
