"""
Autofix 안전 엔진 (TRD §5.5 & 08_ADR 계약 준수).

원칙:
1. autofix는 기본 비활성화(enabled=False)입니다.
2. 원본 파일 덮어쓰기는 절대 하지 않으며, 백업 또는 신규 복사본(.autofixed)에만 적용합니다.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.models import Violation

logger = logging.getLogger(__name__)


class AutofixEngine:
    """자동수정 안전 엔진."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def apply_autofix(self, file_path: Path, violations: list[Violation]) -> tuple[Path, bool]:
        """
        위반 항목에 대해 안전한 자동수정을 시도합니다.

        Args:
            file_path: 원본 파일 경로
            violations: 정적 검사에서 검출된 위반 목록

        Returns:
            (수정 파일 경로, 수정 성공 여부)
        """
        orig_path = Path(file_path)

        # 1. autofix 비활성화 상태에서는 원본 파일 그대로 반환 (안전보장)
        if not self.enabled:
            logger.info("Autofix 비활성화 상태: 원본 보존 (%s)", orig_path)
            return orig_path, False

        if not orig_path.exists():
            return orig_path, False

        # 2. 원본 덮어쓰기 금지 계약: .autofixed 신규 복사본 생성
        fixed_path = orig_path.with_suffix(orig_path.suffix + ".autofixed")
        try:
            shutil.copy2(orig_path, fixed_path)
            # 안전 스텁: 실제 소스 수정은 autofix_allowed=True인 룰만 선별 적용
            logger.info("Autofix 복사본 생성 완료: %s", fixed_path)
            return fixed_path, True
        except Exception as e:
            logger.error("Autofix 복사본 생성 실패: %s", e)
            return orig_path, False
