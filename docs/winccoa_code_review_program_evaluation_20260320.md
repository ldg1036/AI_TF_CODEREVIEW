# WinCC OA 코드리뷰 자동화 전수 감사 보고서

작성일: 2026-03-20

## 1. 감사 범위

- 기준: 규칙 검출 정확도 우선, UI/리포트 표현 품질은 보조 지표로 평가
- 대상 경로: UI, CLI, P1 정적 분석, P2 CtrlppCheck, 규칙 관리 상태, 리포트 생성, triage 가시성, AI/Excel on-demand 진입 상태
- 제외: `autofix apply` 실제 적용, Live AI 실호출

## 2. 실행한 기준선 검증

### 명령

```powershell
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
python backend/tools/verify_p1_rules_matrix.py
python -m unittest backend.tests.test_api_and_reports -v
python -m unittest backend.tests.test_winccoa_context_server -v
npm run test:frontend
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
python backend/main.py --selected-files BenchmarkP1Fixture.ctl
python backend/main.py --selected-files BenchmarkP1Fixture.ctl --enable-ctrlppcheck
python backend/main.py --selected-files GoldenTime.ctl
python backend/main.py --selected-files GoldenTime.ctl --enable-ctrlppcheck
```

### 핵심 결과

- `check_config_rule_alignment`: 활성 P1 규칙 1건, `review_applicability` 미참조 rule_id 43건
- `analyze_template_coverage`: Client 15/15, Server 20/20, 커버리지 100%
- `verify_p1_rules_matrix`: enabled=1, supported=0, positive rate 0%
- `test_api_and_reports`: 169개 중 11개 실패
- `test_winccoa_context_server`: 6개 모두 통과
- `npm run test:frontend`: 11 파일, 47 테스트 모두 통과
- `run_ctrlpp_integration_smoke`: 통과, finding 2건
- `playwright_ui_real_smoke`: 기본 분석은 전 파일 0행, CtrlppCheck 활성화 후에만 44개 review target 표시

### 주요 증빙 경로

- `CodeReview_Report/template_coverage_20260320_003816.json`
- `docs/perf_baselines/p1_rule_matrix_20260320_003816.json`
- `docs/perf_baselines/p1_rule_matrix_20260320_003816.md`
- `tools/integration_results/ctrlpp_integration_20260319_153830.json`
- `tools/integration_results/ui_real_smoke_20260319153959.json`
- `CodeReview_Report/20260320_004000_131829/analysis_summary.json`
- `CodeReview_Report/20260320_004000_124213/analysis_summary.json`
- `CodeReview_Report/20260320_003443_052432_30a5226e/analysis_summary.json`
- `CodeReview_Report/20260320_003501_673246_5b9971e1/analysis_summary.json`

## 3. 현재 상태 요약

### 결론

현재 프로그램은 "코드리뷰 자동화 프로그램"으로서 핵심인 P1 규칙 검출이 사실상 붕괴된 상태다.

- 실제 활성 P1 규칙 정의는 테스트용 `TEST-01` 1건뿐이다.
- `review_applicability.json`은 여전히 실제 규칙 43개를 참조한다.
- 내장 휴리스틱 검출기 구현은 다수 존재하지만, 현재 로딩 구조에서는 호출되지 않는다.
- UI와 운영 화면은 일부 녹색 상태를 보여 주지만, 이는 P1 검출 정상 동작을 의미하지 않는다.

### 현재 자동 분석 결과

| 입력 | 모드 | P1 | P2 | 관찰 |
| --- | --- | ---: | ---: | --- |
| `BenchmarkP1Fixture.ctl` | P1 only | 0 | 0 | 정적 규칙이 아무 것도 나오지 않음 |
| `BenchmarkP1Fixture.ctl` | P1+P2 | 0 | 1 | `voidReturnValueMissingInformation` 1건만 표시 |
| `GoldenTime.ctl` | P1 only | 0 | 0 | 체크리스트 기반 정적 규칙이 아무 것도 나오지 않음 |
| `GoldenTime.ctl` | P1+P2 | 0 | 43 | Ctrlpp 위주로 다량 표시, P1 대체가 아님 |

## 4. 수동 리뷰 대조

### 4.1 BenchmarkP1Fixture.ctl

대상 코드 근거:

- `CodeReview_Data/BenchmarkP1Fixture.ctl:8-10` 연속 `setValue`
- `CodeReview_Data/BenchmarkP1Fixture.ctl:14-15` 연속 `dpSet`

수동 기대 규칙 vs 자동 검출:

| 수동 기대 규칙 | 수동 근거 | 현재 P1 검출 | 현재 P2 대체 검출 | UI 노출 여부 | 리포트 반영 여부 | 분류 |
| --- | --- | --- | --- | --- | --- | --- |
| `PERF-SETMULTIVALUE-ADOPT-01` | `setValue` 3회 연속 호출 | 아니오 | 아니오 | 아니오 | 아니오 | 검출기 미연결 |
| `PERF-DPSET-BATCH-01` 계열 | `dpSet` 인접 연속 호출 | 아니오 | 아니오 | 아니오 | 아니오 | 검출기 미연결 |
| `PERF-DPSET-CHAIN` | 비가드 연속 `dpSet` | 아니오 | 아니오 | 아니오 | 아니오 | 검출기 미연결 |
| `EXC-DP-01` | `dpSet` 결과 확인/오류 계약 부재 | 아니오 | 아니오 | 아니오 | 아니오 | 검출기 미연결 |

현재 자동 결과:

- P1 only: 0건
- P1+P2: `voidReturnValueMissingInformation` 1건만 검출

판정:

- 샘플이 원래 P1 대표 규칙 검출용인데, 현재 프로그램은 체크리스트 규칙을 전혀 검출하지 못한다.
- 사용자는 "문제가 없는 파일"로 오해하기 쉽다.

### 4.2 GoldenTime.ctl

대상 코드 근거:

- `CodeReview_Data/GoldenTime.ctl:297`와 `CodeReview_Data/GoldenTime.ctl:313`의 `0.001`
- `CodeReview_Data/GoldenTime.ctl:250-257`의 수동 합산 로직
- `CodeReview_Data/GoldenTime.ctl:322-324`의 묶음 `dpSet`
- `CodeReview_Data/GoldenTime.ctl:195-218`의 무한 루프 및 `delay`

수동 기대 규칙 vs 자동 검출:

| 수동 기대 규칙 | 수동 근거 | 현재 P1 검출 | 현재 P2 대체 검출 | UI 노출 여부 | 리포트 반영 여부 | 분류 |
| --- | --- | --- | --- | --- | --- | --- |
| `HARD-03` | 임계 소수값 `0.001` 반복 하드코딩 | 아니오 | 아니오 | 아니오 | 아니오 | 검출기 미연결 |
| `PERF-AGG-01` | 루프 내 수동 집계(`sum +=`, `validCount++`) | 아니오 | 부분 대체 아님 | 아니오 | 아니오 | 검출기 미연결 |
| `Loop문 내 처리 조건` 계열 | 루프 정책은 검토 대상이나 현재 코드는 delay 존재 | 미검출 자체는 가능 | P2가 `badPerformanceInLoops`로 다른 관점 검출 | 예 | 예 | 대체 검출 의존 |

현재 자동 결과:

- P1 only: 0건
- P1+P2: 43건

현재 P2의 성격:

- 실제 WinCC OA 체크리스트에 가까운 경고보다 `undefinedVariable`, `uninitvar`, `badPerformanceInLoops` 위주로 과다 노출된다.
- 즉 "많이 잡히는 것처럼 보이지만", 사용자가 원하는 P1 체크리스트 준수 상태를 보여주는 것은 아니다.

## 5. 원인 분석

### 5.1 규칙 미적재

근거:

- `Config/p1_rule_defs.json`에는 테스트 규칙 `TEST-01`만 존재
- `check_config_rule_alignment`에서 활성 P1 규칙 1건, unknown rule_id 43건 확인

영향:

- 실제 체크리스트 규칙군이 런타임에 들어오지 않는다.

### 5.2 검출기 미연결

근거:

- `backend/core/checker_rule_loader_mixin.py:128-145`는 `p1_rule_defs.json`만 로드
- `backend/core/heuristic_checker.py:1297-1309`는 `self.p1_rule_defs`가 비어 있지 않으면 configured rule만 실행 후 즉시 반환
- 같은 파일 안에 `PERF-DPGET-BATCH-01`, `PERF-DPSET-BATCH-01`, `EXC-TRY-01`, `PERF-SETMULTIVALUE-ADOPT-01`, `STYLE-IDX-01`, `HARD-03` 구현이 존재

판정:

- "구현이 없는 것"이 아니라 "현재 구성에서는 도달할 수 없는 것"이 다수 존재한다.

### 5.3 검출기 미구현

근거:

- `ACTIVE-01`은 코드베이스에서 구현 흔적을 찾지 못함
- `PERF-GETMULTIVALUE-ADOPT-01`도 실제 checker 구현은 없고 Live AI 힌트에서만 참조됨

판정:

- 규칙 복구 후에도 일부 기대 rule은 별도 구현이 필요하다.

### 5.4 표현 계층 문제

근거:

- `tools/integration_results/ui_real_smoke_20260319153959.json`에서 기본 분석은 전 파일 0행
- 동일 smoke에서 `ctrlpp_enabled=true` 재시도 후에만 44개 review target 생성
- 같은 smoke 결과에서 `current_review_issues=44`인데 `total_issues=0`
- 설정 화면은 `P1 사용 1/1`, template coverage 100%, smoke passed로 보여 오해를 유발

판정:

- UI/운영 화면이 "P1 정상이 아님"을 명시적으로 드러내지 못한다.

### 5.5 대체 검출 의존

근거:

- Benchmark는 P1 0, P2 1
- GoldenTime는 P1 0, P2 43

판정:

- 원래 P1 체크리스트 규칙으로 설명돼야 할 항목들이 Ctrlpp 결과 유무에 지나치게 의존한다.

## 6. 테스트 실패와 연결되는 증상

`backend.tests.test_api_and_reports` 최신 실행에서 11개 실패:

- `test_api_analyze_ctl_filters_to_server_rules`
- `test_config_representative_rules_are_detected_by_checker`
  - `PERF-SETMULTIVALUE-ADOPT-01`
  - `PERF-GETMULTIVALUE-ADOPT-01`
  - `PERF-DPSET-BATCH-01`
  - `PERF-DPGET-BATCH-01`
  - `ACTIVE-01`
  - `EXC-DP-01`
  - `EXC-TRY-01`
  - `STYLE-IDX-01`
  - `HARD-03`
- `test_post_api_analyze_p1_violations_include_file_field`

해석:

- 실패가 UI 랜더링 깨짐보다 "대표 P1 규칙이 0건"에 집중되어 있다.
- 즉 현재 문제의 중심은 프런트엔드가 아니라 P1 규칙 구성/연결 계층이다.

## 7. 우선 수정 Top 5

1. `Config/p1_rule_defs.json`를 실제 운영 규칙 세트로 복구하고 `review_applicability.json`과 동기화
2. `heuristic_checker.py`에서 configured rule이 실질적으로 무효할 때 built-in checker로 안전하게 fallback하도록 수정
3. `ACTIVE-01`, `PERF-GETMULTIVALUE-ADOPT-01`처럼 기대되지만 실제 checker가 없는 규칙을 구현
4. release gate에 `supported_rules == 0`, `review_applicability_unknown_rule_id_count > 0` 차단 조건 추가
5. UI/운영 화면에 "P1 misconfigured" 상태를 직접 노출하고 `total_issues`/`current_review_issues` 카운터 불일치 수정

## 8. 승인 전 보류 항목

- `autofix apply` 실제 적용 검증
- Live AI 실호출
- 규칙 파일 복구/교체와 연결 코드 수정

## 9. 최종 판정

현재 프로그램은:

- UI, 컨텍스트 서버, Ctrlpp 경로 자체는 살아 있음
- 하지만 "WinCC OA 코드리뷰 자동화"의 핵심인 P1 체크리스트 검출은 현재 신뢰할 수 없음
- 사용자는 Ctrlpp 결과가 보이기 때문에 전체 코드리뷰가 정상 수행된 것으로 오해할 수 있음

따라서 현재 상태의 1차 결론은 다음과 같다.

- 주 결함: `P1 규칙 구성/적재 파이프라인 붕괴`
- 부 결함: 일부 기대 규칙은 실제 구현 부재
- UX 결함: 운영 화면과 스모크 통과 표시가 현재 실패 상태를 충분히 경고하지 못함
