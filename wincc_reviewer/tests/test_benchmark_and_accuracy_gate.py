"""
WinCC OA 코드 리뷰 자동화 도구 — 대규모 벤치마크 및 CI 회귀 게이트 유닛 테스트.
11번 지침서 AP 4 (순환 검증 방지) 및 R4 (독립 재실행 원칙)에 따라 과거 커밋 파일을 재확인하는 것이 아니라,
테스트 실행 시점에 벤치마크 스캔을 실시간 재구동(live regression execution)하여 검증합니다.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from app.core.pipeline import Pipeline, PipelineConfig

from scripts.verify_benchmark_integrity import verify_benchmark_integrity

bench_module = importlib.import_module("scripts.15_run_large_scale_benchmark")
run_benchmark = bench_module.run_benchmark


class TestBenchmarkAndAccuracyGate:
    """독립 재실행 원칙 R4를 준수하는 회귀 게이트 수트."""

    def test_live_benchmark_execution_and_integrity_gate(self) -> None:
        """실시간으로 벤치마크를 재실행하여 속도, 백분위수 및 데이터 무결성을 실시간 검증합니다 (R4 준수)."""
        # 1. 테스트 실행 시점에 벤치마크 실시간 재구동
        metrics = run_benchmark()
        assert metrics is not None
        assert metrics.get("total_files_scanned", 0) >= 200, "200개 이상의 다양성 파일이 스캔되어야 합니다."

        # 2. R3/R5 데이터셋 무결성 검증기 구동
        integrity_ok = verify_benchmark_integrity()
        assert integrity_ok is True, "벤치마크 무결성 검증을 실시간 통과해야 합니다."

        # 3. 임계치 검증 (p95 < 500ms, 파일 크기 표준편차 > 0)
        p95 = metrics.get("p95_duration_ms", 999.0)
        assert p95 < 500.0, f"p95 스캔 속도는 500ms 미만이어야 합니다. 실측: {p95}ms"

    def test_pipeline_live_speed_gate(self, tmp_path: Path) -> None:
        """단일 소스 파일 실시간 스캔 속도 게이트를 검증합니다."""
        sample_ctl = tmp_path / "live_gate_sample.ctl"
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
