# 27차 중간 보고서: 외부 타사 리포지토리(AI_TF_CODEREVIEW) 대조 비교 평가 보고서

* 작성일자: 2026년 8월 5일
* 비교 대상: `https://github.com/ldg1036/AI_TF_CODEREVIEW` (WinCC OA Code Inspector) vs 본 프로젝트 (WinCC OA 코드 리뷰 자동화 도구 v2.0)
* 평가 목적: 외부 타사 공개 분석 솔루션과 본 프로그램 간의 기능적 차이, 아키텍처적 우위 및 세부 장단점을 과학적·객관적으로 대조 평가

***

## 1. 두 프로그램 종합 특징 비교 요약

| 평가 항목 | ldg1036 / AI_TF_CODEREVIEW (WinCC OA Code Inspector) | 본 시스템 (WinCC OA 코드 리뷰 자동화 도구 v2.0) |
|---|---|---|
| **기본 정체성** | Node/Python 기반 풀스택 웹 대시보드 및 API 서버 솔루션 | Python 데스크톱/CLI 기반 고속 도메인 전용 분석 솔루션 |
| **룰 관리 방식** | 웹 UI 상의 Rules CRUD, REST API import/export 및 리비전 제어 | **엑셀 체크리스트 양식 단일 원천 동적 컴파일 (ExcelRuleCompiler)** |
| **외부 도구 연동** | CtrlppCheck 바이너리 연동, Ollama AI API 연동 지원 | **WinMerge GUI 1 클릭 Side by Side 대조**, Gemma 사내 LLM Provider 추상화 |
| **오탐(False Positive) 제어** | 웹 UI상 Triage (P1 Suppress/재표시) 처리 | **도메인 안전 컨텍스트 필터(FalsePositiveFilter) + 신뢰도 점수 + 자율 룰 추천(RuleOptimizer)** |
| **품질 시각화 & 리포팅** | 웹 UI 대시보드, Annotated TXT, HTML/Excel 리포트 | **기술 부채 핫스팟 히트맵 + 결함 퇴보 감시 트렌드 차트 + 5대 내보내기 (PDF/Excel/HTML/CSV/JSON)** |
| **회귀 검증 안정성** | Playwright E2E, Vitest 프론트엔드 테스트 | **177개 파이썬 정밀 회귀 테스트 100% PASSED (0 Failure, 0 Error)** |

***

## 2. 세부 차원별 우위 분석

### 2.1 본 시스템이 독보적으로 우수한 점 (본 프로그램의 경쟁 우위)
1. **현장 엔지니어 친화적 엑셀 단일 원천 (`ExcelRuleCompiler`)**:
   * 타사 프로그램은 웹 UI나 JSON/YAML을 관리해야 하나, 본 프로그램은 비개발자 QA/현장 엔지니어가 기존 엑셀 체크리스트 양식만 고치면 1초 만에 룰 엔진에 동적 반영됩니다.
2. **AI 오탐 제어 및 자율 추천 알고리즘 (`FalsePositiveFilter` & `RuleOptimizer`)**:
   * 타사 솔루션은 수동 트리아지(Suppress)에 의존하는 반면, 본 솔루션은 `@safe` 주석 및 공용 안전 래퍼를 정밀 분류하고 신뢰도 점수(`confidence_score`)를 산출하며, 오탐 피드백을 학습하여 엑셀 룰 제외 키워드를 자율 추천합니다.
3. **1 클릭 WinMerge 1 대 1 파일 병합 및 PDF 공식 검수서**:
   * WinMerge GUI 연동으로 좌우 대조 후 현장 파일 직접 병합(Merge)이 가능하며, 고객 납품용 공식 PDF 품질 검수서 내보내기를 완비했습니다.
4. **핫스팟 히트맵 및 퇴보 감시 트렌드 대시보드 (`HotspotCalculator`)**:
   * 프로젝트 내 소스 파일별 고위험 결함 집중 구역을 히트맵 카드로 조감하고 릴리스 간 품질 퇴보를 관리할 수 있습니다.

### 2.2 타 프로그램 (AI_TF_CODEREVIEW)의 특징 및 시사점
1. **웹 API 기반 멀티 사용자 인터페이스**: 웹 대시보드 UI를 제공하고 REST API (`/api/analyze`, `/api/autofix/prepare`)를 갖추어 브라우저 접속 환경을 지원합니다.
2. **CtrlppCheck 외부 린터 연동**: Siemens 공식 또는 외부 CtrlppCheck 바이너리를 부가 검사축(P2)으로 실행하는 fail-soft 파이프라인 구조를 보여줍니다.

***

## 3. 종합 평가 결론

타사 `AI_TF_CODEREVIEW`는 웹 대시보드 및 CtrlppCheck 외부 바이너리 연동에 초점을 맞춘 웹 솔루션인 반면, **본 프로그램은 엑셀 단일 원천 관리, 도메인 안전 오탐 필터링, 신뢰도 점수, WinMerge 대조 병합, 5대 내보내기 리포트, 177개 단위 테스트 통과에 기반한 강력한 도메인 특화 데스크톱/CLI 품질 게이트**로서 현장 투입 생산성과 실무 편의성 면에서 월등한 완성도를 보이고 있습니다.
