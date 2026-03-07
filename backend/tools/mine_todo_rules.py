import argparse
import csv
import datetime
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

TODO_PATTERN = re.compile(r"(?i)\btodo\b")
TODO_TEXT_PATTERN = re.compile(r"(?i)\btodo\b\s*[:：\-]?\s*(.*)$")


def _find_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_bool(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool value: {value}")


def _parse_encodings(value: str) -> List[str]:
    encodings = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return encodings or ["utf-8", "cp949"]


def _read_text_with_fallback(path: Path, encodings: Sequence[str]) -> Tuple[str, str, str]:
    last_error = ""
    for enc in encodings:
        try:
            return path.read_text(encoding=enc), enc, ""
        except UnicodeDecodeError as exc:
            last_error = f"{enc}: {exc}"
        except Exception as exc:  # pragma: no cover - defensive guard
            last_error = f"{enc}: {exc}"
    return "", "", last_error


def _line_snippet(line: str, max_len: int = 240) -> str:
    compact = re.sub(r"\s+", " ", str(line or "").strip())
    return compact if len(compact) <= max_len else compact[:max_len] + "..."


def _extract_todo_lines(content: str) -> List[Dict]:
    rows = []
    for idx, line in enumerate(content.splitlines(), 1):
        if not TODO_PATTERN.search(line):
            continue
        text_match = TODO_TEXT_PATTERN.search(line)
        extracted = text_match.group(1).strip() if text_match else ""
        rows.append(
            {
                "line_no": idx,
                "line_text": _line_snippet(line),
                "todo_text": extracted,
            }
        )
    return rows


def _normalize_todo_text(text: str) -> str:
    normalized = str(text or "").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^[\-\:\.\,\;\[\]\(\)\{\}\"' ]+", "", normalized)
    normalized = re.sub(r"[\-\:\.\,\;\[\]\(\)\{\}\"' ]+$", "", normalized)
    return normalized or "__todo_only__"


def _rule_mapping(normalized_text: str) -> Dict:
    text = normalized_text

    if any(key in text for key in ("미사용 변수", "unused variable", "미사용변수", "unused")):
        return {
            "suggested_rule_id": "UNUSED-01",
            "suggested_rule_item": "불필요한 코드 지양",
            "suggested_severity": "Low",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "regex",
            "confidence": "high",
        }
    if "dpget" in text and any(key in text for key in ("일괄", "batch", "묶", "optimiz")):
        return {
            "suggested_rule_id": "PERF-DPGET-BATCH-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "high",
        }
    if "dpset" in text and any(key in text for key in ("일괄", "batch", "묶", "optimiz")):
        return {
            "suggested_rule_id": "PERF-DPSET-BATCH-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "high",
        }
    if "dpquery" in text and any(key in text for key in ("from *", "최적화", "지양", "튜닝", "optimiz")):
        return {
            "suggested_rule_id": "PERF-02",
            "suggested_rule_item": "DP Query 최적화 구현",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "regex",
            "confidence": "high",
        }
    if "setvalue" in text and any(key in text for key in ("일괄", "batch", "묶", "optimiz")):
        return {
            "suggested_rule_id": "PERF-SETVALUE-BATCH-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "high",
        }
    if "setvalue" in text and any(
        key in text for key in ("권장", "object 명 동일", "object명동일", "별도로", "하는 이유", "하는이유")
    ):
        return {
            "suggested_rule_id": "PERF-SETVALUE-BATCH-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "medium",
        }
    if "setmultivalue" in text:
        return {
            "suggested_rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "high",
        }
    if "getvalue" in text and any(key in text for key in ("일괄", "batch", "묶", "optimiz")):
        return {
            "suggested_rule_id": "PERF-GETVALUE-BATCH-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "high",
        }
    if "getvalue" in text and any(
        key in text for key in ("다 하는 이유", "다하는이유", "를 다", "하는 이유", "하는이유")
    ):
        return {
            "suggested_rule_id": "PERF-GETVALUE-BATCH-01",
            "suggested_rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
            "suggested_severity": "Warning",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "medium",
        }
    if any(key in text for key in ("중복", "duplicate")):
        return {
            "suggested_rule_id": "CLEAN-DUP-01",
            "suggested_rule_item": "불필요한 코드 지양",
            "suggested_severity": "Low",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "regex",
            "confidence": "medium",
        }
    if any(key in text for key in ("불필요", "dead code", "도달 불가", "unused function", "미사용 함수")):
        return {
            "suggested_rule_id": "CLEAN-DEAD-01",
            "suggested_rule_item": "불필요한 코드 지양",
            "suggested_severity": "Medium",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "flow",
            "confidence": "medium",
        }
    if any(key in text for key in ("하드코딩", "상수화", "magic number", "매직")):
        return {
            "suggested_rule_id": "HARD-03",
            "suggested_rule_item": "하드코딩 지양",
            "suggested_severity": "Medium",
            "static_rule_feasible": True,
            "suggested_detection_strategy": "regex",
            "confidence": "medium",
        }

    manual_hint = any(key in text for key in ("확인 필요", "용도", "왜", "이유", "?", "검토 필요"))
    return {
        "suggested_rule_id": "",
        "suggested_rule_item": "",
        "suggested_severity": "Low",
        "static_rule_feasible": not manual_hint,
        "suggested_detection_strategy": "manual" if manual_hint else "regex",
        "confidence": "low",
    }


def _to_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_csv(path: Path, headers: Sequence[str], rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(headers))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _classify_new_todo_candidates(candidates: Sequence[Dict]) -> List[Dict]:
    classified: List[Dict] = []
    for row in candidates:
        rid = str(row.get("suggested_rule_id", "") or "")
        if not rid.startswith("NEW-"):
            continue
        category = "정적화 대상" if bool(row.get("static_rule_feasible")) else "수동 검토 유지"
        classified.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "suggested_rule_id": rid,
                "category": category,
                "normalized_todo_text": row.get("normalized_todo_text", ""),
                "frequency": row.get("frequency", 0),
                "suggested_detection_strategy": row.get("suggested_detection_strategy", ""),
                "confidence": row.get("confidence", ""),
                "static_rule_feasible": bool(row.get("static_rule_feasible")),
                "source_files": row.get("source_files", []),
                "raw_examples": row.get("raw_examples", []),
            }
        )
    return classified



def _build_rule_proposal_template(new_todo_policy_rows: Sequence[Dict], output_dir: Path) -> str:
    lines = [
        "# Rule Proposal from TODO Mining",
        "",
        "## Context",
        "- Source: TODO mining (`backend/tools/mine_todo_rules.py`)",
        f"- Output directory: `{output_dir}`",
        "",
        "## Candidate Summary",
        f"- NEW-* candidates: {len(new_todo_policy_rows)}",
        f"- Static-target candidates: {sum(1 for row in new_todo_policy_rows if row.get('category') == '정적화 대상')}",
        f"- Manual-review candidates: {sum(1 for row in new_todo_policy_rows if row.get('category') == '수동 검토 유지')}",
        "",
        "## Proposed Rule Additions (NEW-* only)",
    ]

    if not new_todo_policy_rows:
        lines.extend(["- No NEW-* candidates in this run.", ""])
    else:
        for row in new_todo_policy_rows:
            lines.extend(
                [
                    f"### {row.get('suggested_rule_id', '')} ({row.get('category', '')})",
                    f"- Normalized TODO: `{row.get('normalized_todo_text', '')}`",
                    f"- Frequency: {row.get('frequency', 0)}",
                    f"- Suggested detection strategy: `{row.get('suggested_detection_strategy', '')}`",
                    f"- Confidence: `{row.get('confidence', '')}`",
                    "- Draft detector plan:",
                    "  - [ ] regex/composite/flow 중 1개 선택",
                    "  - [ ] 최소 재현 fixture 추가",
                    "  - [ ] false-positive/false-negative 기준 정의",
                    "",
                ]
            )

    lines.extend(
        [
            "## Validation Checklist",
            "- [ ] `python -m unittest backend.tests.test_todo_rule_mining -v`",
            "- [ ] `python backend/tools/check_config_rule_alignment.py --json`",
            "- [ ] 변경된 규칙/매핑이 있으면 template coverage 확인",
            "",
            "## Notes",
            "- 본 템플릿은 자동 초안입니다. 최종 rule_id/rule_item/검출전략은 리뷰 후 확정하세요.",
            "",
        ]
    )

    return "\n".join(lines)

def mine_todo_rules(
    input_dir: str,
    output_dir: str = "",
    min_frequency: int = 1,
    copy_files: bool = True,
    encoding_fallback: Sequence[str] = ("utf-8", "cp949"),
) -> Dict:
    input_root = Path(input_dir).resolve()
    if not input_root.exists() or not input_root.is_dir():
        raise FileNotFoundError(f"Input dir not found: {input_root}")

    if output_dir:
        out_root = Path(output_dir).resolve()
    else:
        project_root = _find_project_root()
        out_root = (project_root / "CodeReview_Report" / f"todo_mining_{_utc_now_stamp()}").resolve()

    todo_copy_root = out_root / "todo_files"
    out_root.mkdir(parents=True, exist_ok=True)
    if copy_files:
        todo_copy_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: List[Dict] = []
    todo_text_groups: Dict[str, Dict] = defaultdict(lambda: {"frequency": 0, "examples": [], "files": set()})
    read_errors: List[Dict] = []

    txt_paths = sorted([p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() == ".txt"])
    for path in txt_paths:
        content, used_encoding, read_error = _read_text_with_fallback(path, encoding_fallback)
        rel_path = str(path.relative_to(input_root))
        if read_error and not content:
            read_errors.append({"file": rel_path, "error": read_error})
            continue

        todo_lines = _extract_todo_lines(content)
        if not todo_lines:
            continue

        if copy_files:
            target = todo_copy_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

        manifest_rows.append(
            {
                "relative_path": rel_path,
                "absolute_path": str(path),
                "encoding": used_encoding,
                "todo_count": len(todo_lines),
                "todo_lines": todo_lines,
            }
        )

        for line in todo_lines:
            normalized = _normalize_todo_text(line.get("todo_text", ""))
            group = todo_text_groups[normalized]
            group["frequency"] += 1
            if len(group["examples"]) < 5:
                group["examples"].append(line.get("todo_text", ""))
            if len(group["files"]) < 20:
                group["files"].add(rel_path)

    candidates = []
    running_new = 1
    for idx, (normalized_text, payload) in enumerate(
        sorted(todo_text_groups.items(), key=lambda x: (-x[1]["frequency"], x[0])),
        1,
    ):
        if payload["frequency"] < min_frequency:
            continue
        mapped = _rule_mapping(normalized_text)
        suggested_rule_id = mapped["suggested_rule_id"]
        if not suggested_rule_id:
            suggested_rule_id = f"NEW-{running_new:04d}"
            running_new += 1
        candidate = {
            "candidate_id": f"CAND-{idx:04d}",
            "normalized_todo_text": normalized_text,
            "raw_examples": payload["examples"],
            "frequency": payload["frequency"],
            "source_files": sorted(payload["files"]),
            "suggested_rule_id": suggested_rule_id,
            "suggested_rule_item": mapped["suggested_rule_item"],
            "suggested_severity": mapped["suggested_severity"],
            "static_rule_feasible": bool(mapped["static_rule_feasible"]),
            "suggested_detection_strategy": mapped["suggested_detection_strategy"],
            "confidence": mapped["confidence"],
        }
        candidates.append(candidate)

    summary = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_dir": str(input_root),
        "output_dir": str(out_root),
        "total_txt_files": len(txt_paths),
        "todo_file_count": len(manifest_rows),
        "total_todo_lines": sum(row["todo_count"] for row in manifest_rows),
        "candidate_count": len(candidates),
        "min_frequency": int(min_frequency),
        "copy_files": bool(copy_files),
        "encoding_fallback": list(encoding_fallback),
        "read_error_count": len(read_errors),
    }
    new_todo_policy_rows = _classify_new_todo_candidates(candidates)
    summary["new_todo_candidate_count"] = len(new_todo_policy_rows)
    summary["new_todo_static_target_count"] = sum(1 for row in new_todo_policy_rows if row["category"] == "정적화 대상")
    summary["new_todo_manual_review_count"] = sum(1 for row in new_todo_policy_rows if row["category"] == "수동 검토 유지")

    _to_json(out_root / "summary.json", summary)
    _to_json(out_root / "todo_file_manifest.json", {"rows": manifest_rows})
    _to_json(out_root / "todo_rule_candidates.json", {"rows": candidates})
    _to_json(
        out_root / "new_todo_policy.json",
        {
            "policy": {
                "version": "1.0",
                "categories": ["정적화 대상", "수동 검토 유지"],
                "rule": "NEW-* 후보는 static_rule_feasible 기준으로 2분류 고정",
            },
            "rows": new_todo_policy_rows,
        },
    )
    _to_json(out_root / "read_errors.json", {"rows": read_errors})

    _to_csv(
        out_root / "todo_file_manifest.csv",
        headers=["relative_path", "absolute_path", "encoding", "todo_count"],
        rows=manifest_rows,
    )
    _to_csv(
        out_root / "todo_rule_candidates.csv",
        headers=[
            "candidate_id",
            "normalized_todo_text",
            "frequency",
            "suggested_rule_id",
            "suggested_rule_item",
            "suggested_severity",
            "static_rule_feasible",
            "suggested_detection_strategy",
            "confidence",
        ],
        rows=candidates,
    )
    _to_csv(
        out_root / "new_todo_policy.csv",
        headers=[
            "candidate_id",
            "suggested_rule_id",
            "category",
            "normalized_todo_text",
            "frequency",
            "suggested_detection_strategy",
            "confidence",
            "static_rule_feasible",
        ],
        rows=new_todo_policy_rows,
    )

    proposal_template_path = out_root / "rule_proposal_template.md"
    proposal_template_path.write_text(
        _build_rule_proposal_template(new_todo_policy_rows, out_root),
        encoding="utf-8",
    )

    return {
        "summary": summary,
        "manifest_rows": manifest_rows,
        "candidate_rows": candidates,
        "new_todo_policy_rows": new_todo_policy_rows,
        "error_rows": read_errors,
        "output_dir": str(out_root),
        "rule_proposal_template": str(proposal_template_path),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mine TODO comments from .txt files and generate static-rule candidates")
    parser.add_argument("--input-dir", required=True, help="Root directory to scan *.txt recursively")
    parser.add_argument("--output-dir", default="", help="Output directory path")
    parser.add_argument("--min-frequency", type=int, default=1, help="Minimum frequency to keep candidate")
    parser.add_argument("--copy-files", type=_parse_bool, default=True, help="Whether to copy todo-containing files")
    parser.add_argument(
        "--encoding-fallback",
        default="utf-8,cp949",
        help="Comma-separated encoding fallback order",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    encodings = _parse_encodings(args.encoding_fallback)
    result = mine_todo_rules(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        min_frequency=max(1, int(args.min_frequency)),
        copy_files=bool(args.copy_files),
        encoding_fallback=encodings,
    )
    summary = result["summary"]
    print(f"[+] TODO mining completed: {result['output_dir']}")
    print(
        f"    txt={summary['total_txt_files']}, todo_files={summary['todo_file_count']}, "
        f"todo_lines={summary['total_todo_lines']}, candidates={summary['candidate_count']}, "
        f"errors={summary['read_error_count']}"
    )


if __name__ == "__main__":
    main()
