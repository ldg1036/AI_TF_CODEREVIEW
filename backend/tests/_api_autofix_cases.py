from ._api_integration_test_base import *
from ._api_integration_test_base import _require_openpyxl


class ApiAutofixCasesMixin:
    def test_autofix_prepare_and_apply_ctl_diff_flow(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )

        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        p3 = analyze_payload.get("violations", {}).get("P3", [])
        self.assertGreaterEqual(len(p3), 1)
        ai_review = p3[0]

        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        self.assertTrue(prepare_payload.get("proposal_id"))
        self.assertEqual(prepare_payload.get("file"), "sample.ctl")
        self.assertIn("--- sample.ctl", prepare_payload.get("unified_diff", ""))
        self.assertTrue(prepare_payload.get("base_hash"))

        diff_status, diff_payload = self._request(
            "GET",
            "/api/autofix/file-diff?" + urllib.parse.urlencode(
                {"file": "sample.ctl", "session_id": analyze_payload.get("output_dir", "")}
            ),
        )
        self.assertEqual(diff_status, 200)
        self.assertEqual(diff_payload.get("proposal_id"), prepare_payload.get("proposal_id"))

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        self.assertTrue(apply_payload.get("applied"))
        self.assertEqual(apply_payload.get("file"), "sample.ctl")
        self.assertTrue(apply_payload.get("backup_path"))
        self.assertTrue(apply_payload.get("audit_log_path"))
        validation = apply_payload.get("validation", {})
        self.assertTrue(validation.get("hash_match"))
        self.assertTrue(validation.get("anchors_match"))
        quality = apply_payload.get("quality_metrics", {})
        self.assertEqual(quality.get("generator_type"), "llm")
        self.assertTrue(quality.get("applied"))

        with open(os.path.join(self.data_dir, "sample.ctl"), "r", encoding="utf-8") as f:
            patched = f.read()
        self.assertIn("[AI-AUTOFIX:", patched)
        self.assertIn("if (isValid) {", patched)

    def test_autofix_prepare_and_apply_raw_txt_llm_only(self):
        self.app.checker.analyze_raw_code = lambda *_args, **_kwargs: [
            {
                "object": "raw_input.txt",
                "event": "Global",
                "violations": [
                    {
                        "issue_id": "P1-RAW-1",
                        "rule_id": "R-RAW",
                        "rule_item": "raw-item",
                        "priority_origin": "P1",
                        "severity": "Warning",
                        "line": 1,
                        "message": "raw test violation",
                    }
                ],
            }
        ]
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 로그를 개선하세요.\n\n"
            "코드:\n```cpp\nDebugN(\"raw-fix\");\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["raw_input.txt"], "allow_raw_txt": True, "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]

        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "raw_input.txt",
                "object": ai_review.get("object", "raw_input.txt"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
                "prepare_mode": "compare",
            },
        )
        self.assertEqual(prepare_status, 200)
        self.assertEqual(prepare_payload.get("generator_type"), "llm")
        proposals = prepare_payload.get("proposals", [])
        self.assertEqual(len(proposals), 1)
        self.assertEqual((proposals[0] or {}).get("generator_type"), "llm")

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "raw_input.txt",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
                "check_ctrlpp_regression": True,
            },
        )
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertEqual(validation.get("syntax_check_skipped_reason"), "non_ctl_file")
        self.assertEqual(validation.get("ctrlpp_regression_skipped_reason"), "non_ctl_file")

        with open(os.path.join(self.data_dir, "raw_input.txt"), "r", encoding="utf-8") as f:
            patched = f.read()
        self.assertIn("[AI-AUTOFIX:", patched)

    def test_autofix_instruction_flag_off_keeps_legacy_hunk_apply(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = False
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertEqual(str(validation.get("instruction_mode", "off")), "off")
        self.assertFalse(bool(validation.get("instruction_apply_success", True)))

    def test_autofix_instruction_flag_on_applies_instruction_path(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = True
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertEqual(str(validation.get("instruction_mode", "")), "applied")
        self.assertTrue(bool(validation.get("instruction_apply_success", False)))
        self.assertEqual(str(validation.get("instruction_path_reason", "")), "applied")
        self.assertEqual(str(validation.get("instruction_failure_stage", "")), "none")
        self.assertIn(str(validation.get("instruction_operation", "")), ("insert", "replace"))
        self.assertGreaterEqual(int(validation.get("instruction_operation_count", 0) or 0), 1)
        self.assertGreaterEqual(int(validation.get("instruction_candidate_hunk_count", 0) or 0), 1)
        self.assertGreaterEqual(int(validation.get("instruction_applied_hunk_count", 0) or 0), 1)
        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("instruction_attempt_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("instruction_apply_success_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("instruction_operation_total_count", 0) or 0), 1)
        self.assertGreaterEqual(int((stats_payload.get("instruction_mode_counts", {}) or {}).get("applied", 0) or 0), 1)

    def test_autofix_instruction_invalid_falls_back_to_hunks(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = True
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            self.assertIsNotNone(proposal)
            proposal["_structured_instruction"] = {
                "target": {"file": "sample.ctl", "object": "sample.ctl", "event": "Global"},
                "operation": "delete",
                "locator": {"kind": "anchor_context", "start_line": 1},
                "payload": {"code": "x"},
                "safety": {"requires_hash_match": True},
            }

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertEqual(str(validation.get("instruction_mode", "")), "fallback_hunks")
        self.assertFalse(bool(validation.get("instruction_apply_success", True)))
        self.assertEqual(str(validation.get("instruction_path_reason", "")), "validation_failed")
        self.assertEqual(str(validation.get("instruction_failure_stage", "")), "validate")
        self.assertTrue(len(validation.get("instruction_validation_errors", []) or []) >= 1)
        self.assertGreaterEqual(int(validation.get("instruction_operation_count", 0) or 0), 1)
        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("instruction_attempt_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("instruction_validation_fail_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("instruction_fallback_to_hunk_count", 0) or 0), 1)
        self.assertGreaterEqual(int((stats_payload.get("instruction_mode_counts", {}) or {}).get("fallback_hunks", 0) or 0), 1)
        self.assertTrue(bool(stats_payload.get("instruction_validation_fail_by_reason", {})))

    def test_autofix_instruction_convert_fail_records_stage_and_stats(self):
        import core.autofix_mixin as mixin_module

        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = True
        original_to_hunks = mixin_module.instruction_to_hunks
        mixin_module.instruction_to_hunks = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("forced_convert_fail"))
        try:
            status, analyze_payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
            self.assertEqual(status, 200)
            ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
            prepare_status, prepare_payload = self._request(
                "POST",
                "/api/autofix/prepare",
                {
                    "file": "sample.ctl",
                    "object": ai_review.get("object", "sample.ctl"),
                    "event": ai_review.get("event", "Global"),
                    "review": ai_review.get("review", ""),
                    "session_id": analyze_payload.get("output_dir", ""),
                },
            )
            self.assertEqual(prepare_status, 200)
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": prepare_payload.get("base_hash"),
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
            )
            self.assertEqual(apply_status, 200)
            validation = apply_payload.get("validation", {})
            self.assertEqual(str(validation.get("instruction_mode", "")), "fallback_hunks")
            self.assertEqual(str(validation.get("instruction_failure_stage", "")), "convert")
            self.assertEqual(str(validation.get("instruction_path_reason", "")), "fallback_hunks")
            stats_status, stats_payload = self._request(
                "GET",
                "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
            )
            self.assertEqual(stats_status, 200)
            self.assertGreaterEqual(int(stats_payload.get("instruction_convert_fail_count", 0) or 0), 1)
        finally:
            mixin_module.instruction_to_hunks = original_to_hunks

    def test_autofix_instruction_engine_fail_records_stage_and_stats(self):
        import core.autofix_mixin as mixin_module

        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = True
        original_apply_with_engine = mixin_module.apply_with_engine
        call_state = {"count": 0}

        def _patched_apply_with_engine(*args, **kwargs):
            call_state["count"] += 1
            if call_state["count"] == 1:
                return {"ok": False, "engine_mode": "failed", "fallback_reason": "forced_engine_fail"}
            return original_apply_with_engine(*args, **kwargs)

        mixin_module.apply_with_engine = _patched_apply_with_engine
        try:
            status, analyze_payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
            self.assertEqual(status, 200)
            ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
            prepare_status, prepare_payload = self._request(
                "POST",
                "/api/autofix/prepare",
                {
                    "file": "sample.ctl",
                    "object": ai_review.get("object", "sample.ctl"),
                    "event": ai_review.get("event", "Global"),
                    "review": ai_review.get("review", ""),
                    "session_id": analyze_payload.get("output_dir", ""),
                },
            )
            self.assertEqual(prepare_status, 200)
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": prepare_payload.get("base_hash"),
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
            )
            self.assertEqual(apply_status, 200)
            validation = apply_payload.get("validation", {})
            self.assertEqual(str(validation.get("instruction_mode", "")), "fallback_hunks")
            self.assertEqual(str(validation.get("instruction_failure_stage", "")), "apply")
            self.assertEqual(str(validation.get("instruction_path_reason", "")), "engine_failed")
            stats_status, stats_payload = self._request(
                "GET",
                "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
            )
            self.assertEqual(stats_status, 200)
            self.assertGreaterEqual(int(stats_payload.get("instruction_engine_fail_count", 0) or 0), 1)
        finally:
            mixin_module.apply_with_engine = original_apply_with_engine

    def test_autofix_compare_proposals_include_structured_instruction_envelope(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "auto",
                "prepare_mode": "compare",
            },
        )
        self.assertEqual(prepare_status, 200)
        self.assertGreaterEqual(len(prepare_payload.get("proposals", []) or []), 1)
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            stored = session.get("autofix", {}).get("proposals", {})
            for view in (prepare_payload.get("proposals") or []):
                pid = str((view or {}).get("proposal_id", ""))
                self.assertTrue(pid)
                proposal = stored.get(pid, {})
                self.assertIsInstance(proposal.get("_structured_instruction"), dict)
                self.assertIsInstance((view or {}).get("instruction_preview"), dict)
                self.assertGreaterEqual(int(((view or {}).get("instruction_preview", {}) or {}).get("operation_count", 0) or 0), 1)

    def test_autofix_compare_selection_prefers_valid_instruction_candidate(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        original_rule_builder = self.app._build_autofix_proposal_from_rule_template

        def _patched_rule_builder(*args, **kwargs):
            proposal = original_rule_builder(*args, **kwargs)
            proposal["_structured_instruction"] = {
                "target": {"file": "sample.ctl", "object": "sample.ctl", "event": "Global"},
                "operation": "delete",
                "locator": {"kind": "anchor_context", "start_line": 1},
                "payload": {"code": "x"},
                "safety": {"requires_hash_match": True},
            }
            return proposal

        self.app._build_autofix_proposal_from_rule_template = _patched_rule_builder
        try:
            status, analyze_payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
            self.assertEqual(status, 200)
            ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
            prepare_status, prepare_payload = self._request(
                "POST",
                "/api/autofix/prepare",
                {
                    "file": "sample.ctl",
                    "object": ai_review.get("object", "sample.ctl"),
                    "event": ai_review.get("event", "Global"),
                    "review": ai_review.get("review", ""),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "generator_preference": "auto",
                    "prepare_mode": "compare",
                },
            )
            self.assertEqual(prepare_status, 200)
            compare_meta = prepare_payload.get("compare_meta", {})
            self.assertEqual(compare_meta.get("selection_policy"), "instruction_validity_then_syntax_then_rule")
            self.assertIsInstance(compare_meta.get("selected_compare_score", {}), dict)
            self.assertGreaterEqual(int((compare_meta.get("selected_compare_score", {}) or {}).get("total", 0) or 0), 0)
            selected_pid = str(prepare_payload.get("selected_proposal_id", ""))
            selected = None
            for item in (prepare_payload.get("proposals") or []):
                if str((item or {}).get("proposal_id", "")) == selected_pid:
                    selected = item
                    break
            self.assertIsNotNone(selected)
            self.assertEqual(str((selected or {}).get("generator_type", "")), "llm")
        finally:
            self.app._build_autofix_proposal_from_rule_template = original_rule_builder

    def test_autofix_apply_rejects_hash_mismatch(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)

        self.assertIn("generator_type", prepare_payload)
        self.assertIn("generator_reason", prepare_payload)
        self.assertIn("quality_preview", prepare_payload)
        self.assertEqual(prepare_payload.get("generator_type"), "llm")

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": "deadbeef",
                "apply_mode": "source_ctl",
            },
        )
        self.assertEqual(apply_status, 409)
        self.assertEqual(apply_payload.get("error_code"), "BASE_HASH_MISMATCH")
        self.assertIn("quality_metrics", apply_payload)
        self.assertEqual((apply_payload.get("quality_metrics") or {}).get("hash_match"), False)
        self.assertIn("hash mismatch", apply_payload.get("error", "").lower())

    def test_autofix_apply_benchmark_relaxed_requires_env_flag(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)

        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": "deadbeef",
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={"X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed"},
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous

        self.assertEqual(apply_status, 409)
        self.assertEqual(apply_payload.get("error_code"), "BASE_HASH_MISMATCH")

    def test_autofix_apply_benchmark_relaxed_bypasses_hash_gate_with_env_flag(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)

        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = "1"
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": "deadbeef",
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={"X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed"},
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous

        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertTrue(bool(validation.get("hash_gate_bypassed", False)))
        self.assertEqual(validation.get("benchmark_observe_mode"), "benchmark_relaxed")

    def test_autofix_apply_benchmark_strict_hash_with_env_still_blocks_hash_mismatch(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)

        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = "1"
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": "deadbeef",
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={"X-Autofix-Benchmark-Observe-Mode": "strict_hash"},
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous

        self.assertEqual(apply_status, 409)
        self.assertEqual(apply_payload.get("error_code"), "BASE_HASH_MISMATCH")

    def test_autofix_apply_benchmark_tuning_headers_ignored_without_observe_gate(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": prepare_payload.get("base_hash"),
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={
                    "X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed",
                    "X-Autofix-Benchmark-Tuning-Min-Confidence": "0.55",
                    "X-Autofix-Benchmark-Tuning-Min-Gap": "0.05",
                    "X-Autofix-Benchmark-Tuning-Max-Line-Drift": "900",
                },
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertFalse(bool(validation.get("benchmark_tuning_applied", True)))
        self.assertEqual(float(validation.get("token_min_confidence_used", 0.0)), 0.8)
        self.assertEqual(float(validation.get("token_min_gap_used", 0.0)), 0.15)

    def test_autofix_apply_benchmark_tuning_headers_applied_with_observe_gate(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = "1"
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": "deadbeef",
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={
                    "X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed",
                    "X-Autofix-Benchmark-Tuning-Min-Confidence": "0.55",
                    "X-Autofix-Benchmark-Tuning-Min-Gap": "0.05",
                    "X-Autofix-Benchmark-Tuning-Max-Line-Drift": "900",
                },
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertTrue(bool(validation.get("benchmark_tuning_applied", False)))
        self.assertAlmostEqual(float(validation.get("token_min_confidence_used", 0.0)), 0.55, places=3)
        self.assertAlmostEqual(float(validation.get("token_min_gap_used", 0.0)), 0.05, places=3)
        self.assertEqual(int(validation.get("token_max_line_drift_used", 0)), 900)

    def test_autofix_apply_rejects_invalid_benchmark_tuning_headers(self):
        self._force_single_internal_violation()
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p1_group = (analyze_payload.get("violations", {}) or {}).get("P1", [])[0]
        violation = (p1_group.get("violations") or [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": p1_group.get("object", "sample.ctl"),
                "event": p1_group.get("event", "Global"),
                "review": "",
                "issue_id": violation.get("issue_id", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
            },
        )
        self.assertEqual(prepare_status, 200)
        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
            headers={
                "X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed",
                "X-Autofix-Benchmark-Tuning-Min-Confidence": "1.5",
            },
        )
        self.assertEqual(apply_status, 400)
        self.assertIn("Min-Confidence", str(apply_payload.get("error", "")))

    def test_autofix_apply_force_structured_header_ignored_without_observe_gate(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = False
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": prepare_payload.get("base_hash"),
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={
                    "X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed",
                    "X-Autofix-Benchmark-Force-Structured-Instruction": "true",
                },
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertEqual(str(validation.get("instruction_mode", "off")), "off")
        self.assertFalse(bool(validation.get("benchmark_structured_instruction_forced", True)))

    def test_autofix_apply_force_structured_header_applied_with_observe_gate(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        self.app.autofix_structured_instruction_enabled = False
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        previous = os.environ.get("AUTOFIX_BENCHMARK_OBSERVE")
        try:
            os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = "1"
            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": prepare_payload.get("base_hash"),
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                },
                headers={
                    "X-Autofix-Benchmark-Observe-Mode": "benchmark_relaxed",
                    "X-Autofix-Benchmark-Force-Structured-Instruction": "true",
                },
            )
        finally:
            if previous is None:
                os.environ.pop("AUTOFIX_BENCHMARK_OBSERVE", None)
            else:
                os.environ["AUTOFIX_BENCHMARK_OBSERVE"] = previous
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertTrue(bool(validation.get("benchmark_structured_instruction_forced", False)))
        self.assertIn(str(validation.get("instruction_mode", "off")), ("applied", "fallback_hunks"))
        self.assertNotEqual(str(validation.get("instruction_path_reason", "off")), "off")

    def test_autofix_prepare_rule_generator_without_review(self):
        self._force_single_internal_violation()
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)

        p1_group = (analyze_payload.get("violations", {}) or {}).get("P1", [])[0]
        violation = (p1_group.get("violations") or [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": p1_group.get("object", "sample.ctl"),
                "event": p1_group.get("event", "Global"),
                "review": "",
                "issue_id": violation.get("issue_id", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
            },
        )
        self.assertEqual(prepare_status, 200)
        self.assertEqual(prepare_payload.get("generator_type"), "rule")
        self.assertEqual(prepare_payload.get("source"), "rule-template")
        self.assertIn("quality_preview", prepare_payload)
        self.assertIn("generator_reason", prepare_payload)
        self.assertTrue(prepare_payload.get("unified_diff"))

    def test_autofix_stats_endpoint_reports_generator_counts(self):
        self._force_single_internal_violation()
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p1_group = (analyze_payload.get("violations", {}) or {}).get("P1", [])[0]
        violation = (p1_group.get("violations") or [])[0]
        prepare_status, _prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": p1_group.get("object", "sample.ctl"),
                "event": p1_group.get("event", "Global"),
                "review": "",
                "issue_id": violation.get("issue_id", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
            },
        )
        self.assertEqual(prepare_status, 200)

        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual((stats_payload.get("by_generator") or {}).get("rule", 0), 1)
        self.assertGreaterEqual(stats_payload.get("proposal_count", 0), 1)

    def test_autofix_prepare_compare_mode_returns_candidates(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "auto",
                "prepare_mode": "compare",
            },
        )
        self.assertEqual(prepare_status, 200)
        proposals = prepare_payload.get("proposals", [])
        self.assertGreaterEqual(len(proposals), 1)
        self.assertLessEqual(len(proposals), 2)
        proposal_ids = {str(p.get("proposal_id", "")) for p in proposals if isinstance(p, dict)}
        self.assertIn(str(prepare_payload.get("selected_proposal_id", "")), proposal_ids)
        compare_meta = prepare_payload.get("compare_meta", {})
        self.assertEqual(compare_meta.get("mode"), "compare")
        self.assertGreaterEqual(int(compare_meta.get("generated_count", 0) or 0), 1)

    def test_autofix_prepare_compare_mode_validation(self):
        status, payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": "sample.ctl",
                "event": "Global",
                "review": "",
                "session_id": "dummy",
                "prepare_mode": "invalid-mode",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("prepare_mode", str(payload.get("error", "")))

    def test_autofix_stats_compare_mode_selected_generator_counts(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "prepare_mode": "compare",
                "generator_preference": "auto",
            },
        )
        self.assertEqual(prepare_status, 200)
        proposals = prepare_payload.get("proposals", [])
        self.assertGreaterEqual(len(proposals), 1)
        selected = next(
            (p for p in proposals if str(p.get("proposal_id", "")) == str(prepare_payload.get("selected_proposal_id", ""))),
            proposals[0],
        )
        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": selected.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": selected.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("prepare_compare_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("compare_apply_count", 0) or 0), 1)
        self.assertIn("apply_engine_structure_success_count", stats_payload)
        self.assertIn("apply_engine_text_fallback_count", stats_payload)
        self.assertIn("selected_apply_engine_mode", stats_payload)
        selected_counts = stats_payload.get("selected_generator_counts", {}) or {}
        selected_gen = str(selected.get("generator_type", "")).lower()
        if selected_gen in ("rule", "llm"):
            self.assertGreaterEqual(int(selected_counts.get(selected_gen, 0) or 0), 1)

    def test_autofix_apply_token_fallback_success(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "llm",
            },
        )
        self.assertEqual(prepare_status, 200)
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        self.assertIsNotNone(session)
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            self.assertIsNotNone(proposal)
            hunks = proposal.get("hunks", [])
            self.assertTrue(hunks and isinstance(hunks[0], dict))
            hunks[0]["context_after"] = 'main(){dpSet("A.B.C",1);}'

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertIn(validation.get("apply_engine_mode"), ("structure_apply", "text_fallback"))
        self.assertEqual(validation.get("locator_mode"), "token_fallback")
        self.assertTrue(validation.get("token_fallback_attempted"))
        self.assertGreaterEqual(float(validation.get("token_fallback_confidence", 0.0) or 0.0), 0.8)

    def test_autofix_apply_anchor_normalized_success(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "llm",
            },
        )
        self.assertEqual(prepare_status, 200)
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            hunks = proposal.get("hunks", [])
            self.assertTrue(hunks and isinstance(hunks[0], dict))
            # Same semantic line with whitespace differences should pass normalized anchor mode.
            hunks[0]["context_after"] = 'main()    {   dpSet("A.B.C", 1);    }'

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        validation = apply_payload.get("validation", {})
        self.assertEqual(validation.get("locator_mode"), "anchor_normalized")
        self.assertFalse(validation.get("token_fallback_attempted"))

    def test_autofix_apply_token_fallback_ambiguous_fail_soft(self):
        with open(os.path.join(self.data_dir, "sample.ctl"), "w", encoding="utf-8") as f:
            f.write('main() { dpSet("A.B.C", 1); }\nmain() { dpSet("A.B.C", 1); }')
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "llm",
            },
        )
        self.assertEqual(prepare_status, 200)
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            hunks = proposal.get("hunks", [])
            hunks[0]["context_after"] = 'main(){dpSet("A.B.C",1);}'
        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
            },
        )
        self.assertEqual(apply_status, 409)
        self.assertEqual(apply_payload.get("error_code"), "ANCHOR_MISMATCH")
        quality = apply_payload.get("quality_metrics", {})
        self.assertTrue(quality.get("token_fallback_attempted"))
        self.assertGreaterEqual(int(quality.get("token_fallback_candidates", 0) or 0), 2)

        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("anchor_mismatch_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("token_fallback_attempt_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("token_fallback_ambiguous_count", 0) or 0), 1)

    def test_autofix_apply_semantic_guard_blocked_and_stats(self):
        self._force_single_internal_violation()
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p1_group = (analyze_payload.get("violations", {}) or {}).get("P1", [])[0]
        violation = (p1_group.get("violations") or [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": p1_group.get("object", "sample.ctl"),
                "event": p1_group.get("event", "Global"),
                "review": "",
                "issue_id": violation.get("issue_id", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
            },
        )
        self.assertEqual(prepare_status, 200)
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            self.assertIsNotNone(proposal)
            hunks = proposal.get("hunks", [])
            self.assertTrue(hunks and isinstance(hunks[0], dict))
            original_candidate = str(proposal.get("_candidate_content", ""))
            hunks[0]["replacement_text"] = 'main() { dpSet("A.B.D", 1); }'
            proposal["_candidate_content"] = original_candidate

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 409)
        self.assertEqual(apply_payload.get("error_code"), "SEMANTIC_GUARD_BLOCKED")
        quality = apply_payload.get("quality_metrics", {})
        self.assertFalse(bool(quality.get("semantic_check_passed", True)))
        self.assertGreaterEqual(int(quality.get("semantic_violation_count", 0) or 0), 1)
        self.assertIn("semantic guard blocked", str(quality.get("rejected_reason", "")).lower())

        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("semantic_guard_checked_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("semantic_guard_blocked_count", 0) or 0), 1)

    def test_autofix_apply_multi_hunk_success_and_stats(self):
        with open(os.path.join(self.data_dir, "sample.ctl"), "w", encoding="utf-8") as f:
            f.write("main()\n{\n  int a = 1;\n  int b = 2;\n  return;\n}\n")
        self._force_single_internal_violation()
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p1_group = (analyze_payload.get("violations", {}) or {}).get("P1", [])[0]
        violation = (p1_group.get("violations") or [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": p1_group.get("object", "sample.ctl"),
                "event": p1_group.get("event", "Global"),
                "review": "",
                "issue_id": violation.get("issue_id", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
            },
        )
        self.assertEqual(prepare_status, 200)
        with open(os.path.join(self.data_dir, "sample.ctl"), "r", encoding="utf-8", errors="ignore") as f:
            current_lines = f.read().splitlines()
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            self.assertIsNotNone(proposal)
            proposal["hunks"] = [
                {
                    "start_line": 3,
                    "end_line": 3,
                    "context_before": current_lines[1],
                    "context_after": current_lines[2],
                    "replacement_text": "  int a = 10;",
                },
                {
                    "start_line": 4,
                    "end_line": 4,
                    "context_before": current_lines[2],
                    "context_after": current_lines[3],
                    "replacement_text": "  int b = 20;",
                },
            ]
            proposal["_candidate_content"] = "main()\n{\n  int a = 10;\n  int b = 20;\n  return;\n}\n"

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 200)
        self.assertEqual((apply_payload.get("validation") or {}).get("apply_engine_mode"), "structure_apply")

        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("multi_hunk_attempt_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("multi_hunk_success_count", 0) or 0), 1)

    def test_autofix_apply_multi_hunk_overlap_blocked(self):
        with open(os.path.join(self.data_dir, "sample.ctl"), "w", encoding="utf-8") as f:
            f.write("main()\n{\n  int a = 1;\n  int b = 2;\n  return;\n}\n")
        self._force_single_internal_violation()
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": False, "mode": "Static"},
        )
        self.assertEqual(status, 200)
        p1_group = (analyze_payload.get("violations", {}) or {}).get("P1", [])[0]
        violation = (p1_group.get("violations") or [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": p1_group.get("object", "sample.ctl"),
                "event": p1_group.get("event", "Global"),
                "review": "",
                "issue_id": violation.get("issue_id", ""),
                "session_id": analyze_payload.get("output_dir", ""),
                "generator_preference": "rule",
            },
        )
        self.assertEqual(prepare_status, 200)
        with open(os.path.join(self.data_dir, "sample.ctl"), "r", encoding="utf-8", errors="ignore") as f:
            current_lines = f.read().splitlines()
        session = self.app._get_review_session(analyze_payload.get("output_dir", ""))
        with session["lock"]:
            proposal = session.get("autofix", {}).get("proposals", {}).get(prepare_payload.get("proposal_id"))
            self.assertIsNotNone(proposal)
            proposal["hunks"] = [
                {
                    "start_line": 3,
                    "end_line": 4,
                    "context_before": current_lines[1],
                    "context_after": current_lines[2],
                    "replacement_text": "  int a = 10;\n  int b = 20;",
                },
                {
                    "start_line": 4,
                    "end_line": 4,
                    "context_before": current_lines[2],
                    "context_after": current_lines[3],
                    "replacement_text": "  int b = 200;",
                },
            ]
            proposal["_candidate_content"] = "main()\n{\n  int a = 10;\n  int b = 200;\n  return;\n}\n"

        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
            },
        )
        self.assertEqual(apply_status, 409)
        self.assertEqual(apply_payload.get("error_code"), "APPLY_ENGINE_FAILED")
        quality = apply_payload.get("quality_metrics", {}) or {}
        self.assertEqual(quality.get("apply_engine_mode"), "failed")
        self.assertEqual(quality.get("apply_engine_fallback_reason"), "overlapping_hunks")

        stats_status, stats_payload = self._request(
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": analyze_payload.get("output_dir", "")}),
        )
        self.assertEqual(stats_status, 200)
        self.assertGreaterEqual(int(stats_payload.get("multi_hunk_attempt_count", 0) or 0), 1)
        self.assertGreaterEqual(int(stats_payload.get("multi_hunk_blocked_count", 0) or 0), 1)

    def test_autofix_apply_ctrlpp_regression_count_is_reported(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )

        original_run_check = self.app.ctrl_tool.run_check

        def fake_run_check(file_path, code_content=None, enabled=None, binary_path=None):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                text = str(code_content or "")
            if "[AI-AUTOFIX:" in text:
                return [
                    {
                        "type": "warning",
                        "severity": "warning",
                        "rule_id": "ctrlppcheck.test",
                        "line": 1,
                        "message": "mock ctrlpp regression",
                        "source": "CtrlppCheck",
                        "priority_origin": "P2",
                    }
                ]
            return []

        self.app.ctrl_tool.run_check = fake_run_check
        try:
            status, analyze_payload = self._request(
                "POST",
                "/api/analyze",
                {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
            )
            self.assertEqual(status, 200)
            ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
            prepare_status, prepare_payload = self._request(
                "POST",
                "/api/autofix/prepare",
                {
                    "file": "sample.ctl",
                    "object": ai_review.get("object", "sample.ctl"),
                    "event": ai_review.get("event", "Global"),
                    "review": ai_review.get("review", ""),
                    "session_id": analyze_payload.get("output_dir", ""),
                },
            )
            self.assertEqual(prepare_status, 200)

            apply_status, apply_payload = self._request(
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id"),
                    "session_id": analyze_payload.get("output_dir", ""),
                    "file": "sample.ctl",
                    "expected_base_hash": prepare_payload.get("base_hash"),
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                    "check_ctrlpp_regression": True,
                },
            )
            self.assertEqual(apply_status, 200)
            validation = apply_payload.get("validation", {})
            self.assertEqual(validation.get("ctrlpp_regression_count"), 1)
        finally:
            self.app.ctrl_tool.run_check = original_run_check

    def test_autofix_apply_ctrlpp_regression_check_real_binary_optional(self):
        if os.environ.get("RUN_CTRLPPCHECK_INTEGRATION", "").strip() != "1":
            self.skipTest("Set RUN_CTRLPPCHECK_INTEGRATION=1 to run CtrlppCheck integration test")
        binary = self.app.ctrl_tool._find_binary()
        if not binary:
            self.skipTest("CtrlppCheck binary not found")
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": analyze_payload.get("output_dir", ""),
            },
        )
        self.assertEqual(prepare_status, 200)
        apply_status, apply_payload = self._request(
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id"),
                "session_id": analyze_payload.get("output_dir", ""),
                "file": "sample.ctl",
                "expected_base_hash": prepare_payload.get("base_hash"),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
                "check_ctrlpp_regression": True,
            },
        )
        self.assertIn(apply_status, (200, 409))
        if apply_status == 200:
            self.assertIn("validation", apply_payload)
            self.assertIn("ctrlpp_regression_count", apply_payload.get("validation", {}))

    def test_autofix_session_ttl_eviction_returns_409(self):
        self._force_single_internal_violation()
        self.app.ai_tool.generate_review = lambda *_args, **_kwargs: (
            "요약: 조건 검증을 추가하세요.\n\n"
            "코드:\n```cpp\nif (isValid) {\n  return;\n}\n```"
        )
        status, analyze_payload = self._request(
            "POST",
            "/api/analyze",
            {"selected_files": ["sample.ctl"], "enable_live_ai": True, "mode": "AI 보조"},
        )
        self.assertEqual(status, 200)
        session_id = analyze_payload.get("output_dir", "")
        ai_review = analyze_payload.get("violations", {}).get("P3", [])[0]
        prepare_status, _prepare_payload = self._request(
            "POST",
            "/api/autofix/prepare",
            {
                "file": "sample.ctl",
                "object": ai_review.get("object", "sample.ctl"),
                "event": ai_review.get("event", "Global"),
                "review": ai_review.get("review", ""),
                "session_id": session_id,
            },
        )
        self.assertEqual(prepare_status, 200)
        session = self.app._get_review_session(session_id)
        self.assertIsNotNone(session)
        self.app.review_session_ttl_sec = 60
        session["last_accessed_at"] = 0

        diff_status, diff_payload = self._request(
            "GET",
            "/api/autofix/file-diff?" + urllib.parse.urlencode({"file": "sample.ctl", "session_id": session_id}),
        )
        self.assertEqual(diff_status, 409)
        self.assertIn("session cache", diff_payload.get("error", "").lower())

