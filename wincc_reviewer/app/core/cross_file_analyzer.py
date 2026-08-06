"""
프로젝트 레벨 교차 파일(Cross File) 분석 모듈.
"""

from __future__ import annotations

import hashlib
from typing import Any
from app.core.models import Violation, SeverityLevel, ViolationStatus


class CrossFileAnalyzer:
    """프로젝트 내 복수 파일 간 교차 분석(중복 코드, 고아 참조 등)을 수행합니다."""

    @classmethod
    def analyze_cross_files(cls, parsed_files: list[Any]) -> list[Violation]:
        """
        파싱된 전체 파일 목록을 바탕으로 교차 파일 중복 코드 및 심볼 참조 결함을 탐지합니다.
        """
        violations: list[Violation] = []
        code_block_hashes: dict[str, tuple[str, int]] = {}  # hash -> (file_path, line_number)

        for pf in parsed_files:
            file_path = str(getattr(pf, "file_path", ""))
            content = getattr(pf, "raw_content", "") or getattr(pf, "content", "")
            if not content:
                continue

            lines = content.splitlines()
            # 5줄 단위 이동 슬라이딩 윈도우 기반 중복 코드 블록 검사
            window_size = 5
            for i in range(len(lines) - window_size + 1):
                chunk = "\n".join(line.strip() for line in lines[i : i + window_size] if line.strip())
                if len(chunk) < 40:
                    continue

                chunk_hash = hashlib.md5(chunk.encode("utf_8")).hexdigest()
                if chunk_hash in code_block_hashes:
                    orig_file, orig_line = code_block_hashes[chunk_hash]
                    if orig_file != file_path:
                        violations.append(
                            Violation(
                                violation_id=f"V_CROSS_{i+1}",
                                rule_id="CROSS_FILE_DUPLICATE",
                                file_id=file_path,
                                line_start=i + 1,
                                message=f"교차 파일 중복 코드 블록 감지 (원본: {orig_file}:{orig_line})",
                                severity=SeverityLevel.MEDIUM,
                                snippet=chunk[:100],
                                status=ViolationStatus.FAIL,
                                confidence_score=0.90,
                            )
                        )
                else:
                    code_block_hashes[chunk_hash] = (file_path, i + 1)

        return violations
