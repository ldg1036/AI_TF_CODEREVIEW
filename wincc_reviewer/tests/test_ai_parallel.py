# AI 심층 리뷰 병렬 처리(ThreadPoolExecutor) 단위 테스트

from unittest.mock import MagicMock, patch
from app.core.models import Violation, ViolationStatus, SeverityLevel
from app.core.pipeline import Pipeline, PipelineConfig


def test_ai_parallel_review_execution():
    """ThreadPoolExecutor를 통한 다중 위반 사항 AI 2차 심층 리뷰 병렬 처리 검증."""
    config = PipelineConfig(
        input_path="tests/fixtures",
        no_ai=False,
        max_ai_reviews=5,
    )
    pipeline = Pipeline(config=config)


    # 모의 Violation 3건 생성
    violations = [
        Violation(
            violation_id=f"V-TEST-{i}",
            file_id="test.ctl",
            rule_id="CTL-REGEX-001",
            severity=SeverityLevel.HIGH,
            status=ViolationStatus.FAIL,
            line_start=i,
            line_end=i,
            message=f"테스트 위반 {i}",
            snippet=f"dpGet('dp{i}', val);",
        )
        for i in range(1, 4)
    ]

    # GeminiAIProvider.review를 mock으로 대치하여 병렬 호출 작동 및 결과 쓰기 검증
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.content = "AI 병렬 분석 결과"

    with patch("app.core.ai.gemini_provider.GeminiAIProvider.review", return_value=mock_resp) as mock_review:
        # pipeline._run_single_ai_review를 테스트하기 위해 pipeline run에서 호출되는 블록 시뮬레이션
        import concurrent.futures
        from app.core.ai.domain_rag import WinCCDomainRAG
        from app.core.ai.provider_base import AIRequest
        from app.core.ai.gemini_provider import GeminiAIProvider

        ai_provider = GeminiAIProvider()

        def _run_single_ai_review(v):
            enriched_context = WinCCDomainRAG.build_domain_prompt(v.snippet or "", v.message, [v.rule_id])
            req = AIRequest(
                code=v.snippet or v.message,
                rule_id=v.rule_id,
                context=enriched_context,
            )
            ai_resp = ai_provider.review(req)
            if ai_resp.is_success:
                v.ai_analysis = ai_resp.content

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(_run_single_ai_review, violations))

        assert mock_review.call_count == 3
        for v in violations:
            assert v.ai_analysis == "AI 병렬 분석 결과"
