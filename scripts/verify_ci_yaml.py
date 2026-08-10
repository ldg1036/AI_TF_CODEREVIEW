"""
CI/CD YAML 워크플로우 정적 검증 스크립트 (IMP 01 검증).
.github/workflows/test.yml 및 release.yml의 YAML 파싱, on 키 중복 (Norway Problem) 부재 및 스텝별 (uses XOR run) 단일화를 검증합니다.
"""

import io
import sys
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

base_dir = Path(__file__).resolve().parent.parent


def verify_ci_yaml(file_path: Path) -> bool:
    """CI YAML 워크플로우 파일 구조의 무결성을 검증합니다."""
    if not file_path.exists():
        print(f"오류: CI 파일이 존재하지 않습니다: {file_path}")
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. YAML 파싱 및 on 키 중복 검사
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, dict):
        print(f"오류: {file_path} 가 딕셔너리 구조가 아닙니다.")
        return False

    # PyYAML은 'on:' 키를 True (boolean) 키 또는 'on' 문자열 키로 파싱합니다.
    on_trigger = parsed.get("on") if "on" in parsed else parsed.get(True)
    if on_trigger is None:
        print(f"오류: {file_path} 에 on 트리거 정의가 누락되었습니다.")
        return False

    # 3. jobs 스텝 구조 검사 (uses XOR run)
    jobs = parsed.get("jobs", {})
    for job_name, job_data in jobs.items():
        steps = job_data.get("steps", [])
        for idx, step in enumerate(steps, start=1):
            has_uses = "uses" in step
            has_run = "run" in step
            if not (has_uses ^ has_run):
                print(f"오류: {file_path} job '{job_name}' step #{idx}는 uses와 run 중 하나만 가져야 합니다: {step}")
                return False

    print(f"성공: {file_path.name} CI YAML 스크마 검증 완료.")
    return True


def main() -> None:
    test_yml = base_dir / ".github" / "workflows" / "test.yml"
    release_yml = base_dir / ".github" / "workflows" / "release.yml"

    v1 = verify_ci_yaml(test_yml)
    v2 = verify_ci_yaml(release_yml)

    if not (v1 and v2):
        sys.exit(1)


if __name__ == "__main__":
    main()
