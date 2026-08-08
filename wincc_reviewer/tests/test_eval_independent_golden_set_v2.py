"""
test_eval_independent_golden_set_v2.py

evaluate_independent_golden_set_v2 평가 파이프라인 유닛 테스트 (R2 호출부 증명)
"""

from __future__ import annotations

import importlib


class TestEvalIndependentGoldenSetV2:
    """독립 골든셋 v2 평가 기능 검증"""

    def test_evaluate_independent_golden_set_v2_execution(self):
        mod = importlib.import_module("scripts.20_eval_independent_golden_set_v2")
        metrics = mod.evaluate_independent_golden_set_v2()
        assert metrics is not None
        assert metrics["cohen_kappa_agreement"] >= 0.85
        assert metrics["target_precision_percent"] >= 85.0
