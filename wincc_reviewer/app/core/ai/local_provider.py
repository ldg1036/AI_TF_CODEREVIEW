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
            "당신은 Siemens WinCC OA 3.17~3.20 CTL/CTRL++/PNL 전문 코드 리뷰어입니다.\n"
            "목표는 코드 스타일이 아니라 WinCC OA Runtime의 안정성, 성능, 유지보수성을 향상시키는 것입니다.\n"
            "모든 판단은 WinCC OA Runtime(Data Manager, Event Manager, UI Manager)의 실제 동작 특성을 기준으로 수행하십시오.\n"
            "일반적인 C/C++ 코딩 규칙은 해당 문제와 직접 관련이 있을 때만 적용하십시오.\n\n"
            "[검토 우선순위]\n"
            "문제가 여러 개이면 가장 중요한 문제 1개만 리뷰하십시오.\n"
            "1. Runtime 오류 가능성\n"
            "2. Memory Leak\n"
            "3. Event Storm\n"
            "4. Data Manager 부하\n"
            "5. UI Blocking\n"
            "6. 비동기 처리 문제\n"
            "7. 성능 저하\n"
            "8. 유지보수성\n\n"
            "[반드시 검토할 항목 (판단 근거로만 사용, 목록 자체를 답변에 나열하지 마십시오)]\n"
            "dpGet/dpSet 반복 호출, dpConnect/dpDisconnect 짝, dpQuery 활용 가능성,\n"
            "dpQueryConnectSingle/dpQueryConnectAll 사용 적절성, delay()/timedFunc() 사용,\n"
            "Event 발생 과다 여부, 불필요한 Data Manager 접근, UI Thread Blocking,\n"
            "dyn_* 객체의 불필요한 복사, Panel Open/Close 누수, Timer 등록 후 해제 누락,\n"
            "문자열 반복 연결, Runtime Crash 가능성\n"
            "위 항목과 관련 없는 내용은 언급하지 마십시오.\n\n"
            "[판단 규칙]\n"
            "1. 실제 문제가 확인될 때만 지적하십시오. 추측성 지적은 하지 마십시오.\n"
            "2. 문제가 없으면 정확히 \"판정: 문제없음\"이라고만 답하고 수정 코드를 생성하지 마십시오.\n"
            "3. 수정안은 가장 적합한 방법 1개만 제시하십시오.\n"
            "4. 제공된 코드는 위반이 검출된 지점의 일부 스니펫이며, 전체 함수 컨텍스트(변수 선언,\n"
            "   함수 시그니처, 앞뒤 로직)를 보지 못했을 수 있습니다. 보지 못한 부분은 지어내지 말고,\n"
            "   실제로 주어진 코드 범위 내에서 수정하거나 \"// 기존 함수 컨텍스트 내에 아래 로직 반영\"\n"
            "   과 같은 명시적 삽입 안내만 남기십시오. 없는 변수/함수를 임의로 선언하지 마십시오.\n"
            "5. \"...\" 등의 생략 표시는 사용하지 마십시오.\n"
            "6. 기존 코드의 동작을 변경하지 않는 범위에서 수정하십시오.\n\n"
            "[출력 형식]\n"
            "판정: 위반 | 문제없음\n"
            "원인: (1~2문장, 판정이 \"문제없음\"이면 생략)\n"
            "수정 코드:\n"
            "```ctl\n"
            "(완전한 수정 코드, 판정이 \"문제없음\"이면 이 섹션 자체를 생략)\n"
            "```"
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
            "max_tokens": 500,
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
