"""
Phase 0 스모크 테스트.

DoD 검증:
    - python -m app.main --help 실행 시 정상 출력
    - pytest 통과
    - 모듈 import 확인
    - 데이터 모델 최소 계약 확인
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestCLI:
    """CLI 진입점 테스트."""

    def test_main_help_exits_zero(self):
        """--help 플래그 실행 시 정상 종료(exit code 0) 확인."""
        from app.main import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_main_no_args_returns_zero(self):
        """인자 없이 실행 시 GUI 모드 시작(launch_ui) 호출 후 정상 종료."""
        from unittest.mock import patch
        import app.ui.app  # ensure module is loaded in sys.modules
        from app.main import main

        with patch("app.ui.app.launch_ui") as mock_ui:
            result = main([])
            assert result == 0
            mock_ui.assert_called_once()

    def test_main_version_exits_zero(self):
        """--version 플래그 실행 시 정상 종료."""
        from app.main import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_main_module_execution(self):
        """python -m app.main --help 실행 확인."""
        import os

        wincc_dir = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{wincc_dir}{os.pathsep}{existing_pp}" if existing_pp else str(wincc_dir)

        result = subprocess.run(
            [sys.executable, "-m", "app.main", "--help"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            env=env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "wincc" in result.stdout.lower()


class TestModuleImports:
    """모듈 import 가능 여부 테스트."""

    def test_import_app(self):
        """app 패키지 import 확인."""
        import app

        assert hasattr(app, "__version__")

    def test_import_core_models(self):
        """core.models 모듈 import 확인."""
        from app.core.models import (
            CheckerType,
            Metrics,
            ParseStatus,
            ParseStatusType,
            ReviewReport,
            RuleDefinition,
            SeverityLevel,
            Violation,
            ViolationStatus,
        )

    def test_import_core_pipeline(self):
        """core.pipeline 모듈 import 확인."""
        from app.core.pipeline import Pipeline, PipelineConfig

    def test_import_parser_base(self):
        """parser.base_parser 모듈 import 확인."""
        from app.core.parser.base_parser import ParsedFile, Parser

    def test_import_rules_base(self):
        """rules.base_rule 모듈 import 확인."""
        from app.core.rules.base_rule import RuleChecker

    def test_import_ai_provider(self):
        """ai.provider_base 모듈 import 확인."""
        from app.core.ai.provider_base import AIProvider, AIRequest, AIResponse

    def test_import_diff_provider(self):
        """diff.winmerge_runner 모듈 import 확인."""
        from app.core.diff.winmerge_runner import DiffChange, DiffProvider, DiffResult


class TestDataModelContract:
    """09_구현착수_패키지_계약.md §4 데이터 모델 최소 계약 검증."""

    def test_rule_definition_required_fields(self):
        """RuleDefinition 필수 필드 확인."""
        from app.core.models import CheckerType, RuleDefinition

        rule = RuleDefinition(
            rule_id="TEST-001",
            source_key="테스트|분류|항목",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
        )
        assert rule.rule_id == "TEST-001"
        assert rule.source_key == "테스트|분류|항목"
        assert rule.file_types == ["CTL"]
        assert rule.checker_type == CheckerType.MANUAL
        assert rule.enabled is True
        assert rule.rule_version == "1.0.0"

    def test_violation_required_fields(self):
        """Violation 필수 필드 확인."""
        from app.core.models import SeverityLevel, Violation, ViolationStatus

        violation = Violation(
            violation_id="V-001",
            rule_id="TEST-001",
            file_id="test.ctl",
            status=ViolationStatus.FAIL,
            severity=SeverityLevel.HIGH,
            message="테스트 위반",
        )
        assert violation.violation_id == "V-001"
        assert violation.status == ViolationStatus.FAIL
        assert violation.severity == SeverityLevel.HIGH

    def test_review_report_required_fields(self):
        """ReviewReport 필수 필드 확인."""
        from app.core.models import Metrics, ReviewReport

        report = ReviewReport(
            schema_version="1.0",
            run_id="run-001",
            rule_source="server.xlsx",
            files=["test.ctl"],
            violations=[],
            errors=[],
            metrics=Metrics(),
        )
        assert report.schema_version == "1.0"
        assert report.run_id == "run-001"
        assert isinstance(report.violations, list)
        assert isinstance(report.errors, list)

    def test_parse_status_required_fields(self):
        """ParseStatus 필수 필드 확인."""
        from app.core.models import ParseStatus, ParseStatusType

        status = ParseStatus(status=ParseStatusType.PARSED)
        assert status.status == ParseStatusType.PARSED

        failed = ParseStatus(
            status=ParseStatusType.PARSE_FAILED,
            file="test.pnl",
            error_message="구조 분석 실패",
        )
        assert failed.status == ParseStatusType.PARSE_FAILED
        assert failed.error_message is not None

    def test_checker_type_enum_values(self):
        """CheckerType enum 값 확인 (09_구현착수 §4)."""
        from app.core.models import CheckerType

        assert CheckerType.BUILTIN == "builtin"
        assert CheckerType.REGEX == "regex"
        assert CheckerType.MANUAL == "manual"

    def test_violation_status_enum_values(self):
        """ViolationStatus enum 값 확인 (09_구현착수 §4)."""
        from app.core.models import ViolationStatus

        assert ViolationStatus.FAIL == "FAIL"
        assert ViolationStatus.MANUAL_REVIEW == "MANUAL_REVIEW"
        assert ViolationStatus.ERROR == "ERROR"

    def test_severity_enum_values(self):
        """SeverityLevel enum 값 확인 (09_구현착수 §4)."""
        from app.core.models import SeverityLevel

        assert SeverityLevel.CRITICAL == "Critical"
        assert SeverityLevel.HIGH == "High"
        assert SeverityLevel.MEDIUM == "Medium"
        assert SeverityLevel.LOW == "Low"
        assert SeverityLevel.INFO == "Info"

    def test_parse_status_type_enum_values(self):
        """ParseStatusType enum 값 확인 (09_구현착수 §4)."""
        from app.core.models import ParseStatusType

        assert ParseStatusType.PARSED == "parsed"
        assert ParseStatusType.PARSE_FAILED == "parse_failed"
        assert ParseStatusType.UNSUPPORTED == "unsupported"


class TestJsonSchemas:
    """JSON Schema 파일 존재 및 유효성 테스트."""

    def test_schemas_exist(self, schemas_dir: Path):
        """필수 JSON Schema 파일 존재 확인."""
        expected = [
            "rule_definition.json",
            "violation.json",
            "review_report.json",
            "parse_status.json",
        ]
        for schema_file in expected:
            path = schemas_dir / schema_file
            assert path.exists(), f"스키마 파일 누락: {schema_file}"

    def test_schemas_valid_json(self, schemas_dir: Path):
        """JSON Schema 파일이 유효한 JSON인지 확인."""
        for schema_file in schemas_dir.glob("*.json"):
            with open(schema_file, encoding="utf-8") as f:
                data = json.load(f)
            assert "$schema" in data, f"{schema_file.name}에 $schema 누락"
            assert "required" in data, f"{schema_file.name}에 required 누락"


class TestConfigFiles:
    """설정 파일 존재 확인 테스트."""

    def test_settings_yaml_exists(self, config_dir: Path):
        """config/settings.yaml 파일 존재 확인."""
        assert (config_dir / "settings.yaml").exists()

    def test_excel_files_exist(self, config_dir: Path):
        """코드리뷰 결과서 Excel 파일 존재 확인 (원본 보존)."""
        client_file = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
        server_file = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
        assert client_file.exists(), "Client 결과서 파일 누락"
        assert server_file.exists(), "Server 결과서 파일 누락"

    def test_excel_files_sizes_unchanged(self, config_dir: Path):
        """Excel 파일 크기가 원본과 동일한지 확인 (변경 방지)."""
        client_file = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
        server_file = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
        # 08_ADR 기준 파일 크기
        assert client_file.stat().st_size == 97665, "Client 결과서 파일 크기 변경 감지"
        assert server_file.stat().st_size == 98921, "Server 결과서 파일 크기 변경 감지"


class TestParserBaseHelper:
    """파서 기본 헬퍼 함수 테스트."""

    def test_create_failed_parse(self):
        """create_failed_parse 헬퍼 함수 동작 확인."""
        from app.core.models import ParseStatusType
        from app.core.parser.base_parser import create_failed_parse

        result = create_failed_parse(Path("test.pnl"), "파일 구조 불일치")
        assert result.parse_status.status == ParseStatusType.PARSE_FAILED
        assert result.parse_status.error_message == "파일 구조 불일치"
        assert result.file_type == "pnl"
