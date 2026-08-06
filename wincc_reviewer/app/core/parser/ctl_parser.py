"""
WinCC OA CTL (CTRL 스크립트) 파서 (TRD §5.1 & Phase 1 기준).

WinCC OA의 .ctl 스크립트 라이브러리 파일을 읽어
함수 선언, 전역변수, 주석, 문자열 리터럴 등을 정규식/토큰 방식으로 추출하고
인코딩 감지 및 파싱 실패 시 안전하게 parse_failed 상태를 반환합니다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.models import ParseStatus, ParseStatusType
from app.core.parser.base_parser import ParsedFile, Parser, create_failed_parse


@dataclass
class CTLFunctionInfo:
    """CTL 함수 정보."""

    name: str
    return_type: str
    params: list[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class CTLVariableInfo:
    """CTL 변수 정보."""

    name: str
    var_type: str
    is_global: bool = False
    line_number: int = 0
    initial_value: str = ""


@dataclass
class CTLParsedMetadata:
    """CTL 파싱 메타데이터 IR."""

    functions: list[CTLFunctionInfo] = field(default_factory=list)
    global_variables: list[CTLVariableInfo] = field(default_factory=list)
    comment_lines: list[int] = field(default_factory=list)


def calculate_file_sha256(file_path: Path) -> str:
    """파일의 SHA256 해시를 계산합니다."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


class CTLParser(Parser):
    """CTL 파일 파서 구현체."""

    SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]

    # CTRL 타입 키워드 정규식
    TYPE_PATTERN = r"(?:void|int|float|string|bool|char|mapping|dyn_int|dyn_float|dyn_string|dyn_bool|dyn_mapping|unsigned|long|time|anytype)"

    # 함수 선언 정규식 예시: void main() 또는 int calculate(int a, string b)
    FUNC_PATTERN = re.compile(
        rf"^\s*({TYPE_PATTERN})\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)",
        re.MULTILINE,
    )

    # 단순 전역변수 선언 정규식 예시: int g_counter = 0; 또는 string g_name;
    VAR_PATTERN = re.compile(
        rf"^\s*({TYPE_PATTERN})\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=\s*([^;]+))?\s*;",
        re.MULTILINE,
    )

    def parse(self, path: Path) -> ParsedFile:
        """
        .ctl 파일을 파싱하여 ParsedFile IR을 생성합니다.

        Args:
            path: 파싱 대상 파일 경로

        Returns:
            ParsedFile IR
        """
        path = Path(path)
        if not path.exists():
            return create_failed_parse(path, f"파일을 찾을 수 없습니다: {path}")

        # 1. 파일 읽기 및 인코딩 자동 디코딩
        raw_bytes = None
        try:
            with open(path, "rb") as f:
                raw_bytes = f.read()
        except Exception as e:
            return create_failed_parse(path, f"파일 읽기 오류: {e}")

        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        content = None
        detected_encoding = ""
        encoding_confidence = 1.0
        encoding_warning = ""

        for idx, enc in enumerate(self.SUPPORTED_ENCODINGS):
            try:
                content = raw_bytes.decode(enc)
                detected_encoding = enc
                if idx > 1:
                    encoding_confidence = 0.65
                    encoding_warning = f"[ENCODING WARNING] 비표준 인코딩({enc})이 감지되었습니다. 한글 및 주석 글자 깨짐 여부를 점검하십시오."
                break
            except (UnicodeDecodeError, ValueError):
                continue

        if content is None:
            return create_failed_parse(path, "지원되는 인코딩으로 디코딩에 실패했습니다.")


        # 줄바꿈 스타일 감지
        newline_style = "\r\n" if "\r\n" in content else "\n"

        # 2. 내용 정규식파싱
        metadata = CTLParsedMetadata()

        try:
            # 주석 라인 수집
            lines = content.splitlines()
            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                    metadata.comment_lines.append(idx)

            # 함수 추출
            for match in self.FUNC_PATTERN.finditer(content):
                ret_type = match.group(1)
                func_name = match.group(2)
                raw_params = match.group(3).strip()

                params = [p.strip() for p in raw_params.split(",") if p.strip()]
                line_start = content[: match.start()].count("\n") + 1

                metadata.functions.append(
                    CTLFunctionInfo(
                        name=func_name,
                        return_type=ret_type,
                        params=params,
                        line_start=line_start,
                        line_end=line_start,  # 스텁에서는 시작 라인과 동일
                    )
                )

            # 전역 변수 추출 (단순화: 함수 정의 외부의 변수 선언)
            for match in self.VAR_PATTERN.finditer(content):
                var_type = match.group(1)
                var_name = match.group(2)
                init_val = match.group(3).strip() if match.group(3) else ""
                line_num = content[: match.start()].count("\n") + 1

                is_global = var_name.startswith("g_") or var_name.startswith("global")
                metadata.global_variables.append(
                    CTLVariableInfo(
                        name=var_name,
                        var_type=var_type,
                        is_global=is_global,
                        line_number=line_num,
                        initial_value=init_val,
                    )
                )

            parse_status = ParseStatus(
                status=ParseStatusType.PARSED,
                file=str(path),
            )

            return ParsedFile(
                file_path=path,
                file_type="ctl",
                parse_status=parse_status,
                original_sha256=file_sha256,
                detected_encoding=detected_encoding,
                encoding_confidence=encoding_confidence,
                encoding_warning=encoding_warning,
                newline_style=newline_style,
                content=content,
                metadata={
                    "functions": [f.__dict__ for f in metadata.functions],
                    "global_variables": [v.__dict__ for v in metadata.global_variables],
                    "comment_lines": metadata.comment_lines,
                },
            )

        except Exception as e:
            return create_failed_parse(path, f"파싱 중 예외 발생: {e}")
