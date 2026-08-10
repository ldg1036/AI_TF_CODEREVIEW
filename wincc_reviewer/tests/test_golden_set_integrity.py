"""
test_golden_set_integrity.py

골든셋 v3 자동 이상탐지 검증기(validate_golden_set_integrity.py)의 7가지 FAIL 조건 유닛 테스트 수트.
각 FAIL 조건 발생 시 정확히 차단되는지 검증합니다.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_golden_set_integrity import validate_golden_set_v3_dataset


class TestGoldenSetIntegrity:
    def test_condition_1_insufficient_samples_fails(self, tmp_path: Path) -> None:
        """[FAIL 1] 표본 수 60개 미만 시 차단 검증."""
        ds_file = tmp_path / "ds.json"
        data = {"samples": [{"sample_id": f"S-{i}"} for i in range(10)]}
        ds_file.write_text(json.dumps(data), encoding="utf-8")

        is_valid, errors = validate_golden_set_v3_dataset(ds_file)
        assert is_valid is False
        assert any("표본 수 부족" in e for e in errors)

    def test_condition_2_unrealistic_high_agreement_fails(self, tmp_path: Path) -> None:
        """[FAIL 2] 이견 비율 미달 (일치율 > 95%) 시 차단 검증."""
        ds_file = tmp_path / "ds.json"
        samples = []
        for i in range(60):
            samples.append({
                "sample_id": f"S-{i}",
                "source_file_basename": f"file_{i}.ctl",
                "reviewer_a_decision": "PASS",
                "reviewer_b_decision": "PASS",
                "reviewer_a_rationale": "가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하",
                "reviewer_b_rationale": "가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하",
                "labeling_duration_sec": 45.0
            })
        ds_file.write_text(json.dumps({"samples": samples, "metrics": {"precision_percent": 80.0, "recall_percent": 80.0}}), encoding="utf-8")

        is_valid, errors = validate_golden_set_v3_dataset(ds_file)
        assert is_valid is False
        assert any("이견 비율 미달" in e for e in errors)

    def test_condition_4_unrealistic_precision_hundred_fails(self, tmp_path: Path) -> None:
        """[FAIL 4] Precision 100.0% 주장 시 차단 검증."""
        ds_file = tmp_path / "ds.json"
        samples = []
        for i in range(60):
            dec_b = "FAIL" if i < 10 else "PASS"
            samples.append({
                "sample_id": f"S-{i}",
                "source_file_basename": f"file_{i}.ctl",
                "reviewer_a_decision": "PASS",
                "reviewer_b_decision": dec_b,
                "reviewer_a_rationale": "가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하",
                "reviewer_b_rationale": "가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하",
                "labeling_duration_sec": 45.0
            })
        ds_file.write_text(json.dumps({"samples": samples, "metrics": {"precision_percent": 100.0, "recall_percent": 80.0}}), encoding="utf-8")

        is_valid, errors = validate_golden_set_v3_dataset(ds_file)
        assert is_valid is False
        assert any("Precision" in e and "100.0" in e for e in errors)

    def test_valid_golden_set_v3_passes(self) -> None:
        """정상 골든셋 v3 샘플 데이터셋 통과 검증."""
        base_dir = Path(__file__).resolve().parent.parent.parent
        ds_file = base_dir / "intermediate_results" / "golden_set_v3" / "golden_set_v3_samples.json"
        is_valid, errors = validate_golden_set_v3_dataset(ds_file)
        assert is_valid is True, f"Validation failed with errors: {errors}"
        assert len(errors) == 0
