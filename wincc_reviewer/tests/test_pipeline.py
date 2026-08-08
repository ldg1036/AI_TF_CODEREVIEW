"""
Pipeline 및 CLI 통합 E2E 테스트 (09_구현착수_패키지_계약.md §3 & §8 기준).

검증 항목:
1. Pipeline.run() E2E 실행 (파싱 -> 룰검사 -> JSON/HTML 리포트 내보내기)
2. CLI 명령 실행: python -m app.main --input <path> --no-ai (exit code 0 및 결과 파일 생성)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

from app.core.pipeline import Pipeline, PipelineConfig


class TestPipelineIntegration:
    """Core Pipeline 통합 E2E 테스트."""

    @pytest.fixture
    def sample_files(self, tmp_path: Path) -> tuple[Path, Path]:
        input_dir = tmp_path / "inputs"
        input_dir.mkdir()

        # CTL 파일 생성
        ctl_file = input_dir / "test_script.ctl"
        ctl_file.write_text("main() {\n    dpConnect('cb', 'dpe');\n}", encoding="utf-8")

        # PNL 파일 생성
        pnl_file = input_dir / "panel1.pnl"
        pnl_file.write_text("shape Btn1\nInitialize()\n{\n    dpSet('dpe', 1);\n}", encoding="utf-8")

        return input_dir, tmp_path / "outputs"

    def test_pipeline_run_with_sample_files(self, sample_files: tuple[Path, Path]):
        """파이프라인 실행 및 JSON/HTML 리포트 저장 검증."""
        input_dir, output_dir = sample_files

        config = PipelineConfig(
            input_path=input_dir,
            output_dir=output_dir,
            no_ai=True,
        )

        pipeline = Pipeline(config)
        report = pipeline.run()

        # 리포트 메타데이터 검증
        assert report.metrics.file_count == 2
        assert len(report.files) == 2
        assert report.run_id != ""

        # 출력 파일 생성 검증
        json_file = output_dir / f"{report.run_id}_review_report.json"
        html_file = output_dir / f"{report.run_id}_review_report.html"

        assert json_file.exists(), f"JSON 리포트 파일 생성 실패: {json_file}"
        assert html_file.exists(), f"HTML 리포트 파일 생성 실패: {html_file}"

    def test_cli_execution_no_ai(self, sample_files: tuple[Path, Path]):
        """09_구현착수 게이트: python -m app.main --input ... --no-ai CLI 실행 검증."""
        input_dir, output_dir = sample_files

        wincc_dir = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{wincc_dir}{os.pathsep}{existing_pp}" if existing_pp else str(wincc_dir)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.main",
                "--input",
                str(input_dir),
                "--output",
                str(output_dir),
                "--no-ai",
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            env=env,
        )

        assert result.returncode == 0, f"CLI 실행 오류 (stderr: {result.stderr})"
        assert "WinCC OA Code Review Completed" in result.stdout

        # 출력 리포트 파일 생성 검증
        output_json_files = list(output_dir.glob("*_review_report.json"))
        output_html_files = list(output_dir.glob("*_review_report.html"))

        assert len(output_json_files) >= 1
        assert len(output_html_files) >= 1
