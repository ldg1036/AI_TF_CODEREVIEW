"""
WinCC OA 실물 샘플 8종 대상 파이프라인 5회 연속 실행 및 p95 성능 Baseline 측정 스크립트.
"""

import csv
import json
import statistics
import sys
import time
from pathlib import Path

# wincc_reviewer 패키지 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wincc_reviewer"))

from app.core.pipeline import Pipeline, PipelineConfig


def measure_p95_baseline():
    project_root = Path(__file__).resolve().parent.parent
    primary_data_dir = project_root / "primary_data"
    output_dir = project_root / "intermediate_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== 파이프라인 5회 연속 실행 및 p95 성능 Baseline 측정 시작 ===")

    run_timings = []
    run_violations_counts = []
    iterations = 5

    for i in range(1, iterations + 1):
        print(f"\n[실행 회차 {i} / {iterations}] 파이프라인 가동 중...")
        cfg = PipelineConfig(
            input_path=primary_data_dir,
            output_dir=output_dir / f"baseline_run_{i}",
            no_ai=True
        )
        start_ts = time.time()
        pipeline = Pipeline(cfg)
        report = pipeline.run()
        end_ts = time.time()

        elapsed_ms = int((end_ts - start_ts) * 1000)
        run_timings.append(elapsed_ms)
        run_violations_counts.append(report.metrics.violation_count)

        print(f"  * 소요 시간: {elapsed_ms} ms (검출 위반: {report.metrics.violation_count} 건, 처리 파일: {report.metrics.file_count} 개)")

    # 통계 계산
    sorted_timings = sorted(run_timings)
    min_ms = sorted_timings[0]
    max_ms = sorted_timings[-1]
    mean_ms = int(statistics.mean(sorted_timings))
    median_ms = int(statistics.median(sorted_timings))

    # p95 계산 (5회 중 95백분위수: 가장 높은 값 근사 또는 인덱스 계산)
    idx_p95 = int(len(sorted_timings) * 0.95)
    idx_p95 = min(idx_p95, len(sorted_timings) - 1)
    p95_ms = sorted_timings[idx_p95]

    print("\n=== 성능 Baseline 통계 요약 (5회 반복) ===")
    print(f"  * 최소 시간(Min): {min_ms} ms")
    print(f"  * 평균 시간(Mean): {mean_ms} ms")
    print(f"  * 중앙값(Median): {median_ms} ms")
    print(f"  * 95 백분위수(p95 Baseline): {p95_ms} ms")
    print(f"  * 최대 시간(Max): {max_ms} ms")

    # JSON 저장
    output_json = output_dir / "performance_baseline_p95.json"
    with open(output_json, "w", encoding="utf-8-sig") as f:
        json.dump({
            "iterations": iterations,
            "timings_ms": run_timings,
            "min_ms": min_ms,
            "mean_ms": mean_ms,
            "median_ms": median_ms,
            "p95_baseline_ms": p95_ms,
            "max_ms": max_ms,
            "file_count": 8,
            "violations_count": run_violations_counts[0] if run_violations_counts else 0
        }, f, ensure_ascii=False, indent=2)

    # CSV 저장 (utf-8-sig 인코딩 적용)
    output_csv = output_dir / "performance_baseline_records.csv"
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "elapsed_ms", "violations_count"])
        for idx, t_ms in enumerate(run_timings, start=1):
            writer.writerow([idx, t_ms, run_violations_counts[idx - 1]])

    print(f"\n성능 Baseline 결과 저장 완료: JSON={output_json}, CSV={output_csv}")

if __name__ == "__main__":
    measure_p95_baseline()
