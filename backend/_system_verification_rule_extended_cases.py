"""Rule extended cases for system verification."""

try:
    from ._system_verification_base import *  # noqa: F403
except ImportError:
    from _system_verification_base import *  # noqa: F403


class SystemVerificationRuleExtendedMixin:
    def test_reporter_excel_template_existence(self):
        templates = [name for name in os.listdir(self.config_dir) if name.lower().endswith(".xlsx")]
        self.assertGreaterEqual(len(templates), 2, "Excel templates not found")

    def test_exc_try_rule_not_detected_for_single_low_risk_call(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          dpGet("A.B.C", v);
        }
        """
        violations = checker.check_try_catch_for_risky_ops(code)
        self.assertFalse(any(v["rule_id"] == "EXC-TRY-01" for v in violations))

    def test_safe_div_detects_missing_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void load_config() {
          string config_value = "x";
          ratio = total / count;
        }
        """
        violations = checker.check_division_zero_guard(code)
        self.assertTrue(any(v["rule_id"] == "SAFE-DIV-01" for v in violations))

    def test_safe_div_not_detected_with_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void load_config() {
          string cfg = "x";
          if (count != 0) {
            ratio = total / count;
          }
        }
        """
        violations = checker.check_division_zero_guard(code)
        self.assertFalse(any(v["rule_id"] == "SAFE-DIV-01" for v in violations))

    def test_safe_div_not_detected_with_if_return_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void load_config() {
          string cfg = "x";
          if (count == 0) return;
          ratio = total / count;
        }
        """
        violations = checker.check_division_zero_guard(code)
        self.assertFalse(any(v["rule_id"] == "SAFE-DIV-01" for v in violations))

    def test_dpset_chain_skips_loop_context(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          while (run) {
            dpSet("A.B.C1", 1);
            dpSet("A.B.C2", 2);
          }
        }
        """
        violations = checker.check_consecutive_dpset(code)
        self.assertFalse(any(v["rule_id"] == "PERF-DPSET-CHAIN" for v in violations))

    def test_perf_setvalue_batch_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            setValue("A.B.C1", v1);
            setValue("A.B.C2", v2);
          }
        }
        """
        violations = checker.check_setvalue_batch_optimization(code)
        self.assertTrue(any(v["rule_id"] == "PERF-SETVALUE-BATCH-01" for v in violations))

    def test_perf_setvalue_batch_not_detected_when_setmultivalue_exists(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            setValue("A.B.C1", v1);
            setValue("A.B.C2", v2);
            setMultiValue("A.B.C1", v1, "A.B.C2", v2);
          }
        }
        """
        violations = checker.check_setvalue_batch_optimization(code)
        self.assertFalse(any(v["rule_id"] == "PERF-SETVALUE-BATCH-01" for v in violations))

    def test_perf_setvalue_batch_detects_multiple_loops_in_one_function(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            setValue("A.B.C1", v1);
            setValue("A.B.C2", v2);
          }
    
          while (run) {
            setValue("X.Y.C1", w1);
            setValue("X.Y.C2", w2);
          }
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-SETVALUE-BATCH-01"]
        self.assertGreaterEqual(len(hits), 2)

    def test_perf_setmultivalue_adopt_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          setValue("A.B.C1", v1);
          setValue("A.B.C2", v2);
          setValue("A.B.C3", v3);
        }
        """
        violations = checker.check_setmultivalue_adoption(code)
        self.assertTrue(any(v["rule_id"] == "PERF-SETMULTIVALUE-ADOPT-01" for v in violations))

    def test_perf_setmultivalue_adopt_reports_one_per_cluster(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          setValue("A.B.C1", v1);
          setValue("A.B.C2", v2);
          setValue("A.B.C3", v3);
          setValue("A.B.C4", v4);
    
          int sep = 0;
          int sep2 = 0;
          int sep3 = 0;
          int sep4 = 0;
          int sep5 = 0;
          int sep6 = 0;
    
          setValue("X.Y.C1", w1);
          setValue("X.Y.C2", w2);
          setValue("X.Y.C3", w3);
          setValue("X.Y.C4", w4);
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-SETMULTIVALUE-ADOPT-01"]
        self.assertEqual(len(hits), 2)

    def test_perf_getvalue_batch_detected(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          while (run) {
            getValue("A.B.C1", v1);
            getValue("A.B.C2", v2);
          }
        }
        """
        violations = checker.check_getvalue_batch_optimization(code)
        self.assertTrue(any(v["rule_id"] == "PERF-GETVALUE-BATCH-01" for v in violations))

    def test_perf_getvalue_batch_detects_multiple_loops_in_one_function(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          while (run) {
            getValue("A.B.C1", v1);
            getValue("A.B.C2", v2);
          }
    
          for (int i=0; i<10; i++) {
            getValue("X.Y.C1", w1);
            getValue("X.Y.C2", w2);
          }
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-GETVALUE-BATCH-01"]
        self.assertGreaterEqual(len(hits), 2)

    def test_perf_getvalue_batch_not_detected_with_cache_guard(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          while (run) {
            if (mappingHasKey(cacheMap, key)) continue;
            getValue("A.B.C1", v1);
            getValue("A.B.C2", v2);
          }
        }
        """
        violations = checker.check_getvalue_batch_optimization(code)
        self.assertFalse(any(v["rule_id"] == "PERF-GETVALUE-BATCH-01" for v in violations))

    def test_perf_getmultivalue_adopt_reports_one_per_cluster(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          getValue("A.B.C1", v1);
          getValue("A.B.C2", v2);
          getValue("A.B.C3", v3);
          getValue("A.B.C4", v4);
    
          int sep = 0;
          int sep2 = 0;
          int sep3 = 0;
          int sep4 = 0;
          int sep5 = 0;
          int sep6 = 0;
    
          getValue("X.Y.C1", w1);
          getValue("X.Y.C2", w2);
          getValue("X.Y.C3", w3);
          getValue("X.Y.C4", w4);
        }
        """
        groups = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        hits = [v for g in groups for v in g.get("violations", []) if v.get("rule_id") == "PERF-GETMULTIVALUE-ADOPT-01"]
        self.assertEqual(len(hits), 2)

    def test_new_perf_rules_ignore_comment_only_tokens(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          // setValue("A.B.C1", v1);
          // setValue("A.B.C2", v2);
          int a = 1; // getValue("A.B.C1", v1);
          DebugN(a);
        }
        """
        event = {"event": "Global", "code": code, "line_start": 1}
        violations = checker.check_event(event, file_type="Server")
        blocked = {"PERF-SETVALUE-BATCH-01", "PERF-SETMULTIVALUE-ADOPT-01", "PERF-GETVALUE-BATCH-01"}
        self.assertFalse(any(v["rule_id"] in blocked for v in violations))

    def test_perf_agg_detected_manual_sum_avg_pattern(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          for (int i=1; i<=10; i++) {
            sum += value;
            count++;
          }
          avg = sum / count;
        }
        """
        violations = checker.check_manual_aggregation_pattern(code)
        self.assertTrue(any(v["rule_id"] == "PERF-AGG-01" for v in violations))

    def test_style_idx_detects_magic_indices(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          parsed[1] = parts[2];
          parsed[2] = parts[3];
          parsed[3] = parts[4];
        }
        """
        violations = checker.check_magic_index_usage(code)
        self.assertTrue(any(v["rule_id"] == "STYLE-IDX-01" for v in violations))

    def test_style_idx_not_detected_with_idx_constants(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        const int IDX_LEVEL_DP = 2;
        const int IDX_USAGE_DP = 3;
        void f() {
          parsed[1] = parts[IDX_LEVEL_DP];
          parsed[2] = parts[IDX_USAGE_DP];
          parsed[3] = parts[IDX_USAGE_DP];
        }
        """
        violations = checker.check_magic_index_usage(code)
        self.assertFalse(any(v["rule_id"] == "STYLE-IDX-01" for v in violations))

    def test_style_header_not_flagged_when_comment_block_exists(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        //******************************************************************************
        // name: main
        // argument:
        // return: void
        //******************************************************************************
        void main()
        {
          DebugN("ok");
        }
        """
        event = {"event": "Global", "code": code, "line_start": 1}
        violations = checker.check_event(event, file_type="Server")
        self.assertFalse(any(v["rule_id"] == "STYLE-HEADER-01" for v in violations))

    def test_hard03_detects_repeated_float_literal(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        void f() {
          fallback = 0.001;
          if (x < 0.001) return;
        }
        """
        violations = checker.check_float_literal_hardcoding(code)
        self.assertTrue(any(v["rule_id"] == "HARD-03" for v in violations))

    def test_hard03_not_detected_with_const(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        const float MIN_USAGE = 0.001;
        void f() {
          fallback = MIN_USAGE;
          if (x < MIN_USAGE) return;
        }
        """
        violations = checker.check_float_literal_hardcoding(code)
        self.assertFalse(any(v["rule_id"] == "HARD-03" for v in violations))

    def test_comment_line_does_not_trigger_dp_rules(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          // dpSet("A.B.C", 1);
          int a = 1; // test
          DebugN(a);
        }
        """
        event = {"event": "Global", "code": code, "line_start": 1}
        violations = checker.check_event(event, file_type="Server")
        self.assertFalse(any(v["rule_id"] == "EXC-DP-01" for v in violations))
        self.assertFalse(any(v["rule_id"] == "PERF-DPSET-CHAIN" for v in violations))

    def test_inline_comment_tail_is_excluded_from_analysis(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
          int a = 1; // dpSet("A.B.C", 1);
          DebugN(a);
        }
        """
        event = {"event": "Global", "code": code, "line_start": 1}
        violations = checker.check_event(event, file_type="Server")
        self.assertFalse(any(v["rule_id"] == "EXC-DP-01" for v in violations))

    def test_issue_id_deterministic(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        event = {"event": "Global", "code": 'sprintf(sql, "SELECT * FROM x WHERE y=%s", input);', "line_start": 1}
        first = checker.check_event(event)
        second = checker.check_event(event)
        self.assertEqual([v["issue_id"] for v in first], [v["issue_id"] for v in second])
