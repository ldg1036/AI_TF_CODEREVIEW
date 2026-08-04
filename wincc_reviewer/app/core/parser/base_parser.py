"""
WinCC OA 코드 리뷰 자동화 도구 — 파서 기본 인터페이스.

TRD §11.3의 최소 인터페이스 계약:
    class Parser(Protocol):
        def parse(self, path: Path) -> ParsedFile: ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.core.models import ParseStatus, ParseStatusType


@dataclass
class ParsedFile:
    """파싱된 파일의 중간 표현(IR)."""

    file_path: Path
    file_type: str  # "ctl", "pnl", "xml"
    parse_status: ParseStatus
    original_sha256: str = ""
    canonical_sha256: str | None = None
    detected_encoding: str = ""
    newline_style: str = ""
    # IR 데이터는 파일 타입별 서브클래스에서 확장
    content: str = ""
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class Parser(Protocol):
    """파서 프로토콜 (TRD §11.3)."""

    def parse(self, path: Path) -> ParsedFile:
        """
        파일을 파싱하여 IR을 생성합니다.

        파싱 실패 시 예외를 발생시키지 않고
        ParseStatus(status=parse_failed)를 반환합니다.

        Args:
            path: 파싱 대상 파일 경로

        Returns:
            ParsedFile: 파싱 결과 IR
        """
        ...


def create_failed_parse(path: Path, error_message: str) -> ParsedFile:
    """파싱 실패 시 안전한 ParsedFile을 생성합니다."""
    return ParsedFile(
        file_path=path,
        file_type=path.suffix.lstrip(".").lower(),
        parse_status=ParseStatus(
            status=ParseStatusType.PARSE_FAILED,
            file=str(path),
            error_message=error_message,
        ),
    )
