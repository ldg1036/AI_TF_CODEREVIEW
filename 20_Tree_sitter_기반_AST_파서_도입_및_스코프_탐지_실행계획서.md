# 20_Tree_sitter_기반_AST_파서_도입_및_스코프_탐지_실행계획서.md

# Tree sitter 기반 구문 AST 파서 도입 및 스코프 기반 탐지 고도화 실행계획서

작성 목적: 정규식 기반 정적 분석의 본질적 한계를 극복하고, Tree sitter 구문 분석 엔진을 도입하여 WinCC OA CTRL 및 C++ 소스 코드를 구문 분석 트리(AST)로 구조화함으로써 스코프 기반 정밀 탐지를 수행하고 오탐률을 0%에 가깝게 최소화하는 실행 계획을 정의한다.

===

## 0. 개요 및 도입 필요성

* 기존 문제점: 단순 정규식 패턴 파서는 주석 내부, 문자열 리터럴, 복합 조건문 분기 스코프 및 함수 변수 생명주기를 인지하지 못하여 오탐을 발생시키는 구조적 한계가 존재함.
* 개선 핵심: Tree sitter 파서 라이브러리를 연동하여 CTRL 및 C++ 문법 구문 트리(AST)를 생성하고, 블록 심볼 스코프 추적 엔진을 구축하여 정적 룰 체커의 분석 정밀도를 극대화함.

===

## 1. 아키텍처 설계 및 모듈 구상

### 1.1 TreeSitterASTParser 모듈 추가
* 위치: [tree_sitter_parser.py](file:///c:/Users/39145/Downloads/클로드prd/wincc_reviewer/app/core/parser/tree_sitter_parser.py)
* 역할:
  1. WinCC OA CTRL 및 C++ 문법 파일(.ctl, .pnl 내부 스크립트)의 Concrete Syntax Tree 생성
  2. 노드 타입 분류(FunctionDeclaration, CompoundStatement, IfStatement, VariableDeclaration, Comment, StringLiteral)
  3. AST 노드 기반 코드 스니펫 및 라인범위 맵핑 제공

### 1.2 스코프 기반 룰 엔진 (Scope Aware Rule Engine) 연동
* 변수 및 함수 스코프 샌드박스 추적: 변수가 선언된 함수 또는 블록 내부에서의 이용 범위 분석
* Guard Clause 인지: 조건식 및 예외 리턴 구문이 포함된 AST 부모 노드를 탐색하여 안전 예외 자동 부여

===

## 2. 룰 체커 AST 바인딩 3대 전략

### 전략 1: 주석 및 문자열 노드 물리적 검사 제외 (AST Node Masking)
* AST 상의 `comment` 노드 및 `string_literal` 노드를 정적 검사 대상에서 사전 마스킹하여 텍스트 오인 오탐 100% 방지

### 전략 2: 제어 흐름 스코프 감지 (Control Flow Scope Awareness)
* `while`, `for` 루프 내부의 무한 루프 검사 시, AST 상의 `break`, `return`, `delay()`, `sleep()` 노드 존재 유무를 블록 단위로 정확하게 파싱하여 오탐 차단

### 전략 3: 래퍼 함수 및 가드 노드 부모 추적 (Parent Node Inspection)
* 호출 노드의 상위 AST 조상 노드를 탐색하여 `getLastError()`, `try_catch`, `safeDpSet` 가드에 둘러싸여 있는지 추적

===

## 3. 단계별 이행 절차

* 단계 1: tree_sitter 파서 의존성 및 C++/CTRL 문법 바인더 구현 [tree_sitter_parser.py](file:///c:/Users/39145/Downloads/클로드prd/wincc_reviewer/app/core/parser/tree_sitter_parser.py)
* 단계 2: 정적 분석 파이프라인 `NormalizationService`에 AST 파서 연동
* 단계 3: 33개 정적 룰 체커 AST 쿼리 및 스코프 추적 로직 바인딩
* 단계 4: 235개 단위 테스트 스위트 회귀 검증 및 [scripts/18_eval_raw_web_golden_set.py](file:///c:/Users/39145/Downloads/클로드prd/scripts/18_eval_raw_web_golden_set.py) 벤치마크 실측 평가

===

## 4. 완료 기준 (DoD)

* [tree_sitter_parser.py](file:///c:/Users/39145/Downloads/클로드prd/wincc_reviewer/app/core/parser/tree_sitter_parser.py) AST 생성 및 스코프 탐지 기능 단위 테스트 통과
* 34개 원본 데이터셋 벤치마크 평가 오탐 건수 0건 달성 (정밀도 100.0% 지향)
* 235개 기존 단위 테스트 100% 통과 유지
* [single_source_metrics.json](file:///c:/Users/39145/Downloads/클로드prd/intermediate_results/single_source_metrics.json) 및 관련 개발 문서 SSOT 최신 수치 동기화
