"""
Autofix 안전 엔진 (TRD §5.5 & 08_ADR 계약 준수).

원칙:
1. autofix는 기본 비활성화(enabled=False)입니다.
2. 원본 파일 덮어쓰기는 절대 하지 않으며, 백업 또는 신규 복사본(.autofixed)에만 적용합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.models import Violation

logger = logging.getLogger(__name__)


class AutofixEngine:
    """자동수정 안전 엔진."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    @staticmethod
    def extract_ai_code_blocks(ai_analysis: str) -> list[str]:
        """AI 분석 텍스트 내의 마크다운 코드 블록(``` ... ```)을 추출합니다."""
        import re

        if not ai_analysis:
            return []
        pattern = r"```(?:ctl|c|cpp|wincc|csharp|javascript|xml|html)?\n(.*?)```"
        matches = re.findall(pattern, ai_analysis, re.DOTALL)
        return [m.strip() for m in matches if m.strip()]

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

        # 1. autofix 비활성화 상태에서는 원본 파일 그대로 반환 (안전보장 계약 준수)
        if not self.enabled:
            logger.info("Autofix 비활성화 상태: 원본 보존 (%s)", orig_path)
            return orig_path, False

        if not orig_path.exists():
            return orig_path, False

        fixed_path = orig_path.with_suffix(orig_path.suffix + ".autofixed")
        try:
            content = ""
            for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
                try:
                    content = orig_path.read_text(encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue

            lines = content.splitlines(keepends=True)
            modified_lines = list(lines)

            applied_changes = False
            ai_guides = []

            for v in violations:
                # AI 분석 결과에서 코드 추출 시도
                blocks = self.extract_ai_code_blocks(v.ai_analysis)
                if blocks:
                    # 첫 번째 추천 코드 블록을 가이드 주석과 함께 원본 위치 또는 파일 상단에 명시
                    suggested_code = blocks[0]
                    guide_comment = (
                        f"// ===== [AI 추천 개선 코드 (Rule: {v.rule_id})] =====\n"
                        + "\n".join([f"// {line}" for line in suggested_code.splitlines()])
                        + "\n// =============================================\n"
                    )

                    # 위반 위치(Line)가 명확하면 해당 라인 바로 아래/위에 추가
                    if v.line_start and 1 <= v.line_start <= len(modified_lines):
                        idx = v.line_start - 1
                        modified_lines[idx] = guide_comment + modified_lines[idx]
                    else:
                        ai_guides.append(guide_comment)
                    applied_changes = True
                elif v.ai_analysis:
                    # 마크다운 코드 블록이 없더라도 AI의 텍스트 조언을 주석 형태로 탑재
                    clean_analysis = v.ai_analysis.replace("\r", "")
                    short_summary = clean_analysis.split("\n")[0]
                    guide_comment = f"// 💡 [AI 심층 가이드 ({v.rule_id})]: {short_summary}\n"
                    if v.line_start and 1 <= v.line_start <= len(modified_lines):
                        idx = v.line_start - 1
                        modified_lines[idx] = guide_comment + modified_lines[idx]
                    else:
                        ai_guides.append(guide_comment)
                    applied_changes = True

            final_content = "".join(ai_guides) + "".join(modified_lines)

            if not applied_changes:
                final_content = f"// [WinCC OA Reviewer - 자동 검사 완료]\n// 위반 항목: {len(violations)}건 (AI 추천 코드 생성 대기중)\n\n" + content

            fixed_path.write_text(final_content, encoding="utf-8")
            logger.info("Autofix 파일 생성 완료: %s", fixed_path)
            return fixed_path, True
        except Exception as e:
            logger.error("Autofix 처리 중 오류 발생: %s", e)
            return orig_path, False
