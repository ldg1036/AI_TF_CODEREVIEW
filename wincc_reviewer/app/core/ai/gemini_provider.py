"""
Gemini 3.6 Pro 기반 AI 리뷰 프로바이더 (TRD §5.8 준수).

WinCC OA CTL/PNL/XML 스크립트에 대한 2차 심층 AI 코드 리뷰 및 개선 가이드를 제공합니다.
"""

from __future__ import annotations

import logging
import os

from app.core.ai.provider_base import AIProvider, AIRequest, AIResponse

logger = logging.getLogger(__name__)


class GeminiAIProvider(AIProvider):
    """Gemini 1.5 Pro AI 리뷰 프로바이더."""

    MODEL_ID = "gemini-1.5-pro"

    def __init__(self, api_key: str | None = None, allow_external_ai: bool = False) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.allow_external_ai = allow_external_ai or (os.environ.get("ALLOW_EXTERNAL_AI", "false").lower() == "true")

    def review(self, request: AIRequest) -> AIResponse:
        """
        Gemini 1.5 Pro 모델을 호출하여 심층 리뷰 응답을 도출합니다.

        Args:
            request: AI 리뷰 요청

        Returns:
            AIResponse
        """
        logger.info("Gemini 1.5 Pro AI 리뷰 시작: rule_id=%s", request.rule_id)

        rule_id = request.rule_id or "GENERAL"
        code_snippet = request.code[:500] if request.code else ""
        context_str = request.context or ""

        # 보안 정책 검증: 외부 AI 동의 옵션(allow_external_ai)이 명시적으로 활성화된 경우만 REST API 호출 시도
        if self.api_key and self.allow_external_ai:
            try:
                import httpx

                prompt = (
                    "당신은 WinCC OA (CTL/PNL) 코드 리뷰 AI입니다. 아래 형식을 반드시 지켜 간결하게 답변하십시오.\n\n"
                    "[출력 형식]\n판정: 위반 | 문제없음\n원인: (1~2문장)\n"
                    "수정 코드: (가장 적합한 수정안 1개, 판정이 문제없음이면 생략)\n\n"
                    f"[검토 항목 / 룰 ID]: {rule_id}\n"
                    f"[검토 조건 및 맥락]: {context_str}\n"
                    f"[대상 소스 코드]:\n```\n{code_snippet}\n```\n\n"
                    "전체 답변은 400자 내외, 코드 블록은 1개만 포함하십시오."
                )

                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500},
                }

                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        res_data = resp.json()
                        text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                        return AIResponse(
                            content=text,
                            model_id=self.MODEL_ID,
                            raw_response=resp.text,
                            is_success=True,
                        )
                    logger.warning("Gemini API 오류 응답: status=%s, body=%s", resp.status_code, resp.text[:300])
            except Exception as e:
                logger.warning("Gemini REST API 호출 중 예외 발생: %s", e)

        # API 키 미설정, 보안 미승인 또는 호출 실패 시 명확한 실패 처리
        return AIResponse(
            content="",
            model_id=self.MODEL_ID,
            is_success=False,
            error_message="Gemini API 호출 실패 또는 보안 미승인 상태입니다. 정적 룰 결과를 참고하십시오.",
        )
