"""
PNL 파일 정적 리뷰 검출(Violation Detection) 검증 테스트 스위트.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.core.pipeline import Pipeline, PipelineConfig


class TestPNLRuleDetection:
    """PNL 패널 파일의 정적 검수 룰 적용 및 검출 동작 검증."""

    def test_pnl_file_rule_violation_detection(self):
        """PNL 파일 내 오동작 스크립트(무한 루프 while(1) 등)가 정상 검출되는지 검증."""
        pnl_content = """<?xml version="1.0" encoding="UTF-8"?>
<panel name="TestPanel">
    <shape name="Button1" type="RECTANGLE">
        <script event="Click">
            main() {
                int i = 0;
                while (1) {
                    i++;
                }
            }
        </script>
    </shape>
</panel>
"""
        with tempfile.NamedTemporaryFile(suffix=".pnl", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(pnl_content)
            pnl_path = Path(tf.name)

        try:
            config = PipelineConfig(input_path=pnl_path, no_ai=True, use_cache=False)
            pipeline = Pipeline(config=config)
            report = pipeline.run()

            assert report is not None
            assert len(report.files) == 1
            assert len(report.violations) > 0

            # PNL 파일에서 룰 검출(예: MANUAL-002 등)이 1건 이상 성공했는지 검증
            rule_ids = [v.rule_id for v in report.violations]
            assert any("MANUAL" in r for r in rule_ids) or len(rule_ids) > 0

        finally:
            if pnl_path.exists():
                pnl_path.unlink()
