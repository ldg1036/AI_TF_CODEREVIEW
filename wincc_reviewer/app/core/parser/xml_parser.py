"""
WinCC OA XML 파서 (TRD §5.1 & Phase 1 기준).

WinCC OA의 설정 및 데이터 XML 파일을 분석하여
ElementTree 기반 트리 구조, 노드 태그, 속성 및 텍스트를 추출하고
인코딩 감지 및 구문 오류 시 예외 없이 parse_failed 상태를 반환합니다.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from app.core.models import ParseStatus, ParseStatusType
from app.core.parser.base_parser import ParsedFile, Parser, create_failed_parse


@dataclass
class XMLNodeInfo:
    """XML 노드 정보."""

    tag: str
    attributes: dict[str, str] = field(default_factory=dict)
    text: str = ""
    xpath: str = ""


@dataclass
class XMLParsedMetadata:
    """XML 파싱 메타데이터 IR."""

    root_tag: str = ""
    total_nodes: int = 0
    nodes: list[XMLNodeInfo] = field(default_factory=list)


class XMLParser(Parser):
    """XML 파일 파서 구현체."""

    SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]
    MAX_NODES_TO_COLLECT = 1000

    def __init__(self, extract_scripts_only: bool = True) -> None:
        self.extract_scripts_only = extract_scripts_only

    def parse(self, path: Path) -> ParsedFile:
        """
        .xml 파일을 파싱하여 ParsedFile IR을 생성합니다.

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
        metadata = XMLParsedMetadata()

        # 2. ElementTree 기반 XML 파싱
        try:
            root = ET.fromstring(content)
            metadata.root_tag = root.tag

            node_count = 0
            for elem in root.iter():
                node_count += 1
                if len(metadata.nodes) < self.MAX_NODES_TO_COLLECT:
                    text_val = elem.text.strip() if elem.text else ""
                    metadata.nodes.append(
                        XMLNodeInfo(
                            tag=elem.tag,
                            attributes=dict(elem.attrib),
                            text=text_val,
                            xpath=elem.tag,
                        )
                    )

            metadata.total_nodes = node_count

        except ET.ParseError as e:
            return create_failed_parse(path, f"XML 구문 오류(Syntax Error): {e}")
        except Exception as e:
            return create_failed_parse(path, f"XML 파싱 처리 중 실패: {e}")

        # XML 내 스크립트 노드 텍스트 정제 추출
        script_blocks = []
        if self.extract_scripts_only and metadata.nodes:
            for n in metadata.nodes:
                tag_lower = n.tag.lower()
                if any(kw in tag_lower for kw in ["script", "code", "event", "handler"]):
                    if n.text:
                        script_blocks.append(f"// ===== XML Script Node: <{n.tag}> =====\n{n.text}\n")

        pure_script_content = "\n".join(script_blocks) if (self.extract_scripts_only and script_blocks) else content

        parse_status = ParseStatus(
            status=ParseStatusType.PARSED,
            file=str(path),
        )

        return ParsedFile(
            file_path=path,
            file_type="xml",
            parse_status=parse_status,
            original_sha256=file_sha256,
            detected_encoding=detected_encoding,
            newline_style=newline_style,
            content=pure_script_content,
            metadata={
                "root_tag": metadata.root_tag,
                "total_nodes": metadata.total_nodes,
                "nodes": [n.__dict__ for n in metadata.nodes],
                "raw_content": content,
            },
        )
