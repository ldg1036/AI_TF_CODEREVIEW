"""HealthCheckMixin – Dependency health checks and verification summary extracted from server.py."""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
ARTIFACT_JSON_ENCODING = "utf-8-sig"


class HealthCheckMixin:
    """Provides dependency health checks (openpyxl, ctrlppcheck, playwright) and verification summary."""

    _RULE_FLAG_MAP = {
        "IGNORECASE": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "DOTALL": re.DOTALL,
    }

    def _get_rules_config_dir(self) -> str:
        checker = getattr(self.app, "checker", None)
        config_dir = str(getattr(checker, "config_dir", "") or "")
        if config_dir:
            return config_dir
        base_dir = str(getattr(self.app, "base_dir", "") or "")
        return os.path.join(base_dir, "Config")

    def _build_rules_health_payload(self) -> Dict[str, Any]:
        checker = getattr(self.app, "checker", None)
        p1_rule_defs = list(getattr(checker, "p1_rule_defs", []) or [])
        parsed_rules = list(getattr(checker, "rules_data", []) or [])
        dependencies = self._build_dependency_health_payload().get("dependencies", {})

        detector_counts: Dict[str, int] = {"regex": 0, "composite": 0, "line_repeat": 0}
        enabled_count = 0
        for rule_def in p1_rule_defs:
            if not isinstance(rule_def, dict):
                continue
            if bool(rule_def.get("enabled", True)):
                enabled_count += 1
            detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
            kind = str(detector.get("kind", "") or "").strip().lower()
            if kind in detector_counts:
                detector_counts[kind] += 1

        file_type_counts: Dict[str, int] = {"Client": 0, "Server": 0}
        for row in parsed_rules:
            if not isinstance(row, dict):
                continue
            rule_type = str(row.get("type", "") or "").strip()
            if rule_type in file_type_counts:
                file_type_counts[rule_type] += 1

        degraded_reasons: List[str] = []
        for dep_key, dep_label in (
            ("openpyxl", "openpyxl missing"),
            ("ctrlppcheck", "CtrlppCheck missing"),
            ("playwright", "Playwright missing"),
        ):
            dep = dependencies.get(dep_key, {}) if isinstance(dependencies, dict) else {}
            if not bool(dep.get("available", False)):
                degraded_reasons.append(dep_label)

        return {
            "available": True,
            "generated_at_ms": self._epoch_ms(),
            "status": "degraded" if degraded_reasons else "ok",
            "message": ", ".join(degraded_reasons),
            "rules": {
                "p1_total": len([row for row in p1_rule_defs if isinstance(row, dict)]),
                "p1_enabled": enabled_count,
                "detector_counts": detector_counts,
                "file_type_counts": file_type_counts,
                "regex_count": int(detector_counts.get("regex", 0)),
                "composite_count": int(detector_counts.get("composite", 0)),
                "line_repeat_count": int(detector_counts.get("line_repeat", 0)),
            },
            "dependencies": {
                "openpyxl": dependencies.get("openpyxl", {}),
                "ctrlppcheck": dependencies.get("ctrlppcheck", {}),
                "playwright": dependencies.get("playwright", {}),
            },
        }

    def _build_rules_list_payload(self) -> Dict[str, Any]:
        p1_rule_defs = self._load_rule_rows()
        rows: List[Dict[str, Any]] = []
        for row in sorted(p1_rule_defs, key=lambda item: int((item or {}).get("order", 0) or 0)):
            if not isinstance(row, dict):
                continue
            detector = row.get("detector", {}) if isinstance(row.get("detector"), dict) else {}
            finding = row.get("finding", {}) if isinstance(row.get("finding"), dict) else {}
            rows.append(
                {
                    "id": str(row.get("id", "") or ""),
                    "rule_id": str(row.get("rule_id", "") or ""),
                    "item": str(row.get("item", "") or ""),
                    "enabled": bool(row.get("enabled", True)),
                    "order": int(row.get("order", 0) or 0),
                    "file_types": [str(item) for item in (row.get("file_types", []) or []) if str(item or "").strip()],
                    "detector_kind": str(detector.get("kind", "") or ""),
                    "severity": str(finding.get("severity", "") or ""),
                    "message": str(finding.get("message", "") or ""),
                    "detector": detector,
                    "finding": finding,
                    "meta": row.get("meta", {}) if isinstance(row.get("meta"), dict) else {},
                }
            )
        return {
            "available": True,
            "generated_at_ms": self._epoch_ms(),
            "config_dir": self._get_rules_config_dir(),
            "rules": rows,
        }

    def _rules_defs_path(self) -> str:
        return os.path.join(self._get_rules_config_dir(), "p1_rule_defs.json")

    def _load_rule_rows(self) -> List[Dict[str, Any]]:
        defs_path = self._rules_defs_path()
        if not os.path.exists(defs_path):
            raise FileNotFoundError(f"p1_rule_defs.json not found: {defs_path}")
        with open(defs_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise RuntimeError("p1_rule_defs.json must be a list")
        return [row for row in payload if isinstance(row, dict)]

    def _write_rule_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        config_dir = self._get_rules_config_dir()
        defs_path = self._rules_defs_path()
        fd, tmp_path = tempfile.mkstemp(prefix="p1_rule_defs_", suffix=".json", dir=config_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(rows, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(tmp_path, defs_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        reload_meta = self.app.reload_rule_configuration()
        return reload_meta

    @classmethod
    def _regex_flags_from_rule(cls, flag_names: Any) -> int:
        if isinstance(flag_names, str):
            flag_names = [flag_names]
        flags = 0
        if not isinstance(flag_names, list):
            return flags
        for name in flag_names:
            key = str(name or "").strip().upper()
            flags |= cls._RULE_FLAG_MAP.get(key, 0)
        return flags

    def _normalize_rule_row(self, row: Dict[str, Any], *, existing_ids: Optional[set[str]] = None, current_id: str = "") -> Dict[str, Any]:
        if not isinstance(row, dict):
            raise ValueError("rule must be an object")
        rule_id_text = str(row.get("id", "") or "").strip()
        if not rule_id_text:
            raise ValueError("rule id must be a non-empty string")
        if existing_ids is not None and rule_id_text != current_id and rule_id_text in existing_ids:
            raise ValueError(f"Duplicate rule id: {rule_id_text}")

        normalized_rule_id = str(row.get("rule_id", "") or "").strip()
        if not normalized_rule_id:
            raise ValueError("rule_id must be a non-empty string")
        item = str(row.get("item", "") or "").strip()
        if not item:
            raise ValueError("item must be a non-empty string")

        file_types = row.get("file_types", ["Client", "Server"])
        if isinstance(file_types, str):
            file_types = [file_types]
        if not isinstance(file_types, list) or not file_types:
            raise ValueError("file_types must be a non-empty list")
        normalized_file_types = []
        for file_type in file_types:
            text = str(file_type or "").strip()
            if text not in ("Client", "Server"):
                raise ValueError("file_types entries must be Client or Server")
            if text not in normalized_file_types:
                normalized_file_types.append(text)

        detector = row.get("detector", {})
        if not isinstance(detector, dict):
            raise ValueError("detector must be an object")
        kind = str(detector.get("kind", "") or "").strip().lower()
        if kind not in {"regex", "composite", "line_repeat", "legacy_handler"}:
            raise ValueError("detector.kind must be one of: regex, composite, line_repeat, legacy_handler")
        normalized_detector = dict(detector)
        normalized_detector["kind"] = kind
        if kind == "regex":
            pattern = str(detector.get("pattern", "") or "")
            if not pattern:
                raise ValueError("regex detector requires pattern")
            flags = detector.get("flags", ["DOTALL", "MULTILINE"])
            try:
                re.compile(pattern, self._regex_flags_from_rule(flags))
            except re.error as exc:
                raise ValueError(f"invalid regex pattern: {exc}") from exc
            if isinstance(flags, str):
                flags = [flags]
            normalized_detector["flags"] = [str(flag or "").strip().upper() for flag in (flags or []) if str(flag or "").strip()]
        elif kind == "composite":
            if not str(detector.get("op", "") or "").strip():
                raise ValueError("composite detector requires op")
        elif kind == "legacy_handler":
            if not str(detector.get("handler", "") or "").strip():
                raise ValueError("legacy_handler detector requires handler")
        elif kind == "line_repeat":
            threshold = int(detector.get("threshold", 3) or 3)
            normalized_detector["threshold"] = max(2, threshold)

        finding = row.get("finding", {})
        if not isinstance(finding, dict):
            raise ValueError("finding must be an object")
        severity = str(finding.get("severity", "") or "").strip()
        message = str(finding.get("message", "") or "").strip()
        if not severity:
            raise ValueError("finding.severity must be a non-empty string")
        if not message:
            raise ValueError("finding.message must be a non-empty string")

        meta = row.get("meta", {})
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            raise ValueError("meta must be an object when provided")

        return {
            "id": rule_id_text,
            "order": int(row.get("order", 0) or 0),
            "enabled": bool(row.get("enabled", True)),
            "file_types": normalized_file_types,
            "rule_id": normalized_rule_id,
            "item": item,
            "detector": normalized_detector,
            "finding": {
                "severity": severity,
                "message": message,
            },
            "meta": meta,
        }

    def _update_rules_enabled_state(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(updates, list) or not updates:
            raise ValueError("updates must be a non-empty list")

        normalized_updates: Dict[str, bool] = {}
        for update in updates:
            if not isinstance(update, dict):
                raise ValueError("each update must be an object")
            rule_id = str(update.get("id", "") or "").strip()
            if not rule_id:
                raise ValueError("update id must be a non-empty string")
            enabled = update.get("enabled", None)
            if not isinstance(enabled, bool):
                raise ValueError("update enabled must be a boolean")
            normalized_updates[rule_id] = enabled

        payload = self._load_rule_rows()
        seen_ids = {str((row or {}).get("id", "") or "") for row in payload if isinstance(row, dict)}
        missing_ids = [rule_id for rule_id in normalized_updates if rule_id not in seen_ids]
        if missing_ids:
            raise ValueError(f"Unknown rule id(s): {missing_ids}")

        applied = 0
        for row in payload:
            if not isinstance(row, dict):
                continue
            rule_id = str(row.get("id", "") or "")
            if rule_id in normalized_updates:
                row["enabled"] = normalized_updates[rule_id]
                applied += 1

        reload_meta = self._write_rule_rows(payload)
        return {
            "updated_count": applied,
            "rules": self._build_rules_list_payload()["rules"],
            "reload": reload_meta,
        }

    def _replace_rule(self, rule_payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = self._load_rule_rows()
        current_id = str(rule_payload.get("id", "") or "").strip()
        existing_ids = {str((row or {}).get("id", "") or "") for row in rows if isinstance(row, dict)}
        if current_id not in existing_ids:
            raise ValueError(f"Unknown rule id(s): ['{current_id}']")
        normalized = self._normalize_rule_row(rule_payload, existing_ids=existing_ids, current_id=current_id)
        new_rows = [normalized if str((row or {}).get("id", "") or "") == current_id else row for row in rows]
        reload_meta = self._write_rule_rows(new_rows)
        return {
            "rule": normalized,
            "rules": self._build_rules_list_payload()["rules"],
            "reload": reload_meta,
        }

    def _create_rule(self, rule_payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = self._load_rule_rows()
        existing_ids = {str((row or {}).get("id", "") or "") for row in rows if isinstance(row, dict)}
        normalized = self._normalize_rule_row(rule_payload, existing_ids=existing_ids)
        rows.append(normalized)
        rows.sort(key=lambda item: (int((item or {}).get("order", 0) or 0), str((item or {}).get("id", "") or "")))
        reload_meta = self._write_rule_rows(rows)
        return {
            "rule": normalized,
            "rules": self._build_rules_list_payload()["rules"],
            "reload": reload_meta,
        }

    def _delete_rule(self, rule_id: str) -> Dict[str, Any]:
        normalized_rule_id = str(rule_id or "").strip()
        if not normalized_rule_id:
            raise ValueError("rule id must be a non-empty string")
        rows = self._load_rule_rows()
        kept_rows = [row for row in rows if str((row or {}).get("id", "") or "") != normalized_rule_id]
        if len(kept_rows) == len(rows):
            raise ValueError(f"Unknown rule id(s): ['{normalized_rule_id}']")
        reload_meta = self._write_rule_rows(kept_rows)
        return {
            "deleted_id": normalized_rule_id,
            "rules": self._build_rules_list_payload()["rules"],
            "reload": reload_meta,
        }

    def _export_rules_payload(self) -> Dict[str, Any]:
        return {
            "available": True,
            "generated_at_ms": self._epoch_ms(),
            "config_dir": self._get_rules_config_dir(),
            "rules": self._load_rule_rows(),
        }

    def _import_rules_payload(self, rules: List[Dict[str, Any]], mode: str = "replace") -> Dict[str, Any]:
        if not isinstance(rules, list) or not rules:
            raise ValueError("rules must be a non-empty list")
        normalized_mode = str(mode or "replace").strip().lower()
        if normalized_mode not in {"replace", "merge"}:
            raise ValueError("mode must be one of: replace, merge")

        existing_rows = self._load_rule_rows()
        existing_ids = {str((row or {}).get("id", "") or "") for row in existing_rows if isinstance(row, dict)}
        normalized_rows: List[Dict[str, Any]] = []
        seen_new_ids: set[str] = set()
        for rule in rules:
            normalized = self._normalize_rule_row(rule, existing_ids=None)
            if normalized["id"] in seen_new_ids:
                raise ValueError(f"Duplicate rule id in import payload: {normalized['id']}")
            seen_new_ids.add(normalized["id"])
            normalized_rows.append(normalized)

        if normalized_mode == "replace":
            final_rows = sorted(normalized_rows, key=lambda item: (int(item.get("order", 0) or 0), str(item.get("id", "") or "")))
        else:
            merged_map = {str((row or {}).get("id", "") or ""): row for row in existing_rows if isinstance(row, dict)}
            for row in normalized_rows:
                merged_map[row["id"]] = row
            final_rows = sorted(merged_map.values(), key=lambda item: (int((item or {}).get("order", 0) or 0), str((item or {}).get("id", "") or "")))

        reload_meta = self._write_rule_rows(final_rows)
        return {
            "imported_count": len(normalized_rows),
            "mode": normalized_mode,
            "rules": self._build_rules_list_payload()["rules"],
            "reload": reload_meta,
        }

    def _playwright_dependency_status(self) -> Dict[str, Any]:
        node_bin = shutil.which("node")
        if not node_bin:
            return {
                "available": False,
                "node_available": False,
                "package_available": False,
                "required_for": ["ui_benchmark"],
                "message": "node binary not found",
            }

        try:
            proc = subprocess.run(
                [node_bin, "-e", "require.resolve('playwright')"],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                check=False,
            )
        except Exception as exc:
            return {
                "available": False,
                "node_available": True,
                "package_available": False,
                "required_for": ["ui_benchmark"],
                "message": f"playwright package check failed: {exc}",
            }

        package_available = proc.returncode == 0
        return {
            "available": bool(package_available),
            "node_available": True,
            "package_available": bool(package_available),
            "required_for": ["ui_benchmark"],
            "message": "playwright package available" if package_available else "playwright package is not installed",
        }

    def _build_dependency_health_payload(self) -> Dict[str, Any]:
        excel_available = bool(self.app.reporter.is_excel_support_available())
        openpyxl_status = {
            "available": excel_available,
            "required_for": ["excel_report", "template_coverage"],
            "message": "openpyxl available" if excel_available else "openpyxl is not installed",
        }

        ctrl_binary = ""
        try:
            ctrl_binary = str(self.app.ctrl_tool._find_binary() or "")
        except Exception:
            ctrl_binary = ""
        ctrl_ready = bool(ctrl_binary)
        ctrl_status = {
            "available": ctrl_ready,
            "binary_path": ctrl_binary,
            "auto_install_on_missing": bool(getattr(self.app.ctrl_tool, "auto_install_on_missing", False)),
            "required_for": ["ctrlpp_analysis", "ctrlpp_regression"],
            "message": "CtrlppCheck binary available" if ctrl_ready else "CtrlppCheck binary not found",
        }

        playwright_status = self._playwright_dependency_status()
        capabilities = {
            "excel_report": {"ready": bool(openpyxl_status["available"]), "dependencies": ["openpyxl"]},
            "template_coverage": {"ready": bool(openpyxl_status["available"]), "dependencies": ["openpyxl"]},
            "ctrlpp_analysis": {"ready": bool(ctrl_status["available"]), "dependencies": ["ctrlppcheck"]},
            "ui_benchmark": {"ready": bool(playwright_status["available"]), "dependencies": ["playwright"]},
        }
        ready_count = sum(1 for item in capabilities.values() if bool(item.get("ready", False)))
        return {
            "status": "ok" if ready_count == len(capabilities) else "degraded",
            "generated_at_ms": self._epoch_ms(),
            "dependencies": {
                "openpyxl": openpyxl_status,
                "ctrlppcheck": ctrl_status,
                "playwright": playwright_status,
            },
            "capabilities": capabilities,
            "summary": {
                "ready_capabilities": ready_count,
                "total_capabilities": len(capabilities),
            },
        }

    def _resolve_latest_verification_summary(self) -> Dict[str, Any]:
        report_dir = Path(str(getattr(self.app.reporter, "output_base_dir", "") or "")).resolve()
        if not report_dir.exists() or not report_dir.is_dir():
            raise FileNotFoundError(f"verification report directory not found: {report_dir}")

        candidates = sorted(
            report_dir.glob("verification_summary_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError("verification summary not found")

        latest = candidates[0]
        try:
            payload = json.loads(latest.read_text(encoding=ARTIFACT_JSON_ENCODING))
        except Exception as exc:
            raise RuntimeError(f"failed to read verification summary: {latest.name}: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid verification summary payload: {latest.name}")

        payload.setdefault("source_file", latest.name)
        payload.setdefault("source_path", str(latest))
        return payload

    def _operational_result_dir_map(self) -> Dict[str, Path]:
        override = getattr(self.app, "operational_result_dirs", None)
        if isinstance(override, dict):
            result: Dict[str, Path] = {}
            for key, value in override.items():
                if not value:
                    continue
                result[str(key)] = Path(str(value)).resolve()
            if result:
                return result
        return {
            "ui_benchmark": Path(PROJECT_ROOT, "tools", "benchmark_results").resolve(),
            "ui_real_smoke": Path(PROJECT_ROOT, "tools", "integration_results").resolve(),
            "ctrlpp_integration": Path(PROJECT_ROOT, "tools", "integration_results").resolve(),
        }

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number:
            return None
        return number

    @staticmethod
    def _summarize_ui_benchmark(payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
        analyze_avg = HealthCheckMixin._safe_float(((summary.get("analyzeUiMs") or {}).get("avg")))
        table_avg = HealthCheckMixin._safe_float(((summary.get("resultTableScrollMs") or {}).get("avg")))
        jump_avg = HealthCheckMixin._safe_float(((summary.get("codeJumpMs") or {}).get("avg")))
        scroll_avg = HealthCheckMixin._safe_float(((summary.get("codeViewerScrollMs") or {}).get("avg")))
        failures = payload.get("threshold_failures", [])
        return {
            "status": "passed" if isinstance(failures, list) and not failures else "failed",
            "finished_at": str(payload.get("finished_at", "") or payload.get("started_at", "") or ""),
            "analyze_ui_avg_ms": analyze_avg,
            "table_scroll_avg_ms": table_avg,
            "code_jump_avg_ms": jump_avg,
            "code_scroll_avg_ms": scroll_avg,
            "iterations": int(payload.get("config", {}).get("iterations", 0) or 0) if isinstance(payload.get("config"), dict) else 0,
            "threshold_failure_count": len(failures) if isinstance(failures, list) else 0,
        }

    @staticmethod
    def _summarize_ui_real_smoke(payload: Dict[str, Any]) -> Dict[str, Any]:
        run = payload.get("run", {}) if isinstance(payload.get("run"), dict) else {}
        after_run = run.get("afterRun", {}) if isinstance(run.get("afterRun"), dict) else {}
        return {
            "status": "passed" if bool(payload.get("ok", False)) else "failed",
            "finished_at": str(payload.get("finished_at", "") or payload.get("started_at", "") or ""),
            "elapsed_ms": HealthCheckMixin._safe_float(run.get("elapsed_ms")),
            "rows": int(after_run.get("rows", 0) or 0),
            "total_issues": str(after_run.get("totalIssues", "") or ""),
            "selected_file": str(((payload.get("backend") or {}).get("selected_target_file", "")) or ""),
        }

    @staticmethod
    def _summarize_ctrlpp_integration(payload: Dict[str, Any]) -> Dict[str, Any]:
        direct = payload.get("direct_smoke", {}) if isinstance(payload.get("direct_smoke"), dict) else {}
        binary = payload.get("binary", {}) if isinstance(payload.get("binary"), dict) else {}
        return {
            "status": str(payload.get("status", "unknown") or "unknown"),
            "finished_at": str(payload.get("finished_at", "") or payload.get("started_at", "") or ""),
            "elapsed_ms": HealthCheckMixin._safe_float(direct.get("elapsed_ms")),
            "finding_count": int(direct.get("finding_count", 0) or 0),
            "binary_exists": bool(binary.get("exists", False)),
            "infra_error": bool(direct.get("infra_error", False)),
        }

    @staticmethod
    def _compute_operational_delta(category: str, latest: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
        delta: Dict[str, Any] = {}
        if category == "ui_benchmark":
            for key in ("analyze_ui_avg_ms", "table_scroll_avg_ms", "code_jump_avg_ms", "code_scroll_avg_ms"):
                latest_value = HealthCheckMixin._safe_float(latest.get(key))
                previous_value = HealthCheckMixin._safe_float(previous.get(key))
                if latest_value is not None and previous_value is not None:
                    delta[key] = round(latest_value - previous_value, 2)
            return delta
        for key in ("elapsed_ms", "rows", "finding_count"):
            latest_value = HealthCheckMixin._safe_float(latest.get(key))
            previous_value = HealthCheckMixin._safe_float(previous.get(key))
            if latest_value is not None and previous_value is not None:
                delta[key] = round(latest_value - previous_value, 2)
        return delta

    def _load_recent_operational_results(self, category: str, limit: int = 2) -> List[Dict[str, Any]]:
        prefix = f"{category}_"
        directory = self._operational_result_dir_map().get(category)
        if directory is None or not directory.exists() or not directory.is_dir():
            return []
        candidates = sorted(
            directory.glob(f"{prefix}*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        results: List[Dict[str, Any]] = []
        for path in candidates[: max(1, int(limit or 1))]:
            try:
                payload = json.loads(path.read_text(encoding=ARTIFACT_JSON_ENCODING))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if category == "ui_benchmark":
                summary = self._summarize_ui_benchmark(payload)
            elif category == "ui_real_smoke":
                summary = self._summarize_ui_real_smoke(payload)
            else:
                summary = self._summarize_ctrlpp_integration(payload)
            summary["source_file"] = path.name
            summary["source_path"] = str(path)
            results.append(summary)
        return results

    def _resolve_latest_operational_results(self) -> Dict[str, Any]:
        categories = {
            "ui_benchmark": "UI Benchmark",
            "ui_real_smoke": "UI Real Smoke",
            "ctrlpp_integration": "Ctrlpp Integration",
        }
        payload: Dict[str, Any] = {
            "generated_at_ms": self._epoch_ms(),
            "categories": {},
        }
        for key, label in categories.items():
            recent = self._load_recent_operational_results(key, limit=2)
            latest = recent[0] if recent else None
            previous = recent[1] if len(recent) > 1 else None
            delta = self._compute_operational_delta(key, latest or {}, previous or {}) if latest and previous else {}
            payload["categories"][key] = {
                "label": label,
                "available": bool(latest),
                "latest": latest,
                "previous": previous,
                "delta": delta,
            }
        return payload

    def _analysis_result_dir(self) -> Path:
        return Path(str(getattr(self.app.reporter, "output_base_dir", "") or "")).resolve()

    def _build_analysis_run_collection(
        self,
        runs: List[Dict[str, Any]],
        invalid_runs: List[str],
        base_message: str = "",
    ) -> Dict[str, Any]:
        warnings = list(invalid_runs)
        message = str(base_message or "")
        if warnings:
            summary = f"skipped {len(warnings)} invalid run(s): {warnings[0]}"
            message = f"{message} ({summary})" if message else summary
        return {
            "runs": runs,
            "invalid_runs": invalid_runs,
            "warnings": warnings,
            "invalid_run_count": len(warnings),
            "message": message,
        }

    def _load_recent_analysis_runs(self, limit: int = 2) -> Dict[str, Any]:
        report_dir = self._analysis_result_dir()
        if not report_dir.exists() or not report_dir.is_dir():
            return self._build_analysis_run_collection([], [])
        candidates = sorted(
            [item for item in report_dir.iterdir() if item.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        runs: List[Dict[str, Any]] = []
        invalid_runs: List[str] = []
        max_runs = max(1, int(limit or 1))
        for item in candidates:
            summary_path = item / "analysis_summary.json"
            if not summary_path.exists():
                invalid_runs.append(f"analysis summary not found: {summary_path}")
                continue
            try:
                payload = json.loads(summary_path.read_text(encoding=ARTIFACT_JSON_ENCODING))
            except Exception as exc:
                invalid_runs.append(f"failed to read analysis summary: {summary_path.name}: {exc}")
                continue
            if not isinstance(payload, dict):
                invalid_runs.append(f"invalid analysis summary payload: {summary_path.name}")
                continue
            runs.append(
                {
                    "output_dir": str(item),
                    "timestamp": item.name,
                    "request_id": str(payload.get("request_id", "") or ""),
                    "summary": payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {},
                    "report_paths": payload.get("report_paths", {}) if isinstance(payload.get("report_paths"), dict) else {},
                    "file_summaries": payload.get("file_summaries", []) if isinstance(payload.get("file_summaries"), list) else [],
                }
            )
            if len(runs) >= max_runs:
                break
        return self._build_analysis_run_collection(runs, invalid_runs)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_file_summary(cls, item: Dict[str, Any]) -> Dict[str, int]:
        return {
            "p1_total": cls._safe_int(item.get("p1_total", 0)),
            "p2_total": cls._safe_int(item.get("p2_total", 0)),
            "p3_total": cls._safe_int(item.get("p3_total", 0)),
            "critical": cls._safe_int(item.get("critical", 0)),
            "warning": cls._safe_int(item.get("warning", 0)),
            "info": cls._safe_int(item.get("info", 0)),
            "total": cls._safe_int(item.get("total", 0)),
        }

    @classmethod
    def _compute_analysis_summary_delta(cls, latest: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, int]:
        keys = (
            "total",
            "critical",
            "warning",
            "info",
            "p1_total",
            "p2_total",
            "p3_total",
            "requested_file_count",
            "successful_file_count",
            "failed_file_count",
        )
        return {
            key: cls._safe_int((latest.get("summary", {}) or {}).get(key, 0)) - cls._safe_int((previous.get("summary", {}) or {}).get(key, 0))
            for key in keys
        }

    @classmethod
    def _compute_analysis_file_diffs(cls, latest: Dict[str, Any], previous: Dict[str, Any]) -> List[Dict[str, Any]]:
        latest_map = {
            str((item or {}).get("file", "") or "(unknown)"): cls._normalize_file_summary(item)
            for item in latest.get("file_summaries", []) or []
            if isinstance(item, dict)
        }
        previous_map = {
            str((item or {}).get("file", "") or "(unknown)"): cls._normalize_file_summary(item)
            for item in previous.get("file_summaries", []) or []
            if isinstance(item, dict)
        }
        file_diffs: List[Dict[str, Any]] = []
        all_files = sorted(set(latest_map.keys()) | set(previous_map.keys()), key=lambda value: value.lower())
        for file_name in all_files:
            current_counts = latest_map.get(
                file_name,
                {"p1_total": 0, "p2_total": 0, "p3_total": 0, "critical": 0, "warning": 0, "info": 0, "total": 0},
            )
            previous_counts = previous_map.get(
                file_name,
                {"p1_total": 0, "p2_total": 0, "p3_total": 0, "critical": 0, "warning": 0, "info": 0, "total": 0},
            )
            delta_counts = {key: current_counts[key] - previous_counts[key] for key in current_counts.keys()}
            if file_name not in previous_map:
                status = "added"
            elif file_name not in latest_map:
                status = "removed"
            elif any(delta_counts.values()):
                status = "changed"
            else:
                status = "unchanged"
            file_diffs.append(
                {
                    "file": file_name,
                    "status": status,
                    "current_counts": current_counts,
                    "previous_counts": previous_counts,
                    "delta_counts": delta_counts,
                }
            )
        file_diffs.sort(
            key=lambda item: (
                0 if str(item.get("status", "")) != "unchanged" else 1,
                -abs(cls._safe_int(item.get("delta_counts", {}).get("p1_total", 0))),
                -abs(cls._safe_int(item.get("delta_counts", {}).get("total", 0))),
                str(item.get("file", "")).lower(),
            )
        )
        return file_diffs

    @staticmethod
    def _merge_analysis_diff_message(primary: str, secondary: str) -> str:
        normalized_primary = str(primary or "").strip()
        normalized_secondary = str(secondary or "").strip()
        if normalized_primary and normalized_secondary:
            return f"{normalized_primary} ({normalized_secondary})"
        return normalized_primary or normalized_secondary

    def _resolve_latest_analysis_diff(self) -> Dict[str, Any]:
        collection = self._load_recent_analysis_runs(limit=2)
        runs = collection.get("runs", []) if isinstance(collection, dict) else []
        warnings = list(collection.get("warnings", []) or []) if isinstance(collection, dict) else []
        invalid_run_count = self._safe_int(collection.get("invalid_run_count", 0)) if isinstance(collection, dict) else 0
        if len(runs) < 2:
            return {
                "available": False,
                "message": "비교 가능한 최근 2회 분석 결과가 없음",
                "latest": self._public_analysis_run(runs[0]) if runs else None,
                "previous": None,
                "delta": {"summary": {}},
                "file_diffs": [],
                "message": self._merge_analysis_diff_message(
                    "비교 가능한 최근 2회 분석 결과가 없음",
                    str(collection.get("message", "") or "") if isinstance(collection, dict) else "",
                ),
                "warnings": warnings,
                "invalid_run_count": invalid_run_count,
            }
        return self._build_analysis_diff_payload(runs[0], runs[1], warnings=warnings, invalid_run_count=invalid_run_count)

    def _build_analysis_diff_payload(
        self,
        latest: Dict[str, Any],
        previous: Dict[str, Any],
        warnings: Optional[List[str]] = None,
        invalid_run_count: int = 0,
    ) -> Dict[str, Any]:
        return {
            "available": True,
            "message": str((warnings or [""])[0] or ""),
            "latest": self._public_analysis_run(latest),
            "previous": self._public_analysis_run(previous),
            "delta": {"summary": self._compute_analysis_summary_delta(latest, previous)},
            "file_diffs": self._compute_analysis_file_diffs(latest, previous),
            "warnings": list(warnings or []),
            "invalid_run_count": self._safe_int(invalid_run_count),
        }

    def _resolve_analysis_diff_runs(self, limit: int = 10) -> Dict[str, Any]:
        collection = self._load_recent_analysis_runs(limit=max(1, int(limit or 10)))
        runs = collection.get("runs", []) if isinstance(collection, dict) else []
        return {
            "available": bool(runs),
            "generated_at_ms": self._epoch_ms(),
            "runs": [self._public_analysis_run(run) for run in runs],
            "message": str(collection.get("message", "") or "") if isinstance(collection, dict) else "",
            "warnings": list(collection.get("warnings", []) or []) if isinstance(collection, dict) else [],
            "invalid_run_count": self._safe_int(collection.get("invalid_run_count", 0)) if isinstance(collection, dict) else 0,
        }

    def _resolve_selected_analysis_diff(self, latest_key: str, previous_key: str) -> Dict[str, Any]:
        normalized_latest = str(latest_key or "").strip()
        normalized_previous = str(previous_key or "").strip()
        if not normalized_latest or not normalized_previous:
            raise ValueError("latest and previous must be non-empty")
        if normalized_latest == normalized_previous:
            raise ValueError("latest and previous must be different runs")

        collection = self._load_recent_analysis_runs(limit=50)
        runs = collection.get("runs", []) if isinstance(collection, dict) else []
        run_map = {
            str(run.get("timestamp", "") or ""): run
            for run in runs
        }
        latest = run_map.get(normalized_latest)
        previous = run_map.get(normalized_previous)
        if latest is None:
            raise FileNotFoundError(f"analysis run not found: {normalized_latest}")
        if previous is None:
            raise FileNotFoundError(f"analysis run not found: {normalized_previous}")
        return self._build_analysis_diff_payload(
            latest,
            previous,
            warnings=list(collection.get("warnings", []) or []) if isinstance(collection, dict) else [],
            invalid_run_count=self._safe_int(collection.get("invalid_run_count", 0)) if isinstance(collection, dict) else 0,
        )

    @staticmethod
    def _public_analysis_run(run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "output_dir": str(run.get("output_dir", "") or ""),
            "timestamp": str(run.get("timestamp", "") or ""),
            "request_id": str(run.get("request_id", "") or ""),
            "summary": run.get("summary", {}) if isinstance(run.get("summary"), dict) else {},
            "report_paths": run.get("report_paths", {}) if isinstance(run.get("report_paths"), dict) else {},
        }
