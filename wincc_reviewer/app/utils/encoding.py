"""
WinCC OA 코드 리뷰 자동화 도구 — 다국어 파일 인코딩 유틸리티.

WinCC OA 환경에서 사용되는 다양한 인코딩(UTF-8, EUC-KR, CP949 등)을 일관되게
자동 감지하고 디코딩하는 공통 함수를 제공합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# WinCC OA 환경에서 지원하는 인코딩 우선순위 (BOM 포함 UTF-8 > UTF-8 > CP949 > EUC-KR > Latin-1)
SUPPORTED_ENCODINGS: list[str] = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]


def read_text_with_fallback(path: Path, encodings: list[str] | None = None) -> str:
    """
    지정된 인코딩 순서대로 파일 읽기를 시도하여 최초 성공한 결과를 반환합니다.

    Args:
        path: 읽을 파일 경로
        encodings: 시도할 인코딩 목록 (기본: SUPPORTED_ENCODINGS)

    Returns:
        디코딩된 파일 텍스트 내용

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        UnicodeDecodeError: 모든 인코딩으로 디코딩에 실패했을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    enc_list = encodings or SUPPORTED_ENCODINGS
    last_error: UnicodeDecodeError | None = None

    for enc in enc_list:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise UnicodeDecodeError(
        last_error.encoding if last_error else "unknown",
        last_error.object if last_error else b"",
        last_error.start if last_error else 0,
        last_error.end if last_error else 0,
        f"지원되는 모든 인코딩({', '.join(enc_list)})으로 디코딩에 실패했습니다: {path}",
    )


def decode_bytes_with_fallback(
    raw_bytes: bytes, encodings: list[str] | None = None
) -> tuple[str, str, float]:
    """
    바이트 데이터를 지정된 인코딩 순서대로 디코딩을 시도합니다.

    Args:
        raw_bytes: 디코딩 대상 바이트 데이터
        encodings: 시도할 인코딩 목록 (기본: SUPPORTED_ENCODINGS)

    Returns:
        (디코딩된 텍스트, 감지된 인코딩명, 인코딩 신뢰도 0.0~1.0)

    Raises:
        UnicodeDecodeError: 모든 인코딩으로 디코딩에 실패했을 때
    """
    enc_list = encodings or SUPPORTED_ENCODINGS
    last_error: UnicodeDecodeError | None = None

    for idx, enc in enumerate(enc_list):
        try:
            content = raw_bytes.decode(enc)
            # 비표준 인코딩(cp949, euc-kr 등)은 신뢰도를 낮게 설정
            confidence = 1.0 if idx <= 1 else 0.65
            return content, enc, confidence
        except (UnicodeDecodeError, ValueError) as e:
            if isinstance(e, UnicodeDecodeError):
                last_error = e
            continue

    raise UnicodeDecodeError(
        last_error.encoding if last_error else "unknown",
        last_error.object if last_error else b"",
        last_error.start if last_error else 0,
        last_error.end if last_error else 0,
        f"지원되는 모든 인코딩({', '.join(enc_list)})으로 디코딩에 실패했습니다.",
    )
