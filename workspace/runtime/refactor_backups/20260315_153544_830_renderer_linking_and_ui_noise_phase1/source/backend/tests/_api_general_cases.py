from ._api_integration_test_base import *
from ._api_integration_test_base import _require_openpyxl


class ApiGeneralCasesMixin:
    def test_get_api_files(self):
        status, payload = self._request("GET", "/api/files")
        self.assertEqual(status, 200)
        names = [item["name"] for item in payload["files"]]
        self.assertIn("sample.ctl", names)

    def test_app_uses_configured_defer_excel_reports_default(self):
        self.assertTrue(self.app.defer_excel_reports_default)

    def test_config_representative_rules_are_detected_by_checker(self):
        cases = {
            "PERF-SETMULTIVALUE-ADOPT-01": {
                "code": 'main() {\n setValue("obj1","enabled",false);\n setValue("obj2","enabled",false);\n }',
                "file_type": "Server",
            },
            "PERF-GETMULTIVALUE-ADOPT-01": {
                "code": 'main() {\n bool b1; bool b2;\n getValue("obj1","enabled",b1);\n getValue("obj2","enabled",b2);\n }',
                "file_type": "Server",
            },
            "PERF-DPSET-BATCH-01": {
                "code": 'main() {\n for (int i=0;i<10;i++) {\n  dpSet("A.B.C", 1);\n  dpSet("A.B.D", 2);\n }\n }',
                "file_type": "Server",
            },
            "PERF-DPGET-BATCH-01": {
                "code": 'main() {\n int x; int y;\n dpGet("A.B.C", x);\n dpGet("A.B.D", y);\n }',
                "file_type": "Server",
            },
            "ACTIVE-01": {
                "code": 'main() {\n dpSet("A.B.C", 1);\n }',
                "file_type": "Server",
            },
            "EXC-DP-01": {
                "code": 'main() {\n dpSet("A.B.C", 1);\n dpGet("A.B.D", x);\n }',
                "file_type": "Server",
            },
            "EXC-TRY-01": {
                "code": 'main() {\n dpSet("A.B.C", 1);\n dpGet("A.B.D", x);\n }',
                "file_type": "Server",
            },
            "STYLE-IDX-01": {
                "code": 'main() {\n string parts[10];\n string a = parts[2];\n string b = parts[3];\n string c = parts[4];\n }',
                "file_type": "Server",
            },
            "HARD-03": {
                "code": 'main() {\n float a = 0.01;\n float b = 0.001;\n }',
                "file_type": "Server",
            },
        }

        for rule_id, case in cases.items():
            with self.subTest(rule_id=rule_id):
                found = self._analyze_rule_ids_for_code(case["code"], file_type=case["file_type"])
                self.assertIn(rule_id, found)

    def test_temp_rule_config_precompiles_regex_and_preserves_order(self):
        self._install_temp_rule_config(
            [
                {
                    "rule_id": "REG-B",
                    "item": "regex-b",
                    "enabled": True,
                    "order": 20,
                    "detector": {"kind": "regex", "pattern": r"delay\s*\("},
                    "finding": {"severity": "Warning", "message": "delay match"},
                },
                {
                    "rule_id": "REG-A",
                    "item": "regex-a",
                    "enabled": True,
                    "order": 10,
                    "detector": {"kind": "regex", "pattern": r"dpSet\s*\("},
                    "finding": {"severity": "Warning", "message": "dpSet match"},
                },
            ]
        )
        found = self._analyze_rule_ids_for_code('main() { dpSet("A.B.C", 1); delay(1); }', file_type="Server")
        self.assertEqual(found[:2], ["REG-A", "REG-B"])

        prepared_rules = self.app.checker.p1_rule_defs
        self.assertEqual([row.get("rule_id") for row in prepared_rules[:2]], ["REG-A", "REG-B"])
        compiled = prepared_rules[0].get("detector", {}).get("_compiled_regex")
        self.assertIsInstance(compiled, re.Pattern)

    def test_invalid_regex_is_fail_soft_at_load_time_only(self):
        with mock.patch("builtins.print") as mocked_print:
            self._install_temp_rule_config(
                [
                    {
                        "rule_id": "REG-BAD",
                        "item": "bad-regex",
                        "enabled": True,
                        "order": 5,
                        "detector": {"kind": "regex", "pattern": "("},
                        "finding": {"severity": "Warning", "message": "broken"},
                    },
                    {
                        "rule_id": "REG-GOOD",
                        "item": "good-regex",
                        "enabled": True,
                        "order": 10,
                        "detector": {"kind": "regex", "pattern": r"dpSet\s*\("},
                        "finding": {"severity": "Warning", "message": "dpSet match"},
                    },
                ]
            )
            load_messages = [
                str(call.args[0])
                for call in mocked_print.call_args_list
                if call.args and "Invalid regex in p1_rule_defs" in str(call.args[0])
            ]
            self.assertEqual(len(load_messages), 1)

            found_first = self._analyze_rule_ids_for_code('main() { dpSet("A.B.C", 1); }', file_type="Server")
            found_second = self._analyze_rule_ids_for_code('main() { dpSet("A.B.C", 1); }', file_type="Server")

            runtime_messages = [
                str(call.args[0])
                for call in mocked_print.call_args_list
                if call.args and "Invalid regex in p1_rule_defs" in str(call.args[0])
            ]
            self.assertEqual(len(runtime_messages), 1)
            self.assertIn("REG-GOOD", found_first)
            self.assertEqual(found_first, found_second)

    def test_get_api_health_deps(self):
        status, payload = self._request("GET", "/api/health/deps")
        self.assertEqual(status, 200)
        self.assertIn("status", payload)
        self.assertIn(payload["status"], {"ok", "degraded"})
        self.assertIn("dependencies", payload)
        deps = payload["dependencies"]
        self.assertIn("openpyxl", deps)
        self.assertIn("ctrlppcheck", deps)
        self.assertIn("playwright", deps)
        self.assertIn("capabilities", payload)
        self.assertIn("summary", payload)
        self.assertIn("ready_capabilities", payload["summary"])
        self.assertIn("total_capabilities", payload["summary"])

    def test_get_api_health_deps_ctrlpp_missing_in_test_env(self):
        status, payload = self._request("GET", "/api/health/deps")
        self.assertEqual(status, 200)
        ctrlpp = payload.get("dependencies", {}).get("ctrlppcheck", {})
        self.assertFalse(bool(ctrlpp.get("available", True)))
        self.assertEqual(str(ctrlpp.get("binary_path", "")), "")

    def test_get_api_rules_health_returns_summary_payload(self):
        status, payload = self._request("GET", "/api/rules/health")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        self.assertIn(payload.get("status"), {"ok", "degraded"})
        self.assertIn("rules", payload)
        self.assertIn("dependencies", payload)
        rules = payload.get("rules", {})
        self.assertEqual(int(rules.get("p1_total", 0)), len(self.app.checker.p1_rule_defs))
        self.assertEqual(int(rules.get("p1_enabled", 0)), len([row for row in self.app.checker.p1_rule_defs if bool(row.get("enabled", True))]))
        self.assertIn("detector_counts", rules)
        self.assertIn("file_type_counts", rules)
        self.assertIn("regex_count", rules)
        self.assertIn("composite_count", rules)
        self.assertIn("line_repeat_count", rules)
        self.assertIn("openpyxl", payload.get("dependencies", {}))
        self.assertIn("ctrlppcheck", payload.get("dependencies", {}))
        self.assertIn("playwright", payload.get("dependencies", {}))

    def test_get_api_rules_health_reports_degraded_message_when_optional_missing(self):
        status, payload = self._request("GET", "/api/rules/health")
        self.assertEqual(status, 200)
        self.assertEqual(str(payload.get("status", "")), "degraded")
        self.assertTrue(str(payload.get("message", "")))
        deps = payload.get("dependencies", {})
        self.assertFalse(bool((deps.get("ctrlppcheck", {}) or {}).get("available", True)))

    def test_get_api_rules_list_returns_rule_rows(self):
        self._install_temp_rule_config(
            [
                {
                    "id": "cfg-test-01",
                    "order": 10,
                    "enabled": True,
                    "file_types": ["Client"],
                    "rule_id": "TEST-01",
                    "item": "테스트 규칙 1",
                    "detector": {"kind": "regex"},
                    "finding": {"severity": "Warning", "message": "message-1"},
                },
                {
                    "id": "cfg-test-02",
                    "order": 20,
                    "enabled": False,
                    "file_types": ["Server"],
                    "rule_id": "TEST-02",
                    "item": "테스트 규칙 2",
                    "detector": {"kind": "composite"},
                    "finding": {"severity": "Critical", "message": "message-2"},
                },
            ],
            parsed_rows=[{"type": "Client"}, {"type": "Server"}],
        )

        status, payload = self._request("GET", "/api/rules/list")
        self.assertEqual(status, 200)
        rows = payload.get("rules", [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].get("id"), "cfg-test-01")
        self.assertTrue(bool(rows[0].get("enabled")))
        self.assertEqual(rows[1].get("detector_kind"), "composite")

    def test_post_api_rules_update_persists_and_reloads(self):
        config_dir = self._install_temp_rule_config(
            [
                {
                    "id": "cfg-test-01",
                    "order": 10,
                    "enabled": True,
                    "file_types": ["Client"],
                    "rule_id": "TEST-01",
                    "item": "테스트 규칙 1",
                    "detector": {"kind": "regex", "pattern": "DebugN"},
                    "finding": {"severity": "Warning", "message": "message-1"},
                }
            ]
        )

        status, payload = self._request("POST", "/api/rules/update", {"updates": [{"id": "cfg-test-01", "enabled": False}]})
        self.assertEqual(status, 200)
        self.assertEqual(int(payload.get("updated_count", 0)), 1)
        self.assertTrue(bool((payload.get("reload", {}) or {}).get("reloaded", False)))

        with open(os.path.join(config_dir, "p1_rule_defs.json"), "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertFalse(bool(saved[0].get("enabled", True)))

        checker_row = next(row for row in self.app.checker.p1_rule_defs if row.get("id") == "cfg-test-01")
        self.assertFalse(bool(checker_row.get("enabled", True)))

    def test_post_api_rules_update_rejects_unknown_rule_id(self):
        self._install_temp_rule_config(
            [
                {
                    "id": "cfg-test-01",
                    "order": 10,
                    "enabled": True,
                    "file_types": ["Client"],
                    "rule_id": "TEST-01",
                    "item": "테스트 규칙 1",
                    "detector": {"kind": "regex", "pattern": "DebugN"},
                    "finding": {"severity": "Warning", "message": "message-1"},
                }
            ]
        )

        status, payload = self._request("POST", "/api/rules/update", {"updates": [{"id": "missing-rule", "enabled": False}]})
        self.assertEqual(status, 400)
        self.assertIn("Unknown rule id", str(payload.get("error", "")))

    def test_post_api_rules_create_adds_rule(self):
        self._install_temp_rule_config([])
        rule = {
            "id": "cfg-created-01",
            "order": 10,
            "enabled": True,
            "file_types": ["Client", "Server"],
            "rule_id": "CREATED-01",
            "item": "생성 규칙",
            "detector": {"kind": "regex", "pattern": "DebugN", "flags": ["MULTILINE"]},
            "finding": {"severity": "Warning", "message": "created"},
            "meta": {"owner": "test"},
        }
        status, payload = self._request("POST", "/api/rules/create", {"rule": rule})
        self.assertEqual(status, 200)
        self.assertEqual(str((payload.get("rule", {}) or {}).get("id", "")), "cfg-created-01")
        exported_status, exported = self._request("GET", "/api/rules/export")
        self.assertEqual(exported_status, 200)
        self.assertEqual(len(exported.get("rules", [])), 1)

    def test_post_api_rules_replace_updates_full_rule(self):
        self._install_temp_rule_config(
            [
                {
                    "id": "cfg-test-01",
                    "order": 10,
                    "enabled": True,
                    "file_types": ["Client"],
                    "rule_id": "TEST-01",
                    "item": "테스트 규칙 1",
                    "detector": {"kind": "regex", "pattern": "DebugN"},
                    "finding": {"severity": "Warning", "message": "message-1"},
                }
            ]
        )
        replacement = {
            "id": "cfg-test-01",
            "order": 20,
            "enabled": False,
            "file_types": ["Server"],
            "rule_id": "TEST-02",
            "item": "변경된 규칙",
            "detector": {"kind": "legacy_handler", "handler": "check_unused_variables"},
            "finding": {"severity": "Low", "message": "changed"},
            "meta": {"tag": "updated"},
        }
        status, payload = self._request("POST", "/api/rules/replace", {"rule": replacement})
        self.assertEqual(status, 200)
        rule = payload.get("rule", {}) or {}
        self.assertEqual(str(rule.get("rule_id", "")), "TEST-02")
        self.assertFalse(bool(rule.get("enabled", True)))

    def test_post_api_rules_delete_removes_rule(self):
        self._install_temp_rule_config(
            [
                {
                    "id": "cfg-test-01",
                    "order": 10,
                    "enabled": True,
                    "file_types": ["Client"],
                    "rule_id": "TEST-01",
                    "item": "테스트 규칙 1",
                    "detector": {"kind": "regex", "pattern": "DebugN"},
                    "finding": {"severity": "Warning", "message": "message-1"},
                }
            ]
        )
        status, payload = self._request("POST", "/api/rules/delete", {"id": "cfg-test-01"})
        self.assertEqual(status, 200)
        self.assertEqual(str(payload.get("deleted_id", "")), "cfg-test-01")
        exported_status, exported = self._request("GET", "/api/rules/export")
        self.assertEqual(exported_status, 200)
        self.assertEqual(len(exported.get("rules", [])), 0)

    def test_post_api_rules_import_merge_replaces_existing_and_adds_new(self):
        self._install_temp_rule_config(
            [
                {
                    "id": "cfg-test-01",
                    "order": 10,
                    "enabled": True,
                    "file_types": ["Client"],
                    "rule_id": "TEST-01",
                    "item": "테스트 규칙 1",
                    "detector": {"kind": "regex", "pattern": "DebugN"},
                    "finding": {"severity": "Warning", "message": "message-1"},
                }
            ]
        )
        status, payload = self._request(
            "POST",
            "/api/rules/import",
            {
                "mode": "merge",
                "rules": [
                    {
                        "id": "cfg-test-01",
                        "order": 11,
                        "enabled": False,
                        "file_types": ["Server"],
                        "rule_id": "TEST-01-UPDATED",
                        "item": "테스트 규칙 수정",
                        "detector": {"kind": "legacy_handler", "handler": "check_unused_variables"},
                        "finding": {"severity": "Low", "message": "updated"},
                    },
                    {
                        "id": "cfg-test-02",
                        "order": 20,
                        "enabled": True,
                        "file_types": ["Client", "Server"],
                        "rule_id": "TEST-02",
                        "item": "신규 규칙",
                        "detector": {"kind": "composite", "op": "complexity"},
                        "finding": {"severity": "Medium", "message": "new"},
                    },
                ],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(int(payload.get("imported_count", 0)), 2)
        exported_status, exported = self._request("GET", "/api/rules/export")
        self.assertEqual(exported_status, 200)
        rows = exported.get("rules", [])
        self.assertEqual(len(rows), 2)
        updated = next(row for row in rows if row.get("id") == "cfg-test-01")
        self.assertEqual(str(updated.get("rule_id", "")), "TEST-01-UPDATED")

    def test_get_api_verification_latest_returns_most_recent_summary(self):
        older = os.path.join(self.data_dir, "verification_summary_20260101_010101.json")
        newer = os.path.join(self.data_dir, "verification_summary_20260101_020202.json")
        with open(older, "w", encoding="utf-8") as f:
            json.dump({"summary": {"passed": 1, "failed": 0}}, f)
        with open(newer, "w", encoding="utf-8") as f:
            json.dump({"summary": {"passed": 2, "failed": 1}}, f)
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))

        status, payload = self._request("GET", "/api/verification/latest")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("summary", {}).get("passed"), 2)
        self.assertEqual(str(payload.get("source_file", "")), "verification_summary_20260101_020202.json")

    def test_get_api_verification_latest_without_summary_returns_404(self):
        status, payload = self._request("GET", "/api/verification/latest")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_get_api_operations_latest_returns_recent_compare_payload(self):
        benchmark_dir = os.path.join(self.data_dir, "benchmark_results")
        integration_dir = os.path.join(self.data_dir, "integration_results")
        os.makedirs(benchmark_dir, exist_ok=True)
        os.makedirs(integration_dir, exist_ok=True)
        self.app.operational_result_dirs = {
            "ui_benchmark": benchmark_dir,
            "ui_real_smoke": integration_dir,
            "ctrlpp_integration": integration_dir,
        }

        older_benchmark = os.path.join(benchmark_dir, "ui_benchmark_20260101_010101.json")
        newer_benchmark = os.path.join(benchmark_dir, "ui_benchmark_20260101_020202.json")
        with open(older_benchmark, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "summary": {
                        "analyzeUiMs": {"avg": 240},
                        "codeJumpMs": {"avg": 50},
                    },
                    "threshold_failures": [],
                    "finished_at": "2026-01-01T01:01:01Z",
                },
                f,
            )
        with open(newer_benchmark, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "summary": {
                        "analyzeUiMs": {"avg": 210},
                        "codeJumpMs": {"avg": 40},
                    },
                    "threshold_failures": [],
                    "finished_at": "2026-01-01T02:02:02Z",
                },
                f,
            )
        os.utime(older_benchmark, (1000, 1000))
        os.utime(newer_benchmark, (2000, 2000))

        ui_smoke = os.path.join(integration_dir, "ui_real_smoke_20260101_020202.json")
        with open(ui_smoke, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ok": True,
                    "backend": {"selected_target_file": "BenchmarkP1Fixture.ctl"},
                    "run": {"elapsed_ms": 777, "afterRun": {"rows": 6, "totalIssues": "6"}},
                    "finished_at": "2026-01-01T02:02:02Z",
                },
                f,
            )

        ctrlpp_smoke = os.path.join(integration_dir, "ctrlpp_integration_20260101_020202.json")
        with open(ctrlpp_smoke, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "status": "passed",
                    "binary": {"exists": True},
                    "direct_smoke": {"elapsed_ms": 28, "finding_count": 2, "infra_error": False},
                    "finished_at": "2026-01-01T02:02:02Z",
                },
                f,
            )

        status, payload = self._request("GET", "/api/operations/latest")
        self.assertEqual(status, 200)
        categories = payload.get("categories", {})
        self.assertIn("ui_benchmark", categories)
        self.assertIn("ui_real_smoke", categories)
        self.assertIn("ctrlpp_integration", categories)
        ui_benchmark = categories.get("ui_benchmark", {})
        self.assertTrue(bool(ui_benchmark.get("available", False)))
        self.assertEqual(ui_benchmark.get("latest", {}).get("source_file"), "ui_benchmark_20260101_020202.json")
        self.assertEqual(ui_benchmark.get("previous", {}).get("source_file"), "ui_benchmark_20260101_010101.json")
        self.assertEqual(ui_benchmark.get("delta", {}).get("analyze_ui_avg_ms"), -30.0)
        self.assertEqual(categories.get("ui_real_smoke", {}).get("latest", {}).get("selected_file"), "BenchmarkP1Fixture.ctl")
        self.assertEqual(categories.get("ctrlpp_integration", {}).get("latest", {}).get("finding_count"), 2)

    def test_get_api_operations_latest_returns_unavailable_when_missing(self):
        benchmark_dir = os.path.join(self.data_dir, "benchmark_results")
        integration_dir = os.path.join(self.data_dir, "integration_results")
        os.makedirs(benchmark_dir, exist_ok=True)
        os.makedirs(integration_dir, exist_ok=True)
        self.app.operational_result_dirs = {
            "ui_benchmark": benchmark_dir,
            "ui_real_smoke": integration_dir,
            "ctrlpp_integration": integration_dir,
        }

        status, payload = self._request("GET", "/api/operations/latest")
        self.assertEqual(status, 200)
        categories = payload.get("categories", {})
        self.assertFalse(bool(categories.get("ui_benchmark", {}).get("available", True)))
        self.assertIsNone(categories.get("ui_benchmark", {}).get("latest"))

    def test_get_api_operations_latest_reads_utf8_sig_artifacts(self):
        benchmark_dir = os.path.join(self.data_dir, "benchmark_results")
        integration_dir = os.path.join(self.data_dir, "integration_results")
        os.makedirs(benchmark_dir, exist_ok=True)
        os.makedirs(integration_dir, exist_ok=True)
        self.app.operational_result_dirs = {
            "ui_benchmark": benchmark_dir,
            "ui_real_smoke": integration_dir,
            "ctrlpp_integration": integration_dir,
        }

        benchmark_path = os.path.join(benchmark_dir, "ui_benchmark_20260101_020202.json")
        with open(benchmark_path, "w", encoding="utf-8-sig") as f:
            json.dump(
                {
                    "summary": {
                        "analyzeUiMs": {"avg": 210},
                        "codeJumpMs": {"avg": 40},
                    },
                    "threshold_failures": [],
                    "finished_at": "2026-01-01T02:02:02Z",
                },
                f,
                ensure_ascii=False,
            )

        ui_smoke = os.path.join(integration_dir, "ui_real_smoke_20260101_020202.json")
        with open(ui_smoke, "w", encoding="utf-8-sig") as f:
            json.dump(
                {
                    "ok": True,
                    "backend": {"selected_target_file": "GoldenTime.ctl"},
                    "run": {"elapsed_ms": 777, "afterRun": {"rows": 6, "totalIssues": "6"}},
                    "finished_at": "2026-01-01T02:02:02Z",
                },
                f,
                ensure_ascii=False,
            )

        status, payload = self._request("GET", "/api/operations/latest")
        self.assertEqual(status, 200)
        categories = payload.get("categories", {})
        self.assertEqual(categories.get("ui_benchmark", {}).get("latest", {}).get("source_file"), "ui_benchmark_20260101_020202.json")
        self.assertEqual(categories.get("ui_real_smoke", {}).get("latest", {}).get("selected_file"), "GoldenTime.ctl")

    def test_get_api_analysis_diff_latest_returns_recent_compare_payload(self):
        older_dir = os.path.join(self.data_dir, "20260101_010101")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(older_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(older_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "request_id": "old-run",
                    "summary": {"total": 3, "critical": 1, "warning": 2, "info": 0, "p1_total": 2, "p2_total": 1, "p3_total": 0},
                    "report_paths": {"html": "combined_analysis_report.html", "excel": [], "reviewed_txt": []},
                    "file_summaries": [
                        {"file": "sample.ctl", "p1_total": 2, "p2_total": 1, "p3_total": 0, "critical": 1, "warning": 2, "info": 0, "total": 3}
                    ],
                },
                f,
            )
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "request_id": "new-run",
                    "summary": {"total": 5, "critical": 1, "warning": 3, "info": 1, "p1_total": 3, "p2_total": 1, "p3_total": 1},
                    "report_paths": {"html": "combined_analysis_report.html", "excel": [], "reviewed_txt": []},
                    "file_summaries": [
                        {"file": "sample.ctl", "p1_total": 3, "p2_total": 1, "p3_total": 0, "critical": 1, "warning": 3, "info": 0, "total": 4},
                        {"file": "other.ctl", "p1_total": 0, "p2_total": 0, "p3_total": 1, "critical": 0, "warning": 0, "info": 1, "total": 1},
                    ],
                },
                f,
            )
        os.utime(older_dir, (1000, 1000))
        os.utime(newer_dir, (2000, 2000))

        status, payload = self._request("GET", "/api/analysis-diff/latest")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        self.assertEqual(payload.get("latest", {}).get("request_id"), "new-run")
        self.assertEqual(payload.get("previous", {}).get("request_id"), "old-run")
        self.assertEqual(payload.get("delta", {}).get("summary", {}).get("total"), 2)
        file_diffs = payload.get("file_diffs", [])
        changed_sample = next(item for item in file_diffs if item.get("file") == "sample.ctl")
        added_other = next(item for item in file_diffs if item.get("file") == "other.ctl")
        self.assertEqual(changed_sample.get("status"), "changed")
        self.assertEqual(changed_sample.get("delta_counts", {}).get("p1_total"), 1)
        self.assertEqual(added_other.get("status"), "added")

    def test_get_api_analysis_diff_latest_unavailable_when_missing_runs(self):
        status, payload = self._request("GET", "/api/analysis-diff/latest")
        self.assertEqual(status, 200)
        self.assertFalse(bool(payload.get("available", True)))
        self.assertIn("비교 가능한 최근 2회", str(payload.get("message", "")))

    def test_get_api_analysis_diff_runs_returns_recent_run_list(self):
        older_dir = os.path.join(self.data_dir, "20260101_010101")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(older_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(older_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "old-run", "summary": {"total": 1}, "report_paths": {}, "file_summaries": []}, f)
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "new-run", "summary": {"total": 2}, "report_paths": {}, "file_summaries": []}, f)
        os.utime(older_dir, (1000, 1000))
        os.utime(newer_dir, (2000, 2000))

        status, payload = self._request("GET", "/api/analysis-diff/runs")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        runs = payload.get("runs", [])
        self.assertEqual(len(runs), 2)
        self.assertEqual(str(runs[0].get("timestamp", "")), "20260101_020202")
        self.assertEqual(str(runs[1].get("timestamp", "")), "20260101_010101")

    def test_get_api_analysis_diff_runs_skips_invalid_historical_runs(self):
        invalid_dir = os.path.join(self.data_dir, "20260101_030303")
        older_dir = os.path.join(self.data_dir, "20260101_010101")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(invalid_dir, exist_ok=True)
        os.makedirs(older_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(older_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "old-run", "summary": {"total": 1}, "report_paths": {}, "file_summaries": []}, f)
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "new-run", "summary": {"total": 2}, "report_paths": {}, "file_summaries": []}, f)
        os.utime(older_dir, (1000, 1000))
        os.utime(newer_dir, (2000, 2000))
        os.utime(invalid_dir, (3000, 3000))

        status, payload = self._request("GET", "/api/analysis-diff/runs")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        runs = payload.get("runs", [])
        self.assertEqual(len(runs), 2)
        self.assertEqual(str(runs[0].get("timestamp", "")), "20260101_020202")
        self.assertEqual(str(runs[1].get("timestamp", "")), "20260101_010101")
        self.assertEqual(int(payload.get("invalid_run_count", 0)), 1)
        self.assertTrue(bool(payload.get("warnings")))
        self.assertIn("analysis summary not found", str(payload.get("warnings", [""])[0]))

    def test_get_api_analysis_diff_compare_returns_selected_pair(self):
        older_dir = os.path.join(self.data_dir, "20260101_010101")
        middle_dir = os.path.join(self.data_dir, "20260101_015959")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(older_dir, exist_ok=True)
        os.makedirs(middle_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(older_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "old-run", "summary": {"total": 1, "p1_total": 1}, "report_paths": {}, "file_summaries": [{"file": "sample.ctl", "p1_total": 1, "p2_total": 0, "p3_total": 0, "critical": 0, "warning": 1, "info": 0, "total": 1}]}, f)
        with open(os.path.join(middle_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "mid-run", "summary": {"total": 4, "p1_total": 3}, "report_paths": {}, "file_summaries": [{"file": "sample.ctl", "p1_total": 3, "p2_total": 1, "p3_total": 0, "critical": 1, "warning": 2, "info": 0, "total": 4}]}, f)
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "new-run", "summary": {"total": 5, "p1_total": 3}, "report_paths": {}, "file_summaries": [{"file": "sample.ctl", "p1_total": 3, "p2_total": 1, "p3_total": 1, "critical": 1, "warning": 2, "info": 1, "total": 5}]}, f)
        os.utime(older_dir, (1000, 1000))
        os.utime(middle_dir, (1500, 1500))
        os.utime(newer_dir, (2000, 2000))

        status, payload = self._request("GET", "/api/analysis-diff/compare?latest=20260101_015959&previous=20260101_010101")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        self.assertEqual(str(payload.get("latest", {}).get("request_id", "")), "mid-run")
        self.assertEqual(str(payload.get("previous", {}).get("request_id", "")), "old-run")
        self.assertEqual(int(payload.get("delta", {}).get("summary", {}).get("total", 0)), 3)

    def test_get_api_analysis_diff_compare_rejects_same_run(self):
        status, payload = self._request("GET", "/api/analysis-diff/compare?latest=20260101_020202&previous=20260101_020202")
        self.assertEqual(status, 400)
        self.assertIn("different runs", str(payload.get("error", "")))

    def test_get_api_analysis_diff_latest_skips_invalid_historical_runs(self):
        invalid_dir = os.path.join(self.data_dir, "20260101_030303")
        older_dir = os.path.join(self.data_dir, "20260101_010101")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(invalid_dir, exist_ok=True)
        os.makedirs(older_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(older_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "old-run", "summary": {"total": 1}, "report_paths": {}, "file_summaries": []}, f)
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "new-run", "summary": {"total": 2}, "report_paths": {}, "file_summaries": []}, f)
        os.utime(older_dir, (1000, 1000))
        os.utime(newer_dir, (2000, 2000))
        os.utime(invalid_dir, (3000, 3000))

        status, payload = self._request("GET", "/api/analysis-diff/latest")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        self.assertEqual(str(payload.get("latest", {}).get("request_id", "")), "new-run")
        self.assertEqual(str(payload.get("previous", {}).get("request_id", "")), "old-run")
        self.assertEqual(int(payload.get("invalid_run_count", 0)), 1)
        self.assertTrue(bool(payload.get("warnings")))
        self.assertIn("analysis summary not found", str(payload.get("warnings", [""])[0]))

    def test_get_api_analysis_diff_latest_unavailable_when_only_one_valid_run_exists(self):
        invalid_dir = os.path.join(self.data_dir, "20260101_010101")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(invalid_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"summary": {"total": 1}, "file_summaries": []}, f)
        os.utime(invalid_dir, (1000, 1000))
        os.utime(newer_dir, (2000, 2000))

        status, payload = self._request("GET", "/api/analysis-diff/latest")
        self.assertEqual(status, 200)
        self.assertFalse(bool(payload.get("available", True)))
        self.assertIn("비교 가능한 최근 2회", str(payload.get("message", "")))
        self.assertEqual(int(payload.get("invalid_run_count", 0)), 1)
        self.assertTrue(bool(payload.get("warnings")))

    def test_get_api_analysis_diff_compare_ignores_invalid_runs_between_selected_valid_runs(self):
        older_dir = os.path.join(self.data_dir, "20260101_010101")
        invalid_dir = os.path.join(self.data_dir, "20260101_015959")
        newer_dir = os.path.join(self.data_dir, "20260101_020202")
        os.makedirs(older_dir, exist_ok=True)
        os.makedirs(invalid_dir, exist_ok=True)
        os.makedirs(newer_dir, exist_ok=True)
        with open(os.path.join(older_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "old-run", "summary": {"total": 1}, "report_paths": {}, "file_summaries": []}, f)
        with open(os.path.join(newer_dir, "analysis_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"request_id": "new-run", "summary": {"total": 4}, "report_paths": {}, "file_summaries": []}, f)
        os.utime(older_dir, (1000, 1000))
        os.utime(invalid_dir, (1500, 1500))
        os.utime(newer_dir, (2000, 2000))

        status, payload = self._request("GET", "/api/analysis-diff/compare?latest=20260101_020202&previous=20260101_010101")
        self.assertEqual(status, 200)
        self.assertTrue(bool(payload.get("available", False)))
        self.assertEqual(int(payload.get("delta", {}).get("summary", {}).get("total", 0)), 3)
        self.assertEqual(int(payload.get("invalid_run_count", 0)), 1)
        self.assertTrue(bool(payload.get("warnings")))


    def test_post_api_analyze_selected_files(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"mode": "Static", "selected_files": ["sample.ctl"]},
        )
        self.assertEqual(status, 200)
        self.assertIn("summary", payload)
        self.assertIn("violations", payload)
        self.assertIn("report_paths", payload)
        self.assertIn("p1_total", payload["summary"])
        self.assertIn("p2_total", payload["summary"])
        self.assertIn("p3_total", payload["summary"])
        self.assertIn("verification_level", payload["summary"])
        self.assertIn(payload["summary"]["verification_level"], {"CORE_ONLY", "CORE+REPORT"})
        self.assertIn("optional_dependencies", payload.get("metrics", {}))
        self.assertIn("openpyxl", payload.get("metrics", {}).get("optional_dependencies", {}))
        self.assertIn("metrics", payload)
        self.assertIn("timings_ms", payload["metrics"])
        self.assertIn("total", payload["metrics"]["timings_ms"])
        self.assertIn("convert", payload["metrics"]["timings_ms"])
        self.assertIn("report_text", payload["metrics"]["timings_ms"])
        self.assertIn("excel_total", payload["metrics"]["timings_ms"])
        self.assertIn("llm_calls", payload["metrics"])
        self.assertIn("convert_cache", payload["metrics"])
        output_dir = str(payload.get("output_dir", "") or "")
        summary_path = os.path.join(output_dir, "analysis_summary.json")
        self.assertTrue(os.path.exists(summary_path))
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_payload = json.load(f)
        self.assertIn("summary", summary_payload)
        self.assertIn("file_summaries", summary_payload)
        self.assertEqual(str(summary_payload.get("output_dir", "")), output_dir)
        self.assertEqual(str(summary_payload.get("request_id", "")), str(payload.get("request_id", "")))

    def test_post_api_analyze_summary_snapshot_write_is_fail_soft(self):
        with mock.patch.object(DirectoryAnalysisPipeline, "_write_analysis_summary_file", side_effect=OSError("disk full")):
            status, payload = self._request(
                "POST",
                "/api/analyze",
                {"mode": "Static", "selected_files": ["sample.ctl"]},
            )
        self.assertEqual(status, 200)
        self.assertIn("summary", payload)
        self.assertIn("output_dir", payload)

    def test_post_api_analyze_uses_configured_defer_excel_default_when_omitted(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"mode": "Static", "selected_files": ["sample.ctl"]},
        )
        self.assertEqual(status, 200)
        self.assertIn("report_jobs", payload)
        excel_jobs = (payload.get("report_jobs") or {}).get("excel") or {}
        self.assertGreaterEqual(len(excel_jobs.get("jobs", [])), 1)

    def test_get_api_ai_models_returns_fail_soft_payload(self):
        self.app.list_ai_models = lambda: {
            "provider": "ollama",
            "available": False,
            "models": [],
            "default_model": "qwen2.5-coder:3b",
            "error": "Ollama not reachable",
        }
        status, payload = self._request("GET", "/api/ai/models")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("provider"), "ollama")
        self.assertFalse(bool(payload.get("available")))
        self.assertEqual(payload.get("models"), [])
        self.assertIn("error", payload)

    def test_get_api_ai_models_typed_error_returns_error_code(self):
        def failing_list_models():
            raise ReviewerTransportError("Ollama not reachable")

        self.app.ai_tool.list_models = failing_list_models
        status, payload = self._request("GET", "/api/ai/models")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("provider"), "ollama")
        self.assertFalse(bool(payload.get("available")))
        self.assertEqual(payload.get("models"), [])
        self.assertEqual(payload.get("error_code"), "AI_REVIEW_TRANSPORT_ERROR")
        self.assertIn("Ollama not reachable", str(payload.get("error", "")))

    def test_llm_reviewer_get_json_timeout_raises_typed_error(self):
        reviewer = LLMReviewer({"provider": "ollama", "timeout_sec": 1, "fail_soft": True}, base_dir=self.data_dir)

        with mock.patch(
            "core.llm_reviewer.urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            with self.assertRaises(ReviewerTimeoutError):
                reviewer._get_json("http://127.0.0.1:11434/api/tags")

    def test_llm_reviewer_get_json_invalid_payload_raises_typed_error(self):
        reviewer = LLMReviewer({"provider": "ollama", "timeout_sec": 1, "fail_soft": True}, base_dir=self.data_dir)

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"not-json"

        with mock.patch("core.llm_reviewer.urllib.request.urlopen", return_value=_FakeResponse()):
            with self.assertRaises(ReviewerResponseError):
                reviewer._get_json("http://127.0.0.1:11434/api/tags")

    def test_llm_reviewer_generate_review_fail_soft_for_unsupported_provider(self):
        reviewer = LLMReviewer({"provider": "unsupported", "fail_soft": True}, base_dir=self.data_dir)
        review = reviewer.generate_review("main() {}", [{"rule_id": "R1", "message": "issue"}])
        self.assertIn("AI live review failed: Unsupported AI provider", review)

    def test_post_api_analyze_live_ai_model_override_is_forwarded(self):
        self._force_single_internal_violation()
        seen = {"model_name": ""}

        def fake_live_review(_code, _violations, **kwargs):
            seen["model_name"] = str(kwargs.get("model_name", "") or "")
            return "LIVE REVIEW"

        self.app.ai_tool.generate_review = fake_live_review
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "selected_files": ["sample.ctl"],
                "enable_live_ai": True,
                "ai_model_name": "llama3.1:8b",
                "mode": "AI 보조",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(seen["model_name"], "llama3.1:8b")
        self.assertGreaterEqual(len(payload.get("violations", {}).get("P3", [])), 1)

    def test_post_api_analyze_external_file_path_succeeds(self):
        external_dir = os.path.join(self.data_dir, "external")
        os.makedirs(external_dir, exist_ok=True)
        external_path = os.path.join(external_dir, "outside.ctl")
        with open(external_path, "w", encoding="utf-8") as f:
            f.write('main() { dpSet("EXT.A", 1); }')

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "mode": "Static",
                "selected_files": [],
                "input_sources": [{"type": "file_path", "value": external_path}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual((payload.get("metrics") or {}).get("file_count"), 1)

        output_dir = str(payload.get("output_dir", "") or "")
        query = urllib.parse.urlencode(
            {"name": external_path, "prefer_source": "true", "output_dir": output_dir}
        )
        viewer_status, viewer_payload = self._request("GET", f"/api/file-content?{query}")
        self.assertEqual(viewer_status, 200)
        self.assertEqual(os.path.normpath(str(viewer_payload.get("resolved_path", ""))), os.path.normpath(external_path))
        self.assertEqual(str(viewer_payload.get("resolved_name", "")), "outside.ctl")

    def test_post_api_analyze_external_folder_path_succeeds(self):
        external_dir = os.path.join(self.data_dir, "folder-input")
        nested_dir = os.path.join(external_dir, "nested")
        os.makedirs(nested_dir, exist_ok=True)
        with open(os.path.join(nested_dir, "folder_target.ctl"), "w", encoding="utf-8") as f:
            f.write('main() { dpSet("FOLDER.A", 1); }')
        with open(os.path.join(nested_dir, "ignored.md"), "w", encoding="utf-8") as f:
            f.write("# ignore")

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "mode": "Static",
                "selected_files": [],
                "input_sources": [{"type": "folder_path", "value": external_dir}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual((payload.get("metrics") or {}).get("file_count"), 1)

    def test_post_api_analyze_external_duplicate_basenames_generate_distinct_artifacts(self):
        external_dir = os.path.join(self.data_dir, "dup-folder")
        dir_a = os.path.join(external_dir, "a")
        dir_b = os.path.join(external_dir, "b")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        file_a = os.path.join(dir_a, "same.ctl")
        file_b = os.path.join(dir_b, "same.ctl")
        with open(file_a, "w", encoding="utf-8") as f:
            f.write('main() { dpSet("DUP.A", 1); }')
        with open(file_b, "w", encoding="utf-8") as f:
            f.write('main() { dpSet("DUP.B", 2); }')

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "mode": "Static",
                "selected_files": [],
                "input_sources": [{"type": "folder_path", "value": external_dir}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual((payload.get("metrics") or {}).get("file_count"), 2)
        report_paths = payload.get("report_paths", {}) or {}
        reviewed_txt = list(report_paths.get("reviewed_txt", []) or [])
        excel_files = list(report_paths.get("excel", []) or [])
        self.assertEqual(len(reviewed_txt), 2)
        self.assertEqual(len(set(reviewed_txt)), 2)
        self.assertTrue(all(name.endswith("_REVIEWED.txt") for name in reviewed_txt))
        if len(excel_files) < 2:
            flush_status, flush_payload = self._request(
                "POST",
                "/api/report/excel",
                {
                    "session_id": payload.get("output_dir", ""),
                    "wait": True,
                    "timeout_sec": 30,
                },
            )
            self.assertEqual(flush_status, 200)
            excel_files = list(((flush_payload.get("report_paths") or {}).get("excel", [])) or [])
        self.assertEqual(len(excel_files), 2)
        self.assertEqual(len(set(excel_files)), 2)

    def test_post_api_analyze_invalid_input_source_returns_400(self):
        missing_path = os.path.join(self.data_dir, "missing-dir", "missing.ctl")
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "mode": "Static",
                "selected_files": [],
                "input_sources": [{"type": "file_path", "value": missing_path}],
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("Input file not found", str(payload.get("error", "")))

    def test_post_api_analyze_empty_input_folder_returns_400(self):
        empty_dir = os.path.join(self.data_dir, "empty-folder")
        os.makedirs(empty_dir, exist_ok=True)
        with open(os.path.join(empty_dir, "ignored.log"), "w", encoding="utf-8") as f:
            f.write("ignore")

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "mode": "Static",
                "selected_files": [],
                "input_sources": [{"type": "folder_path", "value": empty_dir}],
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("supported review files", str(payload.get("error", "")))

    def test_post_api_analyze_start_returns_job(self):
        status, payload = self._request(
            "POST",
            "/api/analyze/start",
            {"mode": "Static", "selected_files": ["sample.ctl"]},
        )
        self.assertEqual(status, 202)
        self.assertTrue(str(payload.get("job_id", "")))
        self.assertEqual(str(payload.get("status", "")), "queued")
        self.assertIn("progress", payload)
        self.assertIn("poll_interval_ms", payload)
        job_id = str(payload.get("job_id", ""))
        self.assertTrue(job_id)
        for _ in range(60):
            poll_status, poll_payload = self._request("GET", f"/api/analyze/status?job_id={urllib.parse.quote(job_id)}")
            self.assertEqual(poll_status, 200)
            if str(poll_payload.get("status", "")) in ("completed", "failed"):
                break
            time.sleep(0.05)

    def test_get_api_analyze_status_unknown_job_returns_404(self):
        status, payload = self._request("GET", "/api/analyze/status?job_id=missing-job-id")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_post_api_analyze_start_and_poll_until_completed(self):
        status, payload = self._request(
            "POST",
            "/api/analyze/start",
            {"mode": "Static", "selected_files": ["sample.ctl"]},
        )
        self.assertEqual(status, 202)
        job_id = str(payload.get("job_id", ""))
        self.assertTrue(job_id)

        final_payload = {}
        for _ in range(60):
            s, p = self._request("GET", f"/api/analyze/status?job_id={urllib.parse.quote(job_id)}")
            self.assertEqual(s, 200)
            final_payload = p
            if str(p.get("status", "")) in ("completed", "failed"):
                break
            time.sleep(0.05)

        self.assertEqual(str(final_payload.get("status", "")), "completed")
        self.assertIn("result", final_payload)
        result = final_payload.get("result", {})
        self.assertIn("summary", result)
        self.assertIn("violations", result)

    def test_post_api_analyze_start_invalid_selection_eventually_fails(self):
        status, payload = self._request(
            "POST",
            "/api/analyze/start",
            {"mode": "Static", "selected_files": ["missing.ctl"]},
        )
        self.assertEqual(status, 202)
        job_id = str(payload.get("job_id", ""))
        self.assertTrue(job_id)

        final_payload = {}
        for _ in range(60):
            s, p = self._request("GET", f"/api/analyze/status?job_id={urllib.parse.quote(job_id)}")
            self.assertEqual(s, 200)
            final_payload = p
            if str(p.get("status", "")) in ("completed", "failed"):
                break
            time.sleep(0.05)

        self.assertEqual(str(final_payload.get("status", "")), "failed")
        self.assertIn("error", final_payload)

    def test_post_api_analyze_p1_violations_include_file_field(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"mode": "Static", "selected_files": ["sample.ctl"]},
        )
        self.assertEqual(status, 200)
        p1_groups = payload.get("violations", {}).get("P1", [])
        self.assertGreaterEqual(len(p1_groups), 1)
        first_group = p1_groups[0]
        violations = first_group.get("violations", [])
        self.assertGreaterEqual(len(violations), 1)
        self.assertEqual(violations[0].get("file"), "sample.ctl")

    def test_post_api_analyze_invalid_file_returns_400(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"mode": "Static", "selected_files": ["missing.ctl"]},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_post_api_analyze_default_mode_ai_assist(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"]},
        )
        self.assertEqual(status, 200)
        self.assertIn("summary", payload)
        self.assertIn("violations", payload)

    def test_post_api_analyze_live_ai_toggle_type_validation(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": "yes"},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertIn("enable_live_ai", payload["error"])

    def test_post_api_analyze_ai_with_context_type_validation(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "ai_with_context": "yes"},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertIn("ai_with_context", payload["error"])

    def test_post_api_analyze_selected_files_type_validation(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": 1},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertIn("selected_files", payload["error"])

    def test_post_api_analyze_allow_raw_txt_type_validation(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["raw_input.txt"], "allow_raw_txt": "false"},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertIn("allow_raw_txt", payload["error"])

    def test_post_api_analyze_live_ai_on_generates_p3(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: "LIVE REVIEW"

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertGreaterEqual(len(p3), 1)
        self.assertEqual(p3[0].get("source"), "live")
        self.assertEqual(p3[0].get("review"), "LIVE REVIEW")
        self.assertEqual(p3[0].get("parent_source"), "P1")
        self.assertTrue(p3[0].get("parent_issue_id"))
        statuses = payload.get("ai_review_statuses", [])
        self.assertTrue(any(item.get("status") == "generated" and item.get("reason") == "generated" for item in statuses))

    def test_post_api_analyze_live_ai_timeout_records_parent_status(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: "AI live review failed: timed out"

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("violations", {}).get("P3", []), [])
        statuses = payload.get("ai_review_statuses", [])
        self.assertTrue(any(item.get("status") == "failed" and item.get("reason") == "timeout" for item in statuses))

    def test_post_api_analyze_live_ai_passes_focus_snippet(self):
        self._force_single_internal_violation()
        seen = {"focus_snippet": "", "issue_context": None, "todo_prompt_context": None}

        def fake_live_review(_code, _violations, **kwargs):
            seen["focus_snippet"] = str(kwargs.get("focus_snippet", "") or "")
            seen["issue_context"] = kwargs.get("issue_context")
            seen["todo_prompt_context"] = kwargs.get("todo_prompt_context")
            return "LIVE REVIEW"

        self.app.ai_tool.generate_review = fake_live_review
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(payload.get("violations", {}).get("P3", [])), 1)
        self.assertTrue(seen["focus_snippet"])
        self.assertIn("dpSet", seen["focus_snippet"])
        self.assertIn("// lines", seen["focus_snippet"])
        self.assertTrue(isinstance(seen["issue_context"], dict))
        self.assertIn("primary", seen["issue_context"])
        self.assertTrue(isinstance(seen["todo_prompt_context"], dict))
        self.assertIn("todo_comment", seen["todo_prompt_context"])
        self.assertIn("snippet", seen["todo_prompt_context"])
        self.assertEqual(str(seen["todo_prompt_context"].get("todo_comment", "")), "test violation")

    def test_post_api_ai_review_generate_single_issue_success(self):
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: "LIVE REVIEW\n```ctl\nsetMultiValue(\"A.B\", vals);\n```"
        violation = {
            "source": "P1",
            "issue_id": "P1-PERF-SETMULTIVALUE-ADOPT-01-1",
            "rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
            "file": "sample.ctl",
            "file_path": os.path.join(self.data_dir, "sample.ctl"),
            "line": 1,
            "object": "sample.ctl",
            "event": "Global",
            "severity": "Warning",
            "message": "multi setValue detected",
        }
        status, payload = self._request(
            "POST",
            "/api/ai-review/generate",
            {"violation": violation, "enable_live_ai": True, "ai_with_context": False},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("available"))
        self.assertEqual((payload.get("review_item") or {}).get("source"), "live")
        self.assertEqual((payload.get("status_item") or {}).get("status"), "generated")
        self.assertEqual((payload.get("status_item") or {}).get("reason"), "generated")

    def test_post_api_ai_review_generate_timeout_reason_mapping(self):
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: "AI live review failed: timed out"
        violation = {
            "source": "P1",
            "issue_id": "P1-R1-1",
            "rule_id": "R1",
            "file": "sample.ctl",
            "file_path": os.path.join(self.data_dir, "sample.ctl"),
            "line": 1,
            "object": "sample.ctl",
            "event": "Global",
            "severity": "Warning",
            "message": "test violation",
        }
        status, payload = self._request(
            "POST",
            "/api/ai-review/generate",
            {"violation": violation, "enable_live_ai": True},
        )
        self.assertEqual(status, 200)
        self.assertFalse(payload.get("available"))
        self.assertEqual((payload.get("status_item") or {}).get("status"), "failed")
        self.assertEqual((payload.get("status_item") or {}).get("reason"), "timeout")

    def test_post_api_ai_review_generate_domain_hint_warning_when_keywords_missing(self):
        calls = {"count": 0}

        def fake_live_review(*_args, **_kwargs):
            calls["count"] += 1
            return "LIVE REVIEW WITHOUT EXPECTED KEYWORDS"

        self.app.ai_tool.generate_review = fake_live_review
        violation = {
            "source": "P1",
            "issue_id": "P1-PERF-SETMULTIVALUE-ADOPT-01-1",
            "rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
            "file": "sample.ctl",
            "file_path": os.path.join(self.data_dir, "sample.ctl"),
            "line": 1,
            "object": "sample.ctl",
            "event": "Global",
            "severity": "Warning",
            "message": "multi setValue detected",
        }
        status, payload = self._request(
            "POST",
            "/api/ai-review/generate",
            {"violation": violation, "enable_live_ai": True},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("available"))
        self.assertGreaterEqual(calls["count"], 2)
        detail = str((payload.get("status_item") or {}).get("detail", "") or "")
        self.assertIn("도메인 가이드 검증 경고", detail)

    def test_post_api_ai_review_generate_domain_hint_warning_when_grouped_code_example_missing(self):
        calls = {"count": 0}

        def fake_live_review(*_args, **_kwargs):
            calls["count"] += 1
            return "LIVE REVIEW\nsetMultiValue should be used for grouped update."

        self.app.ai_tool.generate_review = fake_live_review
        violation = {
            "source": "P1",
            "issue_id": "P1-PERF-SETMULTIVALUE-ADOPT-01-2",
            "rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
            "file": "sample.ctl",
            "file_path": os.path.join(self.data_dir, "sample.ctl"),
            "line": 1,
            "object": "sample.ctl",
            "event": "Global",
            "severity": "Warning",
            "message": "multi setValue detected",
        }
        status, payload = self._request(
            "POST",
            "/api/ai-review/generate",
            {"violation": violation, "enable_live_ai": True},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("available"))
        self.assertGreaterEqual(calls["count"], 2)
        detail = str((payload.get("status_item") or {}).get("detail", "") or "")
        self.assertIn("묶음 처리 코드 예시", detail)

    def test_domain_hint_accepts_grouped_dpset_and_dpget_examples(self):
        grouped_dpset_review = (
            "```ctl\n"
            "dpSet(\"System1:Obj1.enabled\", false,\n"
            "      \"System1:Obj2.enabled\", false);\n"
            "```"
        )
        grouped_dpget_review = (
            "```ctl\n"
            "dpGet(\"System1:Obj1.enabled\", bObj1,\n"
            "      \"System1:Obj2.enabled\", bObj2);\n"
            "```"
        )

        self.assertTrue(self.app._review_has_domain_hint("PERF-DPSET-BATCH-01", grouped_dpset_review))
        self.assertTrue(self.app._review_has_domain_hint("PERF-DPGET-BATCH-01", grouped_dpget_review))

    def test_llm_reviewer_todo_compact_prompt_omits_full_code(self):
        reviewer = self.app.ai_tool
        reviewer.prompt_mode = "todo_compact"
        prompt = reviewer._build_prompt(
            'main() { dpSet("A.B.C", 1);\n DebugN("full-code");\n }',
            [{"rule_id": "R1", "line": 1, "message": "test violation"}],
            issue_context={
                "primary": {
                    "source": "P1",
                    "issue_id": "P1-R1-1",
                    "rule_id": "R1",
                    "line": 1,
                    "file": "sample.ctl",
                    "object": "sample.ctl",
                    "event": "Global",
                    "severity": "Warning",
                    "message": "test violation",
                },
                "linked_findings": [],
            },
            focus_snippet='// lines 1-2\n   1: main() { dpSet("A.B.C", 1);\n   2: DebugN("focus");',
            todo_prompt_context={
                "todo_comment": "test violation",
                "snippet": '// lines 1-2\n   1: main() { dpSet("A.B.C", 1);\n   2: DebugN("focus");',
            },
        )
        self.assertIn("[TODO Comment]", prompt)
        self.assertIn("[Focused Code Snippet]", prompt)
        self.assertNotIn("[Full Code]", prompt)
        self.assertNotIn('DebugN("full-code")', prompt)

    def test_post_api_analyze_live_ai_generates_parent_linked_p3_per_issue(self):
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
            {
                "object": "sample.ctl",
                "event": "Global",
                "violations": [
                    {
                        "issue_id": "P1-A-1",
                        "rule_id": "R-A",
                        "rule_item": "a",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 1,
                        "message": "v1",
                    }
                ],
            },
            {
                "object": "sample.ctl",
                "event": "EvtA",
                "violations": [
                    {
                        "issue_id": "P1-B-1",
                        "rule_id": "R-B",
                        "rule_item": "b",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 1,
                        "message": "v2",
                    }
                ],
            },
        ]
        calls = {"count": 0}

        def fake_live_review(_code, violations, **kwargs):
            calls["count"] += 1
            return f"LIVE REVIEW BATCH size={len(violations)} snippet={bool(kwargs.get('focus_snippet'))}"

        original_batch = self.app.live_ai_batch_groups_per_file
        self.app.live_ai_batch_groups_per_file = 2
        self.app.ai_tool.generate_review = fake_live_review
        try:
            status, payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
        finally:
            self.app.live_ai_batch_groups_per_file = original_batch
        self.assertEqual(status, 200)
        self.assertEqual(calls["count"], 2)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertEqual(len(p3), 2)
        self.assertTrue(all(r.get("source") == "live" for r in p3))
        self.assertTrue(all(r.get("parent_source") == "P1" for r in p3))
        self.assertEqual((payload.get("metrics") or {}).get("llm_calls"), 2)

    def test_post_api_analyze_live_ai_runs_parent_reviews_concurrently(self):
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
            {
                "object": "sample.ctl",
                "event": "Global",
                "violations": [
                    {
                        "issue_id": "P1-A-1",
                        "rule_id": "R-A",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 1,
                        "message": "v1",
                    },
                    {
                        "issue_id": "P1-B-1",
                        "rule_id": "R-B",
                        "priority_origin": "P1",
                        "severity": "Critical",
                        "line": 2,
                        "message": "v2",
                    },
                ],
            }
        ]
        state = {"active": 0, "peak": 0}
        lock = threading.Lock()

        def fake_live_review(*_args, **_kwargs):
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.05)
            with lock:
                state["active"] -= 1
            return "LIVE REVIEW CONCURRENT"

        original_workers = self.app.live_ai_max_workers
        original_limit = self.app.live_ai_max_parent_reviews_per_file
        original_semaphore = self.app._live_ai_semaphore
        self.app.live_ai_max_workers = 2
        self.app.live_ai_max_parent_reviews_per_file = 2
        self.app._live_ai_semaphore = threading.Semaphore(2)
        self.app.ai_tool.generate_review = fake_live_review
        try:
            status, payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
        finally:
            self.app.live_ai_max_workers = original_workers
            self.app.live_ai_max_parent_reviews_per_file = original_limit
            self.app._live_ai_semaphore = original_semaphore
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(payload.get("violations", {}).get("P3", [])), 2)
        self.assertGreaterEqual(state["peak"], 2)

    def test_post_api_analyze_live_ai_marks_priority_limited_status(self):
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
            {
                "object": "sample.ctl",
                "event": "Global",
                "violations": [
                    {
                        "issue_id": "P1-A-1",
                        "rule_id": "R-A",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 1,
                        "message": "v1",
                    },
                    {
                        "issue_id": "P1-B-1",
                        "rule_id": "R-B",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 30,
                        "message": "v2",
                    },
                ],
            }
        ]
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: "LIVE REVIEW"
        original_limit = self.app.live_ai_max_parent_reviews_per_file
        self.app.live_ai_max_parent_reviews_per_file = 1
        try:
            status, payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
        finally:
            self.app.live_ai_max_parent_reviews_per_file = original_limit
        self.assertEqual(status, 200)
        statuses = payload.get("ai_review_statuses", [])
        self.assertTrue(any(item.get("status") == "skipped" and item.get("reason") == "priority_limited" for item in statuses))

    def test_post_api_analyze_live_ai_generates_p3_for_p2_only_issue(self):
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: []
        self.app.ctrl_tool.run_check = lambda *_args, **_kwargs: [
            {
                "rule_id": "CTRL-RULE-01",
                "line": 12,
                "message": "ctrlpp finding",
                "file": "sample.ctl",
                "source": "CtrlppCheck",
                "priority_origin": "P2",
                "severity": "warning",
            }
        ]
        seen = {"todo_prompt_context": None}

        def fake_live_review(*_args, **_kwargs):
            seen["todo_prompt_context"] = _kwargs.get("todo_prompt_context")
            return "LIVE REVIEW P2"

        self.app.ai_tool.generate_review = fake_live_review

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "enable_ctrlppcheck": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertEqual(len(p3), 1)
        self.assertEqual(p3[0].get("parent_source"), "P2")
        self.assertEqual(p3[0].get("parent_rule_id"), "CTRL-RULE-01")
        self.assertEqual(p3[0].get("review"), "LIVE REVIEW P2")
        self.assertTrue(isinstance(seen["todo_prompt_context"], dict))
        self.assertEqual(str(seen["todo_prompt_context"].get("todo_comment", "")), "ctrlpp finding")

    def test_post_api_analyze_live_ai_ignores_garbled_mode_when_toggle_enabled(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: "LIVE REVIEW"

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI ??"},
        )
        self.assertEqual(status, 200)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertGreaterEqual(len(p3), 1)
        self.assertEqual(p3[0].get("review"), "LIVE REVIEW")

    def test_post_api_analyze_live_ai_skips_info_level_parent_issues(self):
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
            {
                "object": "sample.ctl",
                "event": "Global",
                "violations": [
                    {
                        "issue_id": "P1-INFO-1",
                        "rule_id": "R-INFO",
                        "priority_origin": "P1",
                        "severity": "Info",
                        "line": 1,
                        "message": "info only",
                    },
                    {
                        "issue_id": "P1-WARN-1",
                        "rule_id": "R-WARN",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 2,
                        "message": "warning issue",
                    },
                ],
            }
        ]
        calls = {"count": 0}

        def fake_live_review(*_args, **_kwargs):
            calls["count"] += 1
            return "LIVE REVIEW FILTERED"

        self.app.ai_tool.generate_review = fake_live_review
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(calls["count"], 1)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertEqual(len(p3), 1)
        self.assertEqual(p3[0].get("parent_issue_id"), "P1-WARN-1")
        self.assertEqual((payload.get("metrics") or {}).get("llm_calls"), 1)

    def test_post_api_analyze_live_ai_limits_parent_reviews_per_file(self):
        violations = []
        families = ["PERF", "SAFE", "HARD", "DUP"]
        for idx in range(12):
            violations.append(
                {
                    "issue_id": f"P1-WARN-{idx}",
                    "rule_id": f"{families[idx % len(families)]}-{idx}",
                    "priority_origin": "P1",
                    "severity": "Warning",
                    "line": idx + 1,
                    "message": f"warning {idx}",
                }
            )
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
            {
                "object": "sample.ctl",
                "event": "Global",
                "violations": violations,
            }
        ]
        calls = {"count": 0}

        def fake_live_review(*_args, **_kwargs):
            calls["count"] += 1
            return f"LIVE REVIEW {calls['count']}"

        original_limit = self.app.live_ai_max_parent_reviews_per_file
        self.app.live_ai_max_parent_reviews_per_file = 3
        self.app.ai_tool.generate_review = fake_live_review
        try:
            status, payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
        finally:
            self.app.live_ai_max_parent_reviews_per_file = original_limit
        self.assertEqual(status, 200)
        self.assertEqual(calls["count"], 3)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertEqual(len(p3), 3)
        self.assertEqual((payload.get("metrics") or {}).get("llm_calls"), 3)

    def test_recommended_live_ai_parent_review_limit_can_expand_for_critical_mix(self):
        self.app.live_ai_max_parent_reviews_per_file = 3
        eligible = [
            {"severity": "Critical", "object": "sample.ctl", "event": "Global", "parent_rule_id": "PERF-01"},
            {"severity": "Warning", "object": "sample.ctl", "event": "Global", "parent_rule_id": "SAFE-01"},
            {"severity": "Warning", "object": "other.ctl", "event": "EvtA", "parent_rule_id": "HARD-01"},
        ]
        self.assertEqual(self.app._recommended_live_ai_parent_review_limit(eligible), 3)

    def test_recommended_live_ai_parent_review_limit_stays_small_for_same_hotspot_warnings(self):
        self.app.live_ai_max_parent_reviews_per_file = 3
        eligible = [
            {"severity": "Warning", "object": "sample.ctl", "event": "Global", "parent_rule_id": "PERF-01"},
            {"severity": "Warning", "object": "sample.ctl", "event": "Global", "parent_rule_id": "PERF-02"},
            {"severity": "Warning", "object": "sample.ctl", "event": "Global", "parent_rule_id": "PERF-03"},
        ]
        self.assertEqual(self.app._recommended_live_ai_parent_review_limit(eligible), 2)

    def test_post_api_analyze_defer_excel_reports_and_flush_endpoint(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "selected_files": ["sample.ctl"],
                "mode": "Static",
                "enable_ctrlppcheck": False,
                "enable_live_ai": False,
                "defer_excel_reports": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("report_jobs", payload)
        excel_jobs = (payload.get("report_jobs") or {}).get("excel") or {}
        self.assertGreaterEqual(len(excel_jobs.get("jobs", [])), 1)

        flush_status, flush_payload = self._request(
            "POST",
            "/api/report/excel",
            {
                "session_id": payload.get("output_dir", ""),
                "wait": True,
                "timeout_sec": 30,
            },
        )
        self.assertEqual(flush_status, 200)
        self.assertIn("report_jobs", flush_payload)
        self.assertIn("excel", flush_payload.get("report_paths", {}))
        excel_summary = (flush_payload.get("report_jobs") or {}).get("excel") or {}
        self.assertEqual(excel_summary.get("pending_count"), 0)

    def test_cli_parser_accepts_excel_report_mode_flags(self):
        parser = build_arg_parser()
        deferred = parser.parse_args(["--defer-excel-reports"])
        self.assertTrue(deferred.defer_excel_reports)
        self.assertFalse(deferred.sync_excel_reports)

        sync = parser.parse_args(["--sync-excel-reports"])
        self.assertTrue(sync.sync_excel_reports)
        self.assertFalse(sync.defer_excel_reports)

        with self.assertRaises(SystemExit):
            parser.parse_args(["--defer-excel-reports", "--sync-excel-reports"])

    def test_get_api_report_excel_download_returns_attachment(self):
        _require_openpyxl(self)
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "selected_files": ["sample.ctl"],
                "mode": "Static",
                "enable_ctrlppcheck": False,
                "enable_live_ai": False,
                "defer_excel_reports": True,
            },
        )
        self.assertEqual(status, 200)
        flush_status, flush_payload = self._request(
            "POST",
            "/api/report/excel",
            {
                "session_id": payload.get("output_dir", ""),
                "wait": True,
                "timeout_sec": 30,
            },
        )
        self.assertEqual(flush_status, 200)
        excel_files = list((flush_payload.get("report_paths") or {}).get("excel", []) or [])
        self.assertGreaterEqual(len(excel_files), 1)

        query = urllib.parse.urlencode(
            {"output_dir": flush_payload.get("output_dir", ""), "name": excel_files[0]}
        )
        download_status, body, headers = self._request_raw("GET", f"/api/report/excel/download?{query}")
        self.assertEqual(download_status, 200)
        self.assertGreater(len(body), 0)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            str(headers.get("Content-Type", "")),
        )
        self.assertIn("attachment;", str(headers.get("Content-Disposition", "")))

    def test_get_api_report_excel_download_rejects_path_traversal(self):
        status, payload = self._request(
            "GET",
            "/api/report/excel/download?" + urllib.parse.urlencode(
                {"output_dir": self.data_dir, "name": "../escape.xlsx"}
            ),
        )
        self.assertEqual(status, 400)
        self.assertIn("xlsx file", str(payload.get("error", "")))

    def test_get_api_report_excel_download_returns_404_for_missing_file(self):
        report_dir = os.path.join(self.data_dir, "reports")
        os.makedirs(report_dir, exist_ok=True)
        status, payload = self._request(
            "GET",
            "/api/report/excel/download?" + urllib.parse.urlencode(
                {"output_dir": report_dir, "name": "missing.xlsx"}
            ),
        )
        self.assertEqual(status, 404)
        self.assertIn("Excel report not found", str(payload.get("error", "")))

    def test_post_api_analyze_live_ai_off_hides_p3(self):
        self._force_single_internal_violation()
        self.app.ai_tool.get_mock_review = lambda *_args, **_kwargs: "MOCK REVIEW SHOULD NOT APPEAR"

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertEqual(p3, [])
        self.assertEqual(payload.get("summary", {}).get("p3_total"), 0)

    def test_post_api_analyze_live_ai_fail_soft_keeps_200(self):
        self._force_single_internal_violation()
        self.app.ai_tool.provider = "unsupported-provider"
        self.app.ai_tool.fail_soft = True

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertEqual(p3, [])
        self.assertEqual(payload.get("summary", {}).get("p3_total"), 0)

    def test_post_api_analyze_ai_with_context_live_on_uses_context(self):
        self._force_single_internal_violation()
        calls = {"count": 0}

        def fake_fetch_context():
            calls["count"] += 1
            return {
                "enabled": True,
                "project": {"projectName": "TEST_PROJ"},
                "drivers": [{"name": "CTRL"}],
                "error": None,
            }

        def fake_live_review(_code, _violations, use_context=False, context_payload=None, focus_snippet="", **_kwargs):
            if use_context and isinstance(context_payload, dict) and context_payload.get("enabled"):
                return "LIVE REVIEW WITH CONTEXT"
            return "LIVE REVIEW NO CONTEXT"

        self.app.mcp_tool.fetch_context = fake_fetch_context
        self.app.ai_tool.generate_review = fake_live_review

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "selected_files": ["sample.ctl"],
                "enable_live_ai": True,
                "ai_with_context": True,
                "mode": "AI 보조",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(calls["count"], 1)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertGreaterEqual(len(p3), 1)
        self.assertEqual(p3[0].get("review"), "LIVE REVIEW WITH CONTEXT")

    def test_post_api_analyze_ai_with_context_fail_soft_keeps_200(self):
        self._force_single_internal_violation()

        def failing_fetch_context():
            return {"enabled": False, "project": {}, "drivers": [], "error": "mcp timeout"}

        def fake_live_review(_code, _violations, use_context=False, context_payload=None, focus_snippet="", **_kwargs):
            if use_context and isinstance(context_payload, dict) and not context_payload.get("enabled"):
                return "LIVE REVIEW CONTEXT_FALLBACK"
            return "LIVE REVIEW"

        self.app.mcp_tool.fetch_context = failing_fetch_context
        self.app.ai_tool.generate_review = fake_live_review

        status, payload = self._request(
            "POST",
            "/api/analyze",
            {
                "selected_files": ["sample.ctl"],
                "enable_live_ai": True,
                "ai_with_context": True,
                "mode": "AI 보조",
            },
        )
        self.assertEqual(status, 200)
        p3 = payload.get("violations", {}).get("P3", [])
        self.assertGreaterEqual(len(p3), 1)
        self.assertEqual(p3[0].get("review"), "LIVE REVIEW CONTEXT_FALLBACK")

    def test_post_api_analyze_raw_txt_rejected_without_toggle(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["raw_input.txt"]},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertIn("allow_raw_txt", payload["error"])

    def test_post_api_analyze_raw_txt_allowed_with_toggle(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["raw_input.txt"], "allow_raw_txt": True},
        )
        self.assertEqual(status, 200)
        self.assertIn("summary", payload)

    def test_post_api_analyze_ctrlpp_toggle_off(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_ctrlppcheck": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("violations", {}).get("P2", []), [])
        summary = payload.get("summary", {})
        self.assertFalse(bool(summary.get("ctrlpp_preflight_attempted", False)))
        self.assertFalse(bool(summary.get("ctrlpp_preflight_ready", False)))

    def test_post_api_analyze_ctrlpp_toggle_on_missing_binary(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_ctrlppcheck": True, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p2 = payload.get("violations", {}).get("P2", [])
        self.assertGreaterEqual(len(p2), 1)
        self.assertTrue(any(v.get("source") == "CtrlppCheck" for v in p2))
        summary = payload.get("summary", {})
        self.assertFalse(bool(summary.get("ctrlpp_preflight_ready", False)))
        self.assertTrue("ctrlpp" in str(summary.get("ctrlpp_preflight_message", "")).lower())

    def test_post_api_analyze_ctrlpp_toggle_type_validation(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_ctrlppcheck": "yes"},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertIn("enable_ctrlppcheck", payload["error"])

    def test_api_ctrlpp_toggle_on_triggers_autoinstall_path(self):
        self.app.ctrl_tool.auto_install_on_missing = True
        calls = {"count": 0}

        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"

        self.app.ctrl_tool.ensure_installed = fake_ensure
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_ctrlppcheck": True, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(calls["count"], 1)
        p2 = payload.get("violations", {}).get("P2", [])
        self.assertTrue(any("install failed" in (v.get("message", "").lower()) for v in p2))
        summary = payload.get("summary", {})
        self.assertTrue(bool(summary.get("ctrlpp_preflight_attempted", False)))
        self.assertFalse(bool(summary.get("ctrlpp_preflight_ready", False)))

    def test_api_ctrlpp_toggle_on_install_failure_returns_200_with_p2_info(self):
        self.app.ctrl_tool.auto_install_on_missing = True

        def failing_ensure():
            raise CtrlppDownloadError("CtrlppCheck download failed: mocked offline")

        self.app.ctrl_tool.ensure_installed = failing_ensure
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_ctrlppcheck": True, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p2 = payload.get("violations", {}).get("P2", [])
        self.assertGreaterEqual(len(p2), 1)
        self.assertTrue(any("download failed" in (v.get("message", "").lower()) for v in p2))
        summary = payload.get("summary", {})
        self.assertTrue(bool(summary.get("ctrlpp_preflight_attempted", False)))
        self.assertFalse(bool(summary.get("ctrlpp_preflight_ready", False)))
        self.assertEqual(summary.get("ctrlpp_preflight_error_code"), "CTRLPPCHECK_DOWNLOAD_ERROR")

    def test_api_ctrlpp_preflight_skips_without_ctl_target(self):
        self.app.ctrl_tool.auto_install_on_missing = True
        calls = {"count": 0}

        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"

        self.app.ctrl_tool.ensure_installed = fake_ensure
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["raw_input.txt"], "allow_raw_txt": True, "enable_ctrlppcheck": True, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(calls["count"], 0)
        summary = payload.get("summary", {})
        self.assertFalse(bool(summary.get("ctrlpp_preflight_attempted", False)))

    def test_api_analyze_ctl_filters_to_server_rules(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["server_loop.ctl"], "mode": "Static"},
        )
        self.assertEqual(status, 200)
        compact_items = [item.replace(" ", "") for item in self._extract_rule_items(payload)]
        self.assertTrue(any("Loop문내" in item and "처리조건" in item for item in compact_items))

    def test_api_analyze_raw_txt_filters_to_client_rules(self):
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["raw_loop.txt"], "allow_raw_txt": True, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        compact_items = [item.replace(" ", "") for item in self._extract_rule_items(payload)]
        self.assertFalse(any("Loop문내" in item and "처리조건" in item for item in compact_items))

    def test_post_api_analyze_file_failure_exposes_errors_in_payload(self):
        def failing_analyze_file(*_args, **_kwargs):
            raise RuntimeError("forced failure for test")

        self.app.analyze_file = failing_analyze_file
        status, payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "mode": "Static", "enable_ctrlppcheck": False, "enable_live_ai": False},
        )
        self.assertEqual(status, 500)
        self.assertIn("errors", payload)
        self.assertGreaterEqual(len(payload["errors"]), 1)
        self.assertEqual(payload["errors"][0]["file"], "sample.ctl")
        self.assertIn("forced failure for test", payload["errors"][0]["error"])
        self.assertEqual(payload.get("summary", {}).get("failed_file_count"), 1)
        self.assertEqual(payload.get("summary", {}).get("successful_file_count"), 0)

    def test_post_api_analyze_partial_file_failure_returns_207(self):
        original_analyze_file = self.app.analyze_file

        def partially_failing_analyze_file(target, *args, **kwargs):
            if os.path.basename(str(target)) == "server_loop.ctl":
                raise RuntimeError("forced partial failure")
            return original_analyze_file(target, *args, **kwargs)

        self.app.analyze_file = partially_failing_analyze_file
        try:
            status, payload = self._request(
                "POST",
                "/api/analyze",
                {
                    "selected_files": ["sample.ctl", "server_loop.ctl"],
                    "mode": "Static",
                    "enable_ctrlppcheck": False,
                    "enable_live_ai": False,
                },
            )
        finally:
            self.app.analyze_file = original_analyze_file

        self.assertEqual(status, 207)
        self.assertEqual(payload.get("summary", {}).get("requested_file_count"), 2)
        self.assertEqual(payload.get("summary", {}).get("successful_file_count"), 1)
        self.assertEqual(payload.get("summary", {}).get("failed_file_count"), 1)
        self.assertGreaterEqual(len(payload.get("errors", [])), 1)
        self.assertEqual(payload["errors"][0].get("file"), "server_loop.ctl")

    def test_concurrent_analyze_requests_are_isolated(self):
        payload_a = {
            "selected_files": ["sample.ctl"],
            "mode": "Static",
            "enable_ctrlppcheck": False,
            "enable_live_ai": False,
        }
        payload_b = {
            "selected_files": ["server_loop.ctl"],
            "mode": "Static",
            "enable_ctrlppcheck": False,
            "enable_live_ai": False,
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(self._request, "POST", "/api/analyze", payload_a)
            future_b = pool.submit(self._request, "POST", "/api/analyze", payload_b)
            status_a, resp_a = future_a.result(timeout=60)
            status_b, resp_b = future_b.result(timeout=60)

        self.assertEqual(status_a, 200)
        self.assertEqual(status_b, 200)

        output_a = os.path.normpath(resp_a.get("output_dir", ""))
        output_b = os.path.normpath(resp_b.get("output_dir", ""))
        self.assertTrue(os.path.isdir(output_a))
        self.assertTrue(os.path.isdir(output_b))
        self.assertNotEqual(output_a, output_b)

        reviewed_a = set(resp_a.get("report_paths", {}).get("reviewed_txt", []))
        reviewed_b = set(resp_b.get("report_paths", {}).get("reviewed_txt", []))
        self.assertIn("sample_REVIEWED.txt", reviewed_a)
        self.assertIn("server_loop_REVIEWED.txt", reviewed_b)
        self.assertNotIn("server_loop_REVIEWED.txt", reviewed_a)
        self.assertNotIn("sample_REVIEWED.txt", reviewed_b)

    def test_concurrent_analyze_no_report_path_cross_over(self):
        payload_a = {
            "selected_files": ["sample.ctl"],
            "mode": "Static",
            "enable_ctrlppcheck": False,
            "enable_live_ai": False,
        }
        payload_b = {
            "selected_files": ["server_loop.ctl"],
            "mode": "Static",
            "enable_ctrlppcheck": False,
            "enable_live_ai": False,
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(self._request, "POST", "/api/analyze", payload_a)
            future_b = pool.submit(self._request, "POST", "/api/analyze", payload_b)
            status_a, resp_a = future_a.result(timeout=60)
            status_b, resp_b = future_b.result(timeout=60)

        self.assertEqual(status_a, 200)
        self.assertEqual(status_b, 200)

        output_a = os.path.normpath(resp_a.get("output_dir", ""))
        output_b = os.path.normpath(resp_b.get("output_dir", ""))
        excel_a = resp_a.get("report_paths", {}).get("excel", [])
        excel_b = resp_b.get("report_paths", {}).get("excel", [])
        reviewed_a = resp_a.get("report_paths", {}).get("reviewed_txt", [])
        reviewed_b = resp_b.get("report_paths", {}).get("reviewed_txt", [])

        for name in excel_a + reviewed_a:
            self.assertTrue(os.path.exists(os.path.join(output_a, name)))
            self.assertFalse(os.path.exists(os.path.join(output_b, name)))

        for name in excel_b + reviewed_b:
            self.assertTrue(os.path.exists(os.path.join(output_b, name)))
            self.assertFalse(os.path.exists(os.path.join(output_a, name)))

    def test_concurrent_analyze_requests_can_overlap_during_analysis(self):
        first_started = threading.Event()
        second_started = threading.Event()
        release_first = threading.Event()

        original_analyze_file = self.app.analyze_file

        def fake_analyze_file(*args, **kwargs):
            target = args[0] if args else kwargs.get("target", "")
            name = os.path.basename(str(target))
            if name == "sample.ctl":
                first_started.set()
                if not release_first.wait(timeout=5):
                    raise RuntimeError("timeout waiting for release_first")
            elif name == "server_loop.ctl":
                second_started.set()
            return {
                "file": name,
                "internal_violations": [],
                "global_violations": [],
                "ai_reviews": [],
            }

        self.app.analyze_file = fake_analyze_file
        try:
            payload_a = {
                "selected_files": ["sample.ctl"],
                "mode": "Static",
                "enable_ctrlppcheck": False,
                "enable_live_ai": False,
            }
            payload_b = {
                "selected_files": ["server_loop.ctl"],
                "mode": "Static",
                "enable_ctrlppcheck": False,
                "enable_live_ai": False,
            }

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                future_a = pool.submit(self._request, "POST", "/api/analyze", payload_a)
                self.assertTrue(first_started.wait(timeout=5))
                future_b = pool.submit(self._request, "POST", "/api/analyze", payload_b)
                self.assertTrue(
                    second_started.wait(timeout=2),
                    "Second request should reach analyze_file while first request is still blocked",
                )
                release_first.set()
                status_a, _resp_a = future_a.result(timeout=30)
                status_b, _resp_b = future_b.result(timeout=30)

            self.assertEqual(status_a, 200)
            self.assertEqual(status_b, 200)
        finally:
            self.app.analyze_file = original_analyze_file
            release_first.set()


