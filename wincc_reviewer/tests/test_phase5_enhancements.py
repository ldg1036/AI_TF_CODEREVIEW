import pytest
from pathlib import Path
from app.core.dp_variable_tracker import DPVariableTracker
from app.core.autofix_validator import AutofixValidator
from app.core.report.quality_trend_db import QualityTrendDB


def test_dp_variable_tracker_analysis():
    """DP 변수 추적기 분석 검증."""
    code = '''
    void main() {
        dpConnect("workCB", "System1:Pump.status");
        dpSet("System1:Valve.cmd", 1);
    }
    '''
    chains = DPVariableTracker.analyze_script(code)
    assert len(chains) == 2
    assert chains[0].func_type == "dpConnect"
    assert chains[1].dp_name == "System1:Valve.cmd"


def test_autofix_validator_sandbox():
    """Autofix 샌드박스 구문 검증기 테스트."""
    valid_code = "void main() { int a = 10; }"
    invalid_code = ""

    is_val, msg = AutofixValidator.validate_patch(Path("test.ctl"), valid_code)
    assert is_val is True

    is_val_err, msg_err = AutofixValidator.validate_patch(Path("test.ctl"), invalid_code)
    assert is_val_err is False



def test_quality_trend_db_record():
    """품질 트렌드 장기 DB 기록 검증."""
    res = QualityTrendDB.record_run("run_test_001", {"total_files": 5, "violations": []})
    assert res["total_recorded_runs"] >= 1
