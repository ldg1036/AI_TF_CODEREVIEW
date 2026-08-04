"""
Mock AI Provider (TRD §5.8, BLOCKED.md & Phase 3 기준).

사내 AI 인프라 사양 확정 전까지 사용되는 Mock AI 리뷰 프로바이더입니다.
AI Provider 프로토콜을 구현하며, 정적 룰 검사 지적 항목에 대해 2차 심층 제안 문구를 생성합니다.
"""

from __future__ import annotations

import logging

from app.core.ai.provider_base import AIProvider, AIRequest, AIResponse

logger = logging.getLogger(__name__)


class MockAIProvider(AIProvider):
    """Mock AI 리뷰 프로바이더."""

    MODEL_ID = "mock-gemma-local-v1"

    def review(self, request: AIRequest) -> AIResponse:
        """
        Mock AI 리뷰를 수행합니다.

        Args:
            request: AI 리뷰 요청 (코드, 룰 ID, 맥락 등)

        Returns:
            AIResponse
        """
        logger.info("Mock AI 리뷰 수행 중: rule_id=%s", request.rule_id)

        code_snippet = request.code[:100] if request.code else ""
        rule_id = request.rule_id or "GENERAL-REVIEW"

        mock_suggestion = (
            f"[AI 심층 제안 - {rule_id}]\n"
            f"검토 코드 스니펫:\n{code_snippet}\n\n"
            "추천 개선 방향:\n"
            "1. 콜백 연결(dpConnect) 후 리소스 해제(dpDisconnect)가 명시적으로 작성되었는지 재검토하세요.\n"
            "2. 예외 발생 시 안전한 로깅 및 자원 반납 처리(try-catch)를 추가하는 것이 안전합니다."
        )

        return AIResponse(
            content=mock_suggestion,
            model_id=self.MODEL_ID,
            raw_response=f'{{"status": "success", "mock": true, "rule_id": "{rule_id}"}}',
            is_success=True,
        )
