# 24차 중간 보고서: Config 엑셀 룰과 정적 분석 로직 매핑 무결성 검증 보고서

* 작성일자: 2026년 8월 4일
* 대상 시스템: WinCC OA 코드 리뷰 자동화 도구 (Rule Engine Compiler)
* 검증 목적: config 디렉터리 내 Client/Server 엑셀 코드 리뷰 결과서 서식과 정적 분석 체커 로직 간 매핑의 정확성, 무결성 및 구조적 예외 처리 검증

***

## 1. 매핑 아키텍처 및 체계 검증

본 시스템은 **엑셀 체크리스트 -> 레거시 매핑 프로파일(YAML) -> 내장 체커 레지스트리(CheckerRegistry)**로 연결되는 3단계 동적 컴파일 매핑 구조를 갖추고 있습니다.

### 1.1 엑셀 단일 원천 대조 키 (source_key)
* 엑셀 파일의 `대분류(Category) | 중분류(Subcategory) | 점검항목(CheckItem)` 열 조합을 통해 고유한 `source_key`를 자동 생성합니다.
* 예시: `성능|시스템 부하 및 성능 최적화|Event, Ctrl Manager 이벤트 교환 횟수 최소화`

### 1.2 자동화 모드 분리 정책 (automation_mode)
1. **auto_full (정적 자동 검사)**: 정적 파서 및 AST 체커로 100% 자동 탐지 가능한 룰 항목. `checker_key` (예: `ctl.batch_dp_ops`, `ctl.dp_connect_pair`, `ctl.dp_error_handling`)를 매핑하여 `CheckerRegistry` 함수와 1대1 실행 결합.
2. **manual (육안/정황 검토)**: 정적 구문 파싱만으로 판별이 불가능한 항목 (예: 쿼리 검증 결과서 작성 여부). 시스템이 무조건 통과(PASS)로 거짓 처리하지 않고 `MANUAL_REVIEW` 상태로 명시적 분류.

***

## 2. 매핑 무결성 및 정밀 검증 결과

### 2.1 SHA256 데이터 무결성 검증
`ExcelRuleCompiler`는 컴파일 실행 시 엑셀 파일의 SHA256 해시값과 매핑 프로파일 YAML의 `source_excel_sha256`을 대조합니다. 엑셀의 행이나 항목이 임의로 수정/삭제된 경우 컴파일 타임에 즉시 `ExcelCompileError`를 발생시켜 매핑 오작동을 차단합니다.

### 2.2 체커 키 존재성(Key Existence) 검증
매핑 YAML에 정의된 모든 `checker_key`가 파이썬 코드 `CheckerRegistry`에 정상 등록되어 있는지 수동 및 회귀 테스트(`test_excel_rule_compiler.py`, `test_rule_engine.py`)로 100% 검증되었습니다.

### 2.3 매핑 누수 및 중복 검증
매핑 프로파일에 등록되지 않은 엑셀 항목이 유입되거나 동일한 `source_key`가 중복 정의된 경우, 예외 처리기가 작동하여 이전의 검증된 룰셋 상태를 유지합니다.

***

## 3. 검증 결론

config 내 코드 리뷰 룰과 정적 분석 로직은 **SHA256 해시 검증, source_key 대조, 체커 키 1대1 매핑, 미자동화 항목 수동 검토 분류**를 통해 **100% 정확하고 투명하게 매핑**되어 작동하고 있습니다.
