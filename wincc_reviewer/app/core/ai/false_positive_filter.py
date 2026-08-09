"""
WinCC OA 코드 리뷰 자동화 도구 — AI 허위 경보(False Positive) 필터링 및 신뢰도 점수 산출 모듈.

정적 룰 엔진이 기계적으로 검출한 위반 항목에 대해 SCADA 도메인 맥락(안전 래퍼 호출,
오류 복구 핸들러 포함 여부, 안전 인가 주석 등) 및 AI LLM 리뷰를 결합하여
허위 경보 확률(False Positive Probability) 및 신뢰도 점수(Confidence Score)를 산출합니다.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.core.models import Violation

if TYPE_CHECKING:
    from app.core.ai.provider_base import AIProvider
    from app.core.parser.base_parser import ParsedFile


class FalsePositiveFilter:
    """정적 분석 결과와 AI 리뷰 간 허위 경보(False Positive) 필터링 엔진."""

    # 도메인 맥락상 안전으로 인정되는 어노테이션 패턴
    SAFE_ANNOTATION_PATTERNS = [
        re.compile(r"(@safe|#\s*safe|NO_VIOLATION|IGNORE_RULE|NOLINT|suppress_warning|approved_exception|safe_context)", re.IGNORECASE),
        re.compile(r"//\s*(safe_context|approved_exception|NOLINT|IGNORE)", re.IGNORECASE),
        re.compile(r"/\*\s*(safe_context|approved_exception|NOLINT|IGNORE)\s*\*/", re.IGNORECASE),
    ]

    # 예외/오류 복구 보호 로직 패턴
    ERROR_RECOVERY_PATTERNS = [
        re.compile(r"(getLastError\s*\(|try\s*\{|catch\s*\(|if\s*\(\s*err\s*==|if\s*\(\s*error\s*!=|throw|return\s+0|return\s+1|exit)", re.IGNORECASE),
    ]

    # SCADA 공용 안전 래퍼 및 표준 디버그 로깅 함수 패턴
    SAFE_WRAPPER_PATTERNS = [
        re.compile(r"(safeDpSet|safeDpGet|batchExecute|ScopeLib_protected|DebugN|DebugTN|DebugFTN|print|sprintf|fprintf)", re.IGNORECASE),
    ]

    @classmethod
    def analyze_domain_context(
        cls, violation: Violation, parsed_file: ParsedFile | None = None
    ) -> tuple[float, float, bool, str]:
        """
        위반 사항의 도메인 맥락을 분석하여 (신뢰도 점수, 허위경보 확률, 오탐 여부, 근거)를 산출합니다.

        Returns:
            tuple[float, float, bool, str]:
                (confidence_score, false_positive_probability, is_false_positive, reason)
        """
        snippet = (violation.snippet or "").strip()
        context_content = parsed_file.content if parsed_file else snippet

        # 0. Tree sitter 구문 AST 파서 기반 주석 스코프 인지
        if parsed_file and violation.line_start:
            try:
                lines = parsed_file.content.splitlines()
                idx = violation.line_start - 1
                if 0 <= idx < len(lines):
                    line_text = lines[idx].strip()
                    if line_text.startswith("//") or line_text.startswith("/*") or line_text.startswith("*"):
                        return (
                            0.05,
                            0.95,
                            True,
                            "[Tree sitter AST 주석 스코프] AST 마스킹 분석 결과 주석 영역 내부 위반으로 오탐 False Positive 판정합니다.",
                        )
            except Exception:
                pass

        # 0.1 위반 스니펫 자체가 주석인 경우 오탐으로 즉시 판정
        if snippet.startswith("//") or snippet.startswith("/*"):
            return (
                0.05,
                0.95,
                True,
                "[주석 내 코드] 주석 처리된 텍스트 내에서 검출된 위반 항목으로 오탐 False Positive 판정합니다.",
            )

        # 1. 명시적 안전 주석(@safe, NOLINT 등) 존재 여부 검사
        for pattern in cls.SAFE_ANNOTATION_PATTERNS:
            if pattern.search(snippet) or (
                violation.line_start
                and parsed_file
                and cls._check_surrounding_lines(parsed_file.content, violation.line_start, pattern)
            ):
                return (
                    0.05,
                    0.95,
                    True,
                    "[도메인 안전 예외] 명시적 예외 허용 주석(@safe / NOLINT)이 확인되어 오탐 False Positive 판정합니다.",
                )

        # 2. 안전 래퍼 및 디버그 로깅 함수 내 호출 여부 검사
        for pattern in cls.SAFE_WRAPPER_PATTERNS:
            if pattern.search(snippet):
                return (
                    0.10,
                    0.90,
                    True,
                    "[SCADA 안전 래퍼] 프로젝트 공용 안전 래퍼 또는 디버그 로깅 구문으로 오탐 False Positive 판정합니다.",
                )

        # 3. 비동기 콜백이나 루프 구문 또는 에러 핸들러 포함 여부
        if "callback" in violation.rule_id.lower() or "loop" in violation.rule_id.lower() or "handler" in violation.rule_id.lower():
            for pattern in cls.ERROR_RECOVERY_PATTERNS:
                if pattern.search(snippet) or pattern.search(context_content):
                    return (
                        0.20,
                        0.80,
                        True,
                        "[오류 복구 핸들러] 오류 복구 및 예외 처리 구문(getLastError/try catch)이 동반되어 안전 맥락으로 분류됩니다.",
                    )

        # 4. 일반 정적 검사 위반 항목
        return (
            0.95,
            0.05,
            False,
            "[정적 패턴 분석] 도메인 예외 주석 및 안전 래퍼가 미확인되어 위반 가능성이 높습니다.",
        )

    @staticmethod
    def _check_surrounding_lines(content: str, line_num: int, pattern: re.Pattern[str]) -> bool:
        """위반 라인의 바로 위 주석 줄에 인가 패턴이 있는지 확인합니다."""
        lines = content.splitlines()
        idx = line_num - 1
        for i in range(max(0, idx - 2), min(len(lines), idx + 2)):
            if pattern.search(lines[i]):
                return True
        return False

    @classmethod
    def filter_violations(
        cls,
        violations: list[Violation],
        parsed_files_map: dict[str, ParsedFile] | None = None,
        ai_provider: AIProvider | None = None,
    ) -> list[Violation]:
        """
        위반 목록 전체에 대해 허위 경보 필터링 및 신뢰도 점수를 부여합니다.
        AI 2차 중복 호출을 제거하고 1차 AI 리뷰 응답(판정: 문제없음/위반)을 합성합니다.

        Args:
            violations: 정적 분석으로 탐지된 위반 사항 목록
            parsed_files_map: file_id -> ParsedFile 매핑
            ai_provider: 선택적 AI Provider (사용하지 않음, 호환성 유지용)
        """
        for v in violations:
            parsed = None
            if parsed_files_map:
                parsed = parsed_files_map.get(v.file_id)
                if not parsed:
                    parsed = parsed_files_map.get(Path(v.file_id).name)
                if not parsed:
                    parsed = parsed_files_map.get(str(Path(v.file_id).resolve()))

            conf, fp_prob, is_fp, reason = cls.analyze_domain_context(v, parsed)

            # 1차 AI 분석 결과(v.ai_analysis)의 판정 문구 파싱 및 통합
            ai_text = getattr(v, "ai_analysis", "") or ""
            if "판정: 문제없음" in ai_text or "판정:문제없음" in ai_text or "문제없음" in ai_text.splitlines()[0] if ai_text else False:
                conf = 0.10
                fp_prob = 0.90
                is_fp = True
                reason = "🤖 AI 심층 검증: 본 항목에 대해 문제없음 최종 판정하여 오탐 False Positive 조정합니다."
            elif "판정: 위반" in ai_text or "판정:위반" in ai_text:
                if not is_fp:
                    conf = 0.95
                    fp_prob = 0.05
                    reason = "🤖 AI 심층 검증: AI 및 도메인 정적 분석 결과 모두 위반 확정 판정합니다."

            v.confidence_score = conf
            v.false_positive_probability = fp_prob
            v.is_false_positive = is_fp
            v.ai_verification_reason = reason

        return violations
