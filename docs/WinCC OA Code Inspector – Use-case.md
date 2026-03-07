# WinCC OA Code Inspector 사용 시나리오 (v3.0)

마지막 업데이트: 2026-02-27 (현재 구현 기준)

이 문서는 실제 사용 흐름 중심으로 WinCC OA Code Inspector의 대표 사용 시나리오를 정리한다.

## 1. 기본 시나리오: 로컬에서 코드리뷰 수행

1. 사용자가 프로그램을 실행한다.
2. 파일 목록에서 `.ctl` 또는 변환된 텍스트 파일을 선택한다.
3. 분석 버튼을 눌러 P1/P2/P3 분석을 실행한다.
4. 결과 테이블에서 이슈를 클릭해 코드뷰어로 이동한다.
5. 심각도/소스(P1,P2,P3) 필터를 사용해 검토 범위를 줄인다.

결과:
- 요약 점수/건수 확인
- 리포트 산출물 생성
- 상세 코드 검토 가능

## 2. 성능 중심 시나리오: 중간 배치 분석

### 상황
- 파일 수가 늘어나 UI 렌더링/리포트 생성 지연이 체감됨

### 사용 흐름
1. 기본은 분석과 함께 Excel을 즉시 생성한다. 필요 시 `defer_excel_reports=true`로 지연 생성 모드로 전환한다.
2. 먼저 결과 검토를 진행한다.
3. 필요 시 `/api/report/excel` 또는 UI 버튼으로 Excel 생성 flush를 실행한다.
4. `/api/analyze`의 `metrics`를 비교해 병목 구간을 확인한다.

기대 효과:
- 체감 응답성 개선
- Excel 생성 비용 분리

## 3. AI 리뷰 활용 시나리오

1. Live AI를 켠 상태에서 분석 실행
2. P3(AI 리뷰) 항목을 확인
3. AI 카드에서 다음 중 선택
   - `Apply REVIEWED`: `_REVIEWED.txt` 반영
   - `Diff Preview`: source patch 제안 생성/확인
   - `Apply Source`: 승인된 diff를 원본 `.ctl`에 적용

## 4. 승인형 자동수정(LLM/rule) 시나리오

### 4.1 LLM 기반 제안
1. AI 리뷰 텍스트(코드블록 포함)를 기반으로 `autofix/prepare`
2. unified diff 확인
3. `autofix/apply` 호출
4. 검증 성공 시 원본 `.ctl` 반영, 백업/감사로그 저장

### 4.2 Rule 기반 제안
1. 특정 violation 기준으로 `generator_preference=rule`로 prepare
2. 결정적 정규화(diff) 또는 annotation 템플릿 제안 생성
3. diff 검토 후 승인 적용

### 4.3 Auto 모드
- `generator_preference=auto`
- 내부 정책: `rule-first`, 실패 시 `llm-fallback`

## 5. 자동수정 실패/차단 시나리오

### 예시
- 사용자가 diff 준비 후 원본 파일을 수동 수정함
- apply 시 base hash/anchor mismatch 발생

동작:
- 적용 중단
- `error_code` 반환 (`BASE_HASH_MISMATCH`, `ANCHOR_MISMATCH` 등)
- 재분석/재prepare 유도

### 회귀 차단
- heuristic 또는 Ctrlpp 회귀 증가 시(`block_on_regression=true`)
- 적용 차단 + 품질 메트릭 기록

## 6. 운영 검증 시나리오

### 6.1 UI 성능 회귀 점검
- `tools/playwright_ui_benchmark.js` 실행
- `ui_thresholds_*.json` 기준으로 threshold check

### 6.2 서버 성능 baseline 점검
- `tools/http_perf_baseline.py`로 `/api/analyze` 매트릭스 실행
- `docs/perf_baselines/`에 baseline 저장/비교

### 6.3 Ctrlpp 통합 스모크
- `tools/run_ctrlpp_integration_smoke.py` 실행
- direct smoke + unittest harness 결과 확인

## 7. 예외/운영 규칙

- 문서/설정/소스는 UTF-8로 저장 (`docs/encoding_policy.md`)
- 인코딩 문제 발생 시 백업 후 부분 복구, diff 검토 필수
- 자동수정은 승인형 흐름 유지(무승인 자동적용 금지)

