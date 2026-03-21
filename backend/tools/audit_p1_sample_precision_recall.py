import argparse
import datetime as dt
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import CodeInspectorApp, DEFAULT_MODE  # noqa: E402


SAMPLE_EXPECTATIONS: List[Dict[str, Any]] = [
    {
        "file": "BenchmarkP1Fixture.ctl",
        "core_expected_p1_rule_ids": [
            "ACTIVE-01",
            "EXC-DP-01",
            "EXC-TRY-01",
            "PERF-SETMULTIVALUE-ADOPT-01",
        ],
        "notes": [
            "Repeated setValue cluster should trigger setMultiValue adoption guidance.",
            "dpSet without explicit error contract should trigger DP/try-catch rules.",
            "Mutating calls exist without active/enable guard.",
        ],
    },
    {
        "file": "GoldenTime.ctl",
        "core_expected_p1_rule_ids": [
            "HARD-01",
            "HARD-03",
            "PERF-EV-01",
            "STYLE-IDX-01",
        ],
        "notes": [
            "Config path literal is hardcoded.",
            "Repeated 0.001 literal should trigger float hardcoding rule.",
            "Loop/helper path contains repeated event exchange pressure via dpSet.",
            "Magic index access appears in parsed config handling.",
        ],
    },
]


def flatten_p1_rule_ids(payload: Dict[str, Any]) -> List[str]:
    ids: Set[str] = set()
    for group in (payload.get("violations", {}) or {}).get("P1", []) or []:
        if not isinstance(group, dict):
            continue
        for violation in group.get("violations", []) or []:
            if not isinstance(violation, dict):
                continue
            rule_id = str(violation.get("rule_id") or "").strip()
            if rule_id:
                ids.add(rule_id)
    return sorted(ids)


def flatten_p2_rule_ids(payload: Dict[str, Any]) -> List[str]:
    ids: Set[str] = set()
    for violation in (payload.get("violations", {}) or {}).get("P2", []) or []:
        if not isinstance(violation, dict):
            continue
        rule_id = str(violation.get("rule_id") or "").strip()
        if rule_id:
            ids.add(rule_id)
    return sorted(ids)


def compare_core_rule_ids(
    expected_rule_ids: Sequence[str],
    detected_rule_ids: Sequence[str],
) -> Dict[str, Any]:
    expected = {str(value).strip() for value in expected_rule_ids if str(value).strip()}
    detected = {str(value).strip() for value in detected_rule_ids if str(value).strip()}
    matched = sorted(expected & detected)
    missing = sorted(expected - detected)
    unexpected = sorted(detected - expected)
    recall_pct = 100.0 if not expected else round((len(matched) / len(expected)) * 100.0, 2)
    return {
        "core_expected_rule_ids": sorted(expected),
        "detected_rule_ids": sorted(detected),
        "matched_core_rule_ids": matched,
        "missing_core_rule_ids": missing,
        "unexpected_detected_rule_ids": unexpected,
        "core_expected_count": len(expected),
        "detected_count": len(detected),
        "matched_core_count": len(matched),
        "missing_core_count": len(missing),
        "unexpected_detected_count": len(unexpected),
        "core_recall_pct": recall_pct,
    }


def _run_single_analysis(app: CodeInspectorApp, file_name: str, enable_ctrlppcheck: bool) -> Dict[str, Any]:
    return app.run_directory_analysis(
        mode=DEFAULT_MODE,
        selected_files=[file_name],
        enable_ctrlppcheck=enable_ctrlppcheck,
        enable_live_ai=False,
        defer_excel_reports=True,
    )


def _write_reports(output_dir: str, stamp: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"p1_sample_audit_{stamp}.json")
    md_path = os.path.join(output_dir, f"p1_sample_audit_{stamp}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    summary = payload.get("summary", {})
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# P1 Sample Audit\n\n")
        f.write(f"- generated_at: `{payload.get('generated_at')}`\n")
        f.write(f"- sample_count: `{summary.get('sample_count', 0)}`\n")
        f.write(f"- total_core_expected: `{summary.get('total_core_expected', 0)}`\n")
        f.write(f"- total_core_matched: `{summary.get('total_core_matched', 0)}`\n")
        f.write(f"- total_core_missing: `{summary.get('total_core_missing', 0)}`\n")
        f.write(f"- macro_core_recall_pct: `{summary.get('macro_core_recall_pct', 0.0):.2f}%`\n")
        f.write(f"- unexpected_detected_rule_count: `{summary.get('unexpected_detected_rule_count', 0)}`\n\n")
        f.write("## Interpretation\n\n")
        f.write("- `core_recall_pct` compares only manually reviewed must-detect P1 rules.\n")
        f.write("- `unexpected_detected_rule_ids` are not auto-labeled as false positives.\n")
        f.write("- Use unexpected detections as the next manual precision-tuning queue.\n\n")
        f.write("## Samples\n\n")
        for sample in payload.get("samples", []):
            f.write(f"### {sample.get('file')}\n\n")
            f.write(f"- core_recall_pct: `{sample.get('core_recall_pct', 0.0):.2f}%`\n")
            f.write(f"- matched_core_rule_ids: `{', '.join(sample.get('matched_core_rule_ids', [])) or '-'}`\n")
            f.write(f"- missing_core_rule_ids: `{', '.join(sample.get('missing_core_rule_ids', [])) or '-'}`\n")
            f.write(f"- unexpected_detected_rule_ids: `{', '.join(sample.get('unexpected_detected_rule_ids', [])) or '-'}`\n")
            f.write(f"- ctrlpp_p2_rule_ids: `{', '.join(sample.get('ctrlpp_p2_rule_ids', [])) or '-'}`\n")
            f.write(f"- p1_output_dir: `{sample.get('p1_only_output_dir', '')}`\n")
            f.write(f"- p1_p2_output_dir: `{sample.get('p1_p2_output_dir', '')}`\n")
            f.write("\n")
        f.write("## Tuning Queue\n\n")
        for row in payload.get("tuning_queue", []):
            f.write(f"- `{row['rule_id']}`: `{row['sample_count']}` sample(s) | files={', '.join(row['files'])}\n")
    return json_path, md_path


def run(args: argparse.Namespace) -> Dict[str, Any]:
    app = CodeInspectorApp()
    samples: List[Dict[str, Any]] = []
    tuning_counter: Counter[str] = Counter()
    tuning_files: Dict[str, Set[str]] = {}

    total_core_expected = 0
    total_core_matched = 0
    total_core_missing = 0

    for expectation in SAMPLE_EXPECTATIONS:
        file_name = str(expectation["file"])
        p1_only = _run_single_analysis(app, file_name=file_name, enable_ctrlppcheck=False)
        p1_p2 = _run_single_analysis(app, file_name=file_name, enable_ctrlppcheck=True)

        detected_p1_rule_ids = flatten_p1_rule_ids(p1_only)
        detected_p2_rule_ids = flatten_p2_rule_ids(p1_p2)
        compare = compare_core_rule_ids(expectation["core_expected_p1_rule_ids"], detected_p1_rule_ids)

        total_core_expected += int(compare["core_expected_count"])
        total_core_matched += int(compare["matched_core_count"])
        total_core_missing += int(compare["missing_core_count"])

        for rule_id in compare["unexpected_detected_rule_ids"]:
            tuning_counter[rule_id] += 1
            tuning_files.setdefault(rule_id, set()).add(file_name)

        samples.append(
            {
                "file": file_name,
                "notes": list(expectation.get("notes", []) or []),
                **compare,
                "ctrlpp_p2_rule_ids": detected_p2_rule_ids,
                "p1_config_health": dict(p1_only.get("p1_config_health", {}) or {}),
                "p1_only_summary": dict(p1_only.get("summary", {}) or {}),
                "p1_p2_summary": dict(p1_p2.get("summary", {}) or {}),
                "p1_only_output_dir": str(p1_only.get("output_dir", "") or ""),
                "p1_p2_output_dir": str(p1_p2.get("output_dir", "") or ""),
            }
        )

    macro_core_recall_pct = 100.0 if not samples else round(
        sum(float(sample.get("core_recall_pct", 0.0)) for sample in samples) / len(samples),
        2,
    )
    tuning_queue = [
        {
            "rule_id": rule_id,
            "sample_count": count,
            "files": sorted(tuning_files.get(rule_id, set())),
        }
        for rule_id, count in sorted(tuning_counter.items(), key=lambda item: (-item[1], item[0]))
    ]
    payload: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "sample_count": len(samples),
            "total_core_expected": total_core_expected,
            "total_core_matched": total_core_matched,
            "total_core_missing": total_core_missing,
            "macro_core_recall_pct": macro_core_recall_pct,
            "unexpected_detected_rule_count": sum(int(sample["unexpected_detected_count"]) for sample in samples),
        },
        "samples": samples,
        "tuning_queue": tuning_queue,
    }
    if args.write_report:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path, md_path = _write_reports(args.output_dir, stamp, payload)
        payload["report_paths"] = {"json": json_path, "markdown": md_path}
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit P1 recall against manually reviewed sample expectations")
    parser.add_argument(
        "--output-dir",
        default=os.path.join(PROJECT_ROOT, "docs", "perf_baselines"),
        help="Directory where audit JSON/Markdown reports will be written",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Persist JSON/Markdown reports in addition to printing JSON to stdout",
    )
    return parser


if __name__ == "__main__":
    parsed = build_arg_parser().parse_args()
    result = run(parsed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
