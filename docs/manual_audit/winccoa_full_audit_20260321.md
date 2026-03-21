# WinCC OA 실제 전수 감사 보고서

작성일: 2026-03-21  
감사 범위: UI, API, CLI, CtrlppCheck, Live AI 실호출, Excel 리포트, autofix prepare/apply, 원본 복원 검증

## 1. 최종 판정

백엔드 규칙 검출은 이번 감사 기준 샘플 2종에서 수동 리뷰 기대치와 일치했다.

- `BenchmarkP1Fixture.ctl`: 수동 기대 4개 규칙을 CLI/API가 모두 검출
- `GoldenTime.ctl`: 수동 기대 4개 규칙을 CLI/API가 모두 검출
- CtrlppCheck는 두 샘플 모두 P1 결과를 덮어쓰지 않고 additive source로 동작
- Excel 산출물의 finding 수는 확인한 모든 run에서 `analysis_summary.json`과 일치
- 원본 파일 대상 autofix는 실제 apply 후 백업본으로 복원했고 SHA256 해시가 원본과 다시 일치

다만 사람이 실제로 사용하는 관점에서는 아직 신뢰 저하 결함이 남아 있다.

- UI가 실제 `rule_id`를 잘못 표시하거나 `UNKNOWN`으로 치환하는 문제가 있음
- UI AI 탭의 실사용 generate 동작이 프런트엔드 오류로 실패함
- 독립 `ai-review/generate` 결과가 `autofix/prepare` 세션과 연결되지 않아 API 계약이 끊김
- `rules/list`, `rules/export` 읽기 API가 BOM JSON 처리 실패로 응답 자체를 끊음
- 원본 autofix는 복원은 안전했지만, 생성 코드 품질은 낮고 신규 P1 이슈를 유발할 수 있음

## 2. 사전 준비 및 기준선

환경 준비 상태

- `backend/server.py` fresh server 기동 확인
- `npx` 사용 가능 확인
- `Config/config.json` 기준 `ai.provider=ollama`, `model=qwen2.5-coder:3b`, `ollama_url=http://localhost:11434/api/generate`
- `/api/ai/models`에서 `available=true` 확인
- `CtrlppCheck` 설치 상태와 smoke 통과 확인

원본 보호 절차

- 백업 디렉터리: `workspace/runtime/audit_backups/20260321_190922/`
- 보호 대상: `CodeReview_Data/BenchmarkP1Fixture.ctl`, `CodeReview_Data/GoldenTime.ctl`
- 백업 매니페스트: `workspace/runtime/audit_backups/20260321_190922/hash_manifest.json`
- 감사 종료 후 `BenchmarkP1Fixture.ctl` 복원 SHA256 일치 확인

기준선 실행 결과

| Check | Result | Evidence |
| --- | --- | --- |
| config alignment | pass, unknown rule id 0 | `CodeReview_Report/template_coverage_20260321_190947.json` |
| template coverage | client 100%, server 100% | `CodeReview_Report/template_coverage_20260321_190947.json` |
| P1 matrix | positive 100%, negative 100%, mismatch 0% | `docs/perf_baselines/p1_rule_matrix_20260321_190949.json` |
| backend API/report tests | 171 passed, 1 skipped | release gate summary |
| context server tests | 6 passed | release gate summary |
| frontend tests | 47 passed | local run |
| Ctrlpp integration smoke | pass, finding 2 | `tools/integration_results/ctrlpp_integration_20260321_101001.json` |
| UI real smoke | pass, artifact row count 32 | `tools/integration_results/ui_real_smoke_20260321101001.json` |

## 3. 실제 사용 흐름 점검

확인한 흐름

- `대시보드 -> 작업공간 -> 설정`
- `BenchmarkP1Fixture.ctl` P1 only, P1+P2 분석
- `GoldenTime.ctl` P1 only 분석
- `/api/analysis-diff/*` 비교
- Excel 생성 상태 및 파일 존재/행수 대조
- `/api/ai-review/generate` 실호출
- copy 파일 autofix prepare/apply
- 원본 파일 autofix apply 후 즉시 재분석 및 원복

정상 동작으로 확인한 항목

- 설정 화면의 `P1 활성 42`, `미참조 rule_id 0`, `Degraded NO`, `Mode configured`
- `BenchmarkP1Fixture.ctl` UI P1 only 결과 4행
- `BenchmarkP1Fixture.ctl` UI P1+P2 결과 5행
- `GoldenTime.ctl` UI P1 only 결과 4행
- `/api/analysis-diff`에서 Benchmark는 P2 +1, GoldenTime은 P2 +43만 추가
- Excel 상세 시트 및 Ctrlpp 시트 행수가 summary와 일치
- Live AI 백엔드 generate는 실제 Ollama 호출로 응답 생성

## 4. 수동 vs 자동 비교표

| file | manual finding | expected rule_id | CLI P1 only | CLI P1+P2 | UI visible | Excel visible | AI mention | autofix candidate | classification | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BenchmarkP1Fixture.ctl | active guard 없음 | ACTIVE-01 | yes | yes | yes | yes | yes | no | 정상 | 백엔드/Excel/UI 모두 존재 |
| BenchmarkP1Fixture.ctl | dpSet 오류 처리 누락 | EXC-DP-01 | yes | yes | yes, but mislabeled | yes | yes | yes | UI/리포트 누락 | UI는 `EXC-TRY-01`로 잘못 표기 |
| BenchmarkP1Fixture.ctl | try/catch 없음 | EXC-TRY-01 | yes | yes | yes | yes | skipped by priority cap | no | 정상 | 자동 검출 정상 |
| BenchmarkP1Fixture.ctl | 다중 setValue 묶음 처리 필요 | PERF-SETMULTIVALUE-ADOPT-01 | yes | yes | yes | yes | yes | no | 정상 | Ctrlpp 추가행과 분리 유지 |
| GoldenTime.ctl | config path 하드코딩 | HARD-01 | yes | yes | yes, but rule UNKNOWN | yes | yes | no | UI/리포트 누락 | UI severity도 `Info`로 낮아짐 |
| GoldenTime.ctl | 인덱스 매직넘버 | STYLE-IDX-01 | yes | yes | yes, but rule UNKNOWN | yes | severity-filtered | no | UI/리포트 누락 | 백엔드는 `Low`, UI는 `Info`+`UNKNOWN` |
| GoldenTime.ctl | loop/event 경로 내 dpSet | PERF-EV-01 | yes | yes | yes, but shown as PERF-05 | yes | yes | no | UI/리포트 누락 | rule id 변환 오류 |
| GoldenTime.ctl | 임계 소수값 하드코딩 | HARD-03 | yes | yes | yes, but rule UNKNOWN | yes | yes | no | UI/리포트 누락 | 메시지는 맞지만 rule id가 사라짐 |

## 5. 현재 제대로 동작하지 않는 규칙/연결부

### A. 규칙 엔진 자체는 맞지만 UI 표기가 틀린 항목

- `EXC-DP-01`
  - 백엔드/Excel은 정상 검출
  - Benchmark UI는 메시지는 `EXC-DP-01` 성격인데 `Rule EXC-TRY-01`로 표시

- `HARD-01`, `STYLE-IDX-01`, `HARD-03`
  - GoldenTime CLI/API/Excel은 정확한 `rule_id` 보유
  - GoldenTime UI는 `UNKNOWN`으로 표시

- `PERF-EV-01`
  - GoldenTime CLI/API/Excel은 `PERF-EV-01`
  - GoldenTime UI는 `PERF-05`로 표시

### B. 규칙 API 읽기 경로 장애

- `/api/rules/list`
- `/api/rules/export`

서버 stderr에 `Unexpected UTF-8 BOM (decode using utf-8-sig)`가 기록되며 연결이 끊긴다. 규칙 health는 정상인데 list/export만 실패하므로 read path BOM 처리 누락으로 분류한다.

### C. 운영 요약 표시 오류

- `UI Real Smoke` 최신 artifact는 row count 32
- 대시보드/설정 운영 요약은 `행 수 0`으로 표시

즉 smoke 자체는 성공했지만 운영 요약 레이어가 결과를 잘못 읽고 있다.

## 6. Live AI 및 autofix 평가

Live AI

- `/api/ai-review/generate`는 실제 live source 응답 확인
- 저장 증빙: `workspace/runtime/full_audit_20260321_191220/ai_generate_benchmark.json`
- UI AI 탭 `Generate AI Review`는 `qualityPreviewSummaryLines is not defined`로 실패

AI/autofix 계약 문제

- 독립 `/api/ai-review/generate` 결과로 바로 `/api/autofix/prepare` 호출 시 404
- 오류: `Matching AI review was not found in cached session`
- 세션 내부에서 생성된 P3 review를 사용할 때만 `autofix/prepare` 성공

Autofix copy 테스트

- rule-template prepare 성공
- apply는 `SEMANTIC_GUARD_BLOCKED`로 안전 차단

Autofix 원본 테스트

- 원본 파일: `CodeReview_Data/BenchmarkP1Fixture.ctl`
- 세션 내부 live P3 review 기반 `prepare -> file-diff -> apply` 성공
- reanalysis 결과 `before_p1_total=4`, `after_p1_total=3`
- target `EXC-DP-01`은 사라졌지만 `HARD-02` 신규 검출이 생김
- 수정 코드는 기존 `dpSet`를 깔끔하게 대체하지 않고 주석 블록과 추가 try/catch를 삽입하는 방식이라 품질이 낮음
- 감사 종료 후 원본 복원 SHA256 일치
- 증빙: `workspace/runtime/full_audit_20260321_191220/autofix_original_benchmark_live_session.json`

판정

- 안전성: pass
- 복원성: pass
- 코드 품질: fail
- 실사용 자동수정 신뢰도: 낮음

## 7. 파일 경계 및 인코딩 점검

- `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`
  - 분석 가능
  - summary total 38
  - source content 조회 가능

- `POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl`
  - 내용 조회 가능
  - mixed encoding/BOM 노이즈가 화면상 보임

판정

- 기능 자체는 동작
- 사람이 읽는 품질은 인코딩 노이즈 때문에 낮음

## 8. 우선 수정 Top 10

1. GoldenTime UI rule mapping 복구: `HARD-01`, `HARD-03`, `STYLE-IDX-01`, `PERF-EV-01`를 실제 `rule_id`와 severity로 표시
2. Benchmark UI rule mapping 복구: `EXC-DP-01`이 `EXC-TRY-01`로 잘못 보이는 문제 수정
3. `frontend/renderer/autofix-ai.js`의 `qualityPreviewSummaryLines` 참조 오류 수정
4. `/api/rules/list`, `/api/rules/export`에 BOM-safe JSON 로딩 적용
5. 운영 상태 요약의 `UI Real Smoke 행 수` 파서 수정
6. `ai-review/generate`와 `autofix/prepare`의 세션 계약 정리
7. autofix apply 후 기존 원문 대체/삭제 품질 개선
8. autofix 결과에 신규 P1 생성 여부를 더 강하게 차단
9. mixed encoding `.pnl/.txt` viewer 표시 품질 개선
10. Excel queue UI 상태 갱신 주기 점검

## 9. 최종 결론

이번 감사 기준에서 WinCC OA 코드리뷰 자동화 프로그램은 `규칙 엔진` 자체로는 합격이다. 최소 대표 샘플 2종에 대해 사람이 직접 읽어서 기대한 핵심 P1 규칙을 CLI/API/Excel이 빠짐없이 검출했다.

하지만 실제 사용자는 UI, AI, autofix를 통해 결과를 소비하므로 제품 관점의 최종 판정은 `부분 합격`이다. 지금 상태에서는 “검출은 맞는데 화면과 연계 기능이 그 신뢰를 훼손하는” 단계다. 즉, 규칙을 다시 만드는 작업보다 먼저 `UI rule mapping`, `AI 탭 generate`, `rules list/export BOM`, `autofix 세션 계약`을 고치는 것이 체감 품질 개선 효과가 가장 크다.

## 10. 핵심 증빙 경로

- 감사 종합 JSON: `tools/integration_results/full_audit_20260321_191220.json`
- API/UI 실행 메모: `workspace/runtime/full_audit_20260321_191220/api_runs.json`
- 기타 API 점검: `workspace/runtime/full_audit_20260321_191220/api_misc_checks.json`
- Live AI generate: `workspace/runtime/full_audit_20260321_191220/ai_generate_benchmark.json`
- 원본 autofix + 복원: `workspace/runtime/full_audit_20260321_191220/autofix_original_benchmark_live_session.json`
- Benchmark API summary: `CodeReview_Report/20260321_191709_152191/analysis_summary.json`
- Benchmark API summary P1+P2: `CodeReview_Report/20260321_191709_244476/analysis_summary.json`
- GoldenTime API summary: `CodeReview_Report/20260321_191709_352290/analysis_summary.json`
- GoldenTime API summary P1+P2: `CodeReview_Report/20260321_191709_463078/analysis_summary.json`
- UI smoke artifact: `tools/integration_results/ui_real_smoke_20260321101001.json`
