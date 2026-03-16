"""Rule core cases for system verification."""

try:
    from ._system_verification_base import *  # noqa: F403
except ImportError:
    from _system_verification_base import *  # noqa: F403


class SystemVerificationRuleCoreMixin:
    def test_config_existence(self):
        rules_path = os.path.join(self.config_dir, "parsed_rules.json")
        self.assertTrue(os.path.exists(rules_path), f"parsed_rules.json not found at {rules_path}")
    
        with open(rules_path, "r", encoding="utf-8-sig") as f:
            rules = json.load(f)
            self.assertIsInstance(rules, list, "Rules should be a list")
            self.assertGreater(len(rules), 0, "Rules should not be empty")

    def test_pnl_parser_complex(self):
        complex_pnl = '''
    6 13
    "btnStart"
    ""
    1 10 10 E E E 1 E 1 E N "_Transparent" E N "_Transparent" E E
    "Clicked" 1
    "main()\n{\n    if(1) {\n        dpSet(\\"a\\", 1);\n    }\n}" 0
    
    6 14
    "rect"
    ""
    1 20 20 E E E 1 E 1 E N "_Transparent" E N "_Transparent" E E
    "Initialize" 1
    "main()\n{\n    // Nested\n}" 0
    '''
        parser = PnlParser()
        result = parser.normalize_pnl(complex_pnl)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "btnStart")
        self.assertEqual(result[0]["events"][0]["event"], "Clicked")
        self.assertEqual(result[1]["name"], "rect")

    def test_heuristic_checker_sqli(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = 'sprintf(sql, "SELECT * FROM users WHERE name = \'%s\'", input);'
        violations = checker.check_sql_injection(code)
        self.assertTrue(any(v["rule_id"] == "SEC-01" for v in violations), "SQL Injection not detected")

    def test_configured_composite_patterns_detect_with_standard_escape(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        rows = {str(r.get("rule_id") or r.get("id")): r for r in checker.p1_rule_defs if isinstance(r, dict)}
        samples = {
            "SEC-01": 'main(){ sprintf(sql, "SELECT * FROM t WHERE a = %s", input); }',
            "DB-ERR-01": 'main(){ dpQuery("SELECT * FROM T", result); }',
            "EXC-DP-01": 'main(){ dpSet("A.B.C", 1); }',
        }
        for rid, code in samples.items():
            rule = rows[rid]
            analysis = checker._remove_comments(code)
            findings = checker._run_composite_rule(
                rule,
                code=code,
                analysis_code=analysis,
                event_name="Global",
                base_line=1,
                anchor_line=checker._first_function_line(analysis),
            )
            found_ids = {str(x.get("rule_id", "")) for x in findings}
            self.assertIn(rid, found_ids, f"configured composite did not detect {rid}")

    def test_configured_composite_patterns_detect_with_double_escape(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        rows = {str(r.get("rule_id") or r.get("id")): r for r in checker.p1_rule_defs if isinstance(r, dict)}
        samples = {
            "SEC-01": {
                "code": 'main(){ sprintf(sql, "SELECT * FROM t WHERE a = %s", input); }',
                "patch_key": "sql_keywords_pattern",
            },
            "DB-ERR-01": {
                "code": 'main(){ dpQuery("SELECT * FROM T", result); }',
                "patch_key": "query_call_pattern",
            },
            "EXC-DP-01": {
                "code": 'main(){ dpSet("A.B.C", 1); }',
                "patch_key": "dp_call_pattern",
            },
        }
        for rid, meta in samples.items():
            base_rule = dict(rows[rid])
            detector = dict(base_rule.get("detector") or {})
            key = str(meta["patch_key"])
            detector[key] = str(detector.get(key, "")).replace("\\", "\\\\")
            base_rule["detector"] = detector
            code = str(meta["code"])
            analysis = checker._remove_comments(code)
            findings = checker._run_composite_rule(
                base_rule,
                code=code,
                analysis_code=analysis,
                event_name="Global",
                base_line=1,
                anchor_line=checker._first_function_line(analysis),
            )
            found_ids = {str(x.get("rule_id", "")) for x in findings}
            self.assertIn(rid, found_ids, f"double-escaped detector did not detect {rid}")

    def test_heuristic_checker_unused_var(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            int used = 1;
            int unused = 2;
            DebugN(used);
        }
        """
        violations = checker.check_unused_variables(code)
        self.assertTrue(any("unused" in v["message"] for v in violations), "Unused variable not detected")

    def test_exc_dp_rule_no_false_positive_with_try_catch(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            try {
                dpSet("A.B.C", 1);
            } catch {
                DebugTN(getLastError());
            }
        }
        """
        violations = checker.check_dp_function_exception(code)
        self.assertFalse(any(v["rule_id"] == "EXC-DP-01" for v in violations))

    def test_exc_dp_rule_detects_missing_error_handling(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            dpSet("A.B.C", 1);
        }
        """
        violations = checker.check_dp_function_exception(code)
        self.assertTrue(any(v["rule_id"] == "EXC-DP-01" for v in violations))

    def test_perf_dpset_chain_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            dpSet("A.B.C", 1);
            dpSet("A.B.D", 2);
        }
        """
        violations = checker.check_consecutive_dpset(code)
        self.assertTrue(any(v["rule_id"] == "PERF-DPSET-CHAIN" for v in violations))

    def test_perf_dpset_chain_detects_multiple_clusters_in_one_function(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            dpSet("A.B.C", 1);
            dpSet("A.B.D", 2);
            dpSet("A.B.E", 3);
    
            int x = 0;
            int y = 0;
            int z = 0;
    
            dpSet("A.B.F", 4);
            dpSet("A.B.G", 5);
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-DPSET-CHAIN"]
        self.assertEqual(len(hits), 2, "연속 dpSet 클러스터는 함수 내에서 클러스터당 1건만 검출되어야 함")

    def test_perf_dpset_chain_not_detected_with_dpsetwait_or_delta_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            if (oldVal != newVal) {
                dpSetWait("A.B.C", newVal);
            }
            dpSet("A.B.D", 2);
        }
        """
        violations = checker.check_consecutive_dpset(code)
        self.assertFalse(any(v["rule_id"] == "PERF-DPSET-CHAIN" for v in violations))

    def test_perf03_not_detected_when_loop_has_delay(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            while (1) {
                dpGet("A.B.C", x);
                delay(1);
            }
        }
        """
        violations = checker.check_while_delay_policy(code)
        self.assertFalse(any(v["rule_id"] == "PERF-03" for v in violations))

    def test_perf03_active_delay_rule_detects_delay_only_inside_active(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code_ng = """
        main() {
          while (1) {
            if (isActive) {
              dpSet("A.B.C", 1);
              delay(1);
            }
          }
        }
        """
        code_ok = """
        main() {
          while (1) {
            if (isActive) {
              dpSet("A.B.C", 1);
            }
            delay(1);
          }
        }
        """
        ng_groups = checker.analyze_raw_code("sample.ctl", code_ng, file_type="Server")
        ok_groups = checker.analyze_raw_code("sample.ctl", code_ok, file_type="Server")
        ng_ids = [v["rule_id"] for g in ng_groups for v in g.get("violations", [])]
        ok_ids = [v["rule_id"] for g in ok_groups for v in g.get("violations", [])]
        self.assertIn("PERF-03-ACTIVE-DELAY-01", ng_ids)
        self.assertNotIn("PERF-03-ACTIVE-DELAY-01", ok_ids)

    def test_perf02_where_dpt_in_rule_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          dpQuery("SELECT '_online.._value' FROM '*.**' WHERE _DPT IN ('AI','DI')", result);
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        rule_ids = [v["rule_id"] for g in groups for v in g.get("violations", [])]
        self.assertIn("PERF-02-WHERE-DPT-IN-01", rule_ids)

    def test_log_level_rule_detects_missing_debug_level_and_skips_when_present(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code_ng = """
        main() {
          catch {
            writeLog("Script", "failed", LV_WARN);
          }
        }
        """
        code_ok = """
        main() {
          catch {
            writeLog("Script", "failed", LV_WARN);
            DebugTN("dbg2");
          }
        }
        """
        ng_groups = checker.analyze_raw_code("sample.ctl", code_ng, file_type="Server")
        ok_groups = checker.analyze_raw_code("sample.ctl", code_ok, file_type="Server")
        ng_ids = [v["rule_id"] for g in ng_groups for v in g.get("violations", [])]
        ok_ids = [v["rule_id"] for g in ok_groups for v in g.get("violations", [])]
        self.assertIn("LOG-LEVEL-01", ng_ids)
        self.assertNotIn("LOG-LEVEL-01", ok_ids)

    def test_perf05_context_only_alarm_like_dpset(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            dpSet("A.B.PVLAST", val);
        }
        """
        violations = checker.check_dpset_timed_context(code)
        self.assertFalse(any(v["rule_id"] == "PERF-05" for v in violations))

    def test_mem01_not_detected_when_dynremove_present(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            dyn_float buffer;
            while (1) {
                dynAppend(buffer, 1.0);
                dynRemove(buffer, 1);
            }
        }
        """
        violations = checker.check_memory_leaks_advanced(code)
        self.assertFalse(any(v["rule_id"] == "MEM-01" for v in violations))

    def test_std01_not_detected_for_multiline_declaration(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            string logMsg = "A"
                            + "B"
                            + "C";
        }
        """
        violations = checker.check_coding_standards_advanced(code)
        self.assertFalse(any(v["rule_id"] == "STD-01" for v in violations))

    def test_event_exchange_ng_detected_in_looped_dpset_without_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          while(1) {
            dpSet("SYS.A.B", 1);
            dpSet("SYS.A.C", 2);
          }
        }
        """
        violations = checker.check_event_exchange_minimization(code)
        self.assertTrue(any(v["rule_id"] == "PERF-EV-01" for v in violations))

    def test_event_exchange_not_detected_with_batch_or_delta_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          while(1) {
            if (oldVal != newVal) {
              dpSetWait("SYS.A.B", newVal);
            }
            dpSet("SYS.A.C", newVal);
          }
        }
        """
        violations = checker.check_event_exchange_minimization(code)
        self.assertFalse(any(v["rule_id"] == "PERF-EV-01" for v in violations))

    def test_style_name_rule_detects_prefix_violations(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        int globalValue = 0;
        const int maxCount = 10;
        main() {
          int configValue = 1;
        }
        """
        violations = checker.check_style_name_rules(code)
        self.assertTrue(any(v["rule_id"] == "STYLE-NAME-01" for v in violations))

    def test_style_indent_rule_detects_mixed_indent(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = "main() {\n\tint a = 0;\n  int b = 1;\n}\n"
        violations = checker.check_style_indent_rules(code)
        self.assertTrue(any(v["rule_id"] == "STYLE-INDENT-01" for v in violations))

    def test_hard02_detects_repeated_literal_dp_paths(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          dpSet("SITE.AREA.TAG.VALUE", 1);
          dpGet("SITE.AREA.TAG.VALUE", x);
        }
        """
        violations = checker.check_hardcoding_extended(code)
        self.assertTrue(any(v["rule_id"] == "HARD-02" for v in violations))

    def test_clean_dead_code_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          if (false) {
            DebugN("dead");
          }
        }
        """
        violations = checker.check_dead_code(code)
        self.assertTrue(any(v["rule_id"] == "CLEAN-DEAD-01" for v in violations))

    def test_clean_duplicate_block_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          dpSet("A.B.C", 1);
          dpSet("A.B.C", 1);
          dpSet("A.B.C", 1);
        }
        """
        violations = checker.check_duplicate_blocks(code)
        self.assertTrue(any(v["rule_id"] == "CLEAN-DUP-01" for v in violations))

    def test_dup_act_reports_one_per_cluster_and_multiple_clusters(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          setValue("OBJ_A","visible",true);
          setValue("OBJ_A","visible",false);
          setValue("OBJ_A","visible",true);
          setValue("OBJ_A","visible",false);
    
          int sep1 = 0;
          int sep2 = 0;
          int sep3 = 0;
          int sep4 = 0;
          int sep5 = 0;
          int sep6 = 0;
          int sep7 = 0;
          int sep8 = 0;
          int sep9 = 0;
          int sep10 = 0;
          int sep11 = 0;
    
          setValue("OBJ_A","visible",true);
          setValue("OBJ_A","visible",false);
    
          setValue("OBJ_B","enabled",true);
          setValue("OBJ_B","enabled",false);
          setValue("OBJ_B","enabled",true);
        }
        """
        groups = checker.analyze_raw_code("sample.txt", code, file_type="Client")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "DUP-ACT-01"]
        self.assertEqual(len(hits), 2, "DUP-ACT-01은 같은 연속 구간에서는 1건만 검출되어야 함")
        self.assertTrue(any("OBJ_A.visible" in str(v.get("message", "")) for v in hits), "DUP-ACT-01 메시지에 대상명+속성명이 포함되어야 함")

    def test_dup_act_skips_guarded_duplicate_pattern(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          if (prev != value) {
            setValue("OBJ_A","visible",value);
            setValue("OBJ_A","visible",value);
          }
        }
        """
        groups = checker.analyze_raw_code("sample.txt", code, file_type="Client")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "DUP-ACT-01"]
        self.assertEqual(len(hits), 0)

    def test_cfg01_detects_inconsistent_config_parsing(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        bool load_config() {
          string config_line = lineA;
          dyn_string a = strsplit(lineA, ",");
          dyn_string b = strsplit(lineB, ";");
          return true;
        }
        """
        violations = checker.check_config_format_consistency(code)
        self.assertTrue(any(v["rule_id"] == "CFG-01" for v in violations))

    def test_cfg_err_detects_missing_fail_return(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        bool load_config() {
          string cfg = raw;
          dyn_string parts = strsplit(raw, ",");
          if (dynlen(parts) < 7) {
            continue;
          }
          return true;
        }
        """
        violations = checker.check_config_error_contract(code)
        self.assertTrue(any(v["rule_id"] == "CFG-ERR-01" for v in violations))

    def test_perf_dpget_batch_detected_in_loop(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            dpGet("A.B.C1", v1);
            dpGet("A.B.C2", v2);
          }
        }
        """
        violations = checker.check_dpget_batch_optimization(code)
        self.assertTrue(any(v["rule_id"] == "PERF-DPGET-BATCH-01" for v in violations))

    def test_perf_dpget_batch_detects_multiple_loops_in_one_function(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            dpGet("A.B.C1", v1);
            dpGet("A.B.C2", v2);
          }
    
          for (int j=1; j<=10; j++) {
            dpGet("X.Y.C1", w1);
            dpGet("X.Y.C2", w2);
          }
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-DPGET-BATCH-01"]
        self.assertGreaterEqual(len(hits), 2)

    def test_perf_dpget_batch_outside_loop_reports_one_per_cluster(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          dpGet("A.B.C1", v1);
          dpGet("A.B.C2", v2);
          dpGet("A.B.C3", v3);
          dpGet("A.B.C4", v4);
    
          int sep = 0;
          int sep2 = 0;
          int sep3 = 0;
          int sep4 = 0;
          int sep5 = 0;
          int sep6 = 0;
    
          dpGet("X.Y.C1", w1);
          dpGet("X.Y.C2", w2);
          dpGet("X.Y.C3", w3);
          dpGet("X.Y.C4", w4);
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-DPGET-BATCH-01"]
        self.assertEqual(len(hits), 2, "연속 dpGet 클러스터는 함수 내에서 클러스터당 1건만 검출되어야 함")

    def test_perf_dpget_batch_not_detected_with_cache(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            if (mappingHasKey(cacheMap, key)) {
              continue;
            }
            dpGet("A.B.C1", v1);
            dpGet("A.B.C2", v2);
          }
        }
        """
        violations = checker.check_dpget_batch_optimization(code)
        self.assertFalse(any(v["rule_id"] == "PERF-DPGET-BATCH-01" for v in violations))

    def test_perf_dpset_batch_detected_in_loop(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            dpSet("A.B.C1", v1);
            dpSet("A.B.C2", v2);
          }
        }
        """
        violations = checker.check_dpset_batch_optimization(code)
        self.assertTrue(any(v["rule_id"] == "PERF-DPSET-BATCH-01" for v in violations))

    def test_perf_dpset_batch_not_detected_with_wait(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            dpSet("A.B.C1", v1);
            dpSet("A.B.C2", v2);
            dpSetWait("A.B.C1", v1);
          }
        }
        """
        violations = checker.check_dpset_batch_optimization(code)
        self.assertFalse(any(v["rule_id"] == "PERF-DPSET-BATCH-01" for v in violations))

    def test_exc_try_rule_detects_missing_try_catch(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          dpQuery("SELECT * FROM A.B.C");
          dpSet("A.B.C", 1);
        }
        """
        violations = checker.check_try_catch_for_risky_ops(code)
        self.assertTrue(any(v["rule_id"] == "EXC-TRY-01" for v in violations))

    def test_exc_try_rule_not_detected_with_try_catch(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          try {
            dpQuery("SELECT * FROM A.B.C");
          } catch (...) {
            DebugN("err");
          }
        }
        """
        violations = checker.check_try_catch_for_risky_ops(code)
        self.assertFalse(any(v["rule_id"] == "EXC-TRY-01" for v in violations))
