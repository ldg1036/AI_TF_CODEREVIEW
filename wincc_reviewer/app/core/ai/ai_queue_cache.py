"""
ai_queue_cache.py

로컬 AI 2차 리뷰 동시성 세마포어 큐잉 및 TTL 응답 캐시 엔진
SHA256 코드 핑거프린트 기반 응답 캐싱 및 동시 요청 수 제한 제어
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CachedAIResponse:
    """단일 AI 리뷰 응답 캐시 항목"""
    fingerprint: str
    response_text: str
    created_at: float
    ttl_seconds: float = 3600.0


class AIQueueCacheManager:
    """로컬 AI 세마포어 동시성 큐 및 TTL 응답 캐시 관리자"""

    def __init__(self, max_concurrent_requests: int = 5, default_ttl_seconds: float = 3600.0):
        self.max_concurrent_requests = max_concurrent_requests
        self.default_ttl_seconds = default_ttl_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.cache: dict[str, CachedAIResponse] = {}

    def compute_fingerprint(self, code_payload: str, model_id: str) -> str:
        """코드 내용 및 모델 식별자 기반 SHA256 핑거프린트 산출"""
        raw = f"{model_id}:{code_payload}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cached_response(self, fingerprint: str) -> str | None:
        """TTL 이내 유효한 응답 캐시 조회"""
        cached = self.cache.get(fingerprint)
        if not cached:
            return None

        now = time.time()
        if now - cached.created_at > cached.ttl_seconds:
            del self.cache[fingerprint]
            return None

        return cached.response_text

    def store_response(self, fingerprint: str, response_text: str) -> None:
        """AI 리뷰 응답 캐시에 저장"""
        self.cache[fingerprint] = CachedAIResponse(
            fingerprint=fingerprint,
            response_text=response_text,
            created_at=time.time(),
            ttl_seconds=self.default_ttl_seconds
        )

    async def execute_queued_request(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """세마포어 제한 기반 동시성 큐잉 실행"""
        async with self.semaphore:
            return await func(*args, **kwargs)
