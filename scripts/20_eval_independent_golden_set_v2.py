"""
20_eval_independent_golden_set_v2.py

Phase 1 외부 독립 교차 검증 골든셋 v2 정밀도 및 Cohen Kappa 일치도 동적 계산 파이프라인
하드코딩 수치 전면 제거 및 reviewer_labels.json 실측 대조 연산 구현
"""

import json
import os
import sys


def calculate_cohen_kappa(eval_a: list[bool], eval_b: list[bool]) -> float:
    """2인 라벨러 간 Cohen Kappa 일치도 수식 산출"""
    if not eval_a or len(eval_a) != len(eval_b):
        return 0.0

    total = len(eval_a)
    agree = sum(1 for a, b in zip(eval_a, eval_b) if a == b)
    po = agree / total

    p_a_true = sum(1 for a in eval_a if a) / total
    p_b_true = sum(1 for b in eval_b if b) / total
    pe = (p_a_true * p_b_true) + ((1 - p_a_true) * (1 - p_b_true))

    if pe == 1.0:
        return 1.0
    return round((po - pe) / (1 - pe), 2)

def evaluate_independent_golden_set_v2():
    golden_dir = os.path.join("intermediate_results", "golden_set_v2")
    labels_file = os.path.join(golden_dir, "reviewer_labels.json")

    if not os.path.exists(labels_file):
        print(f"오류: 실제 라벨링 파일 부재: {labels_file}")
        return None

    with open(labels_file, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    evaluations = data.get("sample_evaluations", [])
    if not evaluations:
        print("오류: 라벨 데이터 샘플 부재")
        return None

    eval_a = [item["reviewer_a_decision"] for item in evaluations]
    eval_b = [item["reviewer_b_decision"] for item in evaluations]
    ground_truth = [item["ground_truth"] for item in evaluations]

    kappa = calculate_cohen_kappa(eval_a, eval_b)

    # TP, FP, FN 실측 계산
    tp = sum(1 for a, gt in zip(eval_a, ground_truth) if a and gt)
    fp = sum(1 for a, gt in zip(eval_a, ground_truth) if a and not gt)
    fn = sum(1 for a, gt in zip(eval_a, ground_truth) if not a and gt)

    precision = round((tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 100.0, 2)
    recall = round((tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 100.0, 2)

    result_metrics = {
        "dataset_version": "v2.0_dynamic",
        "total_samples_evaluated": len(evaluations),
        "cohen_kappa_agreement": kappa,
        "calculated_precision_percent": precision,
        "calculated_recall_percent": recall,
        "tp_count": tp,
        "fp_count": fp,
        "fn_count": fn,
        "is_mock": False
    }

    output_schema_file = os.path.join(golden_dir, "label_schema.json")
    with open(output_schema_file, "w", encoding="utf-8") as fp:
        json.dump(result_metrics, fp, ensure_ascii=False, indent=2)

    print(f"Phase 1 실측 평가 완료 (하드코딩 제거): 샘플수={len(evaluations)}, Kappa={kappa}, Precision={precision}%, Recall={recall}%")
    return result_metrics

def main():
    print("=== Phase 1 동적 연산 독립 골든셋 v2 실측 평가 시작 ===")
    metrics = evaluate_independent_golden_set_v2()
    if metrics and metrics.get("calculated_precision_percent", 0) >= 75.0:
        print("=== Phase 1 독립 골든셋 동적 연산 실측 검증 성공 ===")
        return 0
    else:
        print("=== Phase 1 독립 골든셋 검증 실패 ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())
