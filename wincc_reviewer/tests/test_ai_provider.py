"""
MockAIProvider 유닛 테스트 (TRD §5.8 & Phase 3 기준).

검증 항목:
1. MockAIProvider.review 실행 및 AIResponse 생성
2. AIResponse 속성(model_id, is_success, content) 검증
"""

from __future__ import annotations

import pytest

from app.core.ai.mock_provider import MockAIProvider
from app.core.ai.provider_base import AIRequest


class TestMockAIProvider:
    """MockAIProvider 유닛 테스트."""

    def test_mock_ai_provider_review(self):
        """MockAIProvider review 실행 및 응답 검증."""
        provider = MockAIProvider()

        req = AIRequest(
            code="void main() { dpConnect('cbTemp', 'dpe'); }",
            rule_id="CTL-RES-001",
            context="Server CTL script",
        )

        resp = provider.review(req)

        assert resp.is_success is True
        assert resp.model_id == "mock-gemma-local-v1"
        assert "CTL-RES-001" in resp.content
        assert "추천 개선 방향" in resp.content
