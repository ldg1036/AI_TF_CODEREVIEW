"""
test_build_anonymized_fixtures.py

build_anonymized_fixtures 파이프라인 유닛 테스트 (R2 호출부 증명)
"""

from __future__ import annotations

import importlib


class TestBuildAnonymizedFixtures:
    """익명화 픽스처 파이프라인 검증"""

    def test_build_anonymized_fixtures_execution(self):
        mod = importlib.import_module("scripts.19_build_anonymized_golden_fixtures")
        res = mod.build_anonymized_fixtures()
        assert res is True
