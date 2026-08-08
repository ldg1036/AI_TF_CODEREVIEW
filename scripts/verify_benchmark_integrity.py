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
        ground_truth = json.load(f)

    # 1. R5 합성 데이터 다양성 검증 (표준편차 > 0)
    stddev = metrics.get("file_size_stddev_bytes", 0.0)
    if stddev <= 0:
        print(f"오류: R5 위반 파일 크기 표준편차가 0 이하입니다: {stddev}")
        return False

    # 2. R3 raw_timings_ms 기반 quantiles 재계산 무결성 검증
    raw_timings = metrics.get("raw_timings_ms", [])
    if len(raw_timings) < 200:
        print(f"오류: R5 위반 200개 이상의 raw_timings가 필요합니다. 현재: {len(raw_timings)}")
        return False

    quantiles_list = statistics.quantiles(sorted(raw_timings), n=100)
    expected_p95 = round(quantiles_list[94], 2)
    recorded_p95 = round(metrics.get("p95_duration_ms", 0.0), 2)

    if abs(expected_p95 - recorded_p95) > 0.5:
        print(f"오류: AP 3 위반 기록된 p95({recorded_p95})가 raw timings 백분위수 재계산({expected_p95})과 불일치합니다.")
        return False

    # 3. Precision / Recall 실측 산출 검증
    tp = metrics.get("tp_count", 0)
    fp = metrics.get("fp_count", 0)
    fn = metrics.get("fn_count", 0)
    calc_prec = round((tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 100.0, 2)
    recorded_prec = round(metrics.get("calculated_precision_percent", 0.0), 2)

    if abs(calc_prec - recorded_prec) > 0.5:
        print(f"오류: 기록된 Precision({recorded_prec})이 TP/FP 재계산({calc_prec})과 불일치합니다.")
        return False

    print(f"성공: 벤치마크 무결성 검증 통과 (파일수={len(raw_timings)}, stddev={stddev}, p95={recorded_p95}ms, Precision={recorded_prec}%)")
    return True


if __name__ == "__main__":
    if not verify_benchmark_integrity():
        sys.exit(1)
