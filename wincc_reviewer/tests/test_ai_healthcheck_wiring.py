"""
WinCC OA 코드 리뷰 자동화 도구 — AI 헬스체크 실배선 유닛 테스트.
IMP 02 명세 및 11번 지침서 R2 규칙에 따라 health_check 호출 및 fast fallback을 mock으로 검증합니다.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.ai.local_provider import LocalAIConfig, LocalAIProvider
from app.core.pipeline import Pipeline, PipelineConfig


class TestAIHealthCheckWiring:
    """AI 사전 헬스체크 실배선 및 빠른 폴백 유닛테스트."""

    def test_health_check_called_and_fast_fallback_when_server_down(self, tmp_path: Path) -> None:
        """헬스체크 실패 시 5초 이내에 정적 룰 모드로 빠른 폴백되는지 검증합니다."""
        sample_ctl = tmp_path / "sample.ctl"
        sample_ctl.write_text("main() { dpGet(\"Sys:Tag\", v); }", encoding="utf-8")

        config = PipelineConfig(input_path=sample_ctl, no_ai=False, enable_diff=False, use_cache=False)
        pipeline = Pipeline(config=config)

        with patch.object(LocalAIProvider, "health_check", return_value=False) as mock_health:
            start_time = time.perf_counter()
            report = pipeline.run()
            elapsed_sec = time.perf_counter() - start_time

            # 1. health_check가 실제 호출되었는지 입증
            mock_health.assert_called()
            # 2. 5초 이내에 빠른 폴백 처리되었는지 검증
            assert elapsed_sec < 5.0, f"헬스체크 실패 시 5초 이내 빠른 폴백이어야 합니다. 실제: {elapsed_sec:.2f}초"
            assert report is not None
            assert report.metrics.file_count == 1

    def test_local_ai_provider_health_check_timeout_behavior(self) -> None:
        """LocalAIProvider의 health_check 메서드가 미가동 IP에 대해 False를 즉시 반환하는지 검증합니다."""
        config = LocalAIConfig(host="192.0.2.1", port=9999, timeout_seconds=60)
        provider = LocalAIProvider(config)

        start_time = time.perf_counter()
        result = provider.health_check(check_timeout=0.5)
        elapsed_sec = time.perf_counter() - start_time

        assert result is False, "미가동 IP에 대한 헬스체크는 False이어야 합니다."
        assert elapsed_sec < 2.0, "지정된 타임아웃 이내에 조기 반환되어야 합니다."
