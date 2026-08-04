"""
WinCC OA PNL (패널) 파서 (TRD §5.1 & Phase 1 기준).

WinCC OA의 .pnl 화면 패널 파일(XML 구조 또는 텍스트 구조)을 분석하여
도형(Shape) 및 이벤트 핸들러(Initialize, Click 등) 내에 포함된 임베디드 CTRL 스크립트를 추출하고
인코딩 감지 및 파싱 실패 시 안전하게 parse_failed 상태를 반환합니다.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from app.core.models import ParseStatus, ParseStatusType
from app.core.parser.base_parser import ParsedFile, Parser, create_failed_parse


@dataclass
class PNLShapeInfo:
    """PNL 도형(Shape) 정보."""

    name: str
    shape_type: str
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class PNLEventHandlerInfo:
    """PNL 임베디드 이벤트 핸들러 정보."""

    event_name: str
    shape_name: str
    script_body: str
    line_number: int = 0


@dataclass
class PNLParsedMetadata:
    """PNL 파싱 메타데이터 IR."""

    shapes: list[PNLShapeInfo] = field(default_factory=list)
    event_handlers: list[PNLEventHandlerInfo] = field(default_factory=list)


class PNLParser(Parser):
    """PNL 파일 파서 구현체."""

    SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]

    # 텍스트 기반 PNL 이벤트 핸들러 정규식 패턴 (XML 파싱 실패 시 폴백)
    EVENT_PATTERN = re.compile(
        r"(?:shape|panel)\s*:\s*([a-zA-Z0-9_]+)[\s\S]*?event\s*:?\s*([a-zA-Z0-9_]+)[\s\S]*?\{([\s\S]*?)\}",
        re.IGNORECASE,
    )

    def parse(self, path: Path) -> ParsedFile:
        """
        .pnl 파일을 파싱하여 ParsedFile IR을 생성합니다.

        Args:
            path: 파싱 대상 파일 경로

        Returns:
            ParsedFile IR
        """
        path = Path(path)
        if not path.exists():
            return create_failed_parse(path, f"파일을 찾을 수 없습니다: {path}")

        # 1. 파일 읽기 및 인코딩 디코딩
        try:
            with open(path, "rb") as f:
                raw_bytes = f.read()
        except Exception as e:
            return create_failed_parse(path, f"파일 읽기 오류: {e}")

        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        content = None
        detected_encoding = ""
        for enc in self.SUPPORTED_ENCODINGS:
            try:
                content = raw_bytes.decode(enc)
                detected_encoding = enc
                break
            except (UnicodeDecodeError, ValueError):
                continue

        if content is None:
            return create_failed_parse(path, "지원되는 인코딩으로 디코딩에 실패했습니다.")

        newline_style = "\r\n" if "\r\n" in content else "\n"
        metadata = PNLParsedMetadata()

        # 2. XML 기반 PNL 파싱 시도
        xml_parsed_success = False
        try:
            root = ET.fromstring(content)
            xml_parsed_success = True

            # XML 노드 순회
            for elem in root.iter():
                tag = elem.tag.lower() if elem.tag else ""

                # 도형 정보 추출 (e.g. <shape name="Button1" type="RECTANGLE">)
                if tag in ("shape", "primitive"):
                    shape_name = elem.attrib.get("name", elem.attrib.get("id", f"Shape_{len(metadata.shapes)+1}"))
                    shape_type = elem.attrib.get("type", elem.tag)
                    metadata.shapes.append(
                        PNLShapeInfo(name=shape_name, shape_type=shape_type, properties=dict(elem.attrib))
                    )

                # 이벤트 스크립트 추출 (e.g. <script event="Initialize">...</script>)
                if "script" in tag or "event" in tag:
                    event_name = elem.attrib.get("event", elem.attrib.get("name", "UnknownEvent"))
                    parent_name = elem.attrib.get("shape", "Panel")
                    script_text = elem.text.strip() if elem.text else ""

                    if script_text:
                        metadata.event_handlers.append(
                            PNLEventHandlerInfo(
                                event_name=event_name,
                                shape_name=parent_name,
                                script_body=script_text,
                            )
                        )
        except Exception:
            # XML 파싱 실패 시 텍스트 파싱 폴백 진행
            xml_parsed_success = False

        # 3. XML 파싱 실패 시 텍스트/정규식 폴백 진행
        if not xml_parsed_success:
            try:
                # 텍스트 내 shape 키워드 수집
                shape_matches = re.finditer(r"\bshape\s+([a-zA-Z0-9_]+)", content, re.IGNORECASE)
                for sm in shape_matches:
                    sname = sm.group(1)
                    metadata.shapes.append(PNLShapeInfo(name=sname, shape_type="generic"))

                # 텍스트 내 event 키워드 및 블록 수집
                event_matches = re.finditer(r"\b(Initialize|Click|RightClick|PanelClose|Scope)\s*\(\s*\)\s*\{([^}]+)\}", content)
                for em in event_matches:
                    ename = em.group(1)
                    ebody = em.group(2).strip()
                    line_no = content[: em.start()].count("\n") + 1
                    metadata.event_handlers.append(
                        PNLEventHandlerInfo(
                            event_name=ename,
                            shape_name="Panel",
                            script_body=ebody,
                            line_number=line_no,
                        )
                    )
            except Exception as e:
                return create_failed_parse(path, f"PNL 텍스트 파싱 처리 중 실패: {e}")

        parse_status = ParseStatus(
            status=ParseStatusType.PARSED,
            file=str(path),
        )

        return ParsedFile(
            file_path=path,
            file_type="pnl",
            parse_status=parse_status,
            original_sha256=file_sha256,
            detected_encoding=detected_encoding,
            newline_style=newline_style,
            content=content,
            metadata={
                "shapes": [s.__dict__ for s in metadata.shapes],
                "event_handlers": [e.__dict__ for e in metadata.event_handlers],
                "is_xml_format": xml_parsed_success,
            },
        )
