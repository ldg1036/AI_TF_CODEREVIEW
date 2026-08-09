"""
Phase 3 이전 검사 리포트 대비 트렌드(Trend) 통계 API 단위 테스트.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.ui.api import JSApi


class TestReviewTrend:
    """이전 리포트 대비 위반 증감(신규/해결/유지) 대조 테스트."""

    def test_trend_no_previous_report(self, tmp_path: Path):
        api = JSApi()
        api.output_dir = tmp_path / "output_none"

        curr_rep = {
            "run_id": "run-001",
            "violations": [
                {"rule_id": "CTL_01", "file_id": "a.ctl", "line_start": 10, "severity": "HIGH"},
            ],
        }

        res = api.get_review_trend(curr_rep)
        assert res["success"] is True
        assert res["has_previous"] is False
        assert res["new_count"] == 1
        assert res["resolved_count"] == 0

    def test_trend_with_previous_report(self, tmp_path: Path):
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 직전 리포트 (prev) 저장
        prev_rep = {
            "run_id": "run-001",
            "violations": [
                {"rule_id": "CTL_01", "file_id": "a.ctl", "line_start": 10, "severity": "HIGH"},
                {"rule_id": "CTL_02", "file_id": "a.ctl", "line_start": 20, "severity": "MEDIUM"},  # 이 항목은 이번에 해결됨
            ],
        }
        prev_file = output_dir / "run-001_review_report.json"
        prev_file.write_text(json.dumps(prev_rep, ensure_ascii=False), encoding="utf-8")
        # 10초 전 시간으로 설정하여 윈도우 mtime 순서 확실히 보장
        past_time = time.time() - 10
        os.utime(prev_file, (past_time, past_time))

        # 현재 리포트 (curr)
        curr_rep = {
            "run_id": "run-002",
            "violations": [
                {"rule_id": "CTL_01", "file_id": "a.ctl", "line_start": 10, "severity": "HIGH"},  # 유지 (unchanged)
                {"rule_id": "CTL_03", "file_id": "b.ctl", "line_start": 5, "severity": "CRITICAL"},  # 신규 (new)
            ],
        }
        curr_file = output_dir / "run-002_review_report.json"
        curr_file.write_text(json.dumps(curr_rep, ensure_ascii=False), encoding="utf-8")

        api = JSApi()
        api.output_dir = output_dir
        res = api.get_review_trend(curr_rep)

        assert res["success"] is True


        assert res["has_previous"] is True
        assert res["new_count"] == 1        # CTL_03
        assert res["resolved_count"] == 1   # CTL_02 (해결됨)
        assert res["unchanged_count"] == 1  # CTL_01 (유지됨)
        assert res["new_violations"][0]["rule_id"] == "CTL_03"
        assert res["resolved_violations"][0]["rule_id"] == "CTL_02"
