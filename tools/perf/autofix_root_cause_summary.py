import argparse
import datetime
import glob
import json
from pathlib import Path
from typing import Dict, List


def _now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _sum_counts(target: Dict[str, int], source: Dict) -> None:
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        try:
            amount = int(value)
        except (TypeError, ValueError):
            amount = 0
        target[str(key)] = target.get(str(key), 0) + amount


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_summary(path: Path) -> Dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "path": str(path),
        "run_count": _safe_int(summary.get("run_count", 0)),
        "apply_attempts": _safe_int(summary.get("apply_attempts", 0)),
        "apply_success_count": _safe_int(summary.get("apply_success_count", 0)),
        "anchor_mismatch_failure_count": _safe_int(summary.get("anchor_mismatch_failure_count", 0)),
        "instruction_apply_rate": float(summary.get("instruction_apply_rate", 0.0) or 0.0),
        "instruction_validation_fail_rate": float(summary.get("instruction_validation_fail_rate", 0.0) or 0.0),
        "error_code_counts": summary.get("error_code_counts", {}),
        "validation_error_fragment_counts": summary.get("validation_error_fragment_counts", {}),
        "instruction_fail_stage_distribution": summary.get("instruction_fail_stage_distribution", {}),
    }


def build_root_cause_summary(rows: List[Dict]) -> Dict:
    agg_error_codes: Dict[str, int] = {}
    agg_validation_fragments: Dict[str, int] = {}
    agg_instruction_fail_stages: Dict[str, int] = {}

    total_run_count = 0
    total_apply_attempts = 0
    total_apply_success = 0
    total_anchor_mismatch_failures = 0
    weighted_instruction_apply_rate = 0.0
    weighted_instruction_validation_fail_rate = 0.0

    for row in rows:
        total_run_count += row["run_count"]
        total_apply_attempts += row["apply_attempts"]
        total_apply_success += row["apply_success_count"]
        total_anchor_mismatch_failures += row["anchor_mismatch_failure_count"]
        weighted_instruction_apply_rate += row["instruction_apply_rate"] * max(row["run_count"], 1)
        weighted_instruction_validation_fail_rate += row["instruction_validation_fail_rate"] * max(row["run_count"], 1)

        _sum_counts(agg_error_codes, row.get("error_code_counts", {}))
        _sum_counts(agg_validation_fragments, row.get("validation_error_fragment_counts", {}))
        _sum_counts(agg_instruction_fail_stages, row.get("instruction_fail_stage_distribution", {}))

    denominator = max(total_run_count, 1)
    avg_instruction_apply_rate = weighted_instruction_apply_rate / denominator
    avg_instruction_validation_fail_rate = weighted_instruction_validation_fail_rate / denominator

    top_error_codes = sorted(agg_error_codes.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    top_validation_fragments = sorted(agg_validation_fragments.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    release_note_snippet = {
        "instruction_apply_rate": round(avg_instruction_apply_rate, 4),
        "instruction_validation_fail_rate": round(avg_instruction_validation_fail_rate, 4),
        "top_error_codes": top_error_codes,
        "top_validation_error_fragments": top_validation_fragments,
        "anchor_mismatch_failure_count": total_anchor_mismatch_failures,
    }

    return {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_file_count": len(rows),
        "total_run_count": total_run_count,
        "total_apply_attempts": total_apply_attempts,
        "total_apply_success_count": total_apply_success,
        "apply_success_rate": round((total_apply_success / max(total_apply_attempts, 1)), 4),
        "anchor_mismatch_failure_count": total_anchor_mismatch_failures,
        "error_code_counts": agg_error_codes,
        "validation_error_fragment_counts": agg_validation_fragments,
        "instruction_fail_stage_distribution": agg_instruction_fail_stages,
        "release_note_snippet": release_note_snippet,
        "source_files": [row["path"] for row in rows],
    }


def to_markdown(payload: Dict) -> str:
    snippet = payload.get("release_note_snippet", {})
    lines = [
        "# Autofix Root Cause Summary",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- input_file_count: {payload.get('input_file_count', 0)}",
        f"- total_run_count: {payload.get('total_run_count', 0)}",
        f"- apply_success_rate: {payload.get('apply_success_rate', 0)}",
        f"- anchor_mismatch_failure_count: {payload.get('anchor_mismatch_failure_count', 0)}",
        "",
        "## Release Note Snippet",
        f"- instruction_apply_rate: {snippet.get('instruction_apply_rate', 0)}",
        f"- instruction_validation_fail_rate: {snippet.get('instruction_validation_fail_rate', 0)}",
        f"- top_error_codes: {json.dumps(snippet.get('top_error_codes', []), ensure_ascii=False)}",
        f"- top_validation_error_fragments: {json.dumps(snippet.get('top_validation_error_fragments', []), ensure_ascii=False)}",
        "",
        "## Error Code Counts",
    ]
    for key, value in sorted((payload.get("error_code_counts") or {}).items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Instruction Fail Stage Distribution")
    for key, value in sorted((payload.get("instruction_fail_stage_distribution") or {}).items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate autofix root-cause metrics from improved baseline JSON files")
    parser.add_argument(
        "--input-glob",
        default="docs/perf_baselines/autofix_apply_improved_*.json",
        help="Glob for autofix improved baseline JSON files",
    )
    parser.add_argument("--output-json", default="", help="Optional output JSON path")
    parser.add_argument("--output-md", default="", help="Optional output markdown path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = sorted(Path(p).resolve() for p in glob.glob(args.input_glob))
    if not files:
        raise FileNotFoundError(f"No files matched: {args.input_glob}")

    rows = [load_summary(path) for path in files]
    payload = build_root_cause_summary(rows)

    default_stem = Path("docs/perf_baselines") / f"autofix_root_cause_summary_{_now_stamp()}"
    output_json = Path(args.output_json).resolve() if args.output_json else default_stem.with_suffix(".json").resolve()
    output_md = Path(args.output_md).resolve() if args.output_md else default_stem.with_suffix(".md").resolve()

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(to_markdown(payload), encoding="utf-8")

    print(f"[+] root cause summary json: {output_json}")
    print(f"[+] root cause summary md: {output_md}")


if __name__ == "__main__":
    main()
