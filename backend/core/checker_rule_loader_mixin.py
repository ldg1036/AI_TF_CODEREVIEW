import json
import os
import re
from typing import Any, Callable, Dict, List


class CheckerRuleLoaderMixin:
    """Host class should expose rule helpers and checker methods via MRO."""

    def _load_rules(self, path: str) -> List[Dict]:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)

            alt_path = path.replace("parsed_rules.json", "rules.json")
            if os.path.exists(alt_path):
                with open(alt_path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"[!] Error loading rules: {e}")
            return []

    def _define_technical_patterns(self) -> Dict:
        return {
            "PERF-01": {
                "pattern": r"(dpConnect|dpQueryConnect)[^\n]{0,200}delay\(",
                "message": "Callback 내부 delay 사용 감지.",
                "severity": "Critical",
                "rule_item": "비동기 처리(dpConnect, dpQueryConnectSingle) 시 Callback 함수 병목 요소 최소화",
            },
            "PERF-02": {
                "pattern": r"dpQuery.*FROM.*[\"'](\*\*|\*\.\*)[\"']",
                "message": "DP Query 전체 범위 조회 패턴 감지.",
                "severity": "Warning",
                "rule_item": "DP Query 최적화 구현",
            },
            "HARD-01": {
                "pattern": r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b|https?://[^\s\"']+|[\"']config/[^\n\"']+[\"']",
                "message": "IP/URL/설정 경로 하드코딩 감지.",
                "severity": "Medium",
                "rule_item": "하드코딩 지양",
            },
            "DB-01": {
                "pattern": r"sprintf.*(SELECT|INSERT|UPDATE|DELETE)",
                "message": "문자열 SQL 조합 감지.",
                "severity": "Critical",
                "rule_item": "바인딩 쿼리 처리",
            },
            "DB-02": {
                # Line-scoped pattern to avoid catastrophic backtracking on large files.
                "pattern": r"^(?!\s*//)[^\n]*\b(SELECT|INSERT|UPDATE|DELETE)\b",
                "message": "쿼리 주석 누락 가능성 감지.",
                "severity": "Info",
                "rule_item": "쿼리 주석 처리",
            },
        }

    @staticmethod
    def _compact_text(text: str) -> str:
        return re.sub(r"\s+", "", str(text or "")).lower()

    def _normalize_rule_item(self, rule_item: str) -> str:
        compact = self._compact_text(rule_item)
        return self.rule_item_aliases.get(compact, compact)

    def _build_allowed_rule_items(self) -> Dict[str, set]:
        allowed = {"Client": set(), "Server": set()}
        for row in self.rules_data:
            if not isinstance(row, dict):
                continue
            rule_type = row.get("type")
            item = row.get("item")
            if rule_type not in allowed:
                continue
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if not stripped or stripped.lower() == "nan":
                continue
            allowed[rule_type].add(self._normalize_rule_item(stripped))
        return allowed

    def _is_rule_allowed(self, rule_item: str, file_type: str) -> bool:
        allowed = self.allowed_rule_items.get(file_type)
        if not allowed:
            # If rules were not loaded, avoid dropping findings silently.
            return True
        normalized = self._normalize_rule_item(rule_item)
        return normalized in allowed

    def _build_item_filter_fallback_rule_ids_by_type(self) -> Dict[str, set]:
        allowed = {"Client": set(), "Server": set()}
        for row in self.p1_rule_defs:
            if not isinstance(row, dict):
                continue
            if not row.get("enabled", False):
                continue
            meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
            if not meta.get("allow_item_filter_fallback"):
                continue
            rule_id = row.get("rule_id")
            if not isinstance(rule_id, str) or not rule_id.strip():
                continue
            for file_type in ("Client", "Server"):
                if self._p1_rule_enabled_for_file_type(row, file_type):
                    allowed[file_type].add(rule_id.strip())
        return allowed

    def _filter_violations_by_file_type(self, violations: List[Dict], file_type: str) -> List[Dict]:
        filtered = []
        fallback_rule_ids = self.item_filter_fallback_rule_ids_by_type.get(file_type, set())
        for violation in violations:
            rule_id = violation.get("rule_id")
            rule_item = violation.get("rule_item")
            if rule_id == "INFO" or not rule_item:
                filtered.append(violation)
                continue
            if self._is_rule_allowed(rule_item, file_type):
                filtered.append(violation)
                continue
            # Narrow fallback for known parsed_rules.json extraction gaps/string drift only.
            if isinstance(rule_id, str) and rule_id in fallback_rule_ids:
                filtered.append(violation)
        return filtered

    def _load_p1_rule_defs(self, rules_path: str) -> List[Dict]:
        try:
            cfg_dir = os.path.dirname(os.path.abspath(rules_path))
            defs_path = os.path.join(cfg_dir, "p1_rule_defs.json")
            if not os.path.exists(defs_path):
                return []
            with open(defs_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print("[!] p1_rule_defs.json must be a list. Falling back to legacy P1 engine.")
                return []
            prepared = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                prepared.append(self._prepare_p1_rule_def(row))
            prepared.sort(key=lambda row: self._safe_int(row.get("_sort_order", 0), 0))
            return prepared
        except Exception as e:
            print(f"[!] Error loading p1 rule defs: {e}")
            return []

    def _build_legacy_detector_handlers(self) -> Dict[str, Callable]:
        return {
            "check_sql_injection": self.check_sql_injection,
            "check_complexity": self.check_complexity,
            "check_unused_variables": self.check_unused_variables,
            "check_db_query_error": self.check_db_query_error,
            "check_dp_function_exception": self.check_dp_function_exception,
            "check_config_format_consistency": self.check_config_format_consistency,
            "check_config_error_contract": self.check_config_error_contract,
            "check_while_delay_policy": self.check_while_delay_policy,
            "check_event_exchange_minimization": self.check_event_exchange_minimization,
            "check_dpset_timed_context": self.check_dpset_timed_context,
            "check_dpget_batch_optimization": self.check_dpget_batch_optimization,
            "check_dpset_batch_optimization": self.check_dpset_batch_optimization,
            "check_setvalue_batch_optimization": self.check_setvalue_batch_optimization,
            "check_setmultivalue_adoption": self.check_setmultivalue_adoption,
            "check_getvalue_batch_optimization": self.check_getvalue_batch_optimization,
            "check_try_catch_for_risky_ops": self.check_try_catch_for_risky_ops,
            "check_division_zero_guard": self.check_division_zero_guard,
            "check_manual_aggregation_pattern": self.check_manual_aggregation_pattern,
            "check_consecutive_dpset": self.check_consecutive_dpset,
            "check_memory_leaks_advanced": self.check_memory_leaks_advanced,
            "check_input_validation": self.check_input_validation,
            "check_coding_standards_advanced": self.check_coding_standards_advanced,
            "check_style_name_rules": self.check_style_name_rules,
            "check_style_indent_rules": self.check_style_indent_rules,
            "check_style_header_rules": self.check_style_header_rules,
            "check_magic_index_usage": self.check_magic_index_usage,
            "check_hardcoding_extended": self.check_hardcoding_extended,
            "check_float_literal_hardcoding": self.check_float_literal_hardcoding,
            "check_dead_code": self.check_dead_code,
            "check_duplicate_blocks": self.check_duplicate_blocks,
            "__ui_block_initialize_delay__": self._legacy_ui_block_initialize_delay,
        }

    @staticmethod
    def _p1_rule_enabled_for_file_type(rule_def: Dict[str, Any], file_type: str) -> bool:
        file_types = rule_def.get("file_types")
        if file_types is None:
            return True
        if isinstance(file_types, str):
            file_types = [file_types]
        if not isinstance(file_types, list):
            return True
        normalized = {str(x).strip().lower() for x in file_types if str(x).strip()}
        if not normalized or "all" in normalized or "both" in normalized:
            return True
        return str(file_type or "").strip().lower() in normalized

    @staticmethod
    def _regex_flags_from_rule(flag_names: Any) -> int:
        if isinstance(flag_names, str):
            flag_names = [flag_names]
        flags = 0
        if not isinstance(flag_names, list):
            return flags
        mapping = {
            "IGNORECASE": re.IGNORECASE,
            "MULTILINE": re.MULTILINE,
            "DOTALL": re.DOTALL,
        }
        for name in flag_names:
            key = str(name or "").strip().upper()
            flags |= mapping.get(key, 0)
        return flags

    def _prepare_p1_rule_def(self, row: Dict[str, Any]) -> Dict[str, Any]:
        prepared = dict(row)
        prepared["_sort_order"] = self._safe_int(prepared.get("order", 0), 0)

        detector = prepared.get("detector", {})
        if not isinstance(detector, dict):
            return prepared

        prepared_detector = dict(detector)
        kind = str(prepared_detector.get("kind", "") or "").strip().lower()
        if kind == "regex":
            raw_pattern = prepared_detector.get("pattern", "")
            normalized_pattern = self._normalize_detector_regex(raw_pattern)
            prepared_detector["pattern"] = normalized_pattern
            flags = self._regex_flags_from_rule(prepared_detector.get("flags", ["DOTALL", "MULTILINE"]))
            prepared_detector["_compiled_flags"] = flags

            event_names = prepared_detector.get("event_names")
            if isinstance(event_names, str):
                event_names = [event_names]
            if isinstance(event_names, list):
                prepared_detector["_allowed_event_names"] = {
                    str(item) for item in event_names if str(item or "").strip()
                }
            else:
                prepared_detector["_allowed_event_names"] = set()

            try:
                prepared_detector["_compiled_regex"] = re.compile(normalized_pattern, flags)
                prepared_detector["_invalid_regex_error"] = ""
            except re.error as exc:
                prepared_detector["_compiled_regex"] = None
                prepared_detector["_invalid_regex_error"] = str(exc)
                print(
                    f"[!] Invalid regex in p1_rule_defs "
                    f"({prepared.get('id', prepared.get('rule_id'))}): {exc}"
                )

        prepared["detector"] = prepared_detector
        return prepared

    @staticmethod
    def _normalize_detector_regex(pattern: Any) -> str:
        text = str(pattern or "")
        if not text:
            return ""
        # Some detector entries were serialized with double-escaped regex tokens
        # like "\\\\b", which should behave as "\\b" at runtime.
        try:
            return re.sub(r"\\\\([\\bBsSdDwW\(\)\[\]\{\}\.\+\*\?\^\$\|])", r"\\\1", text)
        except Exception:
            return text

    def _build_p1_issue(
        self,
        rule_id: str,
        rule_item: str,
        severity: str,
        line: int,
        message: str,
        analysis_code: str,
        event_name: str,
    ) -> Dict:
        return {
            "issue_id": self._build_issue_id(rule_id, analysis_code, line, event_name),
            "rule_id": rule_id,
            "rule_item": rule_item,
            "priority_origin": "P1",
            "severity": severity,
            "line": line,
            "message": message,
        }
