# WinCC OA 코드리뷰 자동화 프로그램 평가

Last Updated: 2026-03-09 (개선 후 재평가)

## 종합 판단

현재 프로그램은 Siemens WinCC OA 코드리뷰 자동화 도구로서 실무 가치가 높다. 특히 `P1(규칙 기반) + P2(CtrlppCheck) + P3(선택형 AI)` 구조, fail-soft optional dependency 처리, UI부터 HTML/Excel/annotated TXT/autofix까지 이어지는 결과 전달 흐름은 제품 완성도를 높이는 요소다.

이번 재평가 기준으로는 이전 평가에서 가장 시급하게 보였던 `report/Excel 기본 동작 불일치`, `heuristic regex hot path`, `report 경로 관찰성 부족`이 의미 있게 완화됐다. 반면 장기적으로 가장 큰 리스크는 더 이상 기본 동작의 불안정성이 아니라 `대형 파일 집중`, `거대한 통합 테스트 의존`, `Windows/인코딩/optional dependency 운영 변동성`이다.

즉, 현재 상태는 "실무 적용 가능한 내부 품질 게이트"에 가깝다. 다음 단계의 핵심은 기능 추가보다 구조 분해와 운영 경로 정리에 있다.

## 평가 범위와 전제

- 본 평가는 기술/운영 관점에 한정한다.
- Siemens 공식 인증, 라이선스, 사업 적용성 평가는 범위 밖이다.
- 성능 평가는 저장소 내 테스트, benchmark, smoke 결과와 현재 설정값을 기준으로 한다.
- 공개 API 계약은 유지된 상태를 전제로 평가한다.

## 항목별 점수

| 평가 축 | 이전 점수 | 현재 점수 | 재평가 판단 |
| --- | ---: | ---: | --- |
| WinCC OA 적합성 | 4.5 | 4.6 | WinCC OA 입력 형식, CtrlppCheck 연동, 규칙/템플릿 구조가 계속 잘 맞물린다. |
| 성능/응답성 | 4.0 | 4.2 | deferred Excel 기본화, 메트릭 분리, heuristic 전처리 캐시로 체감 병목이 줄었다. |
| 신뢰성/검증성 | 4.3 | 4.5 | 회귀 테스트 증가와 py_compile 재검증 성공으로 신뢰도가 더 높아졌다. |
| 유지보수성 | 2.8 | 3.0 | report/Excel 경로와 regex 전처리가 일부 정리됐지만 대형 파일 집중은 여전히 심하다. |
| 운영 실용성 | 3.8 | 4.1 | config/CLI/API 동작이 정렬됐고 deferred 경로가 기본화되어 운영성이 좋아졌다. |

## 이번 재평가에서 확인된 핵심 변화

- `Config/config.json`의 `performance.defer_excel_reports_default=true`가 실제 기본 동작에 반영된다.
- CLI에 `--defer-excel-reports`, `--sync-excel-reports`가 추가되어 HTTP API와 비슷한 제어점을 갖췄다.
- 메트릭이 `report` 총합 외에 `report_text`, `excel_total`을 분리 기록한다.
- report/Excel orchestration 일부가 `backend/core/session_mixin.py`로 이동해 책임이 좁아졌다.
- heuristic regex detector는 로드 시점 전처리/정렬/컴파일을 수행하고, invalid regex 경고도 로드 시점 fail-soft로 한 번만 기록한다.
- 기존 공개 API와 `/api/report/excel`, 다운로드 경로의 계약은 유지된다.

## 재평가 근거

### 1. 회귀 신뢰성

- `python -m unittest backend.tests.test_api_and_reports -v`
  - `Ran 161 tests in 69.491s`
  - `OK (skipped=1)`
- `python -m unittest backend.tests.test_winccoa_context_server -v`
  - `Ran 6 tests`
  - `OK`
- `node --check frontend/renderer.js`
  - 통과
- `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py backend/core/heuristic_checker.py backend/core/session_mixin.py`
  - 통과

이전 평가 대비 테스트 수가 늘었고, 새 회귀 항목에는 `deferred Excel 기본값`, `CLI 플래그`, `regex precompile`, `invalid regex fail-soft` 검증이 포함된다.

### 2. 설정/출력물 정합성

- `python backend/tools/check_config_rule_alignment.py --json`
  - `mismatch_row_count = 0`
- `python backend/tools/analyze_template_coverage.py --fail-soft`
  - `Client 15/15`
  - `Server 20/20`

즉, 규칙 정의와 템플릿 매핑은 현재 기준으로 100% 정합 상태다.

### 3. UI 및 Heuristic 성능 근거

- `tools/benchmark_results/ui_benchmark_20260307155121.json`
  - dataset: `20 files / 2400 P1 violations`
  - `analyzeUi p95 = 253ms`
  - `resultTableScroll p95 = 831ms`
  - `codeJump p95 = 47ms`
  - `codeViewerScroll p95 = 363ms`
- `docs/perf_baselines/ui_thresholds_20260306.json`
  - threshold: `300 / 1050 / 100 / 500ms`
- `docs/perf_baselines/http_perf_baseline_local-sample_20260309_004601.json`
  - heuristic same-build A/B 기준 `improvement_percent = 4.08`
  - `same_findings = true`

즉, UI는 여전히 threshold 이내이고, heuristic 변경은 결과 동일성을 유지하면서 소폭의 스캔 비용 감소를 보였다.

### 4. 실제 사용자 흐름

- `tools/integration_results/ui_real_smoke_20260308150323.json`
  - 분석 실행 성공
  - 추가 AI 분석 성공
  - Excel 생성 및 다운로드 성공
  - 전체 UI run `1066ms`

이 결과는 개선 후에도 주요 사용자 흐름이 끊기지 않았음을 보여준다.

### 5. 구조 복잡도 집중

현재 대형 파일 기준 라인 수:

- `backend/main.py`: 1805 lines
- `backend/server.py`: 980 lines
- `backend/core/heuristic_checker.py`: 2244 lines
- `backend/core/autofix_mixin.py`: 2213 lines
- `frontend/renderer.js`: 6868 lines
- `backend/tests/test_api_and_reports.py`: 5036 lines

이번 변경으로 일부 책임은 분리됐지만, 코드베이스 전체의 구조 집중도는 여전히 높다.

### 6. 운영 설정

`Config/config.json` 기준 주요 기본 설정:

- `analysis_max_workers = 4`
- `ctrlpp_max_workers = 1`
- `live_ai_max_workers = 2`
- `report_max_workers = 1`
- `excel_report_max_workers = 1`
- `defer_excel_reports_default = true`

이전과 달리 interactive 분석 경로에서 Excel 생성을 기본적으로 뒤로 미루므로, 체감 응답성과 운영 일관성은 확실히 좋아졌다. 다만 report/Excel worker 수는 여전히 보수적이다.

## 성능 분석

이번 재평가에서 성능 관련 가장 큰 변화는 `분석 완료 응답`과 `Excel 결과물 생성`의 관계가 더 명확히 분리됐다는 점이다. deferred Excel이 기본 동작이 되었고, sync path는 명시적으로 선택하는 구조가 됐다. 여기에 `report_text`와 `excel_total` 메트릭이 추가되면서, 앞으로 병목이 텍스트 리포트인지 Excel 생성인지 구분해서 볼 수 있게 됐다.

heuristic 경로도 개선됐다. 기존에는 일부 regex detector와 정렬 로직이 요청마다 반복 비용을 만들 가능성이 있었는데, 현재는 로드 시점 전처리와 컴파일을 통해 hot path가 가벼워졌다. 다만 개선 폭은 `4.08%` 수준의 소폭 최적화에 가깝고, 대규모 배치나 다중 사용자 환경에서의 병목이 완전히 사라진 것은 아니다.

결론적으로 현재 성능은 "느리지 않다" 수준을 넘어 "실무 사용에 충분히 안정적이다"에 가깝다. 그러나 report/Excel worker 수가 1로 유지되고 있어 대량 동시 처리 성능은 여전히 보수적으로 보는 것이 맞다.

## 유지보수성 분석

유지보수성은 이전보다 좋아졌지만, 아직 강점이라고 보기는 어렵다. 긍정적인 변화는 분명하다. report/Excel orchestration이 helper로 이동했고, regex detector 전처리가 load-time으로 정리됐고, 이 동작들을 검증하는 테스트도 추가됐다. 즉, `기능 추가 시 만져야 하는 지점`은 일부 줄었다.

하지만 구조 리스크의 본질은 남아 있다. 핵심 기능이 여전히 `main.py`, `heuristic_checker.py`, `autofix_mixin.py`, `renderer.js`, `test_api_and_reports.py` 같은 대형 파일에 강하게 집중돼 있다. 일부 파일은 오히려 더 커졌기 때문에, 유지보수성 점수는 소폭 상승에 그쳐야 한다.

실무 관점에서는 "한 명 또는 소수의 핵심 개발자가 빠르게 개선할 수 있는 구조"에는 가깝지만, "여러 명이 병렬로 장기간 유지보수하기 쉬운 구조"와는 아직 거리가 있다.

## 운영 실용성 분석

운영성은 이번 재평가에서 가장 눈에 띄게 좋아진 축 중 하나다. 이유는 세 가지다.

- config 기본값, HTTP 요청, CLI 제어점이 더 일관되게 맞춰졌다.
- Excel 결과물 생성이 기본적으로 deferred로 이동하면서 interactive 사용성이 좋아졌다.
- 메트릭 분리 덕분에 성능 문제를 관찰하고 설명하기 쉬워졌다.

또한 `/api/analyze`, `/api/analyze/start`, `/api/analyze/status`, `/api/report/excel`, `/api/report/excel/download`, `/api/health/deps` 등 주요 운영 API 흐름은 유지된 채로 성숙도가 올라갔다.

다만 운영 리스크가 완전히 해소된 것은 아니다. Windows 환경, mixed encoding 입력, optional dependency 준비 상태에 따라 운영 편차가 생길 수 있고, report/Excel 처리량은 여전히 보수적인 worker 설정에 묶여 있다.

## 완료되었거나 완화된 항목

- `report/Excel 기본 동작 불일치`
  - `defer_excel_reports_default=true` 반영으로 완화
- `report 경로 관찰성 부족`
  - `report_text`, `excel_total` 메트릭 추가로 완화
- `heuristic regex hot path 반복 비용`
  - 로드 시점 정렬/전처리/컴파일로 완화
- `invalid regex 런타임 반복 경고`
  - 로드 시점 fail-soft 1회 기록으로 완화
- `report/Excel orchestration의 과도한 main.py 집중`
  - helper 추출로 일부 완화

## 장점

- `P1 + P2 + P3` 계층 구조가 명확하고 WinCC OA 코드리뷰 흐름에 잘 맞는다.
- CtrlppCheck, Live AI, Playwright 같은 선택 기능을 fail-soft로 처리해 기본 분석 흐름이 잘 무너지지 않는다.
- 규칙-템플릿 정합성과 템플릿 커버리지가 현재 기준 100%로 유지된다.
- UI, HTML 리포트, Excel, annotated TXT, autofix까지 하나의 워크플로로 연결된다.
- context server와 MCP bridge까지 포함해 확장 여지가 있다.
- 이번 개선으로 deferred Excel 기본화, CLI 제어점, 메트릭 분리가 추가되어 운영 실용성이 높아졌다.

## 단점

- 코어 로직과 프론트가 여전히 대형 단일 파일 중심이다.
- 분석, 리포트, autofix, UI 상태 관리 책임이 충분히 잘게 분리되지 않았다.
- `backend/tests/test_api_and_reports.py` 같은 거대한 통합 테스트에 대한 의존이 높다.
- report/Excel worker 설정이 보수적이라 대량 배치 처리 성능은 제한적이다.
- Windows 파일 잠금, mixed encoding, optional dependency 상태에 따른 운영 변동성이 남아 있다.

## 지금 기준으로 가장 시급한 후속 과제

### 1. 대형 파일 구조 분해

가장 시급한 과제는 `backend/main.py`, `backend/core/autofix_mixin.py`, `backend/core/heuristic_checker.py`, `frontend/renderer.js`를 기능 단위로 분해하는 것이다. 지금은 성능보다 구조 리스크가 더 큰 병목이다.

### 2. 거대 통합 테스트 분할

`backend/tests/test_api_and_reports.py`는 회귀 방어력은 높지만 수정 비용도 크다. report/Excel, API contract, heuristic regression, autofix regression을 더 작은 스위트로 분리하면 변경 속도와 디버깅 효율이 함께 좋아진다.

### 3. 운영 경로 하드닝

Windows temp file/lock 처리, mixed encoding 입력 경계, optional dependency readiness, deferred Excel queue 관찰성을 묶어서 운영 하드닝을 해야 한다. 현재는 기능 실패보다 운영 편차 관리가 더 중요한 단계다.

## 최종 결론

현재 프로그램은 WinCC OA 코드리뷰 자동화 도구로서 충분히 경쟁력이 있다. 이전 평가에서 지적했던 단기 안정화 과제 중 핵심 항목은 실제로 개선됐고, 그 결과 성능/검증성/운영성 점수는 분명히 올라갔다.

이제 가장 시급한 문제는 "기능이 약하다"가 아니라 "구조가 크고 무겁다"에 가깝다. 따라서 다음 투자 우선순위는 새 기능 추가보다 구조 분해, 테스트 분할, 운영 경로 하드닝에 두는 것이 가장 합리적이다.
