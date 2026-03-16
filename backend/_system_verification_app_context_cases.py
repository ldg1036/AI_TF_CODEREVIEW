"""App context cases for system verification."""

try:
    from ._system_verification_base import *  # noqa: F403
except ImportError:
    from _system_verification_base import *  # noqa: F403


class SystemVerificationAppContextMixin:
    def test_target_collection_excludes_stale_generated_txt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ctl_path = os.path.join(temp_dir, "sample.ctl")
            stale_txt_path = os.path.join(temp_dir, "stale_pnl.txt")
            with open(ctl_path, "w", encoding="utf-8") as f:
                f.write("main() { DebugN(\"ok\"); }")
            with open(stale_txt_path, "w", encoding="utf-8") as f:
                f.write("stale")
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
            targets = app.collect_targets()
            basenames = {os.path.basename(path) for path in targets}
    
            self.assertIn("sample.ctl", basenames)
            self.assertNotIn("stale_pnl.txt", basenames)

    def test_default_mode_is_ai_assist(self):
        self.assertEqual(DEFAULT_MODE, "AI 보조")

    def test_live_ai_toggle_off_uses_mock_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write('main() { dpSet("A.B.C", 1); }')
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
    
            app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-R1-1",
                            "rule_id": "R1",
                            "rule_item": "test-item",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 1,
                            "message": "test violation",
                        }
                    ],
                }
            ]
    
            calls = {"live": 0, "mock": 0}
    
            def fake_live_review(*_args, **_kwargs):
                calls["live"] += 1
                return "LIVE REVIEW"
    
            def fake_mock_review(*_args, **_kwargs):
                calls["mock"] += 1
                return "MOCK REVIEW"
    
            app.ai_tool.generate_review = fake_live_review
            app.ai_tool.get_mock_review = fake_mock_review
    
            report = app.analyze_file(target, mode="AI 보조", enable_live_ai=False)
            self.assertEqual(calls["live"], 0)
            self.assertEqual(calls["mock"], 1)
            self.assertEqual(report["ai_reviews"][0]["source"], "mock")
            self.assertEqual(report["ai_reviews"][0]["review"], "MOCK REVIEW")

    def test_live_ai_toggle_on_uses_live_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write('main() { dpSet("A.B.C", 1); }')
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
    
            app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-R1-1",
                            "rule_id": "R1",
                            "rule_item": "test-item",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 1,
                            "message": "test violation",
                        }
                    ],
                }
            ]
    
            calls = {"live": 0, "mock": 0}
    
            def fake_live_review(*_args, **_kwargs):
                calls["live"] += 1
                return "LIVE REVIEW"
    
            def fake_mock_review(*_args, **_kwargs):
                calls["mock"] += 1
                return "MOCK REVIEW"
    
            app.ai_tool.generate_review = fake_live_review
            app.ai_tool.get_mock_review = fake_mock_review
    
            report = app.analyze_file(target, mode="AI 보조", enable_live_ai=True)
            self.assertEqual(calls["live"], 1)
            self.assertEqual(calls["mock"], 0)
            self.assertEqual(report["ai_reviews"][0]["source"], "live")
            self.assertEqual(report["ai_reviews"][0]["review"], "LIVE REVIEW")

    def test_live_ai_fail_soft_message(self):
        reviewer = LLMReviewer(
            ai_config={
                "provider": "unsupported-provider",
                "fail_soft": True,
                "enabled_default": False,
                "timeout_sec": 5,
            }
        )
        text = reviewer.generate_review("main() {}", [])
        self.assertIn("AI live review failed:", text)

    def test_mcp_context_fetch_success(self):
        client = MCPContextClient(
            mcp_config={
                "url": "http://localhost:3000",
                "timeout_sec": 2,
                "max_drivers_in_prompt": 5,
            }
        )
    
        def fake_get_json(endpoint):
            if endpoint == "/context":
                return {"projectName": "TEST_PROJ", "site": "CHEONAN", "environment": "prod"}
            if endpoint == "/drivers":
                return {"drivers": [{"name": "CTRL"}, {"name": "DB"}, {"name": "ALARM"}]}
            return {}
    
        client._get_json = fake_get_json
        payload = client.fetch_context()
        self.assertTrue(payload.get("enabled"))
        self.assertEqual(payload.get("project", {}).get("projectName"), "TEST_PROJ")
        self.assertEqual(len(payload.get("drivers", [])), 3)

    def test_mcp_context_fetch_fail_soft(self):
        client = MCPContextClient(mcp_config={"url": "http://localhost:3000", "timeout_sec": 1})
    
        def failing_get_json(_endpoint):
            raise RuntimeError("mcp offline")
    
        client._get_json = failing_get_json
        payload = client.fetch_context()
        self.assertFalse(payload.get("enabled"))
        self.assertIn("mcp offline", str(payload.get("error", "")))

    def test_llm_prompt_contains_mcp_context_when_enabled(self):
        reviewer = LLMReviewer(ai_config={"provider": "ollama", "fail_soft": True})
        prompt = reviewer._build_prompt(
            code="main() {}",
            violations=[],
            use_context=True,
            context_payload={
                "enabled": True,
                "project": {"projectName": "PROJ_A", "site": "CHEONAN", "environment": "prod"},
                "drivers": [{"name": "CTRL"}, {"name": "DB"}],
            },
        )
        self.assertIn("project=PROJ_A", prompt)
        self.assertIn("drivers=CTRL, DB", prompt)

    def test_llm_prompt_context_fallback_when_missing(self):
        reviewer = LLMReviewer(ai_config={"provider": "ollama", "fail_soft": True})
        prompt = reviewer._build_prompt(
            code="main() {}",
            violations=[],
            use_context=True,
            context_payload={"enabled": False, "error": "offline"},
        )
        self.assertIn("Context: N/A", prompt)

    def test_collect_targets_raw_txt_off_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ctl_path = os.path.join(temp_dir, "sample.ctl")
            raw_txt_path = os.path.join(temp_dir, "raw_input.txt")
            with open(ctl_path, "w", encoding="utf-8") as f:
                f.write("main() { DebugN(\"ok\"); }")
            with open(raw_txt_path, "w", encoding="utf-8") as f:
                f.write("raw")
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
            targets = app.collect_targets()
            basenames = {os.path.basename(path) for path in targets}
    
            self.assertIn("sample.ctl", basenames)
            self.assertNotIn("raw_input.txt", basenames)

    def test_collect_targets_raw_txt_on(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_txt_path = os.path.join(temp_dir, "raw_input.txt")
            with open(raw_txt_path, "w", encoding="utf-8") as f:
                f.write("raw")
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
            targets = app.collect_targets(allow_raw_txt=True)
            basenames = {os.path.basename(path) for path in targets}
    
            self.assertIn("raw_input.txt", basenames)

    def test_collect_targets_selected_raw_txt_requires_toggle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_txt_path = os.path.join(temp_dir, "raw_input.txt")
            with open(raw_txt_path, "w", encoding="utf-8") as f:
                f.write("raw")
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
            targets = app.collect_targets(selected_files=["raw_input.txt"], allow_raw_txt=False)
            basenames = {os.path.basename(path) for path in targets}
    
            self.assertNotIn("raw_input.txt", basenames)

    def test_ctl_uses_server_rules_only(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            while(1) {
                int x;
                dpGet("A.B.C", x);
            }
        }
        """
        findings = checker.analyze_raw_code("sample.ctl", code, file_type="Server")
        rule_items = [
            checker._normalize_rule_item(v["rule_item"])
            for group in findings
            for v in group.get("violations", [])
            if v.get("rule_item")
        ]
        self.assertIn("loop문내에처리조건", rule_items)

    def test_txt_uses_client_rules_only(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        code = """
        main() {
            while(1) {
                int x;
                dpGet("A.B.C", x);
            }
        }
        """
        findings = checker.analyze_raw_code("sample.txt", code, file_type="Client")
        rule_items = [
            checker._normalize_rule_item(v["rule_item"])
            for group in findings
            for v in group.get("violations", [])
            if v.get("rule_item")
        ]
        self.assertNotIn("loop문내에처리조건", rule_items)

    def test_pnl_xml_converted_txt_flows_to_client(self):
        app = CodeInspectorApp()
        self.assertEqual(app.infer_file_type("A_panel_pnl.txt"), "Client")
        self.assertEqual(app.infer_file_type("A_panel_xml.txt"), "Client")

    def test_rule_item_alias_normalization(self):
        checker = HeuristicChecker(os.path.join(self.config_dir, "parsed_rules.json"))
        self.assertEqual(
            checker._normalize_rule_item("Loop문 내의 처리 조건"),
            checker._normalize_rule_item("Loop문 내에 처리 조건"),
        )
        self.assertEqual(
            checker._normalize_rule_item("명명 규칙 및 코딩 스타일 준수 여부 확인"),
            checker._normalize_rule_item("명명 규칙 및 코딩 스타일 준수 확인"),
        )
