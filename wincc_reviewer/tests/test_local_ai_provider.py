"""
WinCC OA 사내 로컬 AI Provider 단위 테스트.
"""

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app.core.ai.local_provider import LocalAIConfig, LocalAIProvider
from app.core.ai.provider_base import AIRequest


class TestLocalAIProvider:
    """LocalAIProvider 테스트 스위트."""

    def test_build_url_default(self):
        """기본 설정으로 URL 구성 검증."""
        provider = LocalAIProvider()
        url = provider._build_url()
        assert url == "http://127.0.0.1:8000/v1/chat/completions"

    def test_build_url_custom_host_port(self):
        """사용자 정의 호스트, 포트, 엔드포인트 검증."""
        cfg = LocalAIConfig(host="192.168.1.100", port=11434, endpoint="api/generate")
        provider = LocalAIProvider(cfg)
        url = provider._build_url()
        assert url == "http://192.168.1.100:11434/api/generate"

    @patch("app.core.ai.local_provider.urlopen")
    def test_review_success_openai_schema(self, mock_urlopen):
        """OpenAI 호환 스키마 정상 응답 처리 검증."""
        cfg = LocalAIConfig(api_key="secret_token")
        provider = LocalAIProvider(cfg)

        mock_resp = MagicMock()
        mock_data = {
            "choices": [
                {
                    "message": {
                        "content": "이벤트 콜백 내 지연을 제거하십시오."
                    }
                }
            ]
        }
        mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        req = AIRequest(code="delay(5);", rule_id="CTL_PRF_001", context="루프 지연 검사")
        resp = provider.review(req)

        assert resp.is_success is True
        assert "이벤트 콜백 내 지연을 제거하십시오." in resp.content
        assert resp.model_id == cfg.model_id

    @patch("app.core.ai.local_provider.urlopen")
    def test_review_http_error_backoff(self, mock_urlopen):
        """HTTP 500 오류 시 재시도 및 안전 실패 반환 검증."""
        cfg = LocalAIConfig(max_retries=2, timeout_seconds=5)
        provider = LocalAIProvider(cfg)

        mock_urlopen.side_effect = HTTPError("http://test", 500, "Internal Error", {}, None)

        req = AIRequest(code="delay(5);", rule_id="CTL_PRF_001")
        resp = provider.review(req)

        assert resp.is_success is False
        assert "HTTP 오류 (500)" in resp.error_message
        assert mock_urlopen.call_count == 2
