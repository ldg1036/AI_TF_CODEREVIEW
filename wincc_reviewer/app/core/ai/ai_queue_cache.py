"""
ai_queue_cache.py

로컬 AI 2차 리뷰 동시성 세마포어 큐잉 및 TTL 응답 캐시 엔진
SHA256 코드 핑거프린트 기반 응답 캐싱 및 동시 요청 수 제한 제어
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class CachedAIResponse:
    """단일 AI 리뷰 응답 캐시 항목"""
    fingerprint: str
    response_text: str
    created_at: float
    ttl_seconds: float = 3600.0


class AIQueueCacheManager:
    """로컬 AI 세마포어 동시성 큐 및 TTL 응답 캐시 관리자 (SQLite 영속성 기반)"""

    def __init__(self, max_concurrent_requests: int = 5, default_ttl_seconds: float = 3600.0, db_path: Path | None = None):
        self.max_concurrent_requests = max_concurrent_requests
        self.default_ttl_seconds = default_ttl_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        if db_path is None:
            # 기본 경로: CWD 하위 cache 디렉터리
            cache_dir = Path.cwd() / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = cache_dir / "ai_review_cache.db"
        else:
            self.db_path = db_path

        self._init_db()

    def _init_db(self) -> None:
        """SQLite 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_cache (
                    fingerprint TEXT PRIMARY KEY,
                    response_text TEXT,
                    created_at REAL,
                    ttl_seconds REAL
                )
            ''')
            conn.commit()

    def compute_fingerprint(self, code_payload: str, model_id: str) -> str:
        """코드 내용 및 모델 식별자 기반 SHA256 핑거프린트 산출"""
        raw = f"{model_id}:{code_payload}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cached_response(self, fingerprint: str) -> str | None:
        """TTL 이내 유효한 응답 캐시 조회 (SQLite)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT response_text, created_at, ttl_seconds FROM ai_cache WHERE fingerprint = ?", (fingerprint,))
            row = cursor.fetchone()

            if not row:
                return None

            response_text, created_at, ttl_seconds = row
            now = time.time()
            if now - created_at > ttl_seconds:
                cursor.execute("DELETE FROM ai_cache WHERE fingerprint = ?", (fingerprint,))
                conn.commit()
                return None

            return response_text

    def store_response(self, fingerprint: str, response_text: str) -> None:
        """AI 리뷰 응답 캐시에 저장 (SQLite)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO ai_cache (fingerprint, response_text, created_at, ttl_seconds)
                VALUES (?, ?, ?, ?)
            ''', (fingerprint, response_text, time.time(), self.default_ttl_seconds))
            conn.commit()

    async def execute_queued_request(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """세마포어 제한 기반 동시성 큐잉 실행"""
        async with self.semaphore:
            return await func(*args, **kwargs)
