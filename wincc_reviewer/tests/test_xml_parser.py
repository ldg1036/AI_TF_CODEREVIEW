"""
XMLParser 유닛 테스트 (TRD §5.1 & Phase 1 기준).

검증 항목:
1. 정상 XML 파일 트리 구조 파싱
2. 잘못된 XML(Syntax Error) 파일에 대해 예외 없이 parse_failed 반환
3. CP949 / UTF-8 인코딩 감지 및 디코딩 검증
4. 존재하지 않는 파일 읽기 시 parse_failed 반환
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.models import ParseStatusType
from app.core.parser.xml_parser import XMLParser


class TestXMLParser:
    """XMLParser 유닛 테스트."""

    def test_parse_valid_xml(self, tmp_path: Path):
        """정상 XML 파일 파싱 테스트."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0">
    <server name="Server1" ip="127.0.0.1">
        <port>8080</port>
    </server>
    <database type="Raima">
        <max_connections>10</max_connections>
    </database>
</config>
"""
        sample_file = tmp_path / "valid_config.xml"
        sample_file.write_text(xml_content, encoding="utf-8")

        parser = XMLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "xml"
        assert parsed.metadata["root_tag"] == "config"
        assert parsed.metadata["total_nodes"] >= 4

        nodes = parsed.metadata["nodes"]
        tags = [n["tag"] for n in nodes]
        assert "server" in tags
        assert "database" in tags

    def test_parse_invalid_xml(self, tmp_path: Path):
        """문법 오류(Syntax Error) XML 파일에 대해 parse_failed 반환 검증 (DoD)."""
        bad_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<config>
    <server name="Server1">
        <port>8080
</config>
"""
        sample_file = tmp_path / "bad_syntax.xml"
        sample_file.write_text(bad_xml_content, encoding="utf-8")

        parser = XMLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSE_FAILED
        assert parsed.parse_status.error_message is not None
        assert "XML 구문 오류" in parsed.parse_status.error_message

    def test_parse_encoding_cp949_xml(self, tmp_path: Path):
        """CP949 인코딩 XML 파일 디코딩 검증."""
        cp949_xml_content = """<?xml version="1.0" encoding="EUC-KR"?>
<설정 파일="테스트">
    <항목 이름="서버설정">정상작동</항목>
</설정>
"""
        sample_file = tmp_path / "cp949_config.xml"
        with open(sample_file, "wb") as f:
            f.write(cp949_xml_content.encode("cp949"))

        parser = XMLParser()
        parsed = parser.parse(sample_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.detected_encoding in ["cp949", "euc-kr"]
        assert "정상작동" in parsed.content

    def test_parse_non_existent_xml(self):
        """존재하지 않는 파일에 대한 parse_failed 반환 검증."""
        parser = XMLParser()
        parsed = parser.parse(Path("non_existent_file.xml"))

        assert parsed.parse_status.status == ParseStatusType.PARSE_FAILED
        assert parsed.parse_status.error_message is not None
        assert "찾을 수 없습니다" in parsed.parse_status.error_message
