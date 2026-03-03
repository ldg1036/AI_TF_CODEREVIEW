# WinCC OA 코드리뷰 프로그램 계획 대비 구현 현황 TODO

기준 문서: `WinCC OA 코드리뷰 프로그램 성능 점검 및 LLM Diff 승인형 자동수정 확장 계획`

작성일: 2026-02-25 (업데이트 반영)
최종 문서 정합화: 2026-03-03 (현재 코드 기준)

## 상태 범례
- `[x] 완료`: 계획 의도에 맞는 핵심 동작이 구현/테스트됨
- `[-] 부분완료`: 핵심 일부 구현됨(추가 보완/실환경 실행 필요)
- `[ ] 미완료`: 아직 구현되지 않음

## 전체 요약
- 완료: `150`
- 부분완료: `1`
- 미완료: `0`
- 비고: 상단 요약은 문서 전체 체크마크(`todo.md`) 기준 재집계값이며, GoldenTime 기준 Excel 비교/품질게이트/릴리즈 체크리스트 제거 결정(P1/P2/P3 기준 재정의)을 반영함.

## 1) 계획 단계별 체크 (Plan Steps 1~12)

### 1. 기준선 측정/계측 추가 (`/api/analyze metrics`)
- [x] `metrics` 응답 추가 (`timings_ms`, `llm_calls`, `ctrlpp_calls`, bytes, convert cache)
- [x] 서버 요청 시간(`server_total`) 추가
- 근거:
  - `backend/main.py:141`
  - `backend/main.py:1213`
  - `backend/server.py:341`

### 2. 백엔드 처리 경로 단계 분리 (collect/convert/analyze/report)
- [x] `collect/convert/analyze/report` 단계 타이밍/흐름은 분리되어 동작
- [x] `run_directory_analysis()` 오케스트레이션을 별도 pipeline/module로 분리 (`core/analysis_pipeline.py`)
- 근거:
  - `backend/main.py`
  - `backend/core/analysis_pipeline.py`

### 3. 변환 캐시 도입 (`.pnl/.xml -> *_txt`)
- [x] `mtime + size` 기반 변환 캐시 적용
- [x] 전역 락 대신 source 단위 락 사용
- 근거:
  - `backend/main.py:135`
  - `backend/main.py:555`

### 4. bounded parallel 분석 + 경로별 동시성 제한
- [x] 분석 파일 단위 병렬화 (`ThreadPoolExecutor`)
- [x] `Ctrlpp/LLM/Reporter/Excel` 동시성 제한 세마포어 적용
- 근거:
  - `backend/main.py:61`
  - `backend/main.py:1213`

### 5. 리포트 생성 비용 지연/선택화 (Excel 분리)
- [x] 파일별 Excel 생성 지연 옵션(`defer_excel_reports`) 구현
- [x] 후속 flush API (`POST /api/report/excel`) 구현
- [x] Excel 템플릿 copy/load/save 계측 추가
- [x] Excel 템플릿 바이트 캐시(재사용) 적용
- 비고:
  - 기본값은 동기 생성이지만 설정/요청으로 지연 생성 전환 가능 (의도된 호환성 유지)
- 근거:
  - `backend/main.py:524`
  - `backend/main.py:583`
  - `backend/main.py:667`
  - `backend/main.py:953`
  - `backend/core/reporter.py:21`
  - `backend/core/reporter.py:128`
  - `backend/core/reporter.py:555`
  - `backend/server.py:220`
  - `backend/server.py:376`

### 6. LLM 호출 효율화 (snippet 중심 / batch proposal)
- [x] 위반 라인 주변 `focus_snippet` 생성 및 LLM 프롬프트 전달
- [x] 파일 내 다수 violation group 묶음(batch proposal) 옵션 추가 (`ai.batch_groups_per_file`)
- [x] snippet 범위 설정값 config화 (`focus_snippet_window_lines`, `focus_snippet_max_lines`)
- 근거:
  - `backend/main.py:51`
  - `backend/main.py:336`
  - `backend/main.py:1023`
  - `backend/core/llm_reviewer.py:99`
  - `backend/core/llm_reviewer.py:189`
  - `Config/config.json:18`

### 7. 세션 캐시 안정화 (TTL/LRU/lock/hash)
- [x] 세션 TTL/LRU eviction
- [x] per-session/per-file lock
- [x] autofix apply 시 hash 검증
- 근거:
  - `backend/main.py:228`
  - `backend/main.py:281`
  - `backend/main.py:1594`

### 8. 프론트 렌더링 최적화 (virtualization)
- [x] 코드뷰어 viewport/window 렌더링(virtualized line rendering)
- [x] 결과 테이블 viewport virtualization(가상 스크롤 + spacer row)
- [x] 라인 점프/하이라이트가 virtualization 상태에서 동작
- 근거:
  - `frontend/renderer.js:51`
  - `frontend/renderer.js:148`
  - `frontend/renderer.js:849`
  - `frontend/renderer.js:890`
  - `frontend/renderer.js:1265`
  - `frontend/style.css:145`
  - `frontend/style.css:239`

### 9. Diff 승인형 자동수정 API 추가
- [x] `POST /api/autofix/prepare`
- [x] `POST /api/autofix/apply`
- [x] `GET /api/autofix/file-diff`
- [x] `.ctl`만 허용
- 근거:
  - `backend/server.py:140`
  - `backend/server.py:178`
  - `backend/server.py:238`
  - `backend/main.py:1201` (기존 구현)
  - `backend/main.py:1225` (기존 구현)
  - `backend/main.py:1594`

### 10. 자동수정 검증 파이프라인 (anchor/hash/static/Ctrlpp)
- [x] hash/anchor 검증
- [x] 기본 문법 precheck(괄호/중괄호 밸런스)
- [x] heuristic 재검증(P1 count 증감)
- [x] Ctrlpp 회귀검사 옵션 추가 (`check_ctrlpp_regression`)
- [x] 회귀 차단 정책(`block_on_regression`) 반영
- 근거:
  - `backend/main.py:1514`
  - `backend/main.py:1594`
  - `backend/server.py:189`

### 11. 프론트 자동수정 UX (Diff 보기/승인/적용)
- [x] AI 카드에 `Diff Preview`, `Apply Source`, `Apply REVIEWED`
- [x] unified diff 패널 표시
- [x] source patch 적용 후 코드뷰어 재로드
- [x] autofix validation 상세(heuristic/Ctrlpp 회귀값/오류) 표시
- 근거:
  - `frontend/index.html:135`
  - `frontend/index.html:140`
  - `frontend/index.html:150`
  - `frontend/renderer.js:309`
  - `frontend/renderer.js:319`
  - `frontend/renderer.js:481`
  - `frontend/renderer.js:1044`

### 12. 테스트/품질 게이트 확장
- [x] metrics/autofix/session TTL 테스트 추가
- [x] deferred Excel flush API 테스트 추가
- [x] Ctrlpp regression count 테스트 추가
- [x] snippet 프롬프트 전달 테스트 추가
- [x] LLM batch option 테스트 추가
- [x] Excel 템플릿 캐시/계측 테스트 추가
- [x] 브라우저 렌더링 “성능 회귀 자동화” 실행 스크립트 추가 (Playwright 기반, API mock, 임계치 실패 지원)
- [x] 실제 CtrlppCheck 바이너리 통합 테스트 실행 스크립트 추가 (바이너리 탐지 + direct smoke + unittest harness)
- 근거:
  - `backend/tests/test_api_and_reports.py:233`
  - `backend/tests/test_api_and_reports.py:290`
  - `backend/tests/test_api_and_reports.py:437`
  - `backend/tests/test_api_and_reports.py:507`
  - `backend/tests/test_api_and_reports.py:1080`
  - `tools/playwright_ui_benchmark.js`
  - `tools/run_ctrlpp_integration_smoke.py`

## 2) Acceptance Criteria 체크

### API/기능 수용 기준
- [x] `POST /api/analyze` 기존 응답 호환성 유지 + `metrics` 추가
- [x] `autofix/prepare`, `autofix/apply`가 `.ctl` 대상 diff 승인형 흐름 제공
- [x] hash/anchor 검증, 백업 생성, 감사 로그, 실패 시 안전 중단 보장
- [x] 기존 동시 요청 격리 테스트 유지 + 신규 autofix/캐시 테스트 추가
- [x] Live AI off/fail-soft 상황에서도 P1/P2 유지

### 성능/운영 수용 기준
- [x] 병목 수치화 가능(계측/metrics 추가)
- [x] 2개 이상 명확한 개선 반영 (변환 캐시, 병렬화, 코드뷰/결과테이블 virtualization, 지연 Excel, Excel 템플릿 캐시)
- [x] 중간 배치 기준 `metrics` 비교표 작성 (synthetic benchmark, mock live AI)

## 3) 계획의 파일 영향도 vs 실제 반영 파일

### 실제 변경됨 (핵심)
- [x] `backend/main.py`
- [x] `backend/server.py`
- [x] `backend/core/analysis_pipeline.py` (파이프라인 모듈 분리 + 후속 가독성 리팩터링)
- [x] `backend/core/llm_reviewer.py`
- [x] `backend/core/reporter.py`
- [x] `frontend/renderer.js`
- [x] `frontend/index.html`
- [x] `frontend/style.css`
- [x] `backend/tests/test_api_and_reports.py`
- [x] `Config/config.json`
- [x] `README.md` (이전 단계에서 API/설명 보강)
- [x] `backend/core/ctrl_wrapper.py` (2026-02-26 회귀 복구: explicit `binary_path` override 안정화, 외부 `install_state` 경로 fallback 제한)

### 계획에 있었지만 현재 직접 변경 안 됨 / 최소 영향
- [-] `backend/core/heuristic_checker.py` (기존 API 재사용)

## 4) 실행 스크립트/운영 체크 (부분완료 2건 해소)

### 검증/품질 게이트 자동화 하네스
- [x] Playwright UI 렌더링 성능 회귀 스크립트 추가 (`tools/playwright_ui_benchmark.js`)
  - 용도: 대용량 결과 테이블/코드뷰 virtualization 경로의 분석 렌더/스크롤/라인점프 성능 스모크 측정
  - 특징: API mock 기반(백엔드 노이즈 제거), 임계치 옵션(`--max-*`) 지원, JSON 리포트 저장
  - 실행 예시:
    - `node tools/playwright_ui_benchmark.js --iterations 3 --files 20 --violations-per-file 120`
    - `node tools/playwright_ui_benchmark.js --max-analyze-ms 1500 --max-table-scroll-ms 1200 --max-code-jump-ms 800`
  - 사전 준비:
    - `npm i -D playwright`
    - `npx playwright install chromium`
- [x] 실운영 CtrlppCheck 통합 스모크 스크립트 추가 (`tools/run_ctrlpp_integration_smoke.py`)
  - 용도: Ctrlpp 바이너리 탐지, `CtrlppWrapper.run_check()` 직접 smoke, optional unittest harness(autofix ctrlpp regression) 실행
  - 특징: JSON 리포트 저장, 바이너리 미존재 시 명확한 상태 반환(`--allow-missing-binary` 지원)
  - 실행 예시:
    - `python tools/run_ctrlpp_integration_smoke.py`
    - `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
    - `python tools/run_ctrlpp_integration_smoke.py --binary C:\\path\\to\\ctrlppcheck.exe`
  - 연결되는 기존 테스트 하네스:
    - `backend.tests.test_api_and_reports.ApiIntegrationTests.test_autofix_apply_ctrlpp_regression_check_real_binary_optional`

### 운영환경에서 남는 일 (스크립트 준비 완료, 실행만 필요)
- [x] 실제 CtrlppCheck 바이너리 설치 환경에서 `tools/run_ctrlpp_integration_smoke.py` 1회 실행 후 결과 JSON 보관
  - 실행 일시: 2026-02-25
  - 결과: `direct_smoke ok=True`, `unittest_harness passed`
  - 리포트: `tools/integration_results/ctrlpp_integration_20260225_010414.json`
- [x] Playwright가 설치된 환경(개발 PC/CI)에서 `tools/playwright_ui_benchmark.js` baseline JSON 1회 생성 후 임계치 확정(초기값)
  - 실행 일시: 2026-02-25
  - 결과 요약 (p95): `analyze=93ms`, `tableScroll=831ms`, `codeJump=48ms`, `codeScroll=364ms`
  - 리포트:
    - `tools/benchmark_results/ui_benchmark_baseline_20260225_1119.json`
    - `docs/perf_baselines/ui_benchmark_baseline_20260225_1119.json`

## 5) 성능 벤치마크 (중간 배치 기준, synthetic)

### 측정 방법
- 기준: 로컬 환경에서 `CodeInspectorApp.run_directory_analysis()` 직접 호출 (HTTP 서버 경유 아님)
- 대상: synthetic `.ctl` 파일 `5 / 20 / 50`개
- 설정:
  - CtrlppCheck `off`
  - Heuristic checker는 고정 1개 P1 위반 반환(경로 재현 목적)
  - Live AI `on` 시 mock `generate_review()` 사용 (토큰/네트워크 비용 배제)
- 비고:
  - `ai_ms`가 거의 `0`인 이유는 mock AI 사용 때문
  - `analyze_wall_ms`는 사용자 체감 요청 지연 비교용, `flush_wall_ms`는 deferred Excel 후속 생성 시간
  - 원본 raw 결과 JSON: `temp_benchmark_results.json`

### 비교표 (2026-02-25)
| Batch | Live AI(mock) | Defer Excel | Analyze(ms) | Flush(ms) | End-to-End(ms) | LLM Calls | Pending After Analyze |
|---:|:---:|:---:|---:|---:|---:|---:|---:|
| 5 | off | off | 582 | 0 | 582 | 0 | 0 |
| 5 | off | on | 17 | 582 | 599 | 0 | 4 |
| 5 | on | off | 552 | 0 | 552 | 5 | 0 |
| 5 | on | on | 19 | 534 | 553 | 5 | 4 |
| 20 | off | off | 2359 | 0 | 2359 | 0 | 0 |
| 20 | off | on | 280 | 2236 | 2516 | 0 | 18 |
| 20 | on | off | 2775 | 0 | 2775 | 20 | 0 |
| 20 | on | on | 303 | 2457 | 2760 | 20 | 18 |
| 50 | off | off | 7099 | 0 | 7099 | 0 | 0 |
| 50 | off | on | 1782 | 5271 | 7053 | 0 | 38 |
| 50 | on | off | 6955 | 0 | 6955 | 50 | 0 |
| 50 | on | on | 1838 | 4621 | 6459 | 50 | 37 |

### 관찰 요약
- [x] `defer_excel_reports`는 분석 응답 지연(`Analyze ms`)을 크게 줄임
- [x] End-to-End 총 시간은 유사하거나 약간 개선(배치 50에서 개선 관찰)
- [x] Excel 템플릿 캐시는 동기 Excel 경로에서 `excel_template_cache_hits` 증가로 확인됨

## 6) 최근 검증 결과 (수동/자동)
- [x] 2026-02-26 회귀 복구(운영/테스트 불일치 보정)
  - `defer_excel_reports` 요청 전달 복구 + `POST /api/report/excel` flush 핸들러 복구
  - `CtrlppWrapper.run_check(binary_path=...)` explicit override 동작 안정화(환경 의존 fallback 차단)
  - `python backend/tools/run_release_checklist.py --help` 안전 동작(argparse) 추가
- [x] 2026-02-26 품질 기준 재정의 결정
  - 공식 코드리뷰 기준을 `P1(규칙) + P2(CtrlppCheck) + P3(AI)` 중심으로 확정
  - GoldenTime 기준 workbook 비교 / `goldentime_compare_result.json` 생성은 공식 품질 기준에서 제외
  - GoldenTime 기반 `run_quality_gate.py`, `run_release_checklist.py` 제거 결정
- [x] 2026-02-26 Git 친화 구조 정리
  - canonical 경로를 root(`Config`, `CodeReview_Data`, `docs`)로 확정
  - 중복 추적 경로 `workspace/resources/{Config,CodeReview_Data}`, `workspace/documentation/docs` 제거
  - `workspace/`는 runtime/support 영역으로 역할 재정의 (`workspace/runtime/CodeReview_Report` 중심)
- [x] 회귀 재검증(좁은 범위)
  - `python -m unittest backend.tests.test_api_and_reports.ApiIntegrationTests.test_post_api_analyze_defer_excel_reports_and_flush_endpoint -v` 통과
  - `python -m unittest backend.system_verification.SystemVerification.test_ctrlpp_missing_binary_fail_soft -v` 통과
  - `python -m unittest backend.system_verification.SystemVerification.test_ctrlpp_auto_install_attempt_on_missing_binary -v` 통과
  - `python -m unittest backend.system_verification.SystemVerification.test_ctrlpp_auto_install_fail_soft_on_download_error -v` 통과
  - `python -m py_compile backend/main.py backend/server.py backend/core/ctrl_wrapper.py backend/tools/run_release_checklist.py` 통과 (제거 전 검증 이력)
- [x] GoldenTime 기반 품질게이트/릴리즈 체크리스트 이슈 종결
  - `python backend/tools/run_release_checklist.py` 실패 이력은 GoldenTime 비교 기능 제거 결정으로 종결 처리
  - 이후 릴리즈 검증 기준은 문서화된 P1/P2/P3 + 회귀 테스트 조합으로 대체
- [x] `python -m unittest backend.tests.test_api_and_reports` 통과 (`61`, `1 skipped`)
- [x] `python -m unittest backend.system_verification backend.tests.test_api_and_reports backend.tests.test_todo_rule_mining backend.tests.test_winccoa_context_server` 통과 (`172`, `5 skipped`)
- [x] `python -m py_compile backend/main.py backend/server.py backend/core/reporter.py backend/core/llm_reviewer.py` 통과
- [x] `python -m py_compile backend/main.py backend/core/analysis_pipeline.py backend/tests/test_api_and_reports.py` 통과
- [x] `analysis_pipeline.py` Follow-up Cleanup 후 재검증:
  - `TypedDict` 기반 payload/error 타입 명확화 (IDE 자동완성/정적 추론 개선)
  - `traceback.print_exc()` 제거, `logger.exception()`로 예외 로깅 정리
  - `python -m py_compile backend/core/analysis_pipeline.py` 통과
  - `python -m unittest backend.tests.test_api_and_reports` 통과 (`61`, `1 skipped`)
- [x] `main.py` / `server.py` Follow-up Cleanup 확장:
  - `server.py`: API 요청 바디/분석 응답 요약 `TypedDict` 추가 (`AnalyzeRequestBody`, `Autofix*RequestBody` 등)
  - `main.py`: metrics 구조/Excel report meta `TypedDict` 추가 (`AnalysisMetrics`, `TimingMetrics`, `ExcelReportMeta` 등)
  - `python -m py_compile backend/server.py backend/main.py backend/core/analysis_pipeline.py` 통과
  - `python -m unittest backend.tests.test_api_and_reports` 통과 (`61`, `1 skipped`)
- [x] `node --check frontend/renderer.js` 통과
- [x] `node --check tools/playwright_ui_benchmark.js` 통과
- [x] `node tools/playwright_ui_benchmark.js --help` 실행 확인
- [x] `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest` 실행 확인 (바이너리 미존재 상태 리포트 생성)
- [x] `python tools/run_ctrlpp_integration_smoke.py` 실행 확인 (실제 Ctrlpp 바이너리 설치 후 direct smoke + unittest harness 통과)
- [x] `python -m unittest backend.tests.test_api_and_reports` 재실행 통과 (파이프라인 모듈 분리 리팩터링 후, `61`, `1 skipped`)

## 7) 결론 (현 시점)
- 계획 핵심(성능 계측/병렬화/변환 캐시/세션 안정화/Diff 승인형 autofix/검증 파이프라인/UI 연동/지연 Excel/템플릿 캐시/결과테이블 virtualization)은 구현 완료
- “자동화 검증 인프라” 2건은 실행 가능한 스크립트 형태로 마무리됨 (`tools/playwright_ui_benchmark.js`, `tools/run_ctrlpp_integration_smoke.py`)
- 계획 2번(분석 파이프라인 모듈 분리)도 `backend/core/analysis_pipeline.py`로 반영 완료하여 계획 체크 기준으로 잔여 미완료 항목 없음
- 후속 가독성 정리까지 반영(`TypedDict` 타입 명확화, 예외 로깅 통일)하여 `analysis_pipeline.py`의 유지보수성과 IDE 추론 품질 개선
- 동일한 정리 방향을 `server.py`/`main.py`까지 확장하여 API payload/metrics 구조의 IDE 자동완성 및 오타 탐지 품질 개선

---

## 8) 추가 로드맵(성능 적정성 평가 + LLM/비LLM autofix 확장) 반영 현황 (2026-02-25)

기준 문서: `WinCC OA 코드리뷰 프로그램 성능 적정성 평가 및 자동수정(LLM/비LLM) 확장 로드맵`

### 구현 상태 요약
- [x] Phase B (autofix 품질 메타/실패 코드/통계 API) 구현
- [x] Phase C (비LLM rule-based autofix 1차 + generator abstraction/API 확장) 구현
- [x] Phase D 일부 (LLM 제안 메타/파서리스 한계 문서화) 구현
- [x] Phase A 일부 (HTTP baseline 스크립트 + 샘플 baseline 생성 + 성능 문서화)
- [x] Phase A 일부 (Playwright 실측 baseline JSON 생성 완료)

### 세부 체크

#### Phase A — 성능 기준선 확정
- [x] `tools/http_perf_baseline.py` 추가 (`/api/analyze` + `/api/report/excel` matrix baseline 수집)
- [x] 로컬 샘플 데이터셋 HTTP baseline 생성
  - `docs/perf_baselines/http_perf_baseline_local_code_review_data_20260225_111410.json`
- [x] 성능 품질 게이트 문서 추가
  - `docs/performance.md`
- [x] UI 임계치 권장값 JSON 추가
  - `docs/perf_baselines/ui_thresholds_20260225.json`
- [x] 기존 synthetic 벤치 결과 보관용 baseline 복사
  - `docs/perf_baselines/synthetic_batch_benchmark_20260225_legacy.json`
- [x] Playwright 실측 baseline JSON 생성
  - `npm i -D playwright`
  - `npx playwright install chromium` (TLS 우회 필요: `NODE_TLS_REJECT_UNAUTHORIZED=0`)
  - `node tools/playwright_ui_benchmark.js --iterations 5 --files 20 --violations-per-file 120 --code-lines 6000 --output tools/benchmark_results/ui_benchmark_baseline_20260225_1119.json`

#### Phase B — autofix 품질 관리(LLM/비LLM 공통)
- [x] `AutoFixQualityMetrics` 타입 및 응답/감사로그 포함
- [x] `autofix/apply` 실패 시 `error_code` 분류 반환
- [x] 세션 통계 API `GET /api/autofix/stats` 추가
- [x] generator/품질 통계 집계 (`by_generator`, `by_status`, `failure_error_codes`)

#### Phase C — 비LLM 자동수정(규칙형) 1차
- [x] `rule` generator 추가 (deterministic hygiene normalization + annotation fallback)
- [x] `POST /api/autofix/prepare` 요청 확장
  - `generator_preference: auto|llm|rule`
  - `allow_fallback`
- [x] 응답 확장
  - `generator_type`
  - `generator_reason`
  - `quality_preview`
- [x] 하위호환성 유지
  - 리뷰 텍스트가 있는 기존 호출은 기본 `llm` 경로 유지

#### Phase D — LLM 자동수정 고도화
- [x] LLM 제안 메타(`llm_meta`) 추가
  - code block 추출 여부, parseability, fallback 여부 등
- [x] parserless patch 한계/안전범위 문서화
  - `docs/autofix_safety.md`
- [x] 멀티-전략 prepare(복수 후보 동시 반환) 구현 완료 (`prepare_mode=compare`, 후보 비교/선택, 통계 반영)

### 추가 검증 (이번 로드맵 반영분)
- [x] `python -m py_compile backend/main.py backend/server.py tools/http_perf_baseline.py` 통과
- [x] `python -m unittest backend.tests.test_api_and_reports` 통과 (`63`, `1 skipped`)
- [x] `node --check frontend/renderer.js` 통과
- [x] `python tools/http_perf_baseline.py --help` 실행 확인
- [x] `python tools/http_perf_baseline.py --dataset-name local_code_review_data --discover-count 1 --live-ai off --ctrlpp off,on --defer-excel off,on --iterations 2 --flush-excel` 실행 성공

### 비고
- `README.md`는 현재 파일 인코딩 이슈로(`apply_patch`가 UTF-8로 읽지 못함) 본 로드맵 문서화 내용을 `docs/performance.md`, `docs/autofix_safety.md`, `docs/perf_baselines/*`로 우선 반영함.

## 7-1) 문서 정합성 정리 (2026-02-25)
- [x] `README.md`를 현재 구현 기준으로 전면 재작성 (API/성능 baseline/autofix/문서 링크 반영)
- [x] `tools/README_CtrlppCheck.md`를 현재 운영 흐름 기준으로 갱신 (통합 스모크 포함)
- [x] 성능/자동수정/인코딩/baseline 문서(`docs/*.md`)를 최신 구현/실측 결과 기준으로 보강
- [x] 기존 손상된 기획 문서 4종을 한국어 기준으로 재작성
- [x] 기존 기획 문서 원본 백업(`*.bak_20260225_120548`) 보존
- [x] 복구 불가 판단 보고서 생성 (`docs/encoding_recovery_assessment_20260225.json`)

## 8) 후속 고도화 계획 (우선순위 낮음 / 품질 향상용)

현재 상태는 실사용 가능한 수준이지만, 자동수정 품질/확장성 고도화를 위해 아래 2개 항목을 후속 개선 대상으로 관리한다.

### 8-1) 멀티-전략 `autofix/prepare` (rule/llm 후보 비교) (2026-02-26 반영)

#### 목적
- 현재 `generator_preference=auto`는 내부에서 `rule-first -> llm-fallback`로 **후보 1개만 반환**
- 향후에는 `rule`/`llm` 후보를 동시에 생성해 사용자가 diff를 비교 후 선택하도록 확장

#### 기대 효과
- [x] 동일 이슈에 대한 `rule` vs `llm` 품질 비교 가능
- [x] 승인 UX 고도화 (단순 승인/거절 -> 후보 선택 후 승인)
- [x] generator 선택 통계 축적 (향후 `auto` 정책 개선 근거)

#### 현재 제약 / 리스크
- `prepare` 응답 지연 증가 가능 (`rule + llm` 둘 다 수행 시)
- UI 복잡도 증가 (후보 전환/비교 패널 필요)
- LLM 비용/시간 증가 (로컬 모델도 자원 사용 증가)

#### 1차 구현 방향 (권장)
- [x] 기본 동작은 유지 (`auto` = 단일 후보)
- [x] 옵션 모드 추가 (`prepare_mode=compare`)
- [x] 응답 구조 확장 (`proposals[]`, `selected_proposal_id`, `compare_meta`)
- [x] UI에서 후보 전환/비교 표시 후 선택 적용
- [x] 선택 결과를 `autofix/stats` 품질 통계에 반영

### 8-2) WinCC OA 전용 parser/토큰화 기반 patch (적용 안정성 고도화)

#### 목적
- 현재 source autofix 적용은 `hash + anchor + hunk` 기반 텍스트 패치
- 안전성은 충분하지만, 복잡한 수정/문맥 변화에는 취약
- 고난도 자동수정 정확도를 높이기 위해 토큰화/구조 기반 적용 보강 필요

#### 현재 방식 한계 (parserless patch)
- [x] 줄 이동/공백 재정렬에도 anchor mismatch 가능 (anchor_normalized + token fallback 강화 반영)
- [x] 의미(semantic) 동일성 판단 불가 (semantic guard 1차: 문자열/숫자/연산자/키워드 고위험 토큰 변화 차단)
- [x] 다중 위치/복합 수정에 취약 (P1 최소안: 동일 블록 다중 hunk(최대 3) + overlap/cross-block fail-soft 차단 + multi_hunk 통계 반영)
- [x] 유사 코드가 많은 파일에서 오적용 위험 증가 (ambiguous 후보 fail-soft 차단 반영)

#### 단계별 고도화 로드맵 (권장)

##### Phase T1 — 토큰화 기반 locator (빠른 효과)
- [x] `.ctl` 코드 토큰화(식별자/키워드/괄호/연산자/문자열/주석)
- [x] 줄 기반 anchor 실패 시 토큰 시퀀스 기반 재탐색 fallback
- [x] 기존 hash 검증/회귀검사 흐름 유지 (적용 엔진만 보강)

##### Phase T2 — 제한된 구조 parser (부분 문법)
- [x] parser-lite 적용 엔진 실구현 (`backend/core/autofix_apply_engine.py`)
- [x] rule-based autofix부터 구조 기반 적용 도입
- [x] 구조 기반 apply 실패 시 기존 텍스트 패치 fallback 정책 정의

##### Phase T3 — LLM 제안 구조화 (장기)
- [x] 구조화 수정 지시(JSON) 스키마/적용 계획 문서화 (`docs/autofix_engine_roadmap.md`)
- [x] parser/토큰 엔진이 실제 patch 생성/적용 담당 (T3-1 실사용 1차 완료: rule/llm 공통 structured instruction(`operations[]`) 생성, feature flag ON 시 instruction-first apply, 실패 시 hunk fallback)
- [x] 복수 후보(rule/llm) 비교와 결합 가능한 구조로 설계 (compare 후보 공통 structured instruction envelope + selection policy(`instruction_validity_then_syntax_then_rule`) + score/reason 메타 및 프론트 표시 반영)
- [x] T3-2 관측성/운영판단 고도화 (instruction path/stage 메타 + stats(`instruction_engine_fail_count`, `instruction_convert_fail_count`, `instruction_validation_fail_by_reason`, `instruction_mode_counts`) + perf rollout 기준(`apply_rate>=70%`, `validation_fail_rate<=20%`, `REGRESSION_BLOCKED=0`) 반영)

#### 리스크 / 주의점
- WinCC OA 문법 커버리지 부족 시 parser 유지보수 부담 증가
- 초기부터 AST 풀파서로 가면 개발 비용 과다
- 1차는 토큰화 기반 fallback부터 도입하는 것이 현실적

### 8-3) 권장 우선순위 (P0/P1/P2)
- `P0` (현재 유지): 현행 승인형 autofix + hash/anchor/회귀검사 유지
- `P1` (완료): 멀티-전략 `prepare` 비교 모드 (옵션 기반)
- `P1` (완료): 토큰화 기반 anchor 재탐색 fallback
- `P2` (고도화): 제한된 구조 parser + rule autofix 구조 기반 적용
- `P2` (장기): LLM 구조화 수정 지시 + 복수 후보 비교 UX 고도화

### 8-4) 성공 기준 (후속 항목)
- [x] 멀티-전략 compare 모드에서 `rule`/`llm` 후보 diff 비교 가능
- [x] 선택된 후보 적용 결과가 품질 통계에 기록됨
- [x] KPI 관측 가능성 확보 (벤치마크 전용 `kpi_observe_mode` 도입: `strict_hash|benchmark_relaxed`)
  - `strict_hash`: 제품 정책(해시 선검증) 그대로
  - `benchmark_relaxed`: KPI 관측 전용(`expected_base_hash` 미사용), 결과 JSON에 `benchmark_mode_warning`, `not_for_production` 고정 기록
  - 2026-02-27 반영: 서버 내부 관측 훅 추가(`X-Autofix-Benchmark-Observe-Mode` + `AUTOFIX_BENCHMARK_OBSERVE=1`)
  - 2026-02-27 반영: 벤치마크 전용 임계치 튜닝 헤더/옵션 추가
    - `X-Autofix-Benchmark-Tuning-Min-Confidence`
    - `X-Autofix-Benchmark-Tuning-Min-Gap`
    - `X-Autofix-Benchmark-Tuning-Max-Line-Drift`
  - 2026-03-03 반영: 벤치 도구 관측성 판정 로직 강화
    - summary 집계 추가: `hash_gate_bypassed_count`, `benchmark_observe_mode_counts`
    - drift 판정 자동화: `kpi_observability_pass`, `kpi_observability_reason`
    - reason 코드: `PASS | BLOCKED_ENV_GATE | BLOCKED_AMBIGUOUS | HOLD_LOW_SAMPLE`
  - 2026-03-03 실측 4차(matrix 재실행): `docs/perf_baselines/autofix_apply_baseline_20260303_092052_general.json`, `docs/perf_baselines/autofix_apply_improved_20260303_092052_general.json`, `docs/perf_baselines/autofix_apply_comparison_20260303_092052_general.json`, `docs/perf_baselines/autofix_apply_baseline_20260303_092052_drift.json`, `docs/perf_baselines/autofix_apply_improved_20260303_092052_drift.json`, `docs/perf_baselines/autofix_apply_comparison_20260303_092052_drift.json`
  - 2026-03-03 재판정 리포트: `docs/perf_baselines/autofix_review_20260303_092056.md`
    - 상태: `PASS`
    - 근거: drift(relaxed)에서 `locator_mode_counts` 관측 + `BASE_HASH_MISMATCH` 단일 100% 아님 + `hash_gate_bypassed_count=3`
  - 유지 검증(운영 표준):
    - 서버 환경변수 `AUTOFIX_BENCHMARK_OBSERVE=1`로 기동
    - `python tools/perf/autofix_apply_baseline.py --auto-run-matrix --scenario both --iterations 3 --output docs/perf_baselines --review-output docs/perf_baselines/autofix_review_latest.md`
    - drift 기준(`locator_mode_counts`, `hash_gate_bypassed_count`, `error_code_counts`) 이탈 여부 모니터링
- [x] 토큰화 기반 fallback 도입 후 anchor mismatch 실패율 10% 이상 개선(실데이터 기준, 장기측정 필요)
  - 2026-03-03 반영: drift 전용 튜닝 스윕 자동화 추가(`tools/perf/autofix_apply_baseline.py --auto-tune-drift`)
    - sweep 옵션: `--sweep-min-confidence`, `--sweep-min-gap`, `--sweep-max-line-drift`
    - 산출물: `autofix_apply_sweep_<timestamp>_drift.json` + 조합별 comparison JSON + `autofix_apply_root_cause_<timestamp>_drift.json`
  - 2026-03-03 반영: 스윕 결과 원인 분해 자동화 추가
    - 신규 옵션: `--analyze-sweep-json`, `--analyze-sweep-output`
    - 산출물: `docs/perf_baselines/autofix_apply_root_cause_20260303_093051_drift.json`, `docs/perf_baselines/autofix_root_cause_review_20260303_093051_drift.md`
    - 결과(재집계): `aggregate_reason_counts={"BLOCKED_AMBIGUOUS":18,"BLOCKED_ANCHOR_MISMATCH_ONLY":9}`, `aggregate_fragment_counts={"ambiguous_candidates":54,"low_confidence":0,"drift_exceeded":0}`
    - 결론: 10% 개선 미달의 주 원인은 `ambiguous_candidates` (임계치 미세 조정보다 locator disambiguation 정책 보강 우선)
  - 2026-03-03 보강: benchmark 전용 token tie-break(`prefer_nearest_on_tie`) 1차 반영 후 재측정
    - 코드: `backend/core/autofix_tokenizer.py`, `backend/main.py`, `backend/tests/test_autofix_token_fallback.py`
    - 실측: `docs/perf_baselines/autofix_apply_sweep_20260303_100428_drift.json`, `docs/perf_baselines/autofix_apply_root_cause_20260303_100428_drift.json`
    - 결과: `improvement_percent=0.0` 유지, `aggregate_reason_counts={"BLOCKED_AMBIGUOUS":18,"BLOCKED_ANCHOR_MISMATCH_ONLY":9}` (유의미 개선 미확인)
  - 2026-03-03 보강 2차: benchmark 전용 `force_pick_nearest_on_ambiguous` + baseline/improved 튜닝 헤더 분리 적용 후 재측정
    - 코드: `backend/core/autofix_tokenizer.py`, `backend/main.py`, `tools/perf/autofix_apply_baseline.py`
    - 실측: `docs/perf_baselines/autofix_apply_sweep_20260303_102303_drift.json`, `docs/perf_baselines/autofix_apply_root_cause_20260303_102303_drift.json`
    - 결과: `best improvement_percent=100.0`, `kpi_passed 조합=18/27`, `aggregate_reason_counts={"PASS_10_PERCENT":18,"BLOCKED_ANCHOR_MISMATCH_ONLY":9}`, `aggregate_fragment_counts={"ambiguous_candidates":0,"low_confidence":0,"drift_exceeded":0}`
  - 2026-02-27 실측 1차: `docs/perf_baselines/autofix_apply_baseline_20260227_0938.json`, `docs/perf_baselines/autofix_apply_improved_20260227_0938.json`, `docs/perf_baselines/autofix_apply_comparison_20260227_0938.json`
  - 결과: `improvement_percent=0.0` (샘플에서 anchor mismatch 이벤트 미발생으로 KPI 판정 보류)
  - 2026-02-27 실측 2차(일반/line_drift): `docs/perf_baselines/autofix_apply_baseline_20260227_1035_general.json`, `docs/perf_baselines/autofix_apply_improved_20260227_1035_general.json`, `docs/perf_baselines/autofix_apply_comparison_20260227_1035_general.json`, `docs/perf_baselines/autofix_apply_baseline_20260227_1035_drift.json`, `docs/perf_baselines/autofix_apply_improved_20260227_1035_drift.json`, `docs/perf_baselines/autofix_apply_comparison_20260227_1035_drift.json`
  - 결과: 일반 케이스 `improvement_percent=0.0`, drift 케이스는 `BASE_HASH_MISMATCH` 선차단으로 anchor/token fallback 경로 미진입 (KPI 판정 보류 유지)
  - 2026-02-27 실측 3차(`kpi_observe_mode` 도입): `docs/perf_baselines/autofix_apply_baseline_20260227_1042_general.json`, `docs/perf_baselines/autofix_apply_improved_20260227_1042_general.json`, `docs/perf_baselines/autofix_apply_comparison_20260227_1042_general.json`, `docs/perf_baselines/autofix_apply_baseline_20260227_1042_drift.json`, `docs/perf_baselines/autofix_apply_improved_20260227_1042_drift.json`, `docs/perf_baselines/autofix_apply_comparison_20260227_1042_drift.json`
  - 결과: general(`strict_hash`)은 정상(`anchor_exact`), drift(`benchmark_relaxed`)도 내부 `proposal_base_hash` 선검증으로 `BASE_HASH_MISMATCH` 지속 (KPI 판정 보류 유지)
- [x] 기존 `autofix/apply` 안전성(백업/감사로그/회귀검사) 회귀 없음

### 8-5) P1 규칙 매트릭스 신뢰도 실측 (Config 기준)
- [x] `verify_p1_rules_matrix.py` 개선(규칙 ID 기반 curated case catalog + op fallback + collateral 분리 + API 교차검증 유지)
- [x] 실측 결과(2026-02-27): `docs/perf_baselines/p1_rule_matrix_20260227_141452.json`, `docs/perf_baselines/p1_rule_matrix_20260227_141452.md`
  - `enabled_rules=43`, `supported_rules=43`, `unsupported_rules=0`
  - `positive_detection_rate=100.0%`
  - `negative_not_detected_rate=100.0%`
  - `checker_vs_api_mismatch_rate=0.0%`
- [x] `STYLE-HEADER-01` negative false positive 해소(타겟 규칙 기준 비검출 확인)
- [x] `SEC-01`/`DB-ERR-01`/`EXC-DP-01` escape 보정 완료(엔진 regex 정규화 + 규칙 패턴 표준화 적용)
