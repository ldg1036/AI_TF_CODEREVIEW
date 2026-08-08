"""
WinCC OA 실물 샘플 골든셋 재검증 및 정확도 지표 재측정 스크립트.
"""

import csv
import json
import logging
import sys
from pathlib import Path

# 프로젝트 루트 및 wincc_reviewer 경로 추가
base_dir = Path(__file__).resolve().parent.parent
wincc_dir = base_dir / "wincc_reviewer"
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))
if str(wincc_dir) not in sys.path:
    sys.path.insert(0, str(wincc_dir))

from app.core.pipeline import Pipeline, PipelineConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GoldenSetRevalidation")


def run_golden_set_revalidation() -> None:
    """primary_data 실물 샘플 8종 대상 재검증 파이프라인 실행 및 결과 산출"""
    target_dir = base_dir / "primary_data"
    if not target_dir.exists():
        logger.error("primary_data 폴더가 존재하지 않습니다: %s", target_dir)
        return

    logger.info("1. primary_data 실물 샘플 탐색 시작: %s", target_dir)
    files = [f for f in target_dir.iterdir() if f.is_file()]
    logger.info("총 발견된 실물 파일 수: %d개", len(files))

    config = PipelineConfig(
        input_path=target_dir,
        no_ai=True,
        no_autofix=True,
        output_dir=base_dir / "intermediate_results" / "golden_set_html",
    )
    pipeline = Pipeline(config)
    rulesets = pipeline._load_rulesets()

    rule_map = {}
    for rtype, res in rulesets.items():
        for r in res.rules:
            rule_map[r.rule_id] = r

    logger.info("2. 리뷰 파이프라인 정적 검사 실행 (완화 로직 적용 후)")
    report = pipeline.run()

    logger.info("3. 실행 완료 및 통계 집계")
    logger.info("스캔 파일 수: %d개, 위반 발견 건수: %d건", len(report.files), len(report.violations))

    violations_data = []
    rule_detection_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}

    for v in report.violations:
        rid = v.rule_id
        rule_def = rule_map.get(rid)
        rule_name = rule_def.check_item if rule_def else "미매핑"
        checker_key = rule_def.checker_key if rule_def else "N/A"
        sev = str(v.severity.value if hasattr(v.severity, "value") else v.severity)

        rule_detection_counts[rid] = rule_detection_counts.get(rid, 0) + 1
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        violations_data.append({
            "file_name": Path(v.file_id).name,
            "rule_id": rid,
            "rule_name": rule_name,
            "checker_key": checker_key,
            "severity": sev,
            "line_start": v.line_start or 0,
            "line_end": v.line_end or 0,
            "code_snippet": (v.snippet or "").strip(),
            "message": v.message,
        })

    logger.info("4. 룰별 재검증 검출 수량:")
    for rid, count in sorted(rule_detection_counts.items()):
        logger.info("  * 룰 ID: %s | 검출건수: %d건", rid, count)

    # 결과 산출물 저장 경로
    out_json = base_dir / "intermediate_results" / "golden_set_metrics.json"
    out_csv = base_dir / "secondary_data" / "golden_set_revalidation_summary.csv"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    summary_data = {
        "evaluation_target": "primary_data_8_real_samples",
        "total_files": len(report.files),
        "total_violations": len(report.violations),
        "timings_ms": report.metrics.timings_ms,
        "rule_detection_counts": rule_detection_counts,
        "severity_counts": severity_counts,
        "note": "오탐 완화 로직(Pnl init context 및 batch operation exception) 반영 후 재검증 지표",
    }

    with open(out_json, "w", encoding="utf_8_sig") as f_json:
        json.dump({"summary": summary_data, "violations": violations_data}, f_json, ensure_ascii=False, indent=2)

    with open(out_csv, "w", encoding="utf_8_sig", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=[
            "file_name",
            "rule_id",
            "rule_name",
            "checker_key",
            "severity",
            "line_start",
            "line_end",
            "code_snippet",
            "message",
        ])
        writer.writeheader()
        writer.writerows(violations_data)

    logger.info("골든셋 재검증 JSON 및 CSV 결과 저장 완료.")


if __name__ == "__main__":
    run_golden_set_revalidation()
