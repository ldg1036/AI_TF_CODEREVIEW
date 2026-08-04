"""
WinCC OA 코드 리뷰 자동화 도구 — 사내 로컬 AI Provider.

사내 로컬 서버(vLLM, Ollama, Llama.cpp 등 OpenAI 호환 HTTP API)와 통신하여
정적 룰 위반 및 소스 코드에 대한 심층 수정 가이드를 요청합니다.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.ai.provider_base import AIProvider, AIRequest, AIResponse

logger = logging.getLogger(__name__)


@dataclass
class LocalAIConfig:
    """사내 로컬 AI 서버 연동 설정."""

    host: str = "127.0.0.1"
    port: int = 8000
    api_key: str = ""
    endpoint: str = "/v1/chat/completions"
    model_id: str = "sane_local_llm"
    timeout_seconds: int = 60
    max_retries: int = 3
    temperature: float = 0.2


class LocalAIProvider(AIProvider):
    """
    사내 로컬 서버 연동 AI 프로바이더.

    IP, PORT, API_KEY 및 엔드포인트를 주입받아 REST 요청을 수행하며,
    일시적 장애(429, 5xx, 연결 실패) 발생 시 지수 백오프 재시도를 진행합니다.
    """

    def __init__(self, config: LocalAIConfig | None = None) -> None:
        self.config = config or LocalAIConfig()

    def _build_url(self) -> str:
        """호스트와 포트, 엔드포인트를 결합하여 전체 HTTP URL을 구성합니다."""
        host = self.config.host.strip()
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"http://{host}"
        endpoint = self.config.config_endpoint if hasattr(self.config, "config_endpoint") else self.config.endpoint
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{host}:{self.config.port}{endpoint}"

    def review(self, request: AIRequest) -> AIResponse:
        """
        로컬 AI 서버에 코드 리뷰를 요청합니다.

        Args:
            request: AI 리뷰 요청 객체

        Returns:
            AIResponse: 심층 리뷰 결과 또는 실패 상태
        """
        url = self._build_url()
        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        system_prompt = (
            "당신은 WinCC OA (Siemens SIMATIC WinCC Open Architecture) 및 CTL/PNL 스크립트 전문 코드 리뷰어입니다. "
            "제시되는 룰 위반 내역과 소스 코드를 분석하여, 안정적이고 효율적인 개선 방안 및 수정 구문 가이드를 명확하게 제시하십시오."
        )

        user_content = (
            f"[위반 룰 ID]: {request.rule_id}\n"
            f"[문맥 설명]: {request.context}\n"
            f"[검토 소스 코드]:\n{request.code}\n"
        )

        payload = {
            "model": self.config.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.config.temperature,
        }

        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        retry_delay = 1.0
        last_error = ""

        for attempt in range(1, self.config.max_retries + 1):
            try:
                req = Request(url, data=body_bytes, headers=headers, method="POST")
                with urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    resp_data = resp.read().decode("utf-8")
                    parsed_json = json.loads(resp_data)

                    # OpenAI 호환 응답 파싱
                    content = ""
                    if "choices" in parsed_json and len(parsed_json["choices"]) > 0:
                        content = parsed_json["choices"][0].get("message", {}).get("content", "")
                    elif "content" in parsed_json:
                        content = str(parsed_json["content"])
                    else:
                        content = str(resp_data)

                    logger.info("로컬 AI 리뷰 요청 성공 (시도 횟수: %d): url=%s", attempt, url)
                    return AIResponse(
                        content=content.strip(),
                        model_id=self.config.model_id,
                        raw_response=resp_data,
                        is_success=True,
                    )

            except HTTPError as e:
                last_error = f"HTTP 오류 ({e.code}): {e.reason}"
                logger.warning("로컬 AI 요청 HTTP 오류 (시도 %d/%d): %s", attempt, self.config.max_retries, last_error)
                if e.code in (429, 500, 502, 503, 504) and attempt < self.config.max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2.0
                    continue
                break

            except (URLError, TimeoutError, Exception) as e:
                last_error = f"통신 실패 ({type(e).__name__}): {e}"
                logger.warning("로컬 AI 요청 실패 (시도 %d/%d): %s", attempt, self.config.max_retries, last_error)
                if attempt < self.config.max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2.0
                    continue
                break

        logger.error("로컬 AI 서버 연동 최종 실패: url=%s, error=%s", url, last_error)
        return AIResponse(
            content="",
            model_id=self.config.model_id,
            is_success=False,
            error_message=f"로컬 AI 연동 실패: {last_error}",
        )
