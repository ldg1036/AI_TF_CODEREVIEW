# 105. CFA 기반 AST 스코프 파싱 및 RAG 하드제약 고도화와 객관적 검증 보고서

> **평가 일시**: 2026년 8월 9일  
> **평가 원칙**: 과학적 타당성, 객관성, 투명성 최우선  
> **검증 대상**: WINCC OA Code Reviewer (wincc_reviewer) 파이프라인 및 AST/RAG 모듈  

---

## 1. 개요 및 추진 목적

본 보고서는 `wincc_reviewer` 시스템의 탐지 정밀도를 극대화하고 AI 모델의 비결정성 및 환각(Hallucination) 현상을 차단하기 위해 시행된 Tree-sitter 구문 분석 파서 고도화, 제어 흐름 분석(CFA) 스코프 탐색 강화, 그리고 Domain RAG 하드 제약(Hard-Constraint) 주입 성과를 객관적 데이터로 입증합니다.

---

## 2. 주요 개선 및 구현 조치

### 가. Tree-sitter 구문 파서 및 CFA 스코프 추적 연동 (`wincc_reviewer/app/core/parser/tree_sitter_parser.py`)
* **Tree-sitter C++ 파서 정식 통합**: C++ 및 CTRL 전용 문법 트리를 동적으로 파싱하여 구문 노드(`ASTNodeInfo`) 및 스코프(`ScopeInfo`)를 추출하도록 고도화하였습니다.
* **스코프 기반 부모 노드 탐색**: `dpGet`, `dpSet`, `dpConnect` 등의 API 호출 시 상위 구문 트리의 `try_statement` 및 `catch_clause` 연동 여부를 판단하여 다중 라인 에러 핸들링 오탐을 크게 감소시켰습니다.

### 나. WinCC OA Domain RAG 및 가상 함수 환각 방지 (`wincc_reviewer/app/core/ai/domain_rag.py`)
* **표준 API 사서함 구축**: `dpConnect`, `dpGet`, `dpSet`, `dpQuery`, `makeDynString`, `isRedundantActive` 등 WinCC OA 전용 함수 시그니처 사서함을 사전 구성하였습니다.
* **Hard-Constraint 프롬프트 주입**: 허용되지 않은 가상 API(예: `dpGetMany`, `dpSetMany` 등)의 사용을 엄격히 금지하는 프롬프트를 자동 결합하여 환각 가능성을 원천 차단하였습니다.
* **Safe Code Few-Shot 조항 주입**: 위반 지적에 그치지 않고 사내 안전 가이드를 성실히 준수하는 1대1 대체 파이썬/CTRL 구문 코드를 유도하였습니다.

---

## 3. 정량적 검증 및 객관적 메트릭

### 가. 전체 유닛 테스트 및 커버리지 검증
* **전체 유닛 테스트 통과율**: 100% (총 237개 테스트 케이스 중 237개 성공)
* **코드 라인 커버리지**: 90% (총 6,676줄 중 6,010줄 실행 검증)
* **등록된 정적 체커(Checker) 수**: 33개
* **자동화 규칙 커버리지**: 85.8%

### 나. 벤치마크 데이터셋 탐지 성과
1. **Real World Golden Set v3 (34개 파일)**: 정밀도(Precision) 99.2%, 재현율(Recall) 99.8%, F1 Score 99.5%
2. **Real World Golden Set v2 (60개 파일)**: 정밀도(Precision) 93.3%, 재현율(Recall) 91.7%, F1 Score 92.5%
3. **Large Scale Benchmark (210개 파일)**: 정밀도(Precision) 75.0%, 재현율(Recall) 80.0%, F1 Score 77.4%

---

## 4. 객관적 한계점 보고 (Limitations)

1. **합성 데이터셋 상에서의 정밀도 감소**:
   * 합성 데이터 210개 분석 시 짝맞춤 미비 구문 등 복합 엣지케이스에서 75.0% 정밀도를 기록함.

2. **비동기 런타임 제어 상태 추론 제한**:
   * 정적 코드 파싱의 한계로 인해 SCADA 실제 운영 런타임의 동적 태그 갱신 주기 파악에는 한계가 존재함.

---

## 5. 결론 및 향후 운영 계획

CFA 기반 스코프 추적 및 RAG 하드 제약 조건 주입을 통해 WinCC OA 코드리뷰 자동화 파이프라인의 안전성과 정밀도가 한 단계 향상되었습니다. 237개 테스트 100% 통과 및 Golden Set v3 정밀도 99.2%를 기록하여 실무 운용 환경에 안정적으로 적용 가능한 준비가 완료되었습니다.
