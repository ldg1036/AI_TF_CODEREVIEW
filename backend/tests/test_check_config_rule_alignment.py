import json
import tempfile
import unittest
from pathlib import Path

from backend.tools.check_config_rule_alignment import run


class CheckConfigRuleAlignmentTests(unittest.TestCase):
    def _write_json(self, path: Path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_repo_fixture(self, root: Path, review_items: dict, p1_rows: list[dict]):
        config_dir = root / "Config"
        config_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(config_dir / "parsed_rules.json", [])
        self._write_json(config_dir / "p1_rule_defs.json", p1_rows)
        self._write_json(
            config_dir / "review_applicability.json",
            {
                "manual_only_items": [],
                "manual_condition_keywords": [],
                "items": review_items,
            },
        )

    def test_detects_broken_duplicate_and_unknown_review_applicability_items(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_repo_fixture(
                root,
                review_items={
                    "???? ??": {"required_rule_ids": ["RULE-01"]},
                    "정상 항목 A": {"required_rule_ids": ["RULE-02", "RULE-03"]},
                    "정상 항목 B": {"required_rule_ids": ["RULE-03", "RULE-02"]},
                    "미참조 항목": {"required_rule_ids": ["UNKNOWN-99"]},
                },
                p1_rows=[
                    {"rule_id": "RULE-01", "enabled": True},
                    {"rule_id": "RULE-02", "enabled": True},
                    {"rule_id": "RULE-03", "enabled": True},
                ],
            )

            result = run(root)

            self.assertEqual(result["summary"]["review_applicability_broken_key_count"], 1)
            self.assertEqual(result["summary"]["review_applicability_duplicate_semantic_count"], 1)
            self.assertEqual(result["summary"]["review_applicability_unknown_rule_id_count"], 1)

    def test_collects_nested_rule_id_fields_from_p1_defs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_repo_fixture(
                root,
                review_items={
                    "복잡도": {"required_rule_ids": ["COMP-01", "COMP-02"]},
                },
                p1_rows=[
                    {
                        "id": "legacy-check_complexity",
                        "enabled": True,
                        "detector": {
                            "kind": "composite",
                            "line_rule_id": "COMP-01",
                            "depth_rule_id": "COMP-02",
                        },
                    }
                ],
            )

            result = run(root)

            self.assertEqual(result["summary"]["review_applicability_unknown_rule_id_count"], 0)


if __name__ == "__main__":
    unittest.main()
