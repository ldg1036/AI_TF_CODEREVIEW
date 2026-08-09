"""
UI 위반 필터링 및 파일 트리 요약 API 단위 테스트.
"""

from __future__ import annotations

import pytest
from app.ui.api import JSApi


@pytest.fixture
def sample_report_dict() -> dict:
    return {
        "violations": [
            {
                "violation_id": "V-001",
                "rule_id": "CTL_RES_001",
                "file_id": "scripts/main.ctl",
                "severity": "CRITICAL",
                "message": "connect without disconnect",
            },
            {
                "violation_id": "V-002",
                "rule_id": "CTL_PERF_001",
                "file_id": "scripts/sub/loop.ctl",
                "severity": "HIGH",
                "message": "infinite loop without delay",
            },
            {
                "violation_id": "V-003",
                "rule_id": "CTL_PERF_001",
                "file_id": "panels/main.pnl",
                "severity": "INFO",
                "message": "pnl connect info",
            },
            {
                "violation_id": "V-004",
                "rule_id": "CTL_ERR_001",
                "file_id": "panels/sub/dialog.pnl",
                "severity": "MEDIUM",
                "message": "no try catch",
            },
        ]
    }


class TestUIFiltering:
    """filter_review_results 및 get_file_tree_summary 단위 테스트."""

    def setup_method(self):
        self.api = JSApi()

    def test_filter_by_severities(self, sample_report_dict):
        res = self.api.filter_review_results(
            sample_report_dict, severities=["CRITICAL", "HIGH"]
        )
        assert res["success"] is True
        assert res["total_violations"] == 2
        ids = [v["violation_id"] for v in res["violations"]]
        assert "V-001" in ids and "V-002" in ids
        assert "V-003" not in ids and "V-004" not in ids
        assert res["severity_counts"]["CRITICAL"] == 1
        assert res["severity_counts"]["HIGH"] == 1
        assert res["severity_counts"]["MEDIUM"] == 0

    def test_filter_by_rule_id(self, sample_report_dict):
        res = self.api.filter_review_results(
            sample_report_dict, rule_id="CTL_PERF_001"
        )
        assert res["success"] is True
        assert res["total_violations"] == 2
        assert all(v["rule_id"] == "CTL_PERF_001" for v in res["violations"])

    def test_filter_by_path_prefix(self, sample_report_dict):
        res = self.api.filter_review_results(
            sample_report_dict, path_prefix="scripts/"
        )
        assert res["success"] is True
        assert res["total_violations"] == 2
        assert all(str(v["file_id"]).startswith("scripts/") for v in res["violations"])

    def test_filter_combined(self, sample_report_dict):
        res = self.api.filter_review_results(
            sample_report_dict,
            severities=["HIGH", "INFO"],
            path_prefix="panels/",
        )
        assert res["success"] is True
        assert res["total_violations"] == 1
        assert res["violations"][0]["violation_id"] == "V-003"

    def test_file_tree_summary_hierarchy(self, sample_report_dict):
        res = self.api.get_file_tree_summary(sample_report_dict)
        assert res["success"] is True
        assert res["total_files"] == 4
        assert res["total_violations"] == 4

        tree = res["tree"]
        names = [item["name"] for item in tree]
        assert "scripts" in names
        assert "panels" in names

        # scripts 노드 확인 (위반 2건: main.ctl 1건, sub/loop.ctl 1건)
        scripts_node = next(n for n in tree if n["name"] == "scripts")
        assert scripts_node["type"] == "dir"
        assert scripts_node["violation_count"] == 2
        child_names = [c["name"] for c in scripts_node["children"]]
        assert "main.ctl" in child_names
        assert "sub" in child_names
