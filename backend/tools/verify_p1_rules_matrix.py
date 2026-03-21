import argparse
import datetime as dt
import http.client
import json
import os
import sys
import tempfile
import threading
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from http.server import ThreadingHTTPServer


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.heuristic_checker import HeuristicChecker  # noqa: E402
from main import CodeInspectorApp  # noqa: E402
from server import BASE_DIR, CodeInspectorHandler  # noqa: E402
from p1_rule_case_catalog import get_rule_case  # noqa: E402


@dataclass
class RuleCase:
    supported: bool
    reason: str
    positive: str = ""
    negative: str = ""
    source: str = ""
    file_type: str = ""
    notes: str = ""


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _rule_public_id(rule: Dict[str, Any]) -> str:
    return str(rule.get("rule_id") or rule.get("id") or "UNKNOWN")


def _expected_rule_ids(rule: Dict[str, Any]) -> Set[str]:
    ids = set()
    rid = str(rule.get("rule_id") or "").strip()
    if rid:
        ids.add(rid)
    rid2 = str(rule.get("id") or "").strip()
    if rid2:
        ids.add(rid2)
    detector = rule.get("detector") if isinstance(rule.get("detector"), dict) else {}
    for k in ("line_rule_id", "depth_rule_id"):
        v = str(detector.get(k) or "").strip()
        if v:
            ids.add(v)
    return ids


def _preferred_file_type(rule: Dict[str, Any]) -> str:
    types = rule.get("file_types")
    if isinstance(types, str):
        types = [types]
    if not isinstance(types, list) or not types:
        return "Server"
    normalized = [str(x).strip().lower() for x in types]
    if "server" in normalized:
        return "Server"
    if "client" in normalized:
        return "Client"
    return "Server"


def _op_case(op: str) -> RuleCase:
    cases: Dict[str, Tuple[str, str]] = {
        "callback_delay_usage": (
            'void OnDpChanged(){ delay(1); }\nmain(){ dpConnect("OnDpChanged", "System1:Example.Value:_online.._value"); }',
            'void OnDpChanged(){ DebugN("ok"); }\nmain(){ dpConnect("OnDpChanged", "System1:Example.Value:_online.._value"); delay(1); }',
        ),
        "sql_injection": (
            'main(){ sprintf(sql, "SELECT * FROM users WHERE name = \'%s\'", input); }',
            'main(){ dpQuery("SELECT * FROM users WHERE id = $1", args); }',
        ),
        "complexity": (
            "main(){\n" + "\n".join([f"if(a=={i}){{a++;}}" for i in range(20)]) + "\n}",
            "main(){ if(a){a++;} else {a--;} }",
        ),
        "unused_variables": (
            "main(){ int used=1; int unused=2; DebugN(used); }",
            "main(){ int used=1; int used2=2; DebugN(used); DebugN(used2); }",
        ),
        "db_query_error": (
            "main(){ dpQuery(\"SELECT * FROM T\", r); }",
            "main(){ // SELECT * FROM T\n DebugN(\"ok\"); }",
        ),
        "dp_function_exception": (
            'main(){ dpSet("A.B.C", 1); }',
            'main(){ try { dpSet("A.B.C", 1); } catch { DebugTN(getLastError()); } }',
        ),
        "config_format_consistency": (
            'main(){ string s = "A::B::"; }',
            'main(){ string s = "A.B.C"; }',
        ),
        "config_error_contract": (
            'main(){ if (isError()) { DebugN("x"); } }',
            'main(){ if (!isError()) { DebugN("ok"); } }',
        ),
        "while_delay_policy": (
            'main(){ while(1){ dpGet("A.B.C", x); } }',
            'main(){ while(1){ dpGet("A.B.C", x); delay(1); } }',
        ),
        "while_delay_outside_active": (
            'main(){ while(1){ if(isActive){ dpSet("A.B.C",1); delay(1);} } }',
            'main(){ while(1){ if(isActive){ dpSet("A.B.C",1);} delay(1);} }',
        ),
        "event_exchange_minimization": (
            'main(){ while(1){ dpSet("SYS.A.B",1); dpSet("SYS.A.C",2); } }',
            'main(){ while(1){ if(oldVal!=newVal){ dpSetWait("SYS.A.B",newVal);} } }',
        ),
        "dpset_timed_context": (
            'main(){ dpSet("SITE.ALARM.STATE", 1); }',
            'main(){ dpSetTimed("SITE.ALARM.STATE", 1); }',
        ),
        "dpget_batch_optimization": (
            'main(){ while(1){ int a; int b; dpGet("A.B.C",a); dpGet("A.B.D",b); } }',
            'main(){ while(1){ dyn_string dps; dpGet(dps, vals); } }',
        ),
        "dpset_batch_optimization": (
            'main(){ while(1){ dpSet("A.B.C",1); dpSet("A.B.D",2); } }',
            'main(){ while(1){ dpSetWait("A.B.C",1); } }',
        ),
        "setvalue_batch_optimization": (
            'main(){ while(1){ setValue("A",1); setValue("B",2);} }',
            'main(){ while(1){ setMultiValue("A",1,"B",2);} }',
        ),
        "setmultivalue_adoption": (
            'main(){ while(1){ setValue("A",1); setValue("B",2); } }',
            'main(){ while(1){ setMultiValue("A",1,"B",2); } }',
        ),
        "getmultivalue_adoption": (
            'main(){ while(1){ getValue("A",a); getValue("B",b); } }',
            'main(){ while(1){ getMultiValue(dpList, vals); } }',
        ),
        "getvalue_batch_optimization": (
            'main(){ while(1){ getValue("A",a); getValue("B",b); } }',
            'main(){ while(1){ getMultiValue(dpList, vals); } }',
        ),
        "try_catch_for_risky_ops": (
            'main(){ dpSet("A.B.C",1); dpGet("A.B.C",x); }',
            'main(){ try { dpSet("A.B.C",1); dpGet("A.B.C",x);} catch { DebugTN(getLastError()); } }',
        ),
        "division_zero_guard": (
            "main(){ float z=0; float r=100/z; }",
            "main(){ float z=0; if(z!=0){ float r=100/z; } }",
        ),
        "manual_aggregation_pattern": (
            "main(){ while(1){ total += v; cnt++; } }",
            "main(){ while(1){ avg = dynAvg(vals); } }",
        ),
        "consecutive_dpset": (
            'main(){ dpSet("A.B.C",1); dpSet("A.B.D",2); }',
            'main(){ if(oldVal!=newVal){ dpSetWait("A.B.C",newVal);} }',
        ),
        "memory_leaks_advanced": (
            "main(){ dyn_float b; while(1){ dynAppend(b,1.0); } }",
            "main(){ dyn_float b; while(1){ dynAppend(b,1.0); dynRemove(b,1);} }",
        ),
        "input_validation": (
            "main(){ string input; system(input); }",
            "main(){ string input; if(strlen(input)<10){ system(input);} }",
        ),
        "coding_standards_advanced": (
            "main(){\n" + "\n".join([f"int variableName{i}=0;" for i in range(8)]) + "\n}",
            "main(){ const int MAX_COUNT=10; int x=1; }",
        ),
        "style_name_rules": (
            "int globalValue = 0; const int maxCount = 10; main(){ int configValue = 1; }",
            "int g_value = 0; const int MAX_COUNT = 10; main(){ int l_value = 1; }",
        ),
        "style_indent_mixed": (
            "main() {\n\tint a = 0;\n  int b = 1;\n}\n",
            "main() {\n    int a = 0;\n    int b = 1;\n}\n",
        ),
        "style_header_rules": (
            "main(){\n  int x=0;\n}",
            "// header: script info\nmain(){ int x=0; }",
        ),
        "magic_index_usage": (
            "main(){ parts[2]=a; parts[3]=b; parts[4]=c; }",
            "main(){ const int IDX_A=2; parts[IDX_A]=a; }",
        ),
        "hardcoding_extended": (
            'main(){ dpSet("SITE.AREA.TAG.VALUE",1); dpGet("SITE.AREA.TAG.VALUE",x); }',
            'main(){ dpSet(cfgPath,1); dpGet(cfgPath,x); }',
        ),
        "float_literal_hardcoding": (
            "main(){ float a=0.001; float b=0.001; }",
            "main(){ const float EPS=0.001; float a=EPS; }",
        ),
        "dead_code": (
            'main(){ if(false){ DebugN("dead"); } }',
            'main(){ if(true){ DebugN("live"); } }',
        ),
        "ui_block_initialize_delay": (
            "main(){ Initialize(){ delay(1); } }",
            "main(){ Initialize(){ dpSetWait(\"A.B\",1); } }",
        ),
        "debug_logging_presence": (
            'main(){ catch { writeLog("Script","failed",LV_WARN); } }',
            'main(){ catch { writeLog("Script","failed",LV_WARN); DebugTN("dbg"); } }',
        ),
        "logging_level_policy": (
            'main(){ catch { writeLog("Script","failed",LV_WARN); } }',
            'main(){ catch { writeLog("Script","failed",LV_WARN); DebugTN("dbg2"); } }',
        ),
        "script_active_condition_check": (
            'main(){ dpSet("A.B.C",1); }',
            'main(){ if(isActive){ dpSet("A.B.C",1); } }',
        ),
        "duplicate_action_handling": (
            'main(){ OBJ_A.visible=1; OBJ_A.visible=1; OBJ_A.visible=1; }',
            'main(){ OBJ_A.visible=1; OBJ_B.visible=1; }',
        ),
    }
    if op not in cases:
        return RuleCase(False, "CASE_GENERATION_UNSUPPORTED")
    pos, neg = cases[op]
    return RuleCase(True, "ok", positive=pos, negative=neg, source="op_fallback")


def _regex_case(rule_id: str, pattern: str) -> RuleCase:
    table = {
        "PERF-01": ('main(){ dpConnect("a","b"); delay(1); }', 'main(){ dpConnect("a","b"); DebugN("ok"); }'),
        "PERF-02": ('main(){ dpQuery("SELECT _online.._value FROM \'*.**\'", r); }', 'main(){ dpQuery("SELECT _online.._value FROM \'A.B.C\'", r); }'),
        "HARD-01": ('main(){ string s="http://example.com"; }', 'main(){ string s=cfgUrl; }'),
        "DB-01": ('main(){ sprintf(sql, "SELECT * FROM T"); }', 'main(){ sql = "SELECT * FROM T"; }'),
        "PERF-02-WHERE-DPT-IN-01": (
            'main(){ dpQuery("SELECT \'_online.._value\' FROM \'*.**\' WHERE _DPT IN (\'AI\',\'DI\')", r); }',
            'main(){ dpQuery("SELECT \'_online.._value\' FROM \'*.**\' WHERE _DPT = \'AI\'", r); }',
        ),
        "DB-02": ('main(){ SELECT value FROM T; }', 'main(){ // SELECT value FROM T; }'),
    }
    if rule_id in table:
        pos, neg = table[rule_id]
        return RuleCase(True, "ok", positive=pos, negative=neg, source="op_fallback")
    return RuleCase(False, "CASE_GENERATION_UNSUPPORTED")


def _line_repeat_case(detector: Dict[str, Any]) -> RuleCase:
    threshold = int(detector.get("threshold") or detector.get("min_repeat") or 3)
    line = "dpSet(\"A.B.C\", 1);"
    pos_count = max(threshold, 3)
    neg_count = max(1, threshold - 1)
    positive = "main(){\n" + "\n".join([line for _ in range(pos_count)]) + "\n}"
    negative = "main(){\n" + "\n".join([line for _ in range(neg_count)]) + "\n}"
    return RuleCase(True, "ok", positive=positive, negative=negative, source="op_fallback")


def _catalog_case(rule_id: str) -> RuleCase:
    row = get_rule_case(rule_id)
    if not row:
        return RuleCase(False, "CASE_GENERATION_UNSUPPORTED")
    positive = str(row.get("positive_code") or "")
    negative = str(row.get("negative_code") or "")
    if not positive or not negative:
        return RuleCase(False, "CASE_GENERATION_UNSUPPORTED")
    return RuleCase(
        True,
        "ok",
        positive=positive,
        negative=negative,
        source="rule_catalog",
        file_type=str(row.get("file_type") or ""),
        notes=str(row.get("notes") or ""),
    )


def build_rule_case(rule: Dict[str, Any], case_source: str = "mixed") -> RuleCase:
    detector = rule.get("detector") if isinstance(rule.get("detector"), dict) else {}
    kind = str(detector.get("kind") or "").strip().lower()
    rid = _rule_public_id(rule)
    if case_source in ("mixed", "rule_catalog"):
        catalog_case = _catalog_case(rid)
        if catalog_case.supported:
            return catalog_case
        if case_source == "rule_catalog":
            return catalog_case
    if kind == "regex":
        return _regex_case(rid, str(detector.get("pattern") or ""))
    if kind == "line_repeat":
        return _line_repeat_case(detector)
    if kind == "composite":
        return _op_case(str(detector.get("op") or "").strip().lower())
    return RuleCase(False, "CASE_GENERATION_UNSUPPORTED")


def _collect_rule_ids_from_checker(groups: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for g in groups:
        for v in g.get("violations", []):
            rid = str(v.get("rule_id") or "").strip()
            if rid:
                ids.add(rid)
    return ids


def _collect_rule_ids_from_api(payload: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for group in payload.get("violations", {}).get("P1", []):
        for v in group.get("violations", []):
            rid = str(v.get("rule_id") or "").strip()
            if rid:
                ids.add(rid)
    return ids


def _run_checker_case(
    checker: HeuristicChecker,
    rule: Dict[str, Any],
    code: str,
    file_type: str,
    ext: str,
) -> List[Dict[str, Any]]:
    op = str((rule.get("detector") or {}).get("op") or "").strip().lower()
    if op == "ui_block_initialize_delay":
        event_data = {"event": "Initialize", "code": code, "line_start": 1}
        violations = checker.check_event(event_data, file_type=file_type)
        if not violations:
            return []
        return [{"object": f"sample{ext}", "event": "Initialize", "violations": violations}]
    return checker.analyze_raw_code(f"sample{ext}", code, file_type=file_type)


class _ApiHarness:
    def __init__(self, data_dir: str):
        self._tmp = data_dir
        self._app = CodeInspectorApp()
        self._app.data_dir = data_dir
        frontend_dir = os.path.join(BASE_DIR, "frontend")

        def handler(*args, **kwargs):
            return CodeInspectorHandler(*args, app=self._app, frontend_dir=frontend_dir, **kwargs)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=3)

    def analyze(self, filename: str) -> Dict[str, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=20)
        body = {
            "mode": "Static",
            "selected_files": [filename],
            "allow_raw_txt": True,
            "enable_live_ai": False,
            "enable_ctrlppcheck": False,
            "defer_excel_reports": True,
        }
        payload = json.dumps(body)
        conn.request("POST", "/api/analyze", payload, {"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        conn.close()
        data = json.loads(raw) if raw else {}
        if resp.status != 200:
            return {"_error": f"HTTP {resp.status}", "_payload": data}
        return data


def _write_reports(output_dir: str, stamp: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"p1_rule_matrix_{stamp}.json")
    md_path = os.path.join(output_dir, f"p1_rule_matrix_{stamp}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    summary = payload.get("summary", {})
    failures = payload.get("failures", {})
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# P1 Rule Matrix Verification\n\n")
        f.write(f"- generated_at: `{payload.get('generated_at')}`\n")
        f.write(f"- enabled_rules: `{summary.get('enabled_rules', 0)}`\n")
        f.write(f"- supported_rules: `{summary.get('supported_rules', 0)}`\n")
        f.write(f"- unsupported_rules: `{summary.get('unsupported_rules', 0)}`\n")
        f.write(f"- positive_detection_rate: `{summary.get('positive_detection_rate', 0):.2f}%`\n")
        f.write(f"- negative_not_detected_rate: `{summary.get('negative_not_detected_rate', 0):.2f}%`\n")
        f.write(f"- checker_vs_api_mismatch_rate: `{summary.get('checker_vs_api_mismatch_rate', 0):.2f}%`\n\n")
        f.write("## Failures\n\n")
        for key in (
            "NO_POSITIVE_HIT",
            "FALSE_POSITIVE_ON_NEGATIVE",
            "RULE_ID_MISMATCH",
            "TYPE_ROUTING_MISMATCH",
            "CASE_GENERATION_UNSUPPORTED",
            "CHECKER_API_MISMATCH",
        ):
            rows = failures.get(key, [])
            f.write(f"### {key} ({len(rows)})\n")
            for rid in rows:
                f.write(f"- `{rid}`\n")
            f.write("\n")
    return json_path, md_path


def run(args: argparse.Namespace) -> Dict[str, Any]:
    config_dir = os.path.join(args.project_root, "Config")
    p1_defs_path = os.path.join(config_dir, "p1_rule_defs.json")
    parsed_rules_path = os.path.join(config_dir, "parsed_rules.json")
    _ = _read_json(parsed_rules_path)
    p1_defs = _read_json(p1_defs_path)
    if not isinstance(p1_defs, list):
        raise RuntimeError("p1_rule_defs.json must be a list")

    checker = HeuristicChecker(parsed_rules_path)
    enabled_rules = [r for r in p1_defs if isinstance(r, dict) and r.get("enabled", False)]
    selected_types = {x.strip().lower() for x in (args.selected_types or []) if x.strip()}
    if selected_types:
        filtered = []
        for r in enabled_rules:
            ftype = _preferred_file_type(r).lower()
            if ftype in selected_types:
                filtered.append(r)
        enabled_rules = filtered

    failures: Dict[str, List[str]] = {
        "NO_POSITIVE_HIT": [],
        "FALSE_POSITIVE_ON_NEGATIVE": [],
        "RULE_ID_MISMATCH": [],
        "TYPE_ROUTING_MISMATCH": [],
        "CASE_GENERATION_UNSUPPORTED": [],
        "CHECKER_API_MISMATCH": [],
    }
    results: List[Dict[str, Any]] = []
    api_mismatch_count = 0
    api_checked_count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        harness = None if args.skip_api_crosscheck else _ApiHarness(tmpdir)
        try:
            for rule in enabled_rules:
                rid = _rule_public_id(rule)
                expected_ids = _expected_rule_ids(rule)
                preferred_file_type = _preferred_file_type(rule)
                case = build_rule_case(rule, case_source=args.case_source)
                file_type = str(case.file_type or preferred_file_type)
                ext = ".ctl" if file_type == "Server" else ".txt"
                row: Dict[str, Any] = {
                    "rule_id": rid,
                    "expected_rule_ids": sorted(expected_ids),
                    "file_type": file_type,
                    "detector_kind": str((rule.get("detector") or {}).get("kind") or ""),
                    "detector_op": str((rule.get("detector") or {}).get("op") or ""),
                    "supported_case": case.supported,
                    "unsupported_reason": "" if case.supported else case.reason,
                    "case_source": case.source or "unknown",
                    "case_notes": case.notes or "",
                }

                if not case.supported:
                    failures["CASE_GENERATION_UNSUPPORTED"].append(rid)
                    row.update(
                        {
                            "positive_detected": False,
                            "negative_not_detected": False,
                            "rule_id_match": False,
                            "file_type_match": False,
                            "target_positive_hit": False,
                            "target_negative_clear": False,
                            "collateral_positive_ids": [],
                            "collateral_negative_ids": [],
                            "checker_positive_ids": [],
                            "checker_negative_ids": [],
                            "api_positive_ids": [],
                            "api_negative_ids": [],
                            "checker_api_match": None,
                        }
                    )
                    results.append(row)
                    continue

                checker_pos = _run_checker_case(checker, rule, case.positive, file_type, ext)
                checker_neg = _run_checker_case(checker, rule, case.negative, file_type, ext)
                checker_pos_ids = _collect_rule_ids_from_checker(checker_pos)
                checker_neg_ids = _collect_rule_ids_from_checker(checker_neg)

                target_positive_hit = bool(checker_pos_ids & expected_ids)
                target_negative_clear = not bool(checker_neg_ids & expected_ids)
                positive_detected = target_positive_hit
                negative_not_detected = target_negative_clear
                rule_id_match = target_positive_hit
                collateral_positive_ids = sorted(checker_pos_ids - expected_ids)
                collateral_negative_ids = sorted(checker_neg_ids - expected_ids)

                opposite_file_type = "Client" if file_type == "Server" else "Server"
                opposite_ids = _collect_rule_ids_from_checker(
                    _run_checker_case(
                        checker,
                        rule,
                        case.positive,
                        opposite_file_type,
                        ".txt" if opposite_file_type == "Client" else ".ctl",
                    )
                )
                only_one_type = len({str(x).strip().lower() for x in (rule.get("file_types") or [])}) == 1
                file_type_match = True
                if only_one_type and (opposite_ids & expected_ids):
                    file_type_match = False

                if not positive_detected:
                    failures["NO_POSITIVE_HIT"].append(rid)
                if not negative_not_detected:
                    failures["FALSE_POSITIVE_ON_NEGATIVE"].append(rid)
                if not rule_id_match:
                    failures["RULE_ID_MISMATCH"].append(rid)
                if not file_type_match:
                    failures["TYPE_ROUTING_MISMATCH"].append(rid)

                api_pos_ids: Set[str] = set()
                api_neg_ids: Set[str] = set()
                checker_api_match: Optional[bool] = None
                detector = rule.get("detector") if isinstance(rule.get("detector"), dict) else {}
                op = str(detector.get("op") or "").strip().lower()
                skip_api_crosscheck_for_rule = op == "ui_block_initialize_delay"
                if harness is not None and not skip_api_crosscheck_for_rule:
                    pos_name = f"{urllib.parse.quote(rid, safe='')}_pos{ext}"
                    neg_name = f"{urllib.parse.quote(rid, safe='')}_neg{ext}"
                    with open(os.path.join(tmpdir, pos_name), "w", encoding="utf-8") as f:
                        f.write(case.positive)
                    with open(os.path.join(tmpdir, neg_name), "w", encoding="utf-8") as f:
                        f.write(case.negative)

                    api_pos_payload = harness.analyze(pos_name)
                    api_neg_payload = harness.analyze(neg_name)
                    if "_error" not in api_pos_payload and "_error" not in api_neg_payload:
                        api_checked_count += 1
                        api_pos_ids = _collect_rule_ids_from_api(api_pos_payload)
                        api_neg_ids = _collect_rule_ids_from_api(api_neg_payload)
                        api_pos_hit = bool(api_pos_ids & expected_ids)
                        api_neg_clear = not bool(api_neg_ids & expected_ids)
                        checker_api_match = (api_pos_hit == target_positive_hit) and (api_neg_clear == target_negative_clear)
                        if not checker_api_match:
                            failures["CHECKER_API_MISMATCH"].append(rid)
                            api_mismatch_count += 1

                row.update(
                    {
                        "positive_detected": positive_detected,
                        "negative_not_detected": negative_not_detected,
                        "target_positive_hit": target_positive_hit,
                        "target_negative_clear": target_negative_clear,
                        "rule_id_match": rule_id_match,
                        "file_type_match": file_type_match,
                        "collateral_positive_ids": collateral_positive_ids,
                        "collateral_negative_ids": collateral_negative_ids,
                        "checker_positive_ids": sorted(checker_pos_ids),
                        "checker_negative_ids": sorted(checker_neg_ids),
                        "api_positive_ids": sorted(api_pos_ids),
                        "api_negative_ids": sorted(api_neg_ids),
                        "checker_api_match": checker_api_match,
                    }
                )
                results.append(row)
        finally:
            if harness is not None:
                harness.close()

    supported = [r for r in results if r["supported_case"]]
    unsupported = [r for r in results if not r["supported_case"]]
    pos_pass = sum(1 for r in supported if r["positive_detected"])
    neg_pass = sum(1 for r in supported if r["negative_not_detected"])
    pos_rate = (pos_pass / len(supported) * 100.0) if supported else 0.0
    neg_rate = (neg_pass / len(supported) * 100.0) if supported else 0.0
    mismatch_rate = (api_mismatch_count / api_checked_count * 100.0) if api_checked_count else 0.0

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "project_root": args.project_root,
        "summary": {
            "enabled_rules": len(enabled_rules),
            "supported_rules": len(supported),
            "unsupported_rules": len(unsupported),
            "positive_detection_rate": pos_rate,
            "negative_not_detected_rate": neg_rate,
            "checker_vs_api_mismatch_rate": mismatch_rate,
            "checker_vs_api_checked_rules": api_checked_count,
        },
        "failures": failures,
        "results": results,
    }

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path, md_path = _write_reports(args.output_dir, stamp, payload)
    payload["artifacts"] = {"json": json_path, "markdown": md_path}
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Verify enabled P1 rules by matrix positive/negative cases.")
    p.add_argument(
        "--project-root",
        default=PROJECT_ROOT,
        help="Project root path (default: repository root).",
    )
    p.add_argument(
        "--output-dir",
        default=os.path.join(PROJECT_ROOT, "docs", "perf_baselines"),
        help="Directory where JSON/MD artifacts are written.",
    )
    p.add_argument(
        "--skip-api-crosscheck",
        action="store_true",
        help="Skip /api/analyze cross-check and run checker-only matrix.",
    )
    p.add_argument(
        "--selected-types",
        nargs="*",
        choices=["server", "client"],
        help="Optional file type filter.",
    )
    p.add_argument(
        "--case-source",
        choices=["rule_catalog", "op_fallback", "mixed"],
        default="mixed",
        help="Case generation source policy (default: mixed).",
    )
    p.add_argument("--json", action="store_true", help="Print final payload as JSON.")
    return p


def main() -> int:
    args = build_parser().parse_args()
    payload = run(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        s = payload["summary"]
        print("[P1 Matrix] done")
        print(f"enabled={s['enabled_rules']} supported={s['supported_rules']} unsupported={s['unsupported_rules']}")
        print(f"positive_rate={s['positive_detection_rate']:.2f}% negative_rate={s['negative_not_detected_rate']:.2f}%")
        print(f"checker_vs_api_mismatch_rate={s['checker_vs_api_mismatch_rate']:.2f}%")
        print(f"json={payload['artifacts']['json']}")
        print(f"md={payload['artifacts']['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
