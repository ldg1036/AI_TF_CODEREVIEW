import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _build_parsed_items_by_type(parsed_rows: list[dict]) -> dict[str, set[str]]:
    items_by_type: dict[str, set[str]] = defaultdict(set)
    for row in parsed_rows:
        if not isinstance(row, dict):
            continue
        row_type = row.get("type")
        item = row.get("item")
        if not isinstance(row_type, str):
            continue
        if not isinstance(item, str):
            continue
        item = item.strip()
        if not item or item.lower() == "nan":
            continue
        items_by_type[row_type].add(item)
    return items_by_type


def _collect_mismatches(p1_rows: list[dict], parsed_items_by_type: dict[str, set[str]]) -> list[dict]:
    mismatches: list[dict] = []
    for row in p1_rows:
        if not isinstance(row, dict) or not row.get("enabled", True):
            continue
        item = row.get("item")
        if not isinstance(item, str) or not item.strip():
            continue
        file_types = row.get("file_types") or []
        if not isinstance(file_types, list):
            continue
        for file_type in file_types:
            if not isinstance(file_type, str):
                continue
            if item not in parsed_items_by_type.get(file_type, set()):
                mismatches.append(
                    {
                        "rule_id": row.get("rule_id"),
                        "id": row.get("id"),
                        "type": file_type,
                        "item": item,
                        "detector_kind": (row.get("detector") or {}).get("kind"),
                        "allow_item_filter_fallback": bool((row.get("meta") or {}).get("allow_item_filter_fallback")),
                    }
                )
    return mismatches


def _collect_nan_item_rows(parsed_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for idx, row in enumerate(parsed_rows):
        if not isinstance(row, dict):
            continue
        item = row.get("item")
        is_nan = item is None or isinstance(item, float)
        if isinstance(item, str):
            s = item.strip().lower()
            is_nan = is_nan or (not s) or s == "nan"
        if not is_nan:
            continue
        cps = row.get("check_points") or []
        first_check = ""
        if isinstance(cps, list) and cps and isinstance(cps[0], dict):
            first_check = str(cps[0].get("content", ""))
        rows.append(
            {
                "idx": idx,
                "type": row.get("type"),
                "category": row.get("category"),
                "sub_category": row.get("sub_category"),
                "item": row.get("item"),
                "check_points_len": len(cps) if isinstance(cps, list) else None,
                "first_check": first_check[:200],
            }
        )
    return rows


def _collect_review_applicability_key_issues(items: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    broken_key_pattern = re.compile(r"�|\?{2,}")
    for key in items:
        if broken_key_pattern.search(key):
            issues.append({"item": key, "reason": "broken_text_pattern"})
    return issues


def _collect_review_applicability_duplicate_semantics(items: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for item, cfg in items.items():
        if not isinstance(cfg, dict):
            continue
        required_rule_ids = cfg.get("required_rule_ids") or []
        if not isinstance(required_rule_ids, list):
            continue
        normalized_rule_ids = tuple(sorted({str(rule_id).strip() for rule_id in required_rule_ids if str(rule_id).strip()}))
        if not normalized_rule_ids:
            continue
        grouped[normalized_rule_ids].append(item)

    duplicates: list[dict[str, Any]] = []
    for required_rule_ids, keys in grouped.items():
        if len(keys) <= 1:
            continue
        duplicates.append(
            {
                "items": sorted(keys),
                "required_rule_ids": list(required_rule_ids),
                "reason": "duplicate_required_rule_ids",
            }
        )
    return duplicates


def _collect_review_applicability_unknown_rule_ids(items: dict[str, Any], known_rule_ids: set[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item, cfg in items.items():
        if not isinstance(cfg, dict):
            continue
        required_rule_ids = cfg.get("required_rule_ids") or []
        if not isinstance(required_rule_ids, list):
            continue
        for rule_id in required_rule_ids:
            rid = str(rule_id).strip()
            if rid and rid not in known_rule_ids:
                issues.append({"item": item, "rule_id": rid, "reason": "unreferenced_rule_id"})
    return issues




def _iter_rule_ids_from_obj(obj: Any):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if "rule_id" in str(key).lower():
                rid = str(value).strip()
                if rid:
                    yield rid
            yield from _iter_rule_ids_from_obj(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_rule_ids_from_obj(value)


def _collect_known_rule_ids(p1_rows: list[dict]) -> set[str]:
    known_rule_ids: set[str] = set()
    for row in p1_rows:
        if not isinstance(row, dict):
            continue
        known_rule_ids.update(_iter_rule_ids_from_obj(row))
    return known_rule_ids


def run(root: Path) -> dict:
    config_dir = root / "Config"
    parsed_path = config_dir / "parsed_rules.json"
    p1_defs_path = config_dir / "p1_rule_defs.json"
    review_applicability_path = config_dir / "review_applicability.json"

    parsed_rows = _load_json(parsed_path)
    p1_rows = _load_json(p1_defs_path)
    review_applicability = _load_json(review_applicability_path)

    parsed_items_by_type = _build_parsed_items_by_type(parsed_rows)
    mismatches = _collect_mismatches(p1_rows, parsed_items_by_type)
    nan_item_rows = _collect_nan_item_rows(parsed_rows)
    review_applicability_items = review_applicability.get("items", {}) if isinstance(review_applicability, dict) else {}
    if not isinstance(review_applicability_items, dict):
        review_applicability_items = {}
    known_rule_ids = _collect_known_rule_ids(p1_rows)
    review_key_issues = _collect_review_applicability_key_issues(review_applicability_items)
    review_duplicate_semantics = _collect_review_applicability_duplicate_semantics(review_applicability_items)
    review_unknown_rule_ids = _collect_review_applicability_unknown_rule_ids(review_applicability_items, known_rule_ids)

    enabled_p1_rows = [r for r in p1_rows if isinstance(r, dict) and r.get("enabled", True)]
    detector_counts = Counter((r.get("detector") or {}).get("kind") for r in enabled_p1_rows)

    summary = {
        "parsed_rows": len(parsed_rows) if isinstance(parsed_rows, list) else None,
        "parsed_unique_items": {k: len(v) for k, v in parsed_items_by_type.items()},
        "p1_rule_rows": len(p1_rows) if isinstance(p1_rows, list) else None,
        "p1_rule_rows_enabled": len(enabled_p1_rows),
        "detector_counts": dict(detector_counts),
        "legacy_handler_rows": sum(1 for r in enabled_p1_rows if (r.get("detector") or {}).get("kind") == "legacy_handler"),
        "proxy_legacy_rows": sum(1 for r in enabled_p1_rows if (r.get("detector") or {}).get("proxy_legacy_handler")),
        "mismatch_row_count": len(mismatches),
        "mismatch_unique_rule_count": len({(m.get("rule_id"), m.get("id")) for m in mismatches}),
        "nan_item_row_count": len(nan_item_rows),
        "review_applicability_item_count": len(review_applicability_items),
        "review_applicability_broken_key_count": len(review_key_issues),
        "review_applicability_duplicate_semantic_count": len(review_duplicate_semantics),
        "review_applicability_unknown_rule_id_count": len(review_unknown_rule_ids),
    }

    return {
        "summary": summary,
        "mismatches": mismatches,
        "nan_item_rows": nan_item_rows,
        "review_applicability_key_issues": review_key_issues,
        "review_applicability_duplicate_semantics": review_duplicate_semantics,
        "review_applicability_unknown_rule_ids": review_unknown_rule_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check alignment between parsed_rules.json and p1_rule_defs.json")
    parser.add_argument("--root", default=None, help="Repository root path (defaults to script-relative repo root)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print full JSON result")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    result = run(root)

    has_review_applicability_quality_error = any(
        [
            result["review_applicability_key_issues"],
            result["review_applicability_duplicate_semantics"],
            result["review_applicability_unknown_rule_ids"],
        ]
    )

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if has_review_applicability_quality_error else 0

    s = result["summary"]
    print("[Config Rule Alignment]")
    print(f"- root: {root}")
    print(f"- parsed_rules rows: {s['parsed_rows']}")
    print(f"- parsed_rules unique items by type: {s['parsed_unique_items']}")
    print(f"- p1_rule_defs rows(enabled): {s['p1_rule_rows_enabled']} / {s['p1_rule_rows']}")
    print(f"- detector counts: {s['detector_counts']}")
    print(f"- legacy_handler rows: {s['legacy_handler_rows']}")
    print(f"- proxy_legacy rows: {s['proxy_legacy_rows']}")
    print(f"- mismatch rows: {s['mismatch_row_count']} (unique rules: {s['mismatch_unique_rule_count']})")
    print(f"- parsed_rules item=NaN rows: {s['nan_item_row_count']}")
    print(f"- review_applicability items: {s['review_applicability_item_count']}")
    print(f"- review_applicability broken keys: {s['review_applicability_broken_key_count']}")
    print(f"- review_applicability duplicate semantics: {s['review_applicability_duplicate_semantic_count']}")
    print(f"- review_applicability unknown rule_ids: {s['review_applicability_unknown_rule_id_count']}")

    if result["mismatches"]:
        print("\n[Mismatches]")
        for m in result["mismatches"]:
            fb = " (fallback)" if m.get("allow_item_filter_fallback") else ""
            print(f"- {m.get('rule_id')} [{m.get('type')}] item={m.get('item')}{fb}")

    if result["nan_item_rows"]:
        print("\n[parsed_rules item=NaN rows]")
        for row in result["nan_item_rows"]:
            print(f"- idx={row['idx']} type={row['type']} item={row['item']} first_check={row['first_check']}")

    if result["review_applicability_key_issues"]:
        print("\n[review_applicability key issues]")
        for issue in result["review_applicability_key_issues"]:
            print(f"- item={issue['item']} reason={issue['reason']}")

    if result["review_applicability_duplicate_semantics"]:
        print("\n[review_applicability duplicate semantics]")
        for issue in result["review_applicability_duplicate_semantics"]:
            print(
                f"- items={issue['items']} required_rule_ids={issue['required_rule_ids']} reason={issue['reason']}"
            )

    if result["review_applicability_unknown_rule_ids"]:
        print("\n[review_applicability unknown rule_ids]")
        for issue in result["review_applicability_unknown_rule_ids"]:
            print(f"- item={issue['item']} rule_id={issue['rule_id']} reason={issue['reason']}")

    return 1 if has_review_applicability_quality_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
