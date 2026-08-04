"""
WinCC OA 도메인 특화 RAG 사서함 및 Few-Shot Safe Code 변환 유닛 테스트 (test_domain_rag.py).
"""

from app.core.ai.domain_rag import WinCCDomainRAG


def test_get_relevant_context_matching_keyword():
    """dpConnect 및 dpSet 사용 코드에 대한 API 사서함 검색 테스트."""
    code = 'int rc = dpConnect("cb_func", true, "System1:Valve.state");'
    ctx = WinCCDomainRAG.get_relevant_context(code)
    assert "dpConnect" in ctx
    assert "workFunc(콜백 함수)" in ctx
    assert "[WinCC OA 도메인 API 사서함 컨텍스트]" in ctx


def test_get_relevant_context_default_fallback():
    """특수 키워드가 없는 코드에 대한 기본 가이드 제공 테스트."""
    code = 'int a = 10;'
    ctx = WinCCDomainRAG.get_relevant_context(code)
    assert "dpConnect" in ctx
    assert "isRedundantActive" in ctx


def test_get_few_shot_prompt():
    """Safe Code 1:1 완결 구문 변환 Few-Shot 예제 검증."""
    few_shot = WinCCDomainRAG.get_few_shot_prompt()
    assert "autofix_candidate" in few_shot
    assert "if (rc != 0)" in few_shot


def test_build_domain_prompt():
    """RAG 컨텍스트와 Few-Shot이 결합된 통합 프롬프트 조립 테스트."""
    base_prompt = "다음 WinCC OA 코드를 심사하시오."
    code = 'dpSet("Valve1", 1);'
    enriched = WinCCDomainRAG.build_domain_prompt(code, base_prompt, rule_ids=["CTL-RES-001"])
    assert "다음 WinCC OA 코드를 심사하시오." in enriched
    assert "### [WinCC OA 도메인 API 사서함 컨텍스트]" in enriched
    assert "dpSet" in enriched
    assert "[WinCC OA Safe Code Few-Shot 예제]" in enriched
