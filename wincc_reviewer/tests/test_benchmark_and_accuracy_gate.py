"""
WinCC OA 코드 리뷰 자동화 도구 — 대규모 벤치마크 및 CI 회귀 게이트 유닛 테스트.
IMP 03 및 IMP 06 명세에 따라 p95 처리 속도, 메모리 Peak 및 회귀 정밀도 임계치를 검증합니다.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.core.pipeline import Pipeline, PipelineConfig


class TestBenchmarkAndAccuracyGate:
    """대규모 벤치마크 회귀 게이트 테스트 수트."""

    def test_large_scale_benchmark_metrics_contract(self) -> None:
        """intermediate_results/large_scale_benchmark_metrics.json 계약 및 회귀 지표를 검증합니다."""
        metrics_file = Path("intermediate_results/large_scale_benchmark_metrics.json")
        assert metrics_file.exists(), "대규모 벤치마크 실측 지표 파일이 존재해야 합니다."

        with open(metrics_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("total_files_scanned", 0) >= 200, "200개 이상의 파일이 검사되어야 합니다."
        assert data.get("p95_duration_ms", 999.0) < 500.0, "p95 처리시간은 500ms 미만이어야 합니다."
        assert data.get("avg_time_per_file_ms", 999.0) < 10.0, "파일당 평균 처리시간은 10ms 미만이어야 합니다."
        assert data.get("sample_precision_rate_percent", 0.0) == 100.0, "정밀도는 100%이어야 합니다."

    def test_pipeline_benchmark_execution_speed_gate(self, tmp_path: Path) -> None:
        """단일 픽스처 스캔 시 500ms 이내 처리되는 속도 게이트를 검증합니다."""
        sample_ctl = tmp_path / "gate_sample.ctl"
        sample_ctl.write_text(
            """
            void main() {
                float v;
                dpGet("System1:Sensor.val", v);
            }
            """,
            encoding="utf-8",
        )

        config = PipelineConfig(input_path=sample_ctl, no_ai=True, enable_diff=False, use_cache=False)
        pipeline = Pipeline(config=config)

        report = pipeline.run()
        assert report is not None
        assert report.metrics.file_count == 1
        assert report.metrics.timings_ms.get("total", 0) < 500, "단일 파일 파이프라인 처리는 500ms 이내에 수행되어야 합니다."
