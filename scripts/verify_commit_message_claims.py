"""
verify_commit_message_claims.py

Anti-Gaming 5원칙(수치-소스 강제 바인딩) 및 6원칙(반올림·과장 표현 금지)을 자동 검증하는 커밋 메시지 검증기.
SSOT(intermediate_results/single_source_metrics.json)의 실측 수치와 커밋 메시지의 수치 주장을 정밀 대조합니다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

base_dir = Path(__file__).resolve().parent.parent
ssot_file = base_dir / "intermediate_results" / "single_source_metrics.json"

FORBIDDEN_EXAGGERATED_TERMS = [
    r"완전히\s*해소",
    r"100%\s*완수",
    r"전면\s*해결",
    r"모든\s*문제\s*해결",
    r"완벽\s*해결",
    r"오류\s*0건\s*완수",
]


def load_ssot_metrics() -> dict[str, Any]:
    if not ssot_file.exists():
        print(f"오류: SSOT 파일이 존재하지 않습니다: {ssot_file}")
        sys.exit(1)

    with open(ssot_file, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_commit_message(commit_msg: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    ssot_data = load_ssot_metrics()

    gov_metrics = ssot_data.get("test_and_governance_metrics", {})
    if not gov_metrics:
        gov_metrics = ssot_data

    # 1. 정성 과장 표현 검사 (SSOT 실측 수치 명시 부재 시 거부)
    for term_regex in FORBIDDEN_EXAGGERATED_TERMS:
        match = re.search(term_regex, commit_msg)
        if match:
            if "SSOT:" not in commit_msg and "single_source_metrics.json" not in commit_msg:
                errors.append(
                    f"금지된 과장 표현 금지 규칙 위반: '{match.group(0)}' (SSOT 소수점 수치 병기 필수)"
                )

    # 2. 정량 퍼센트 표기 대조 검사
    percent_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", commit_msg)
    if percent_matches:
        ssot_cov = float(gov_metrics.get("automation_coverage_percent", 0.0))
        for p_str in percent_matches:
            val = float(p_str)
            if "커버리지" in commit_msg or "coverage" in commit_msg.lower():
                if abs(val - ssot_cov) > 0.01:
                    errors.append(
                        f"수치 주장 불일치: 커밋 메시지 주장({val}%) != SSOT 실측({ssot_cov}%)"
                    )

    # 3. 체커 개수 수치 대조 검사
    checker_matches = re.findall(r"(\d+)\s*개\s*체커", commit_msg)
    if checker_matches:
        ssot_checkers = int(gov_metrics.get("registered_checkers_count", gov_metrics.get("total_checkers_registered", 0)))
        for c_str in checker_matches:
            val = int(c_str)
            if val != ssot_checkers:
                errors.append(
                    f"체커 개수 불일치: 커밋 메시지 주장({val}개) != SSOT 실측({ssot_checkers}개)"
                )

    return len(errors) == 0, errors


def main() -> None:
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("사용법: python scripts/verify_commit_message_claims.py <commit_msg_file|text>")
        sys.exit(1)

    arg = sys.argv[1]
    path_obj = Path(arg)
    if path_obj.exists() and path_obj.is_file():
        commit_msg = path_obj.read_text(encoding="utf-8")
    else:
        commit_msg = arg

    is_valid, errors = verify_commit_message(commit_msg)
    if not is_valid:
        print("=== [COMMITS VERIFICATION FAILED] Anti-Gaming 규칙 위반으로 커밋이 거부되었습니다 ===")
        for err in errors:
            print(f" * {err}")
        print("SSOT 파일(intermediate_results/single_source_metrics.json)의 실측값을 확인해 주세요.")
        sys.exit(1)

    print("=== [COMMITS VERIFICATION PASSED] 커밋 메시지 수치 바인딩 무결성 검증 통과 ===")


if __name__ == "__main__":
    main()
