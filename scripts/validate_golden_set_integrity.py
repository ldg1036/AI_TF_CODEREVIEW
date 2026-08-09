"""
validate_golden_set_integrity.py

골든셋 v3 자동 이상탐지 검증기 (Anti-Gaming 1~4원칙 준수).
아래 7가지 FAIL 조건 중 하나라도 해당 시 즉시 파이프라인을 FAIL 처리합니다.

[FAIL 조건]
1. 표본 수 < 60
2. reviewer_a_decision == reviewer_b_decision 인 비율 > 95% (이견 5% 미만)
3. Cohen's Kappa 계산값 == 1.0 (정확히 1.0인 경우)
4. Precision 또는 Recall == 100.0 (정확히 100.0)
5. 전체 샘플 중 동일 원본 파일에서 파생된 샘플 비율 > 40%
6. reviewer_rationale 필드가 50자 미만이거나 공백인 샘플 비율 > 30%
7. 라벨링 소요시간이 샘플당 평균 30초 미만
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
v3_dir = base_dir / "intermediate_results" / "golden_set_v3"
manifest_file = base_dir / "intermediate_results" / "golden_set_v3_manifest.json"


def calculate_kappa(table: list[list[int]]) -> float:
    total = sum(sum(row) for row in table)
    if total == 0:
        return 0.0
    po = sum(table[i][i] for i in range(len(table))) / total
    pe = 0.0
    for i in range(len(table)):
        row_sum = sum(table[i])
        col_sum = sum(table[j][i] for j in range(len(table)))
        pe += (row_sum * col_sum) / (total * total)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def validate_golden_set_v3_dataset(dataset_file: Path) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not dataset_file.exists():
        return False, [f"골든셋 v3 데이터셋 파일이 존재하지 않습니다: {dataset_file}"]

    with open(dataset_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data.get("samples", [])

    # Condition 1: Sample count < 60
    if len(samples) < 60:
        reasons.append(f"[FAIL 1] 표본 수 부족: {len(samples)}개 < 60개")

    if not samples:
        return False, reasons

    # Condition 2: Agreement rate > 95% (Disagreement < 5%)
    agree_count = 0
    short_rationale_count = 0
    file_origin_counts: dict[str, int] = {}
    total_duration_sec = 0.0

    for s in samples:
        dec_a = s.get("reviewer_a_decision")
        dec_b = s.get("reviewer_b_decision")
        if dec_a == dec_b:
            agree_count += 1

        rat_a = s.get("reviewer_a_rationale", "")
        rat_b = s.get("reviewer_b_rationale", "")
        if len(rat_a.strip()) < 50 or len(rat_b.strip()) < 50:
            short_rationale_count += 1

        origin = s.get("source_file_basename", "unknown")
        file_origin_counts[origin] = file_origin_counts.get(origin, 0) + 1
        total_duration_sec += float(s.get("labeling_duration_sec", 0))

    agree_ratio = agree_count / len(samples)
    if agree_ratio > 0.95:
        reasons.append(f"[FAIL 2] 이견 비율 미달 (일치율 {agree_ratio*100:.1f}% > 95.0%)")

    # Condition 3: Cohen's Kappa == 1.0
    # Construct 2x2 confusion matrix (PASS vs FAIL)
    tp = sum(1 for s in samples if s.get("reviewer_a_decision") == "FAIL" and s.get("reviewer_b_decision") == "FAIL")
    tn = sum(1 for s in samples if s.get("reviewer_a_decision") == "PASS" and s.get("reviewer_b_decision") == "PASS")
    fp = sum(1 for s in samples if s.get("reviewer_a_decision") == "PASS" and s.get("reviewer_b_decision") == "FAIL")
    fn = sum(1 for s in samples if s.get("reviewer_a_decision") == "FAIL" and s.get("reviewer_b_decision") == "PASS")

    table = [[tp, fp], [fn, tn]]
    kappa = calculate_kappa(table)
    if math.isclose(kappa, 1.0, abs_tol=1e-9):
        reasons.append(f"[FAIL 3] 비현실적인 완벽 일치: Cohen's Kappa = {kappa:.4f} == 1.0")

    # Condition 4: Precision or Recall == 100.0
    prec = data.get("metrics", {}).get("precision_percent", 0.0)
    rec = data.get("metrics", {}).get("recall_percent", 0.0)
    if math.isclose(prec, 100.0, abs_tol=1e-9) or math.isclose(rec, 100.0, abs_tol=1e-9):
        reasons.append(f"[FAIL 4] 비현실적 지표: Precision({prec}%) 또는 Recall({rec}%) == 100.0%")

    # Condition 5: Same origin file ratio > 40%
    max_origin_count = max(file_origin_counts.values()) if file_origin_counts else 0
    max_origin_ratio = max_origin_count / len(samples)
    if max_origin_ratio > 0.40:
        reasons.append(f"[FAIL 5] 샘플 다양성 부족: 단일 파일 파생 비율 {max_origin_ratio*100:.1f}% > 40.0%")

    # Condition 6: Short rationale ratio > 30%
    short_rationale_ratio = short_rationale_count / len(samples)
    if short_rationale_ratio > 0.30:
        reasons.append(f"[FAIL 6] 라벨 판단근거 미흡 비율 {short_rationale_ratio*100:.1f}% > 30.0%")

    # Condition 7: Avg labeling time < 30 sec per sample
    avg_duration = total_duration_sec / len(samples)
    if avg_duration < 30.0:
        reasons.append(f"[FAIL 7] 비정상적 고속 라벨링: 샘플당 평균 소요시간 {avg_duration:.1f}초 < 30.0초")

    return len(reasons) == 0, reasons


def main() -> None:
    dataset_path = v3_dir / "golden_set_v3_samples.json"
    is_valid, errors = validate_golden_set_v3_dataset(dataset_path)

    if not is_valid:
        print("=== [GOLDEN SET INTEGRITY VALIDATION FAILED] ===")
        for err in errors:
            print(f" * {err}")
        sys.exit(1)

    print("=== [GOLDEN SET INTEGRITY VALIDATION PASSED] 골든셋 v3 무결성 검증 완수 ===")


if __name__ == "__main__":
    main()
