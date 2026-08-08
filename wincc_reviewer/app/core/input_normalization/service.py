"""
입력 정규화 서비스 (TRD §5.1 & Phase 1 기준).

입력 파일의 확장자에 따라 적절한 파서(CTL/PNL/XML)로 디스패치하고,
canonical text/IR 변환 및 원본·정규화 SHA256, 인코딩, 줄바꿈 방식을 기록합니다.
미지원 확장자인 경우 예외 발생 없이 ParseStatus(status="unsupported")를 반환합니다.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.core.models import ParseStatus, ParseStatusType
from app.core.parser.base_parser import ParsedFile, Parser
from app.core.parser.ctl_parser import CTLParser
from app.core.parser.pnl_parser import PNLParser
from app.core.parser.xml_parser import XMLParser

logger = logging.getLogger(__name__)


class NormalizationService:
    """입력 정규화 서비스 및 파서 디스패처."""

    PARSER_MAP: dict[str, type[Parser]] = {
        ".ctl": CTLParser,
        ".pnl": PNLParser,
        ".xml": XMLParser,
    }
    _CACHE: dict[tuple[str, float], ParsedFile] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """파싱 결과 캐시를 초기화합니다."""
        cls._CACHE.clear()

    @classmethod
    def _resolve_parser(cls, path: Path) -> tuple[str, type[Parser] | None]:
        """파일명에서 실제 파서 유형 및 파서 클래스를 추출합니다."""
        name_lower = path.name.lower()
        if name_lower.endswith(".ctl") or ".ctl." in name_lower or name_lower.endswith("_ctl.txt"):
            return ".ctl", CTLParser
        if name_lower.endswith(".pnl") or ".pnl." in name_lower or name_lower.endswith("_pnl.txt"):
            return ".pnl", PNLParser
        if name_lower.endswith(".xml") or ".xml." in name_lower or name_lower.endswith("_xml.txt"):
            return ".xml", XMLParser

        ext = path.suffix.lower()
        return ext, cls.PARSER_MAP.get(ext)

    @classmethod
    def normalize_and_parse(cls, path: Path, extract_scripts_only: bool = True) -> ParsedFile:
        """
        파일을 확장자에 맞춰 자동 파싱하고 정규화 메타데이터를 기록합니다. (mtime 기반 캐싱 지원)

        Args:
            path: 파싱 및 정규화 대상 파일 경로
            extract_scripts_only: PNL/XML에서 스크립트만 정제 파싱할지 여부

        Returns:
            ParsedFile IR
        """
        path = Path(path)

        # mtime 기반 파싱 캐시 탐색 (옵션 키 추가)
        cache_key = None
        if path.exists():
            try:
                mtime = path.stat().st_mtime
                cache_key = (str(path.resolve()), mtime, extract_scripts_only)
                if cache_key in cls._CACHE:
                    logger.debug("파싱 캐시 적중(Cache Hit): %s", path)
                    return cls._CACHE[cache_key]
            except Exception:
                pass

        ext, parser_cls = cls._resolve_parser(path)

        # 미지원 확장자 처리
        if parser_cls is None:
            logger.info("지원하지 않는 확장자 스킵: %s (%s)", path, ext)
            return ParsedFile(
                file_path=path,
                file_type=ext.lstrip("."),
                parse_status=ParseStatus(
                    status=ParseStatusType.UNSUPPORTED,
                    file=str(path),
                    error_message=f"지원하지 않는 파일 확장자입니다: '{ext}'",
                ),
            )

        # 파서 실행 (PNL, XML 파서인 경우 extract_scripts_only 주입)
        if parser_cls in (PNLParser, XMLParser):
            parser = parser_cls(extract_scripts_only=extract_scripts_only)
        else:
            parser = parser_cls()

        parsed = parser.parse(path)

        # canonical 정보 생성 및 기록
        if parsed.content:
            canonical_text = parsed.content.replace("\r\n", "\n")
            canonical_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
            canonical_file_id = f"{path.stem}_{canonical_sha256[:8]}"

            parsed.canonical_sha256 = canonical_sha256
            parsed.metadata["canonical_file_id"] = canonical_file_id
            parsed.metadata["canonical_sha256"] = canonical_sha256

        # 캐시 저장
        if cache_key is not None:
            cls._CACHE[cache_key] = parsed

        return parsed
