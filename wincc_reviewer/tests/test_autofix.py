"""
AutofixEngine 유닛 테스트 (TRD §5.5 & 08_ADR 계약 준수).

검증 항목:
1. enabled=False (기본값) 상태에서 원본 파일 덮어쓰기 미발생 및 원본 유지 검증
2. enabled=True 상태에서도 원본 보존 및 .autofixed 신규 파일 생성 검증
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.autofix.engine import AutofixEngine
from app.core.models import SeverityLevel, Violation, ViolationStatus


class TestAutofixEngine:
    """AutofixEngine 유닛 테스트."""

    def test_autofix_disabled_by_default(self, tmp_path: Path):
        """enabled=False 디폴트 상태 안전 보장 검증."""
        sample_file = tmp_path / "sample.ctl"
        sample_file.write_text("void main() {}", encoding="utf-8")
        orig_size = sample_file.stat().st_size

        engine = AutofixEngine(enabled=False)
        violation = Violation(
            violation_id="V-001",
            rule_id="CTL-RES-001",
            file_id=str(sample_file),
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.HIGH,
            message="위반",
        )

        res_path, success = engine.apply_autofix(sample_file, [violation])

        assert success is False
        assert res_path == sample_file
        assert sample_file.stat().st_size == orig_size

    def test_autofix_enabled_creates_copy(self, tmp_path: Path):
        """enabled=True 상태에서도 원본 파일 덮어쓰기 0건 및 .autofixed 생성 검증."""
        sample_file = tmp_path / "sample.ctl"
        sample_file.write_text("void main() {}", encoding="utf-8")
        orig_content = sample_file.read_text(encoding="utf-8")

        engine = AutofixEngine(enabled=True)
        res_path, success = engine.apply_autofix(sample_file, [])

        assert success is True
        assert res_path != sample_file
        assert res_path.name.endswith(".ctl.autofixed")
        assert sample_file.read_text(encoding="utf-8") == orig_content  # 원본 보존 확인
