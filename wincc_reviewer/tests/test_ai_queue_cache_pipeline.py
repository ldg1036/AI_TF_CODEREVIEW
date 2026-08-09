"""
AI 리뷰 큐 캐시 파이프라인 실연동 검증 테스트.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from pathlib import Path
import pytest

from app.core.models import SeverityLevel, Violation, ViolationStatus, ReviewReport
from app.core.pipeline import Pipeline, PipelineConfig
from app.core.ai.provider_base import AIResponse


def test_ai_queue_cache_reduces_provider_calls(tmp_path):
    sample_file = tmp_path / "sample_cache.ctl"
    sample_file.write_text("void main() { int i = 0; while(1) { i++; } }", encoding="utf-8")

    mock_ai_provider = MagicMock()
    mock_ai_provider.review.return_value = AIResponse(
        is_success=True,
        content="AI 리뷰: 무한 루프 내 delay 함수를 추가하십시오.",
    )

    config = PipelineConfig(
        input_path=sample_file,
        output_dir=tmp_path / "output",
        no_ai=False,
        use_ai_queue_cache=True,
    )
    pipeline = Pipeline(config)
    pipeline.ai_provider = mock_ai_provider

    # 1차 실행: AI 프로바이더 호출 발생
    report1 = pipeline.run()
    first_call_count = mock_ai_provider.review.call_count
    assert first_call_count > 0

    # 2차 실행 (동일 파이프라인 인스턴스): 캐시 히트로 AI 프로바이더 추가 호출 0건
    mock_ai_provider.review.reset_mock()
    report2 = pipeline.run()
    second_call_count = mock_ai_provider.review.call_count

    assert second_call_count == 0, f"2차 실행에서 AI 프로바이더 추가 호출이 0건이어야 하지만 {second_call_count}건 호출됨"
