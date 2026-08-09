"""
WinCC OA 코드 리뷰 자동화 도구 — 주석 제거 공통 유틸리티.

모든 체커가 일관되게 사용할 주석 제거 함수를 제공합니다.
블록 주석(/* ... */), 라인 주석(//), 전처리기 지시문(#)을 제거하고
(원본_라인번호, 정제된_코드) 튜플 목록을 반환합니다.
"""

from __future__ import annotations


def strip_comments(content: str) -> list[tuple[int, str]]:
    """소스 코드에서 모든 주석을 제거하고 유효 코드 라인만 추출합니다.

    처리 대상:
    - 블록 주석: /* ... */ (여러 줄에 걸칠 수 있음)
    - 라인 주석: // 이후 내용 제거
    - 전처리기 지시문: # 으로 시작하는 라인 (#uses, #include 등)

    Args:
        content: 원본 소스 코드 문자열

    Returns:
        (1 기반 라인 번호, 정제된 코드 문자열) 튜플 리스트.
        빈 문자열이 되는 라인은 제외됩니다.
    """
    clean_lines: list[tuple[int, str]] = []
    in_block_comment = False

    for idx, line in enumerate(content.splitlines(), start=1):
        if in_block_comment:
            if "*/" in line:
                in_block_comment = False
                # */ 이후 코드가 남아 있을 수 있음
                after_close = line.split("*/", 1)[1]
                code_part = _strip_inline(after_close)
                if code_part:
                    clean_lines.append((idx, code_part))
            continue

        stripped = line.strip()

        # 전처리기 지시문 (#uses, #include 등) 스킵
        if stripped.startswith("#"):
            continue

        # 블록 주석 시작 확인
        if "/*" in line:
            before_open = line.split("/*", 1)[0]
            after_open = line.split("/*", 1)[1]

            if "*/" in after_open:
                # 한 줄 안에서 열고 닫힘: /* ... */ 제거 후 나머지 처리
                after_close = after_open.split("*/", 1)[1]
                reconstructed = before_open + after_close
                code_part = _strip_inline(reconstructed)
                if code_part:
                    clean_lines.append((idx, code_part))
            else:
                # 여러 줄 블록 주석 진입
                in_block_comment = True
                code_part = _strip_inline(before_open)
                if code_part:
                    clean_lines.append((idx, code_part))
            continue

        # 일반 라인: 인라인 // 주석 제거
        code_part = _strip_inline(line)
        if code_part:
            clean_lines.append((idx, code_part))

    return clean_lines


def _strip_inline(line: str) -> str:
    """라인 내 // 주석을 제거하고 양끝 공백을 정리합니다.

    문자열 리터럴 안의 //는 보존합니다 (간이 처리).
    """
    # 문자열 리터럴 외부의 // 만 제거하는 간이 처리
    in_string = False
    quote_char = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == quote_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                return line[:i].strip()
        i += 1
    return line.strip()
