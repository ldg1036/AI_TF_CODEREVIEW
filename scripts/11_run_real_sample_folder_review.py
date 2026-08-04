"""
WinCC OA 실물 프로젝트 폴더 코드 리뷰 검출 및 룰 매핑 검증 스크립트.
"""

import csv
import json
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 PATH에 추가
base_dir = Path(__file__).resolve().parent.parent
wincc_dir = base_dir / "wincc_reviewer"
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))
if str(wincc_dir) not in sys.path:
    sys.path.insert(0, str(wincc_dir))

from app.core.pipeline import Pipeline, PipelineConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RealSampleReviewScript")


def run_sample_folder_review() -> None:
    """실물 샘플 폴더에 대해 리뷰 파이프라인을 실행하고 결과를 기록합니다."""
    target_dir = Path(r"C:\Users\39145\Downloads\Coder_Wincc-main\CodeReview_Data\새 폴더")
    if not target_dir.exists():
        logger.error("대상 폴더가 존재하지 않습니다: %s", target_dir)
        return

    logger.info("1. 실물 샘플 폴더 탐색 시작: %s", target_dir)
    files = [f for f in target_dir.iterdir() if f.is_file()]
    logger.info("총 발견된 파일 수: %d개", len(files))
    for f in files:
        logger.info("  * 파일명: %s (크기: %d 바이트)", f.name, f.stat().st_size)

    logger.info("2. 엑셀 룰셋 로드 및 매핑 무결성 검사")
    config = PipelineConfig(
        input_path=target_dir,
        no_ai=True,
        no_autofix=True,
        output_dir=base_dir / "intermediate_results" / "sample_folder_html",
    )
    pipeline = Pipeline(config)
    rulesets = pipeline._load_rulesets()

    rule_map = {}
    total_excel_rules = 0
    for rtype, res in rulesets.items():
        logger.info("  * %s 룰셋 컴파일 성공: 룰 수 = %d개", rtype, len(res.rules))
        total_excel_rules += len(res.rules)
        for r in res.rules:
            rule_map[r.rule_id] = r
    logger.info("로드된 통합 엑셀 룰 정의 수: %d개", len(rule_map))

    logger.info("3. 리뷰 파이프라인 정적 검사 실행")
    report = pipeline.run()

    logger.info("4. 실행 완료 및 통계 집계")
    logger.info("  * 전체 스캔 파일 수: %d개", len(report.files))
    logger.info("  * 위반 발견 건수: %d건", len(report.violations))
    logger.info("  * 실행 시간(ms): %s", report.metrics.timings_ms)

    # 파싱 상태 요약
    parse_summary = []
    for pstatus in report.errors:
        parse_summary.append({
            "file": Path(pstatus.file).name,
            "status": str(pstatus.status.value if hasattr(pstatus.status, "value") else pstatus.status),
            "error": pstatus.error_message or "",
        })
        logger.info("  [파싱 오류/알림] %s -> status=%s", Path(pstatus.file).name, pstatus.status)

    # 위반 내역 및 룰 매핑 분석
    violations_data = []
    rule_detection_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    mapped_count = 0
    unmapped_count = 0

    for v in report.violations:
        rid = v.rule_id
        rule_def = rule_map.get(rid)
        rule_name = rule_def.check_item if rule_def else "매핑 정보 없음"
        checker_key = rule_def.checker_key if rule_def else "N/A"
        source_key = rule_def.source_key if rule_def else "N/A"
        sev = str(v.severity.value if hasattr(v.severity, "value") else v.severity)

        rule_detection_counts[rid] = rule_detection_counts.get(rid, 0) + 1
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        if rule_def:
            mapped_count += 1
        else:
            unmapped_count += 1

        violations_data.append({
            "file_name": Path(v.file_id).name,
            "rule_id": rid,
            "rule_name": rule_name,
            "checker_key": checker_key,
            "source_key": source_key,
            "severity": sev,
            "line_start": v.line_start or 0,
            "line_end": v.line_end or 0,
            "code_snippet": (v.snippet or "").strip(),
            "message": v.message,
            "is_mapped_to_excel": bool(rule_def),
        })

    logger.info("5. 룰별 검출 및 엑셀 매핑 현황:")
    logger.info("  * 정상 엑셀 룰 매핑 위반 수: %d건, 미매핑 룰 위반 수: %d건", mapped_count, unmapped_count)
    for rid, count in sorted(rule_detection_counts.items()):
        rule_def = rule_map.get(rid)
        rname = rule_def.check_item if rule_def else "미등록 룰"
        ckey = rule_def.checker_key if rule_def else "N/A"
        skey = rule_def.source_key if rule_def else "N/A"
        logger.info("  * 룰 ID: %s | 체커: %s | 소스키: %s | 매핑: %s | 검출건수: %d건 | 명칭: %s", rid, ckey, skey, "YES" if rule_def else "NO", count, rname)

    logger.info("6. 심각도별 분포:")
    for sev, count in sorted(severity_counts.items()):
        logger.info("  * %s: %d건", sev, count)

    # 결과 산출물 폴더 준비
    out_json = base_dir / "intermediate_results" / "11_sample_folder_review_results.json"
    out_csv = base_dir / "secondary_data" / "11_sample_folder_violation_summary.csv"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # JSON 저장
    full_output = {
        "summary": {
            "total_files": len(report.files),
            "total_violations": len(report.violations),
            "timings_ms": report.metrics.timings_ms,
            "mapped_violations": mapped_count,
            "unmapped_violations": unmapped_count,
            "severity_counts": severity_counts,
            "rule_detection_counts": rule_detection_counts,
        },
        "parse_summary": parse_summary,
        "violations": violations_data,
    }
    with open(out_json, "w", encoding="utf_8_sig") as f_json:
        json.dump(full_output, f_json, ensure_ascii=False, indent=2)
    logger.info("JSON 분석 결과 저장 완료: %s", out_json)

    # CSV 저장 (utf_8_sig)
    with open(out_csv, "w", encoding="utf_8_sig", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=[
            "file_name",
            "rule_id",
            "rule_name",
            "checker_key",
            "source_key",
            "severity",
            "line_start",
            "line_end",
            "code_snippet",
            "message",
            "is_mapped_to_excel",
        ])
        writer.writeheader()
        writer.writerows(violations_data)
    logger.info("CSV 위반 목록 저장 완료: %s", out_csv)


if __name__ == "__main__":
    run_sample_folder_review()
