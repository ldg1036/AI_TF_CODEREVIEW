from ._api_integration_test_base import *
from ._api_integration_test_base import _require_openpyxl


class ReportQualityCasesMixin:
    def setUp(self):
        self.project_root = PROJECT_ROOT
        self.config_dir = os.path.join(self.project_root, "Config")
        self.tmp_dir = tempfile.TemporaryDirectory()

        self.reporter = Reporter(config_dir=self.config_dir)
        self.reporter.output_dir = self.tmp_dir.name
        os.makedirs(self.reporter.output_dir, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    @staticmethod
    def _find_header_col(ws, header_text, default):
        for r in range(1, min(ws.max_row, 40) + 1):
            for c in range(1, min(ws.max_column, 20) + 1):
                value = str(ws.cell(r, c).value or "").strip()
                if header_text in value:
                    return c
        return default

    @staticmethod
    def _find_status_col(ws):
        return ReportQualityCasesMixin._find_header_col(ws, "1차 검증", 6)

    def _sample_report_data(self):
        return {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-02-test1",
                            "rule_id": "PERF-02",
                            "rule_item": "DP Query 최적화 구현",
                            "priority_origin": "P1",
                            "severity": "Critical",
                            "line": 1,
                            "message": "query scope too wide",
                        },
                        {
                            "issue_id": "P1-UNKNOWN-test2",
                            "rule_id": "UNKNOWN-99",
                            "rule_item": "non-matching-item",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 2,
                            "message": "unmatched violation",
                        },
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }

    def _sample_report_with_p2_only(self):
        return {
            "file": "sample.ctl",
            "internal_violations": [],
            "global_violations": [
                {
                    "rule_id": "PERF-02",
                    "line": 10,
                    "message": "p2 only finding",
                    "severity": "warning",
                    "source": "CtrlppCheck",
                }
            ],
            "ai_reviews": [],
        }

    @staticmethod
    def _find_item_row(ws, item_text):
        for r in range(1, ws.max_row + 1):
            if str(ws.cell(r, 4).value or "").strip() == item_text:
                return r
        return None

    def _status_and_message_for_item(self, ws, item_text):
        row = self._find_item_row(ws, item_text)
        self.assertIsNotNone(row, item_text)
        status_col = self._find_status_col(ws)
        review_col = self._find_header_col(ws, "검증 결과", 7)
        return row, ws.cell(row, status_col).value, str(ws.cell(row, review_col).value or "").strip()

    def test_html_report_contains_rows_and_severity_class(self):
        data = self._sample_report_data()
        self.reporter.generate_html_report(
            data,
            "quality.html",
            report_meta={
                "verification_level": "CORE+REPORT",
                "optional_dependencies": {"openpyxl": {"available": False}},
            },
        )
        report_path = os.path.join(self.reporter.output_dir, "quality.html")

        self.assertTrue(os.path.exists(report_path))
        with open(report_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("<table>", html)
        self.assertIn('class="critical"', html)
        self.assertIn("query scope too wide", html)
        self.assertIn("검증 레벨", html)
        self.assertIn("CORE+REPORT", html)

    def test_excel_report_creates_unmatched_sheet_and_marks_ng(self):
        _require_openpyxl(self)
        data = self._sample_report_data()
        output_name = "quality.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)

        output_path = os.path.join(self.reporter.output_dir, output_name)
        self.assertTrue(os.path.exists(output_path))

        load_workbook = _require_openpyxl(self)

        wb = load_workbook(output_path)
        active = wb.active
        status_col = self._find_status_col(active)
        col_values = [active.cell(row=r, column=status_col).value for r in range(1, active.max_row + 1)]
        self.assertIn("NG", col_values)
        self.assertIn("미분류_위반사항", wb.sheetnames)

    def test_excel_template_sheet_writes_primary_status_to_f_and_guidance_to_g(self):
        load_workbook = _require_openpyxl(self)
        data = self._sample_report_data()
        output_name = "quality_template_columns.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)

        output_path = os.path.join(self.reporter.output_dir, output_name)
        wb = load_workbook(output_path)
        active = wb.active

        template_path = os.path.join(self.config_dir, self.reporter.SERVER_TEMPLATE)
        template_wb = load_workbook(template_path)
        template_ws = template_wb.active

        primary_col = self._find_status_col(active)
        review_col = self._find_header_col(active, "검증 결과", 7)
        remarks_col = self._find_header_col(active, "비고", 8)

        target_row = None
        for row in range(18, active.max_row + 1):
            if str(active.cell(row, primary_col).value or "").strip() == "NG":
                target_row = row
                break

        self.assertIsNotNone(target_row)
        self.assertEqual(primary_col, 6)
        self.assertEqual(review_col, 7)
        self.assertEqual(remarks_col, 8)
        self.assertIn(active.cell(target_row, primary_col).value, {"NG", "OK", "N/A"})
        self.assertTrue(str(active.cell(target_row, review_col).value or "").strip())
        self.assertEqual(
            active.cell(target_row, remarks_col).value,
            template_ws.cell(target_row, remarks_col).value,
        )

    def test_excel_report_returns_timing_metrics_and_template_cache_hits(self):
        _require_openpyxl(self)
        data = self._sample_report_data()
        first = self.reporter.fill_excel_checklist(data, file_type="Server", output_filename="quality_cache_1.xlsx")
        second = self.reporter.fill_excel_checklist(data, file_type="Server", output_filename="quality_cache_2.xlsx")
        self.assertIsInstance(first, dict)
        self.assertIsInstance(second, dict)
        self.assertTrue(first.get("generated"))
        self.assertTrue(second.get("generated"))
        self.assertIn("timings_ms", first)
        self.assertIn("copy", (first.get("timings_ms") or {}))
        self.assertIn("load", (first.get("timings_ms") or {}))
        self.assertIn("save", (first.get("timings_ms") or {}))
        self.assertTrue(second.get("template_cache_hit"))

    def test_excel_submission_contains_detail_and_verify_sheets(self):
        data = self._sample_report_data()
        output_name = "quality_sheets.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)

        load_workbook = _require_openpyxl(self)

        output_path = os.path.join(self.reporter.output_dir, output_name)
        wb = load_workbook(output_path)
        self.assertIn("상세결과", wb.sheetnames)
        self.assertIn("검증 결과", wb.sheetnames)
        self.assertIn("CtrlppCheck_결과", wb.sheetnames)

    def test_ctrlpp_sheet_exists_and_checklist_ignores_p2_for_status(self):
        data = self._sample_report_with_p2_only()
        output_name = "quality_p2_only.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)

        load_workbook = _require_openpyxl(self)

        output_path = os.path.join(self.reporter.output_dir, output_name)
        wb = load_workbook(output_path)
        self.assertIn("CtrlppCheck_결과", wb.sheetnames)
        ctrlpp_ws = wb["CtrlppCheck_결과"]
        self.assertGreaterEqual(ctrlpp_ws.max_row, 2)

        active = wb.active
        target_row = None
        for r in range(1, active.max_row + 1):
            if active.cell(r, 4).value == "DP Query 최적화 구현":
                target_row = r
                break
        self.assertIsNotNone(target_row)
        # P2 only finding must not flip checklist body result to NG.
        status_col = self._find_status_col(active)
        self.assertNotEqual(active.cell(target_row, status_col).value, "NG")

    def test_checklist_event_exchange_turns_ng_when_perf_ev_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-EV-01-1",
                            "rule_id": "PERF-EV-01",
                            "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 10,
                            "message": "loop dpset burst",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_event_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "Event, Ctrl Manager 이벤트 교환 횟수 최소화")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_style_item_turns_ng_when_style_rules_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-STYLE-NAME-01-1",
                            "rule_id": "STYLE-NAME-01",
                            "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                            "priority_origin": "P1",
                            "severity": "Low",
                            "line": 2,
                            "message": "name style",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_style_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "명명 규칙 및 코딩 스타일 준수 확인")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_unnecessary_code_turns_ng_when_clean_rules_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-CLEAN-DEAD-01-1",
                            "rule_id": "CLEAN-DEAD-01",
                            "rule_item": "불필요한 코드 지양",
                            "priority_origin": "P1",
                            "severity": "Medium",
                            "line": 20,
                            "message": "dead code",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_clean_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "불필요한 코드 지양")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_config_item_turns_ng_when_cfg_rules_found(self):
        data = {
            "file": "sample_config.ctl",
            "internal_violations": [
                {
                    "object": "sample_config.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-CFG-01-1",
                            "rule_id": "CFG-01",
                            "rule_item": "config 항목 정합성 확인",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 12,
                            "message": "cfg mismatch",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_cfg_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "config 항목 정합성 확인")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_event_item_turns_ng_when_dpget_batch_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-DPGET-BATCH-01-1",
                            "rule_id": "PERF-DPGET-BATCH-01",
                            "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 30,
                            "message": "dpget batch",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_event_dpget_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "Event, Ctrl Manager 이벤트 교환 횟수 최소화")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_event_item_turns_ng_when_dpset_batch_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-DPSET-BATCH-01-1",
                            "rule_id": "PERF-DPSET-BATCH-01",
                            "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 31,
                            "message": "dpset batch",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_event_dpset_batch_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "Event, Ctrl Manager 이벤트 교환 횟수 최소화")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_config_item_turns_ng_when_safe_div_found(self):
        data = {
            "file": "sample_config.ctl",
            "internal_violations": [
                {
                    "object": "sample_config.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-SAFE-DIV-01-1",
                            "rule_id": "SAFE-DIV-01",
                            "rule_item": "config 항목 정합성 확인",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 31,
                            "message": "safe div",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_cfg_safe_div_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "config 항목 정합성 확인")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_event_item_turns_ng_when_setvalue_batch_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-SETVALUE-BATCH-01-1",
                            "rule_id": "PERF-SETVALUE-BATCH-01",
                            "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 31,
                            "message": "setvalue batch",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_event_setvalue_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "Event, Ctrl Manager 이벤트 교환 횟수 최소화")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_event_item_turns_ng_when_setmultivalue_adopt_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-SETMULTIVALUE-ADOPT-01-1",
                            "rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
                            "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 32,
                            "message": "setmultivalue adopt",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_event_setmultivalue_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "Event, Ctrl Manager 이벤트 교환 횟수 최소화")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_event_item_turns_ng_when_getvalue_batch_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-GETVALUE-BATCH-01-1",
                            "rule_id": "PERF-GETVALUE-BATCH-01",
                            "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                            "priority_origin": "P1",
                            "severity": "Warning",
                            "line": 33,
                            "message": "getvalue batch",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_event_getvalue_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "Event, Ctrl Manager 이벤트 교환 횟수 최소화")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_style_item_turns_ng_when_style_idx_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-STYLE-IDX-01-1",
                            "rule_id": "STYLE-IDX-01",
                            "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                            "priority_origin": "P1",
                            "severity": "Low",
                            "line": 33,
                            "message": "index style",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_style_idx_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "명명 규칙 및 코딩 스타일 준수 확인")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_checklist_hardcoding_turns_ng_when_hard03_found(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-HARD-03-1",
                            "rule_id": "HARD-03",
                            "rule_item": "하드코딩 지양",
                            "priority_origin": "P1",
                            "severity": "Medium",
                            "line": 40,
                            "message": "float literal",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_hard03_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        row = self._find_item_row(ws, "하드코딩 지양")
        self.assertIsNotNone(row)
        status_col = self._find_status_col(ws)
        self.assertEqual(ws.cell(row, status_col).value, "NG")

    def test_loop_checklist_returns_na_when_while_pattern_missing(self):
        data = {
            "file": "sample.ctl",
            "source_code": "main()\n{\n  return;\n}\n",
            "internal_violations": [],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_loop_na.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        _, status, message = self._status_and_message_for_item(ws, "Loop문 내에 처리 조건")
        self.assertEqual(status, "N/A")
        self.assertEqual(message, self.reporter.PATTERN_NOT_FOUND_MESSAGE)

    def test_loop_checklist_returns_ok_when_while_pattern_present_without_findings(self):
        data = {
            "file": "sample.ctl",
            "source_code": "main()\n{\n  while (TRUE)\n  {\n    if (isActive)\n    {\n      foo();\n    }\n    delay(1);\n  }\n}\n",
            "internal_violations": [],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_loop_ok.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        _, status, message = self._status_and_message_for_item(ws, "Loop문 내에 처리 조건")
        self.assertEqual(status, "OK")
        self.assertEqual(message, "")

    def test_loop_checklist_turns_ng_when_active_delay_rule_found(self):
        data = {
            "file": "sample.ctl",
            "source_code": "main()\n{\n  while (TRUE)\n  {\n    if (isActive)\n    {\n      delay(1);\n    }\n  }\n}\n",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-PERF-03-ACTIVE-DELAY-01-1",
                            "rule_id": "PERF-03-ACTIVE-DELAY-01",
                            "rule_item": "Loop문 내에 처리 조건",
                            "priority_origin": "P1",
                            "severity": "Critical",
                            "line": 5,
                            "message": "while loop delay may exist only inside Active guard.",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_loop_active_ng.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        _, status, message = self._status_and_message_for_item(ws, "Loop문 내에 처리 조건")
        self.assertEqual(status, "NG")
        self.assertIn("PERF-03-ACTIVE-DELAY-01", message)

    def test_partial_automation_items_return_na_guidance_without_findings(self):
        data = {
            "file": "sample.ctl",
            "source_code": "main()\n{\n  dyn_string items;\n  const int sample = 10;\n  return;\n}\n",
            "internal_violations": [],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_partial_automation.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        for item_text in ("메모리 누수 체크", "하드코딩 지양", "디버깅용 로그 작성 확인"):
            _, status, message = self._status_and_message_for_item(ws, item_text)
            self.assertEqual(status, "N/A")
            self.assertEqual(message, self.reporter.PARTIAL_AUTOMATION_MESSAGE)

    def test_query_comment_item_returns_manual_guidance_without_findings(self):
        data = {
            "file": "sample.ctl",
            "source_code": "main()\n{\n  string query = \"SELECT * FROM table\";\n}\n",
            "internal_violations": [],
            "global_violations": [],
            "ai_reviews": [],
        }
        output_name = "quality_query_comment_manual.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)
        load_workbook = _require_openpyxl(self)

        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        ws = wb.active
        _, status, message = self._status_and_message_for_item(ws, "쿼리 주석 처리")
        self.assertEqual(status, "N/A")
        self.assertEqual(message, self.reporter.MANUAL_REVIEW_MESSAGE)


    def test_excel_report_writes_verification_meta_sheet(self):
        _require_openpyxl(self)
        data = self._sample_report_data()
        output_name = "quality_verify_meta.xlsx"
        self.reporter.fill_excel_checklist(
            data,
            file_type="Server",
            output_filename=output_name,
            report_meta={
                "verification_level": "CORE+REPORT",
                "optional_dependencies": {"openpyxl": {"available": True}},
            },
        )

        load_workbook = _require_openpyxl(self)
        wb = load_workbook(os.path.join(self.reporter.output_dir, output_name))
        self.assertIn("검증메타", wb.sheetnames)
        ws = wb["검증메타"]
        rows = {str(ws.cell(r, 1).value): str(ws.cell(r, 2).value) for r in range(2, ws.max_row + 1)}
        self.assertEqual(rows.get("verification_level"), "CORE+REPORT")
        self.assertEqual(rows.get("openpyxl"), "available")

    def test_detail_sheet_row_count_matches_findings(self):
        data = self._sample_report_data()
        output_name = "quality_detail_rows.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)

        load_workbook = _require_openpyxl(self)

        output_path = os.path.join(self.reporter.output_dir, output_name)
        wb = load_workbook(output_path)
        ws = wb["상세결과"]
        detail_rows = ws.max_row - 1
        self.assertEqual(detail_rows, 2)

    def test_verify_sheet_columns_and_status_values(self):
        data = self._sample_report_data()
        output_name = "quality_verify_sheet.xlsx"
        self.reporter.fill_excel_checklist(data, file_type="Server", output_filename=output_name)

        load_workbook = _require_openpyxl(self)

        output_path = os.path.join(self.reporter.output_dir, output_name)
        wb = load_workbook(output_path)
        ws = wb["검증 결과"]

        headers = [ws.cell(1, c).value for c in range(1, 9)]
        self.assertEqual(headers, ["No", "대분류", "중분류", "소분류", "검증 조건", "1차 검증", "검증 결과", "비고"])

        status_values = [
            ws.cell(r, 6).value
            for r in range(2, ws.max_row + 1)
            if ws.cell(r, 6).value is not None
        ]
        self.assertGreater(len(status_values), 0)
        for status in status_values:
            self.assertIn(status, {"NG", "OK", "N/A"})

        guidance_values = [
            str(ws.cell(r, 7).value or "").strip()
            for r in range(2, ws.max_row + 1)
            if str(ws.cell(r, 6).value or "").strip() == "NG"
        ]
        self.assertTrue(any(guidance_values))

        remarks_values = [str(ws.cell(r, 8).value or "").strip() for r in range(2, ws.max_row + 1)]
        self.assertTrue(all(not value for value in remarks_values))

    def test_annotated_txt_inserts_review_comments(self):
        data = self._sample_report_data()
        source = "line1\nline2\nline3"
        self.reporter.generate_annotated_txt(source, data, "annotated.txt")

        output_path = os.path.join(self.reporter.output_dir, "annotated.txt")
        self.assertTrue(os.path.exists(output_path))

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("// >>TODO", content)
        self.assertNotIn("// [REVIEW]", content)
        self.assertNotIn("// [META]", content)

    def test_annotated_txt_inserts_todo_and_comment_above_line(self):
        data = self._sample_report_data()
        source = "line1\nline2\nline3"
        self.reporter.generate_annotated_txt(source, data, "annotated_order.txt")

        output_path = os.path.join(self.reporter.output_dir, "annotated_order.txt")
        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        idx_todo = lines.index("// >>TODO")
        idx_msg = idx_todo + 1
        idx_code = lines.index("line1")

        self.assertTrue(lines[idx_msg].startswith("// "))
        self.assertLess(idx_todo, idx_code)
        self.assertLess(idx_msg, idx_code)
        self.assertFalse(any(line.startswith("// [REVIEW]") for line in lines))
        self.assertFalse(any(line.startswith("// [META]") for line in lines))

    def test_annotated_txt_keeps_single_human_comment_line(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-HARD-1",
                            "rule_id": "HARD-01",
                            "severity": "Medium",
                            "line": 1,
                            "message": "IP/URL/설정 경로 하드코딩 감지.",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        self.reporter.generate_annotated_txt("line1", data, "annotated_dedup.txt")
        output_path = os.path.join(self.reporter.output_dir, "annotated_dedup.txt")
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("// IP/URL/설정 경로 하드코딩 감지.", content)
        self.assertNotIn("// [REVIEW]", content)
        self.assertNotIn("// [META]", content)
        self.assertNotIn("// // 설정 파일 또는 상수로 대체 권장", content)

    def test_annotated_txt_inserts_only_ai_code_lines_for_accepted_ai_review(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "TankMgr",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-CFG-1",
                            "rule_id": "CFG-01",
                            "severity": "Warning",
                            "line": 1,
                            "message": "config 파싱 형식 불일치 가능성, delimiter/필드수 검증 권장.",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [
                {
                    "file": "sample.ctl",
                    "object": "TankMgr",
                    "event": "Global",
                    "status": "Accepted",
                    "review": "요약: config 파싱 검증을 추가하세요.\n\n코드:\n```cpp\nif (parts.size() != 6) {\n  return;\n}\n```",
                }
            ],
        }
        self.reporter.generate_annotated_txt("line1", data, "annotated_ai_code.txt")
        output_path = os.path.join(self.reporter.output_dir, "annotated_ai_code.txt")
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("// [AI CODE] if (parts.size() != 6) {", content)
        self.assertIn("// [AI CODE]   return;", content)
        self.assertNotIn("// [AI REVIEW]", content)
        self.assertNotIn("요약:", content)

    def test_unused_variable_comment_message_format(self):
        data = {
            "file": "sample.ctl",
            "internal_violations": [
                {
                    "object": "sample.ctl",
                    "event": "Global",
                    "violations": [
                        {
                            "issue_id": "P1-UNUSED-1",
                            "rule_id": "UNUSED-01",
                            "rule_item": "불필요한 코드 지양",
                            "priority_origin": "P1",
                            "severity": "Low",
                            "line": 2,
                            "message": "미사용 변수 감지: 'ip'",
                        }
                    ],
                }
            ],
            "global_violations": [],
            "ai_reviews": [],
        }
        source = "line1\n  string ip = \"192.168.0.1\";\nline3"
        self.reporter.generate_annotated_txt(source, data, "annotated_unused.txt")

        output_path = os.path.join(self.reporter.output_dir, "annotated_unused.txt")
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("// 미사용 변수 감지: ip", content)
        self.assertNotIn("// [REVIEW]", content)
        self.assertNotIn("// [META]", content)

    def test_duplicate_block_rule_message_matches_line_based_detection(self):
        from backend.core.heuristic_checker import HeuristicChecker

        checker = HeuristicChecker()
        code = "\n".join(
            [
                "main() {",
                "  totalValue = 1;",
                "  totalValue = 1;",
                "  totalValue = 1;",
                "}",
            ]
        )
        findings = checker.check_duplicate_blocks(code)
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].get("rule_id"), "CLEAN-DUP-01")
        self.assertEqual(findings[0].get("message"), "동일 코드 라인 반복(3회 이상) 감지.")


if __name__ == "__main__":
    unittest.main()
