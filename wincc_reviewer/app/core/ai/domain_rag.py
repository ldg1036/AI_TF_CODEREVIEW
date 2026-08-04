"""
WinCC OA 도메인 특화 AI/RAG 사서함 및 Few-Shot Safe Code 프롬프트 관리자 (04_AI_프롬프트_설계서.md §12).

주요 기능:
1. WinCC OA 표준 API (dpConnect, dpGet, dpSet, makeDynString 등) 지식 기반 RAG 컨텍스트 추출
2. Safe Code 1:1 완결 구문 (autofix_candidate) Few-Shot 예제 제공
3. 범용 프롬프트와 RAG 컨텍스트를 동적 결합하여 할루시네이션 방지 및 검토 정밀도 극대화
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class WinCCDomainRAG:
    """WinCC OA 도메인 특화 RAG 컨텍스트 및 Few-Shot 생성기."""

    # WinCC OA 공식 매뉴얼 기반 표준 함수 지식 사서함
    KNOWLEDGE_BASE: dict[str, str] = {
        "dpConnect": (
            "API: int dpConnect(string workFunc, bool immediate, string dp1, ...);\n"
            "권장사항: dpConnect 호출 시 workFunc(콜백 함수)의 존재 여부 및 인자 시그니처(string dp, anytype val)를 "
            "반드시 일치시켜야 하며, 비동기 통신 에러 방지를 위해 반환값 에러 체크를 권장합니다."
        ),
        "dpGet": (
            "API: int dpGet(string dp1, anytype &var1, ...);\n"
            "권장사항: 동기식 데이터포인트 조회 함수로, 대량 조회 시 루프 내부에서 개별 dpGet 호출 대신 "
            "dpGetPeriod나 다중 데이터포인트 한번에 조회를 권장합니다."
        ),
        "dpSet": (
            "API: int dpSet(string dp1, anytype var1, ...);\n"
            "권장사항: 설정 실패 시 제어 설비 오동작 위험이 있으므로 dpSet 반환 코드(0 == OK)를 반드시 검사해야 합니다."
        ),
        "dpQuery": (
            "API: int dpQuery(string query, dyn_dyn_anytype &tab);\n"
            "권장사항: SQL 스타일 쿼리 수행 시 WHERE 절 조건을 명확히 기재하여 시스템 과부하를 방지해야 합니다."
        ),
        "makeDynString": (
            "API: dyn_string makeDynString(...);\n"
            "권장사항: 동적 문자열 배열 초기화 시 사용하며, 타입 불일치 방지를 위해 각 인자의 타입을 확인해야 합니다."
        ),
        "isRedundantActive": (
            "API: bool isRedundantActive();\n"
            "권장사항: 이중화(Redundancy) 시스템에서 현재 노드가 Active 서버일 때만 제어 명령이 실행되도록 방어 코드를 작성해야 합니다."
        ),
    }

    FEW_SHOT_SAFE_CODE_EXAMPLE: str = """
[WinCC OA Safe Code Few-Shot 예제]
위반 지적 메시지에 그치지 않고 사내 보안 및 성능 가이드를 만족하는 완결된 1:1 대체 구문(autofix_candidate)을 작성하십시오.

예시 입력:
  dpSet("System1:Valve1.state", 1);

예시 출력 (autofix_candidate):
  int rc = dpSet("System1:Valve1.state", 1);
  if (rc != 0) {
      DebugN("ERROR: dpSet failed for Valve1.state, rc = " + rc);
  }
"""

    @classmethod
    def get_relevant_context(cls, code_content: str, rule_ids: list[str] | None = None) -> str:
        """
        소스 코드 및 규칙 ID를 분석하여 가장 관련성 높은 WinCC OA API 사서함 컨텍스트를 추출합니다.

        Args:
            code_content: 대상 소스 코드 문자열
            rule_ids: 검사 규칙 ID 목록 (기본 None)

        Returns:
            결합된 마크다운 형식의 RAG 컨텍스트 텍스트
        """
        matched_keys: list[str] = []
        for kw, doc in cls.KNOWLEDGE_BASE.items():
            if kw.lower() in code_content.lower() or (rule_ids and any(kw.lower() in r.lower() for r in rule_ids)):
                matched_keys.append(kw)

        if not matched_keys:
            # 기본적으로 가장 핵심인 dpConnect 및 isRedundantActive 가이드를 제공
            matched_keys = ["dpConnect", "isRedundantActive"]

        context_lines = [f"- **{key}**: {cls.KNOWLEDGE_BASE[key]}" for key in matched_keys]
        return "### [WinCC OA 도메인 API 사서함 컨텍스트]\n" + "\n".join(context_lines)

    @classmethod
    def get_few_shot_prompt(cls) -> str:
        """Safe Code 1:1 완결 구문 변환을 유도하는 Few-Shot 가이드를 반환합니다."""
        return cls.FEW_SHOT_SAFE_CODE_EXAMPLE.strip()

    @classmethod
    def build_domain_prompt(cls, code_content: str, base_prompt: str, rule_ids: list[str] | None = None) -> str:
        """
        기본 프롬프트에 RAG 도메인 컨텍스트 및 Safe Code Few-Shot 예제를 결합합니다.

        Args:
            code_content: 분석 대상 소스 코드
            base_prompt: 기본 사용자/시스템 프롬프트
            rule_ids: 적용 룰셋 ID 목록

        Returns:
            도메인 특화 컨텍스트가 주입된 완성된 프롬프트
        """
        rag_ctx = cls.get_relevant_context(code_content, rule_ids)
        few_shot = cls.get_few_shot_prompt()

        enriched_prompt = (
            f"{base_prompt}\n\n"
            f"===\n"
            f"{rag_ctx}\n\n"
            f"===\n"
            f"{few_shot}\n"
        )
        return enriched_prompt
