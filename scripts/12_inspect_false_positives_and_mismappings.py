"""
WinCC OA 실물 샘플 209건 위반에 대한 오매핑(Mismapping) 및 오탐(False Positive) 정밀 검사 스크립트.
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
logger = logging.getLogger("FalsePositiveInspector")


def inspect_mismappings_and_false_positives() -> None:
    """209건 위반 데이터를 대상으로 오매핑 및 오탐 가능성을 심층 검사합니다."""
    target_dir = Path(r"C:\Users\39145\Downloads\Coder_Wincc-main\CodeReview_Data\새 폴더")
    if not target_dir.exists():
        logger.error("대상 폴더가 존재하지 않습니다: %s", target_dir)
        return

    logger.info("1. 파이프라인 및 엑셀 룰셋 로드")
    config = PipelineConfig(
        input_path=target_dir,
        no_ai=True,
        no_autofix=True,
        output_dir=base_dir / "intermediate_results" / "sample_folder_html",
    )
    pipeline = Pipeline(config)
    rulesets = pipeline._load_rulesets()

    rule_map = {}
    for rtype, res in rulesets.items():
        for r in res.rules:
            rule_map[r.rule_id] = r

    report = pipeline.run()
    logger.info("총 위반 건수: %d건", len(report.violations))

    # 오매핑(Mismapping) 검사: rule_id와 checker_type/source_key의 논리적 불일치 검사
    mismapping_count = 0
    mismapping_details = []

    # 오탐/과다탐지(False Positive / Over-detection) 분류 카운터
    tp_count = 0  # 정탐 (True Positive)
    fp_candidate_count = 0  # 컨텍스트 기반 오탐 의심 또는 예외 허용 대상
    fp_details = []

    # 파일별 콘텐츠 캐시 (주석 및 문맥 확인용)
    file_contents = {}
    for fpath in target_dir.iterdir():
        if fpath.is_file():
            try:
                file_contents[fpath.name] = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                file_contents[fpath.name] = []

    for v in report.violations:
        rid = v.rule_id
        rule_def = rule_map.get(rid)
        fname = Path(v.file_id).name
        snippet = (v.snippet or "").strip()
        lno = v.line_start or 0

        # 1) 오매핑 검사
        is_mismapped = False
        reason_mismapping = ""
        if not rule_def:
            is_mismapped = True
            reason_mismapping = "엑셀 룰셋에 매핑되는 룰 정의가 없음"
        else:
            # 규칙 ID와 체커 식별자의 논리적 일치 여부 확인
            if rid == "CTL_PRF_002" and rule_def.checker_key != "ctl.batch_dp_ops":
                is_mismapped = True
                reason_mismapping = "CTL_PRF_002가 ctl.batch_dp_ops 체커와 매핑되지 않음"
            elif rid == "CTL_RES_001" and rule_def.checker_key != "ctl.dp_connect_pair":
                is_mismapped = True
                reason_mismapping = "CTL_RES_001이 ctl.dp_connect_pair 체커와 매핑되지 않음"
            elif rid == "CTL_ERR_002" and rule_def.checker_key != "ctl.try_catch":
                is_mismapped = True
                reason_mismapping = "CTL_ERR_002가 ctl.try_catch 체커와 매핑되지 않음"
            elif rid == "CTL_PRF_001" and rule_def.checker_key != "ctl.loop_delay":
                is_mismapped = True
                reason_mismapping = "CTL_PRF_001이 ctl.loop_delay 체커와 매핑되지 않음"

        if is_mismapped:
            mismapping_count += 1
            mismapping_details.append({
                "file_name": fname,
                "rule_id": rid,
                "line": lno,
                "snippet": snippet,
                "reason": reason_mismapping,
            })

        # 2) 오탐(False Positive / Over-detection) 후보 검사
        is_fp_candidate = False
        fp_reason = ""
        classification_type = "True Positive (정탐)"

        if rid == "CTL_RES_001":
            # PNL 화면 스크립트에서 UI 닫힘 시 자동 해제되는 dpConnect는 개발자 관점에서 허용 예외 대상일 수 있음
            if fname.endswith(".pnl") or fname.endswith("_pnl.txt"):
                is_fp_candidate = True
                fp_reason = "UI 패널 스크립트 내 dpConnect 호출 (화면 종료 시 자동 해제되는 컨텍스트 예외 허용 대상)"
                classification_type = "Contextual Exception (컨텍스트 예외)"

        elif rid == "CTL_PRF_002":
            # 15라인 이내 3회 이상 밀집이지만 if/else if 등 분기문 안에 개별적으로 존재하는 경우
            lines = file_contents.get(fname, [])
            surrounding = ""
            start_idx = max(0, lno - 3)
            end_idx = min(len(lines), lno + 3)
            for idx in range(start_idx, end_idx):
                surrounding += lines[idx] + " "
            if "if (" in surrounding or "else if" in surrounding or "case " in surrounding:
                is_fp_candidate = True
                fp_reason = "조건문(if/else/case) 분기 내부의 단건 호출 (동시 실행 배치 호출이 아닌 분기 호출 가능성)"
                classification_type = "Potential Over-detection (분기문 내 단건 호출)"

        elif rid == "CTL_ERR_002":
            # Try Catch 미비로 잡혔으나 main이나 기본 콜백 단건인 경우
            if "main(" in snippet or "EventInitialize" in snippet:
                is_fp_candidate = False

        if is_fp_candidate:
            fp_candidate_count += 1
            fp_details.append({
                "file_name": fname,
                "rule_id": rid,
                "line": lno,
                "snippet": snippet,
                "classification_type": classification_type,
                "reason": fp_reason,
            })
        else:
            tp_count += 1

    logger.info("=== [오매핑 및 오탐 검사 결과 요약] ===")
    logger.info("1. 전체 검출 건수: %d건", len(report.violations))
    logger.info("2. 오매핑(Mismapping) 건수: %d건", mismapping_count)
    logger.info("3. 정탐(True Positive) 건수: %d건", tp_count)
    logger.info("4. 컨텍스트 예외 및 오탐 의심(Contextual Exception / Over-detection) 건수: %d건", fp_candidate_count)

    # 룰별 오탐/예외 분류 통계
    rule_fp_stats: dict[str, dict[str, int]] = {}
    for v in report.violations:
        rid = v.rule_id
        if rid not in rule_fp_stats:
            rule_fp_stats[rid] = {"total": 0, "tp": 0, "context_except_or_fp": 0}
        rule_fp_stats[rid]["total"] += 1

    for item in fp_details:
        rid = item["rule_id"]
        rule_fp_stats[rid]["context_except_or_fp"] += 1

    for rid, stats in rule_fp_stats.items():
        stats["tp"] = stats["total"] - stats["context_except_or_fp"]
        logger.info("  * 룰 %s: 총 %d건 -> 정탐 %d건 | 예외/의심 %d건", rid, stats["total"], stats["tp"], stats["context_except_or_fp"])

    # 결과 JSON 및 CSV 저장
    out_json = base_dir / "intermediate_results" / "12_mismapping_inspection_results.json"
    out_csv = base_dir / "secondary_data" / "12_mismapping_and_false_positive_analysis.csv"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    result_json = {
        "summary": {
            "total_violations": len(report.violations),
            "mismapping_count": mismapping_count,
            "true_positive_count": tp_count,
            "context_except_or_fp_count": fp_candidate_count,
            "rule_fp_stats": rule_fp_stats,
        },
        "mismapping_details": mismapping_details,
        "fp_details": fp_details,
    }

    with open(out_json, "w", encoding="utf_8_sig") as f_json:
        json.dump(result_json, f_json, ensure_ascii=False, indent=2)
    logger.info("JSON 결과 저장 완료: %s", out_json)

    with open(out_csv, "w", encoding="utf_8_sig", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=[
            "file_name",
            "rule_id",
            "line",
            "snippet",
            "classification_type",
            "reason",
        ])
        writer.writeheader()
        for item in fp_details:
            writer.writerow(item)
    logger.info("CSV 상세 명세 저장 완료: %s", out_csv)


if __name__ == "__main__":
    inspect_mismappings_and_false_positives()
