import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tools.mine_todo_rules import mine_todo_rules


class TodoRuleMiningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_text(self, rel_path: str, text: str, encoding: str = "utf-8"):
        path = self.input_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)
        return path

    def test_detect_todo_case_insensitive(self):
        self._write_text(
            "a.txt",
            "\n".join(
                [
                    "// TODO: first",
                    "// todo: second",
                    "// ToDo: third",
                ]
            ),
        )

        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir))
        summary = result["summary"]
        self.assertEqual(summary["todo_file_count"], 1)
        self.assertEqual(summary["total_todo_lines"], 3)

    def test_inline_todo_comment_detected(self):
        self._write_text("b.txt", "int a; // todo: remove variable")
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir))
        self.assertEqual(result["summary"]["todo_file_count"], 1)
        row = result["manifest_rows"][0]
        self.assertEqual(row["todo_count"], 1)
        self.assertEqual(row["todo_lines"][0]["line_no"], 1)

    def test_non_todo_not_detected(self):
        self._write_text("c.txt", "int a = 1; // comment only")
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir))
        self.assertEqual(result["summary"]["todo_file_count"], 0)
        self.assertEqual(result["summary"]["candidate_count"], 0)

    def test_copy_preserves_relative_path(self):
        self._write_text("nested/deep/d.txt", "// todo: check this")
        mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir), copy_files=True)
        copied = self.output_dir / "todo_files" / "nested" / "deep" / "d.txt"
        self.assertTrue(copied.exists())

    def test_encoding_fallback_cp949(self):
        path = self.input_dir / "cp949.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "// todo : 미사용 변수"
        path.write_bytes(text.encode("cp949"))

        result = mine_todo_rules(
            str(self.input_dir),
            output_dir=str(self.output_dir),
            encoding_fallback=("utf-8", "cp949"),
        )
        self.assertEqual(result["summary"]["todo_file_count"], 1)
        self.assertEqual(result["manifest_rows"][0]["encoding"].lower(), "cp949")

    def test_rule_candidate_grouping_and_frequency(self):
        self._write_text("f1.txt", "// TODO: 미사용 변수 제거")
        self._write_text("f2.txt", "// todo: 미사용 변수 제거")
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir), min_frequency=1)
        candidates = result["candidate_rows"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["frequency"], 2)

    def test_static_rule_feasible_flag(self):
        self._write_text("g1.txt", "// todo: 미사용 변수 삭제")
        self._write_text("g2.txt", "// todo: 용도 확인 필요?")
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir), min_frequency=1)
        candidates = result["candidate_rows"]
        by_norm = {c["normalized_todo_text"]: c for c in candidates}

        usable = next(v for k, v in by_norm.items() if "미사용 변수" in k)
        manual = next(v for k, v in by_norm.items() if "용도 확인 필요" in k)

        self.assertTrue(usable["static_rule_feasible"])
        self.assertEqual(usable["suggested_rule_id"], "UNUSED-01")
        self.assertFalse(manual["static_rule_feasible"])
        self.assertEqual(manual["suggested_detection_strategy"], "manual")
        self.assertTrue(manual["suggested_rule_id"].startswith("NEW-"))


    def test_rule_mapping_for_sentence_style_setvalue_getvalue_todos(self):
        self._write_text(
            "h1.txt",
            "// TODO: bool_enabled -> bool 타입으로 마지막 하나 enable 만 가지고 할껀데, getvalue 를 다 하는 이유?",
        )
        self._write_text(
            "h2.txt",
            "// TODO: return 값이 true 가 아닌경우 별도로 dpset 해주는 하는 이유? object 명 동일하다면 setvalue 권장",
        )
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir), min_frequency=1)
        by_norm = {c["normalized_todo_text"]: c for c in result["candidate_rows"]}

        getvalue_row = next(v for k, v in by_norm.items() if "getvalue" in k)
        setvalue_row = next(v for k, v in by_norm.items() if "setvalue" in k)

        self.assertEqual(getvalue_row["suggested_rule_id"], "PERF-GETVALUE-BATCH-01")
        self.assertEqual(setvalue_row["suggested_rule_id"], "PERF-SETVALUE-BATCH-01")

    def test_rule_mapping_for_dpset_and_dpquery_todos(self):
        self._write_text("i1.txt", "// TODO: dpSet 일괄 처리")
        self._write_text("i2.txt", "// TODO: dpquery 최적화 from * 지양 테스트 필요")
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir), min_frequency=1)
        by_norm = {c["normalized_todo_text"]: c for c in result["candidate_rows"]}

        dpset_row = next(v for k, v in by_norm.items() if "dpset" in k)
        dpquery_row = next(v for k, v in by_norm.items() if "dpquery" in k)
        self.assertEqual(dpset_row["suggested_rule_id"], "PERF-DPSET-BATCH-01")
        self.assertEqual(dpquery_row["suggested_rule_id"], "PERF-02")

class TodoRuleMiningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_text(self, rel_path: str, text: str):
        path = self.input_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_new_todo_policy_outputs_two_fixed_categories(self):
        self._write_text("manual.txt", "// TODO: reason 확인 필요?")
        self._write_text("auto.txt", "// TODO: custom static candidate")
        result = mine_todo_rules(str(self.input_dir), output_dir=str(self.output_dir), min_frequency=1)

        policy_rows = result["new_todo_policy_rows"]
        self.assertGreaterEqual(len(policy_rows), 1)
        categories = {row["category"] for row in policy_rows}
        self.assertTrue(categories.issubset({"정적화 대상", "수동 검토 유지"}))
        self.assertTrue((self.output_dir / "new_todo_policy.json").exists())
        self.assertTrue((self.output_dir / "new_todo_policy.csv").exists())


if __name__ == "__main__":
    unittest.main()
