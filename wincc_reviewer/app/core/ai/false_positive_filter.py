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
        re.compile(r"(@safe|#\s*safe|NO_VIOLATION|IGNORE_RULE)", re.IGNORECASE),
        re.compile(r"//\s*(safe_context|approved_exception)", re.IGNORECASE),
    ]

    # 예외/오류 복구 보호 로직 패턴
    ERROR_RECOVERY_PATTERNS = [
        re.compile(r"(getLastError\s*\(|try\s*\{|catch\s*\(|if\s*\(\s*err\s*==\s*0)", re.IGNORECASE),
    ]

    # SCADA 공용 안전 래퍼 함수 패턴
    SAFE_WRAPPER_PATTERNS = [
        re.compile(r"(safeDpSet|safeDpGet|batchExecute|ScopeLib_protected)", re.IGNORECASE),
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
        snippet = violation.snippet or ""
        context_content = parsed_file.content if parsed_file else snippet

        # 1. 명시적 안전 주석(@safe 등) 존재 여부 검사
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
                    "[도메인 안전 예외] 명시적 예외 허용 주석(@safe / IGNORE_RULE)이 확인되어 오탐(False Positive)으로 판정합니다.",
                )

        # 2. 안전 래퍼 함수 내 호출 여부 검사
        for pattern in cls.SAFE_WRAPPER_PATTERNS:
            if pattern.search(snippet) or pattern.search(context_content):
                return (
                    0.20,
                    0.80,
                    True,
                    "[SCADA 안전 래퍼] 프로젝트 공용 안전 래퍼 함수 내 호출로 판단되어 허위 경보 확률(80%)이 높습니다.",
                )

        # 3. 비동기 콜백이나 루프 구문에서 오류 복구 핸들러 포함 여부
        if "callback" in violation.rule_id.lower() or "loop" in violation.rule_id.lower():
            for pattern in cls.ERROR_RECOVERY_PATTERNS:
                if pattern.search(snippet) or pattern.search(context_content):
                    return (
                        0.30,
                        0.70,
                        True,
                        "[오류 복구 핸들러] 오류 복구 및 예외 처리 구문(getLastError/try-catch)이 동반되어 안전 맥락으로 분류됩니다.",
                    )

        # 4. 일반 정적 검사 위반 항목 (진짜 위반 True Positive 가능성 높음)
        return (
            0.95,
            0.05,
            False,
            "[진성 위반 검증] 도메인 보호 로직이나 안전 예외 주석이 확인되지 않아 실제 위반(Confidence: 95%)으로 판정합니다.",
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

        Args:
            violations: 정적 분석으로 탐지된 위반 사항 목록
            parsed_files_map: file_id -> ParsedFile 매핑
            ai_provider: 선택적 AI Provider (온프레미스/클라우드 LLM)
        """
        for v in violations:
            parsed = parsed_files_map.get(v.file_id) if parsed_files_map else None
            conf, fp_prob, is_fp, reason = cls.analyze_domain_context(v, parsed)

            v.confidence_score = conf
            v.false_positive_probability = fp_prob
            v.is_false_positive = is_fp
            v.ai_verification_reason = reason

            # AI Provider 리뷰가 명확히 주입되었고 진짜 위반일 경우 LLM 검증 메시지 보강
            if ai_provider and not is_fp:
                try:
                    from app.core.ai.provider_base import AIRequest
                    req = AIRequest(code=v.snippet, rule_id=v.rule_id, context=v.message)
                    res = ai_provider.review(req)
                    if res.is_success and res.content:
                        v.ai_analysis = res.content
                except Exception:
                    pass

        return violations
