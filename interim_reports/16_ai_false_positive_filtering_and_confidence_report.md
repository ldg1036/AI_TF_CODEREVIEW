# 16차 중간 보고서: AI 허위 경보(False Positive) 필터링 및 신뢰도 점수(Confidence Score) 산출 루프 구현

* 작성일자: 2026년 8월 3일
* 대상 모듈: WinCC OA 코드 리뷰 자동화 도구 (Phase 15 고도화)

---

## 1. 개요 및 구현 타당성
정적 룰 엔진이 기계적으로 검출한 경고 중 실제 SCADA 제어 시스템 도메인 맥락상 안전한 예외 상황(안전 주석, 오류 복구 핸들러 포함, 프로젝트 안전 래퍼 호출)을 식별하고 허위 경보(False Positive) 가능성 및 신뢰도 점수(Confidence Score)를 산출하는 모듈을 구축하였습니다.

---

## 2. 세부 아키텍처 및 적용 내용

1. **데이터 모델 확장 (`app/core/models.py`)**
   * `Violation` 클래스에 다음 4개 선택 필드를 하위 호환 가능하게 추가하였습니다.
     * `confidence_score` (float | None): 0.0 ~ 1.0 (정밀 신뢰도 점수)
     * `false_positive_probability` (float | None): 0.0 ~ 1.0 (허위 경보 확률)
     * `is_false_positive` (bool): AI/도메인 맥락에 따른 오탐 판정 여부
     * `ai_verification_reason` (str): 도메인 안전 컨텍스트 판단 사유 설명

2. **도메인 맥락 허위 경보 필터링 엔진 (`app/core/ai/false_positive_filter.py`)**
   * **명시적 안전 예외 주석**: `@safe`, `IGNORE_RULE`, `NO_VIOLATION` 등의 주석이 달린 구문은 신뢰도 0.05, 허위 경보 확률 0.95(False Positive = True)로 판정합니다.
   * **SCADA 공용 안전 래퍼 호출**: `safeDpSet()`, `safeDpGet()`, `batchExecute()` 등 프로젝트 내부에서 예외 처리가 검증된 래퍼 함수 호출 시 오탐으로 분류합니다.
   * **예외/오류 복구 구문 동반**: 비동기 콜백이나 통신 루프 내에서 `getLastError()` 또는 `try-catch` 복구 로직이 함께 있는 경우 안전 맥락으로 인가합니다.

3. **HTML 통합 리포트 및 파이프라인 시각화 연동**
   * 리포트 위반 항목 렌더링 카드 내에 `[🤖 AI 오탐(False Positive) 판정]` 또는 `[🤖 AI 진성 위반 검증 (Confidence: 95%)]` 배지를 시각적으로 출력하도록 `html_report_builder.py`를 보강하였습니다.

---

## 3. 과학적 실증 및 회귀 테스트 결과

1. **단위 실증 테스트 (`tests/test_false_positive_filter.py`)**
   * 5개 테스트 케이스(안전 주석, 안전 래퍼, 오류 복구 핸들러, 진성 위반 판정, 일괄 처리 기능) 100% 통과
2. **전체 시스템 회귀 테스트**
   * 실행 명령: `python -m pytest tests/ -v`
   * 최종 수치: **172 passed in 23.49s (0 Error, 0 Failure)**
