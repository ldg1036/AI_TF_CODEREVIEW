"""
NormalizationService 유닛 테스트 (TRD §5.1 & Phase 1 기준).

검증 항목:
1. .ctl, .pnl, .xml 파일 확장자별 파서 자동 디스패치
2. canonical_file_id 및 canonical_sha256 산출 검증
3. 미지원 확장자(.txt, .csv 등)에 대한 unsupported 상태 반환
4. 파싱 실패 파일의 parse_failed 상태 전파 검증
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.input_normalization.service import NormalizationService
from app.core.models import ParseStatusType


class TestNormalizationService:
    """NormalizationService 유닛 테스트."""

    def test_normalize_ctl_file(self, tmp_path: Path):
        """CTL 파일 정규화 파싱 및 디스패치 테스트."""
        ctl_content = "void main() { dpConnect('cb', 'dpe'); }"
        ctl_file = tmp_path / "test_script.ctl"
        ctl_file.write_text(ctl_content, encoding="utf-8")

        parsed = NormalizationService.normalize_and_parse(ctl_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "ctl"
        assert parsed.canonical_sha256 is not None
        assert "canonical_file_id" in parsed.metadata
        assert parsed.metadata["canonical_file_id"].startswith("test_script_")

    def test_normalize_pnl_file(self, tmp_path: Path):
        """PNL 파일 정규화 파싱 및 디스패치 테스트."""
        pnl_content = "shape Btn1\nClick()\n{\n    dpSet('dpe', 1);\n}"
        pnl_file = tmp_path / "panel1.pnl"
        pnl_file.write_text(pnl_content, encoding="utf-8")

        parsed = NormalizationService.normalize_and_parse(pnl_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "pnl"
        assert parsed.canonical_sha256 is not None

    def test_normalize_xml_file(self, tmp_path: Path):
        """XML 파일 정규화 파싱 및 디스패치 테스트."""
        xml_content = "<root><data>10</data></root>"
        xml_file = tmp_path / "config.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        parsed = NormalizationService.normalize_and_parse(xml_file)

        assert parsed.parse_status.status == ParseStatusType.PARSED
        assert parsed.file_type == "xml"
        assert parsed.canonical_sha256 is not None

    def test_normalize_unsupported_file(self, tmp_path: Path):
        """미지원 확장자 파일에 대해 예외 없이 unsupported 반환 검증."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("random notes", encoding="utf-8")

        parsed = NormalizationService.normalize_and_parse(txt_file)

        assert parsed.parse_status.status == ParseStatusType.UNSUPPORTED
        assert parsed.parse_status.error_message is not None
        assert "지원하지 않는 파일 확장자" in parsed.parse_status.error_message

    def test_normalize_parse_failed_file(self, tmp_path: Path):
        """손상된 XML 파일 파싱 시 parse_failed 상태 유지 검증."""
        bad_xml_file = tmp_path / "bad.xml"
        bad_xml_file.write_text("<root><unclosed>", encoding="utf-8")

        parsed = NormalizationService.normalize_and_parse(bad_xml_file)

        assert parsed.parse_status.status == ParseStatusType.PARSE_FAILED
        assert parsed.parse_status.error_message is not None
        assert "XML 구문 오류" in parsed.parse_status.error_message

    def test_normalization_caching(self, tmp_path: Path):
        """동일 파일 재파싱 시 캐시 적중(Cache Hit) 동작 검증."""
        ctl_content = "void main() { delay(1); }"
        ctl_file = tmp_path / "cache_test.ctl"
        ctl_file.write_text(ctl_content, encoding="utf-8")

        NormalizationService.clear_cache()
        parsed1 = NormalizationService.normalize_and_parse(ctl_file)
        parsed2 = NormalizationService.normalize_and_parse(ctl_file)

        assert parsed1 is parsed2

