# WinCC OA 실제 전수 감사 보고서

작성 시각: 2026-03-21 23:45 KST

## 요약

- 감사 범위: `UI`, `API`, `CLI`, `CtrlppCheck`, `Live AI`, `Excel`, `autofix(copy/original restore)`
- 대표 기준 샘플인 `BenchmarkP1Fixture.ctl`, `GoldenTime.ctl`에서는 수동 코드리뷰 기대 규칙과 자동 검출 결과가 일치했다.
- 현재 가장 큰 문제는 `P1 규칙 검출 실패`가 아니라 `txt/pnl 경계 처리`, `workspace 표시 집계`, `Live AI/autofix 품질 일관성`이다.
- 원본 `BenchmarkP1Fixture.ctl`에 대한 live autofix 적용 후 즉시 복원까지 수행했고, SHA256 해시는 감사 전과 동일하게 복원되었다.

최종 판정

- 규칙 엔진 관점: 합격
- 제품 관점: 부분 합격

## 감사 범위와 주요 증빙

- 기계 요약 JSON: [full_audit_20260321_232426.json](D:/AI_TF_CODEREVIEW-main/tools/integration_results/full_audit_20260321_232426.json)
- 백업/복원 해시: [hash_manifest.json](D:/AI_TF_CODEREVIEW-main/workspace/runtime/audit_backups/20260321_232426/hash_manifest.json)
- 현재 감사 런타임 산출물: [full_audit_20260321_232426](D:/AI_TF_CODEREVIEW-main/workspace/runtime/full_audit_20260321_232426)
- UI smoke: [ui_real_smoke_20260321144115.json](D:/AI_TF_CODEREVIEW-main/tools/integration_results/ui_real_smoke_20260321144115.json)
- release gate: [release_gate_20260321_232728_578477.json](D:/AI_TF_CODEREVIEW-main/CodeReview_Report/release_gate_20260321_232728_578477.json)
- P1 matrix: [p1_rule_matrix_20260321_232531.md](D:/AI_TF_CODEREVIEW-main/docs/perf_baselines/p1_rule_matrix_20260321_232531.md)
- 설정 화면 스크린샷: [settings-overview.png](D:/AI_TF_CODEREVIEW-main/output/playwright/full_audit_20260321_232426/settings-overview.png)
- `.pnl` 경계 화면 스크린샷: [workspace-pnl-boundary.png](D:/AI_TF_CODEREVIEW-main/output/playwright/full_audit_20260321_232426/workspace-pnl-boundary.png)

## 기준선 결과

- `check_config_rule_alignment`: unknown `rule_id` 0, 활성 P1 42/43
- `analyze_template_coverage`: client 15/15, server 20/20
- `verify_p1_rules_matrix`: enabled 42, supported 42, positive 100%, negative 100%
- `backend.tests.test_api_and_reports`: `177 passed, 1 skipped`
- `backend.tests.test_winccoa_context_server`: `6 passed`
- `npm run test:frontend`: `54 passed`
- `run_ctrlpp_integration_smoke`: passed, finding 2
- `release_gate --with-live-ai --with-live-ai-ui`: `14 passed, 0 failed`

## 실제 사용자 흐름 점검

### 대시보드 / 설정

- 설정 화면은 API와 일치하게 `P1 활성 42`, `미참조 rule_id 0`, `Degraded NO`, `Mode configured`를 표시했다.
- 운영 검증 카드 값은 `release_gate` 산출물을 기준으로 보여 주며, 현재 ad-hoc smoke가 아니라 최신 gate smoke를 가리킨다.
- `UI Real Smoke` 카드의 `37행` 표시는 [ui_real_smoke_release_gate_20260321_232728_578477.json](D:/AI_TF_CODEREVIEW-main/tools/integration_results/ui_real_smoke_release_gate_20260321_232728_578477.json)과 일치한다.

### 작업공간

- `BenchmarkP1Fixture.ctl` P1 only: 4건 표시, rule id와 line 모두 정확
- `BenchmarkP1Fixture.ctl` P1+P2: 5건 표시, P2 1건만 additive
- `GoldenTime.ctl` P1 only: 4건 표시, `HARD-01`, `STYLE-IDX-01`, `PERF-EV-01`, `HARD-03` 정확
- `GoldenTime.ctl` P1+P2: 총 47건, P1 4건 유지 + P2 추가
- `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`: REVIEWED.txt 렌더는 가능하지만 UI count가 CLI/Excel과 다름
- `POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl`: boundary 처리 불안정. `.pnl` synthetic row와 `_pnl.txt` native row가 동시에 보임

### Live AI / Compare / Prepare

- Live AI generate, compare modal, prepare patch, unified diff까지 실제로 동작했다.
- 최신 smoke 증빙에서는 `LLM (127)`이 선택되고 placeholder 누수는 없었다.
- 다만 patch 의미 품질은 아직 완전하지 않다.
  - 한 run에서는 `setMultiValue(...)`를 권고하면서 diff에는 `dpSet(...)`이 생성됨
  - 다른 run에서는 정상적으로 `setMultiValue(...)`가 생성됨
- 즉 기능은 살아 있지만, patch 의미가 run마다 안정적으로 재현되지는 않는다.

### Excel / triage / autofix

- Excel 파일은 각 CLI run에서 생성되었고, `상세결과` sheet의 row 수는 대표 `.ctl` 샘플에서 summary와 일치했다.
- fresh smoke에서도 triage suppress/show suppressed/unsuppress round trip은 완료되었다.
- copy autofix는 semantic guard가 실제로 막았고, original live autofix는 적용 후 복원까지 완료됐다.

## 수동 코드리뷰 vs 자동 결과 비교

| file | manual finding | expected rule | CLI P1 | CLI P1+P2 | UI | Excel | 판정 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BenchmarkP1Fixture.ctl | repeated setValue block | PERF-SETMULTIVALUE-ADOPT-01 | yes | yes | yes | yes | 일치 |
| BenchmarkP1Fixture.ctl | active guard missing | ACTIVE-01 | yes | yes | yes | yes | 일치 |
| BenchmarkP1Fixture.ctl | try/catch or error contract missing | EXC-TRY-01 | yes | yes | yes | yes | 일치 |
| BenchmarkP1Fixture.ctl | dpSet result/error handling missing | EXC-DP-01 | yes | yes | yes | yes | 일치 |
| GoldenTime.ctl | hardcoded config path | HARD-01 | yes | yes | yes | yes | 일치 |
| GoldenTime.ctl | magic index usage | STYLE-IDX-01 | yes | yes | yes | yes | 일치 |
| GoldenTime.ctl | loop/event dpSet pattern | PERF-EV-01 | yes | yes | yes | yes | 일치 |
| GoldenTime.ctl | hardcoded float threshold | HARD-03 | yes | yes | yes | yes | 일치 |
| POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt | large duplicated panel-derived code | COMP-01 / CLEAN-DUP-01 / PERF-* cluster | yes | yes | partial | yes | UI count mismatch |
| POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl | converted panel boundary | boundary only | yes | yes | partial | yes | UI boundary defect |

대표 `.ctl` 샘플 기준으로는 `필수 기대 규칙 누락 0`, `critical false positive 0`이었다.

## 현재 확인된 개선 필요 항목

### 1. txt workspace count mismatch

- 증상: `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`는 CLI summary와 Excel detail에서 38건인데 workspace UI는 17건만 표시했다.
- 분류: `UI/리포트 누락`
- 영향: 사람이 UI만 보면 검출기가 덜 잡았다고 오해할 수 있다.

### 2. .pnl boundary mixing

- 증상: `.pnl` 선택 시 `REVIEW-ONLY-*.pnl-*` synthetic row와 `_pnl.txt` 기반 native row가 한 리스트에서 섞였다.
- 일부 synthetic row는 `UNKNOWN` rule label을 가진다.
- CLI `.pnl` summary는 38건인데 workspace는 50건을 보여 줬다.
- 분류: `구현은 있으나 미연결`
- 영향: panel source review의 canonical source가 무엇인지 사용자 입장에서 불명확하다.

### 3. Live AI patch semantics non-determinism

- 증상: 동일 PERF 이슈에 대해 한 run은 `dpSet(...)`, 다른 run은 `setMultiValue(...)`를 제안했다.
- 분류: `AI 실호출 실패`
- 영향: compare/prepare가 성공해도 patch 의미를 신뢰하기 어렵다.

### 4. autofix apply quality gap

- 증상: original Benchmark live apply는 성공했지만, 재분석 후 P1 total이 4 -> 5로 증가했고 `HARD-02`가 추가되었다.
- 적용된 diff는 다음과 같다.

```diff
// [AI-AUTOFIX:e82f0a49] 요약: 다중 setValue 호출이 감지되었습니다. setMultiValue 구문을 적용 권장합니다.
setMultiValue("A.B.C1", v1, "A.B.C2", v2, "A.B.C3", v3);
// [/AI-AUTOFIX:e82f0a49]
```

- 재분석 후 규칙:
  - `EXC-DP-01`
  - `PERF-SETMULTIVALUE-ADOPT-01`
  - `EXC-TRY-01`
  - `ACTIVE-01`
  - `HARD-02`
- 분류: `autofix 안전성/복원 실패`
- 영향: apply 성공 여부만으로는 patch 품질을 판정할 수 없다.

### 5. semantic guard는 유효하게 동작

- copy benchmark에 대한 deterministic `rule` patch는 `SEMANTIC_GUARD_BLOCKED`로 차단되었다.
- 이 부분은 결함이 아니라 안전장치가 실제로 작동했다는 긍정 증빙이다.

## 현재 규칙 검출 실패 / 미구현 여부 점검

이번 감사 기준에서 `현재 프로그램이 대표 P1 규칙을 검출하지 못하는 사례`는 찾지 못했다.

- `BenchmarkP1Fixture.ctl`: 4/4 일치
- `GoldenTime.ctl`: 4/4 일치
- `CtrlppCheck`: P1을 대체하지 않고 additive로 동작

따라서 현재 우선순위는 `규칙 검출기 복구`가 아니라 아래다.

- workspace 집계/정규화 정확성
- converted input boundary 처리
- Live AI/autofix 품질 안정화

## 기능 추가 제안

### 즉시 수정 권고

- triage entry에 `owner`, `expires_at`, 변경 이력 추가
- `P1 only`, `P1+P2`, `Live AI`, `raw txt`용 저장 가능한 analysis preset 추가

### 중기 구조개선

- Excel queue에 retry/history UX 추가
- rules editor에 sample preview와 dry-run detector preview 추가

### 문서/운영 개선

- audit mode 전용 consolidated report 생성기 추가

## 유지보수 개선 제안

### 즉시 수정 권고

- workspace normalization path 분리
  - txt/pnl에서 synthetic row와 native row가 섞이는 경로를 끊어야 한다.

### 중기 구조개선

- frontend 대형 파일 분해
  - [renderer.js](D:/AI_TF_CODEREVIEW-main/frontend/renderer.js): 약 2034 lines
  - [autofix-ai.js](D:/AI_TF_CODEREVIEW-main/frontend/renderer/autofix-ai.js): 약 1484 lines
  - [workspace-view.js](D:/AI_TF_CODEREVIEW-main/frontend/renderer/workspace-view.js): 약 1315 lines
- backend 대형 mixin 분해
  - [live_ai_review_mixin.py](D:/AI_TF_CODEREVIEW-main/backend/core/live_ai_review_mixin.py): 약 829 lines
  - [analysis_pipeline.py](D:/AI_TF_CODEREVIEW-main/backend/core/analysis_pipeline.py): 약 548 lines

### 문서/운영 개선

- encoding/BOM/cp949 boundary policy 공통화
- audit artifact retention/cleanup 자동화
- smoke/gate telemetry와 ad-hoc manual test artifact를 더 명확히 분리

## 우선 수정 Top 10

1. txt workspace finding count를 CLI/Excel과 일치시키기
2. `.pnl` 선택 시 하나의 canonical stream만 보여 주도록 정리하기
3. synthetic `.pnl` row의 `UNKNOWN` rule label 제거
4. Live AI patch 생성에서 canonical WinCC OA transform을 deterministic하게 만들기
5. apply 성공 판정에 post-apply heuristic delta를 포함하기
6. synthetic row와 native finding을 UI에서 명확히 구분하기
7. triage suppression에 owner/expiry/history 추가하기
8. preset 기반 분석 실행 추가하기
9. frontend workspace/autofix 상태 관리를 더 작은 모듈로 분리하기
10. full audit를 한 번에 모으는 report generator 추가하기

## 원본 복원 검증

- 대상 파일: [BenchmarkP1Fixture.ctl](D:/AI_TF_CODEREVIEW-main/CodeReview_Data/BenchmarkP1Fixture.ctl)
- 감사 전 SHA256: `8EF0759431A030B3002F143F91D68AB4417E5B91C4FD536835DA24CA744CED27`
- 복원 후 SHA256: `8EF0759431A030B3002F143F91D68AB4417E5B91C4FD536835DA24CA744CED27`
- 판정: 복원 성공

상세 증빙

- copy autofix: [autofix_copy_prepare.json](D:/AI_TF_CODEREVIEW-main/workspace/runtime/full_audit_20260321_232426/autofix_copy_prepare.json)
- original live autofix: [autofix_original_benchmark_live_session.json](D:/AI_TF_CODEREVIEW-main/workspace/runtime/full_audit_20260321_232426/autofix_original_benchmark_live_session.json)

## 결론

현재 프로그램은 WinCC OA 코드리뷰 자동화 프로그램으로서 `대표 정적 규칙 검출`은 제대로 동작한다. `BenchmarkP1Fixture.ctl`, `GoldenTime.ctl` 기준으로는 수동 리뷰와 자동 결과가 맞는다.

하지만 제품으로서 완성도를 보려면 아직 남은 문제가 있다.

- txt/pnl boundary에서 workspace 표시가 엔진 결과를 충실히 반영하지 못함
- Live AI/autofix는 기능적으로는 동작하지만 patch 의미 품질이 안정적이지 않음
- apply 성공 후에도 heuristic regression이 생길 수 있어 후속 품질 gate가 더 필요함

즉, 지금은 `검출기`는 합격이고 `사람이 매일 믿고 쓰는 제품`으로 가기 위한 마무리 단계가 남아 있는 상태다.
