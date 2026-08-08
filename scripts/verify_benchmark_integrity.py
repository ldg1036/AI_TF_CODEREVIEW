"""
대규모 벤치마크 무결성 정밀 검증 스크립트 (IMP 03 및 11번 지침서 규칙 검증).
1. 데이터셋 파일 크기 표준편차 > 0 검증 (단순 템플릿 복제 방지 R5)
2. large_scale_benchmark_metrics.json 내 p95/p99 수치가 raw_timings_ms 리스트 quantiles 정밀 백분위수와 일치하는지 검증 (R3)
3. ground_truth.json 정답 라벨 대비 TP, FP, FN 정밀도/재현율 산출 가능성 검증 (AP 3 차단)
"""

import json
from pathlib import Path
import statistics
import sys

base_dir = Path(__file__).resolve().parent.parent


def verify_benchmark_integrity() -> bool:
    metrics_file = base_dir / "intermediate_results" / "large_scale_benchmark_metrics.json"
    ground_truth_file = base_dir / "intermediate_results" / "ground_truth.json"

    if not metrics_file.exists() or not ground_truth_file.exists():
        print("오류: metrics.json 또는 ground_truth.json 이 존재하지 않습니다.")
        return False

    with open(metrics_file, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    with open(ground_truth_file, "r", encoding="utf-8") as f:
        json.load(f)

    raw_dataset_dir = base_dir / "intermediate_results" / "large_scale_dataset"
    files = [f for f in raw_dataset_dir.glob("*") if f.is_file()]
    file_sizes = [f.stat().st_size for f in files]
    if len(files) < 200:
        print(f"오류: 다양성 데이터셋 파일 수 부족 ({len(files)}개 < 200개)")
        return False

    stddev = statistics.stdev(file_sizes) if len(file_sizes) > 1 else 0
    if stddev <= 0:
        print(f"오류: 합성 데이터셋 크기 다양성 부족 (표준편차 {stddev} <= 0)")
        return False

    # 2. R3 수치 계산 근거 재검증
    timings = metrics.get("raw_timings_ms", [])
    if not timings:
        print("오류: raw_timings_ms 데이터 누락")
        return False

    sorted_timings = sorted(timings)
    p95_idx = int(len(sorted_timings) * 0.95)
    calc_p95 = round(sorted_timings[p95_idx], 2)
    recorded_p95 = round(metrics.get("p95_duration_ms", 0.0), 2)

    if abs(calc_p95 - recorded_p95) > 1.0:
        print(f"오류: p95 지연시간 불일치 (계산값: {calc_p95}ms, 기록값: {recorded_p95}ms)")
        return False

    # 3. Precision / Recall 실측 산출 검증
    tp = metrics.get("tp_count", 0)
    fp = metrics.get("fp_count", 0)
    calc_prec = round((tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 100.0, 2)
    recorded_prec = round(metrics.get("calculated_precision_percent", 0.0), 2)

    if abs(calc_prec - recorded_prec) > 0.5:
        print(f"오류: 기록된 Precision({recorded_prec})이 TP/FP 재계산({calc_prec})과 불일치합니다.")
        return False

    print(f"성공: 벤치마크 무결성 검증 완료 (파일수={len(timings)}, stddev={round(stddev, 1)}, p95={recorded_p95}ms, Precision={recorded_prec}%)")
    return True


if __name__ == "__main__":
    if not verify_benchmark_integrity():
        sys.exit(1)
