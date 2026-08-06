from pathlib import Path
from app.main import main


def test_cli_fail_on_severity_option():
    """--fail-on-severity 옵션 지정 시 지정 이상 심각도 감지 시 exit code 1 반환 검증."""
    fixture_dir = Path(__file__).parent / "fixtures"
    ret = main([
        "--input", str(fixture_dir),
        "--no-ai",
        "--fail-on-severity", "Info"
    ])
    assert ret == 1


def test_cli_fail_on_severity_pass_when_no_matching():
    """지정 심각도보다 낮은 결과만 존재 시 exit code 0 반환 검증."""
    fixture_dir = Path(__file__).parent / "fixtures"
    ret = main([
        "--input", str(fixture_dir),
        "--no-ai",
        "--fail-on-severity", "Critical"
    ])
    assert ret == 0
