"""
test_ai_queue_cache.py

AIQueueCacheManager AI 큐 및 캐시 유닛 테스트 (R2 호출부 증명)
"""

from __future__ import annotations

import asyncio
import pytest
from app.core.ai.ai_queue_cache import AIQueueCacheManager


class TestAIQueueCacheManager:
    """AIQueueCacheManager 세마포어 큐 및 TTL 캐시 검증"""

    def test_fingerprint_and_cache(self):
        manager = AIQueueCacheManager(default_ttl_seconds=100.0)
        payload = "void main() { int a = 1; }"
        model_id = "sane_local_llm"

        fp = manager.compute_fingerprint(payload, model_id)
        assert len(fp) == 64

        assert manager.get_cached_response(fp) is None

        manager.store_response(fp, "AI Review Result: Clean Code")
        cached = manager.get_cached_response(fp)
        assert cached == "AI Review Result: Clean Code"

    def test_queued_execution(self):
        manager = AIQueueCacheManager(max_concurrent_requests=2)

        async def dummy_ai_call(val: int) -> int:
            await asyncio.sleep(0.01)
            return val * 2

        res = asyncio.run(manager.execute_queued_request(dummy_ai_call, 10))
        assert res == 20

