# WinCC OA 코드리뷰 자동화 재감사 보고서

작성일: 2026-03-21

## 1. 실행 범위

- 기준선 점검
  - `python backend/tools/check_config_rule_alignment.py --json`
  - `python backend/tools/verify_p1_rules_matrix.py`
  - `python backend/tools/analyze_template_coverage.py`
  - `python -m unittest backend.tests.test_winccoa_context_server -v`
  - `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
- 실제 사용자 흐름
  - fresh UI smoke 실행
  - 브라우저 수동 점검: `대시보드 -> 작업공간 -> 설정`
  - 샘플 파일: `BenchmarkP1Fixture.ctl`, `GoldenTime.ctl`
  - 경계 파일: `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`
- 산출물 확인
  - UI smoke JSON
  - `analysis_summary.json`
  - Excel 결과서
  - rules list/export API
  - AI models API

## 2. 기준선 결과

- config alignment
  - `p1_rule_rows=43`
  - `enabled=42`
  - `review_applicability_unknown_rule_id_count=0`
- P1 matrix
  - `enabled=42`
  - `supported=42`
  - `positive_rate=100%`
  - `negative_rate=100%`
  - `checker_vs_api_mismatch_rate=0%`
- template coverage
  - Client `15/15`
  - Server `20/20`
- context server unittest
  - `6 passed`
- Ctrlpp smoke
  - `passed`
  - `finding_count=2`

주요 증빙:

- `D:\AI_TF_CODEREVIEW-main\docs\perf_baselines\p1_rule_matrix_20260321_210508.md`
- `D:\AI_TF_CODEREVIEW-main\docs\perf_baselines\p1_rule_matrix_20260321_210508.json`
- `D:\AI_TF_CODEREVIEW-main\CodeReview_Report\template_coverage_20260321_210531.json`
- `D:\AI_TF_CODEREVIEW-main\tools\integration_results\ctrlpp_integration_20260321_120532.json`

## 3. 실제 UI 점검 결과

### 3.1 대시보드 / 설정

- `UI Benchmark: passed`
- `UI Real Smoke: passed`
- `Ctrlpp Integration: passed`
- `P1 활성 42`
- `미참조 rule_id 0`
- `Degraded NO`
- `Mode configured`
- `/api/rules/list` 200 응답 확인
- `/api/rules/export` 200 응답 확인
- `/api/ai/models` 200 응답 확인, `qwen2.5-coder:3b` 포함

### 3.2 작업공간 수동 재현

#### BenchmarkP1Fixture.ctl

작업공간 UI에서 P1 only 분석 시 아래 4건이 정확히 표시됨.

- `PERF-SETMULTIVALUE-ADOPT-01`
- `ACTIVE-01`
- `EXC-TRY-01`
- `EXC-DP-01`

세부 패널, 코드 뷰어, Excel 상세결과 모두 같은 rule id와 severity를 유지함.

#### GoldenTime.ctl

작업공간 UI에서 P1 only 분석 시 아래 4건이 정확히 표시됨.

- `HARD-01` at line 16
- `STYLE-IDX-01` at line 159
- `PERF-EV-01` at line 195
- `HARD-03` at line 298

세부 패널, 코드 뷰어, Excel 상세결과 모두 같은 rule id와 severity를 유지함.

### 3.3 경계 파일

- `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`는 파일 목록, 분석 대상, reviewed txt 생성까지 정상 동작함
- 최신 UI smoke 기준 전체 분석 3파일 중 하나로 포함되어 처리 완료됨

주요 증빙:

- `D:\AI_TF_CODEREVIEW-main\tools\integration_results\ui_real_smoke_20260321120555.json`
- `D:\AI_TF_CODEREVIEW-main\CodeReview_Report\20260321_210808_271945\analysis_summary.json`
- `D:\AI_TF_CODEREVIEW-main\CodeReview_Report\20260321_211150_033059\analysis_summary.json`
- `D:\AI_TF_CODEREVIEW-main\CodeReview_Report\20260321_210808_271945\CodeReview_Submission_BenchmarkP1Fixture_20260321_210808_271945.xlsx`
- `D:\AI_TF_CODEREVIEW-main\CodeReview_Report\20260321_211150_033059\CodeReview_Submission_GoldenTime_20260321_211150_033059.xlsx`

## 4. 수동 리뷰 대조

### 4.1 BenchmarkP1Fixture.ctl

수동 판정:

- line 8: 연속 `setValue` 3회 -> `PERF-SETMULTIVALUE-ADOPT-01`
- line 8: 상태 변경 호출 전 active/enable guard 없음 -> `ACTIVE-01`
- line 14: `dpSet` 호출에 대한 try/catch 부재 -> `EXC-TRY-01`
- line 14: `dpSet` 결과/오류 확인 부재 -> `EXC-DP-01`

자동 결과:

- CLI P1 only: 4/4 일치
- UI P1 only: 4/4 일치
- Excel 상세결과: 4/4 일치

### 4.2 GoldenTime.ctl

수동 판정:

- line 16: `"config/config.GoldenTime"` 하드코딩 -> `HARD-01`
- line 159: `parsedData[1]`, `parsedData[2]` 등 인덱스 매직넘버 -> `STYLE-IDX-01`
- line 195 이후: loop -> `GoldenTimeCalculation()` -> 내부 `dpSet` 수행 -> `PERF-EV-01`
- line 298: `0.001` 임계 소수 상수 -> `HARD-03`

자동 결과:

- CLI P1 only: 4/4 일치
- UI P1 only: 4/4 일치
- Excel 상세결과: 4/4 일치

## 5. 현재 결함 및 개선사항

### 5.1 규칙 검출 관점

- 이번 재감사 범위의 대표 샘플 2종에서는 필수 수동 기대 규칙 누락이 없었음
- 이번 재감사 범위에서 대표 샘플 기준 critical false positive는 확인되지 않았음
- 현재 P1 규칙 검출 엔진 자체는 대표 샘플 기준으로 정상 판정 가능 상태임

### 5.2 제품 사용성 관점의 남은 문제

#### A. Live AI / Autofix 결과 품질 부족

Benchmark `PERF-SETMULTIVALUE-ADOPT-01` 이슈에서 Live AI review 생성 후 compare/prepare를 수행하면 LLM proposal preview에 아래 문제가 보였음.

- 예시 코드 텍스트가 실제 대상 코드로 충분히 치환되지 않음
- literal `=>` 표기가 남아 있음
- 실제 파일의 `A.B.C1`, `A.B.C2`, `A.B.C3` 대신 예시용 객체명(`obj_auto_sel1`)이 노출됨

판정:

- `규칙 검출 실패`가 아니라 `AI/autofix 품질 문제`
- 자동 적용 신뢰도는 아직 낮음

#### B. AI compare 기본 선택 정책 개선 필요

- Live AI review를 막 생성한 직후 compare/prepare를 열었을 때 기본 선택이 `LLM`이 아니라 `RULE` 후보로 유지됨
- 사용자가 수동으로 `LLM` 후보를 눌러야 실제 AI 제안 diff를 볼 수 있었음

판정:

- `검출 실패`는 아님
- 실사용 UX와 AI 기능 가시성을 떨어뜨리는 선택 정책 문제

#### C. mixed encoding 표시 품질

- `GoldenTime.ctl` 원문 일부 주석은 콘솔 인코딩에서 깨져 보였음
- 다만 UI, rule id, line 매핑, Excel 결과서에는 직접적인 검출 오류를 만들지는 않았음

판정:

- `검출 로직 문제`보다는 텍스트 표시/콘솔 인코딩 문제

## 6. 최종 판정

이번 재감사 기준 결론:

- WinCC OA 코드리뷰 자동화 프로그램은 대표 샘플 2종에서 WinCC OA 코드리뷰 규칙대로 `검출은 정상 동작`함
- 현재 프로그램상의 결과물과 수동 1차 코드리뷰 결과는 대표 샘플 기준으로 일치함
- 현재 우선 개선 포인트는 `규칙 미검출`보다 `Live AI/autofix 품질`과 `proposal 기본 선택 UX`에 있음

우선순위 제안:

1. Live AI/autofix prompt/post-processing 보강
2. compare modal 기본 proposal 선택 정책 개선
3. mixed encoding 원문 표시 개선
4. representative sample 외 추가 실파일 세트 확장 감사
