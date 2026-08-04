"""
WinCC OA 코드 리뷰 자동화 도구 — AI Provider 기본 인터페이스.

TRD §11.3의 최소 인터페이스 계약:
    class AIProvider(Protocol):
        def review(self, request: AIRequest) -> AIResponse: ...

BLOCKED 항목 (BLOCKED.md 참조):
    - endpoint URL 및 허용 HTTPS host/port
    - 인증 방식 및 비밀값 주입 방법
    - 요청/응답 JSON 필드 및 streaming 여부
    - 모델명, 버전, 컨텍스트 길이, 최대 출력 토큰
    확정 전에는 mock_provider만 사용합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class AIRequest:
    """AI 리뷰 요청."""

    code: str
    context: str = ""
    rule_id: str = ""
    prompt_template: str = ""


@dataclass
class AIResponse:
    """AI 리뷰 응답."""

    content: str
    model_id: str = ""
    raw_response: str = ""
    is_success: bool = True
    error_message: str = ""


@runtime_checkable
class AIProvider(Protocol):
    """AI Provider 프로토콜 (TRD §11.3)."""

    def review(self, request: AIRequest) -> AIResponse:
        """
        AI에 리뷰를 요청합니다.

        기본값: AI OFF, 타임아웃 60초, 최대 재시도 3회 (TRD §5.8)

        Args:
            request: AI 리뷰 요청

        Returns:
            AI 리뷰 응답
        """
        ...
