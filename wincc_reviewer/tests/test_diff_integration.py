"""
Git diff 증분 검사 모드 E2E 통합 테스트.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.diff_filter import GitDiffFilter
from app.core.pipeline import Pipeline, PipelineConfig


def test_git_diff_filter_e2e(tmp_path: Path):
    # 1. 임시 Git 저장소 초기화
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)

    test_file = repo_dir / "sample.ctl"
    initial_content = "void main()\n{\n    int a = 1;\n    int b = 2;\n}\n"
    test_file.write_text(initial_content, encoding="utf-8")

    subprocess.run(["git", "add", "sample.ctl"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

    # 2. 파일 변경 (일부 라인만 수정 및 새로운 위반 코드 추가)
    modified_content = "void main()\n{\n    int a = 1;\n    while(1) { a++; }\n    int b = 2;\n}\n"
    test_file.write_text(modified_content, encoding="utf-8")

    # 3. Git diff 파싱 검증
    res = subprocess.run(["git", "diff", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
    diff_map = GitDiffFilter.parse_unified_diff(res.stdout)

    assert "sample.ctl" in diff_map or str(test_file) in diff_map or any(k.endswith("sample.ctl") for k in diff_map)

    # 4. 파이프라인 diff_only=True 모드 검증
    config = PipelineConfig(
        input_path=test_file,
        output_dir=repo_dir / "output",
        diff_only=True,
        no_ai=True,
    )
    pipeline = Pipeline(config)
    report = pipeline.run()

    assert report is not None
    assert report.metrics.file_count == 1
