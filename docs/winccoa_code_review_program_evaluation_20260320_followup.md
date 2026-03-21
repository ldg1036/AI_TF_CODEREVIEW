# WinCC OA 코드리뷰 자동화 프로그램 후속 구현 보고서
작성일: 2026-03-20

## 1. 목적

이 문서는 2026-03-20 전수 감사에서 확인된 핵심 결함을 후속 구현으로 복구한 뒤,
실제 프로그램이 WinCC OA 코드리뷰 자동화 도구로서 다시 동작하는지 확인한 결과를 정리한다.

이번 라운드의 목표는 세 가지였다.

- P1 규칙 정의 복구
- degraded P1 config 감지와 fail-soft fallback 구현
- UI, API, 리포트가 현재 상태를 사실대로 보여주도록 정직성 확보

## 2. 핵심 결론

결론부터 말하면, 이전 감사에서 확인된 "P1 정적 규칙 검출 붕괴" 상태는 해소되었다.

- `Config/p1_rule_defs.json`은 정상 기준으로 복구되었다.
- `review_applicability.json`과의 unknown rule id mismatch는 0건이 되었다.
- degraded P1 config를 감지하는 health 정보가 런타임, API, 리포트, UI에 모두 노출된다.
- configured P1이 깨져도 기존 built-in P1 경로가 함께 실행되도록 fallback이 추가되었다.
- `BenchmarkP1Fixture.ctl`, `GoldenTime.ctl` 모두 P1 only 분석에서 실제 P1 결과가 다시 나온다.
- `analysis_summary.json`의 `summary.p1_total`도 실제 P1 finding 수 기준으로 수정되었다.

즉, 현재 프로그램은 다시 "P1 정적 규칙 기반 코드리뷰 자동화 프로그램"으로 동작한다.
다만 이후 단계에서는 오검출/누락률 튜닝과 규칙 정밀도 개선을 별도 품질 단계로 가져가는 것이 맞다.

## 3. Before / After

| 항목 | 복구 전 | 복구 후 |
| --- | --- | --- |
| P1 규칙 정의 | 활성 1건, 테스트 규칙만 존재 | 총 43건, 활성 42건 |
| `review_applicability` unknown rule id | 43 | 0 |
| P1 매트릭스 지원률 | enabled=1, supported=0 | enabled=42, supported=42 |
| P1 positive rate | 0% | 100% |
| `BenchmarkP1Fixture.ctl` P1 only | 0건 | 5건 |
| `GoldenTime.ctl` P1 only | 0건 | 9건 |
| UI 기본 분석 결과 | Ctrlpp off에서 0행 | Ctrlpp off에서도 행 렌더링 |
| 설정 화면 상태 표기 | `P1 사용 1/1`처럼 오해 유발 | `P1 활성`, `미참조 rule_id`, `Degraded`, `Mode` 직접 표기 |
| `analysis_summary.json`의 `p1_total` | P1 그룹 수 | 실제 P1 finding 수 |

## 4. 구현 내용

### 4.1 P1 규칙 정의 복구

- `Config/p1_rule_defs.json`을 `519ab33` 기준으로 복구했다.
- `PERF-DPSET-CHAIN`은 요청대로 `enabled: false`를 유지했다.
- 복구 후 총 43행, 활성 42행 상태를 확인했다.

### 4.2 P1 config health 추가

런타임에서 아래를 기준으로 `p1_config_health`를 계산한다.

- 활성 규칙 수가 1개 이상인지
- `review_applicability` unknown rule id가 0인지
- configured detector op가 현재 실행기에서 지원 가능한지

health가 깨지면 다음 정보가 노출된다.

- `degraded`
- `mode`
- `reason_codes`
- `unknown_review_rule_ids`
- `unsupported_detector_ops`

### 4.3 degraded fallback 구현

이전에는 `self.p1_rule_defs`가 비어 있지 않으면 configured P1만 실행하고 바로 return했다.
이 구조 때문에 깨진 설정 파일이 있어도 기존 built-in P1 검출기가 완전히 우회됐다.

지금은 다음처럼 동작한다.

- healthy config: configured P1만 사용
- degraded config: configured P1 + legacy/built-in P1를 함께 실행
- 결과 병합: `(rule_id, line, message, file)` 기준 dedupe

이 변경으로 "구성 파일이 깨졌는데 침묵 실패하는 상태"를 막았다.

### 4.4 상태 표기 / 리포트 정직성 개선

다음 출력에 `p1_config_health`가 포함된다.

- `/api/rules/health`
- `/api/analyze` 응답
- `analysis_summary.json`
- 설정 화면 규칙/의존성 관리 카드

### 4.5 P1 요약 카운트 정정

후속 검증 과정에서 `summary.p1_total`이 실제 finding 수가 아니라 P1 그룹 수로 집계되는 문제를 추가로 발견했다.
이번 라운드에서 이 부분도 같이 수정했다.

## 5. 샘플 파일 검증

### 5.1 BenchmarkP1Fixture.ctl

P1 only 결과:

- `ACTIVE-01`
- `EXC-DP-01`
- `EXC-TRY-01`
- `PERF-SETMULTIVALUE-ADOPT-01`
- `STYLE-NAME-01`

총 5건의 P1 finding이 다시 검출된다.

P1+P2 결과:

- P1 5건 유지
- P2 `voidReturnValueMissingInformation` 1건 추가

즉, Ctrlpp는 다시 "대체 채널"이 아니라 "추가 채널"로 동작한다.

### 5.2 GoldenTime.ctl

P1 only 결과:

- `CFG-01`
- `HARD-01`
- `HARD-03`
- `LOG-LEVEL-01`
- `PERF-01`
- `PERF-EV-01`
- `SAFE-DIV-01`
- `STYLE-IDX-01`
- `STYLE-NAME-01`

총 9건의 P1 finding이 검출된다.

P1+P2 결과:

- P1 9건 유지
- P2 43건 추가

즉, `GoldenTime.ctl`도 이제 P1 only 분석에서 의미 있는 결과를 제공한다.

## 6. 실제 UI 점검 결과

fresh port로 백엔드를 직접 띄우고 실제 브라우저에서 확인했다.

- `대시보드 -> 설정` 이동 정상
- 설정 화면에 다음 값 표시 확인
  - `P1 활성 42`
  - `미참조 rule_id 0`
  - `Degraded NO`
  - `Mode configured`
- fresh UI smoke에서 `BenchmarkP1Fixture.ctl` 기준 Ctrlpp off 상태로 `38`개 결과 행 렌더링 확인

즉, 기존처럼 "Ctrlpp를 켜야만 결과가 보이는 상태"는 재현되지 않았다.

## 7. 검증 결과

실행한 주요 검증:

```powershell
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
python backend/tools/verify_p1_rules_matrix.py
python -m unittest backend.tests.test_api_and_reports -v
python -m unittest backend.tests.test_winccoa_context_server -v
npm run test:frontend
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
node tools/playwright_ui_real_smoke.js --port 8877 --timeout-ms 120000
python backend/main.py --selected-files BenchmarkP1Fixture.ctl
python backend/main.py --selected-files BenchmarkP1Fixture.ctl --enable-ctrlppcheck
python backend/main.py --selected-files GoldenTime.ctl
python backend/main.py --selected-files GoldenTime.ctl --enable-ctrlppcheck
```

핵심 결과:

- `check_config_rule_alignment`: unknown rule id 0
- `analyze_template_coverage`: Client/Server 100%
- `verify_p1_rules_matrix`: enabled 42, supported 42, positive rate 100%
- `backend.tests.test_api_and_reports`: 171 passed, 1 skipped
- `backend.tests.test_winccoa_context_server`: 6 passed
- `npm run test:frontend`: 47 passed
- `run_ctrlpp_integration_smoke`: passed
- `playwright_ui_real_smoke`: passed, fresh backend instance 기준 검증

## 8. 주요 산출물

- `docs/perf_baselines/p1_rule_matrix_20260320_011003.json`
- `docs/perf_baselines/p1_rule_matrix_20260320_011003.md`
- `tools/integration_results/ui_real_smoke_20260319161900.json`
- `tools/integration_results/ctrlpp_integration_20260319_161132.json`
- `CodeReview_Report/20260320_012527_574678/analysis_summary.json`
- `CodeReview_Report/20260320_012527_578946_6cf6ac2f/analysis_summary.json`
- `CodeReview_Report/20260320_012527_602075/analysis_summary.json`
- `CodeReview_Report/20260320_012527_578946/analysis_summary.json`

## 9. 남은 과제

현재 blocker 급 결함은 해소됐다.
이후 단계에서는 아래를 별도 품질 개선 과제로 보는 것이 적절하다.

1. 샘플 외 실파일에 대한 오검출/누락률 측정
2. 규칙별 precision / recall 비교표 작성
3. Ctrlpp와 P1 결과의 중복/상호보완 설명 개선
4. 감사 산출물과 runtime backup 산출물 정리 정책 수립

## 10. 최종 판단

이전 감사 시점의 프로그램은 "P1 정적 규칙 검출 붕괴" 상태였다.
후속 구현 이후 현재 프로그램은 다음 기준을 충족한다.

- P1 규칙 정의가 정상적으로 로드된다.
- 설정이 깨지면 degraded 상태가 명시된다.
- degraded 상태에서도 검출이 0건으로 침묵 실패하지 않는다.
- API, 리포트, UI가 현재 상태를 숨기지 않는다.
- 대표 샘플 2종에서 P1 only 결과가 실제로 다시 검출된다.

따라서 현재 버전은 WinCC OA 코드리뷰 자동화 프로그램으로서 기본 기능을 회복했다고 판단한다.
