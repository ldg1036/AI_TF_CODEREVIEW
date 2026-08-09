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
    지정된 인코딩 순서대로 파일 읽기를 시도하며 fast-path 적용으로 디코딩 성능을 최적화합니다.
    """
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    raw_bytes = path.read_bytes()
    content, _, _ = decode_bytes_with_fallback(raw_bytes, encodings)
    return content


def decode_bytes_with_fallback(
    raw_bytes: bytes, encodings: list[str] | None = None
) -> tuple[str, str, float]:
    """
    Fast-path 디코딩(ASCII/UTF-8 직행)을 통해 시도 횟수 및 지연 시간을 대폭 축소합니다.
    """
    # 1. ASCII / UTF-8 Fast-path (대부분의 스크립트 파일 대다수 커버)
    try:
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            return raw_bytes[3:].decode("utf-8"), "utf-8-sig", 1.0
        return raw_bytes.decode("utf-8"), "utf-8", 1.0
    except UnicodeDecodeError:
        pass

    # 2. 비표준 다국어 인코딩 폴백 (CP949, EUC-KR 등)
    enc_list = [e for e in (encodings or SUPPORTED_ENCODINGS) if e not in ("utf-8", "utf-8-sig")]
    last_error: UnicodeDecodeError | None = None

    for enc in enc_list:
        try:
            content = raw_bytes.decode(enc)
            return content, enc, 0.65
        except (UnicodeDecodeError, ValueError) as e:
            if isinstance(e, UnicodeDecodeError):
                last_error = e
            continue

    raise UnicodeDecodeError(
        last_error.encoding if last_error else "unknown",
        last_error.object if last_error else b"",
        last_error.start if last_error else 0,
        last_error.end if last_error else 0,
        f"지원되는 모든 인코딩({', '.join(encodings or SUPPORTED_ENCODINGS)})으로 디코딩에 실패했습니다.",
    )
