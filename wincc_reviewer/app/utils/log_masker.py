"""
로그 및 출력 마스킹 유틸리티 모듈.
"""


def mask_api_key(api_key: str | None) -> str:
    """
    API 키 민감 정보를 마스킹 처리합니다.
    예: 'secret_12345678' -> 'sec***5678'
    """
    if not api_key:
        return ""
    length = len(api_key)
    if length <= 6:
        return "***"
    return f"{api_key[:3]}***{api_key[-4:]}"

def mask_code_snippet(snippet: str | None, max_lines: int = 5) -> str:
    """
    로그 출력 시 원본 소스코드 전체 노출을 방지하기 위한 마스킹 및 요약 유틸리티.
    """
    if not snippet:
        return ""
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return "[CODE_SNIPPET_MASKED]"
    return f"[CODE_SNIPPET_MASKED ({len(lines)} lines)]"
