"""
SCADA 특화 외부 명령 실행 및 프로세스 생성 위험 탐지 체커.
"""

from __future__ import annotations

import re
from typing import Any
from app.core.models import RuleDefinition, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile


class CheckScadaSecurityExec:
    """CTL 스크립트 내 외부 시스템 명령 실행 패턴 탐지 체커."""

    UNSAFE_EXEC_PATTERNS = [
        r"\bsystem\s*\(",
        r"\bpopen\s*\(",
        r"\bexec\s*\(",
        r"\bCreateProcess\s*\(",
        r"\bWinExec\s*\(",
        r"\bShellExecute\s*\(",
    ]

    def check(self, parsed_file: Any, rule_def: RuleDefinition) -> list[Violation]:
        violations: list[Violation] = []
        content = getattr(parsed_file, "raw_content", "") or getattr(parsed_file, "content", "")
        if not content:
            return violations

        file_path = str(getattr(parsed_file, "file_path", ""))
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            for pattern in self.UNSAFE_EXEC_PATTERNS:
                if re.search(pattern, line):
                    violations.append(
                        Violation(
                            violation_id=f"V_SEC_{idx}",
                            rule_id=rule_def.rule_id if rule_def else "SCADA_SEC_001",
                            file_id=file_path,
                            line_start=idx,
                            message="SCADA 스크립트 내 검증되지 않은 외부 시스템 프로세스 실행 함수 감지 (명령 주입 위험)",
                            severity=SeverityLevel.CRITICAL,
                            snippet=line.strip(),
                            status=ViolationStatus.FAIL,
                            confidence_score=0.95,
                        )
                    )
                    break

        return violations
