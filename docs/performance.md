# Performance Baselines and Quality Gates

Last Updated: 2026-03-17

## 목표

이 프로젝트의 성능 검사는 아래 3가지를 분리해서 판단합니다.

- 프론트 UI가 여전히 반응하는가
- end-to-end analyze 경로가 허용 범위인가
- heuristic 최적화가 실제로 scan 비용을 줄였는가

## 사용 가능한 도구

- UI benchmark: `node tools/playwright_ui_benchmark.js`
- real UI smoke: `node tools/playwright_ui_real_smoke.js`
- HTTP baseline: `python tools/http_perf_baseline.py`
- heuristic same-build baseline: `python tools/http_perf_baseline.py --focus heuristic`

## 현재 UI 관측 구조

### 대시보드
- compact 시스템 상태 요약만 표시
- 최근 smoke / benchmark 한 줄 요약
- dependency badge 요약

### 설정
- 운영 검증 상세
  - UI benchmark
  - UI real smoke
  - Ctrlpp integration
- 규칙 / 의존성 관리

즉, 운영 검증 상세 비교 카드는 더 이상 대시보드의 기본 카드가 아니라 `설정` 화면에 있습니다.

## 프론트 기준 성능 체크

### 빠른 프론트 회귀

```powershell
npm run test:frontend
```

### Real UI smoke

```powershell
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

현재 smoke는 다음까지 포함해 검증합니다.
- workspace 진입
- 결과 row 렌더링
- code jump
- detail / AI 경로
- P1 triage suppress / unsuppress round-trip

### UI benchmark

```powershell
node tools/playwright_ui_benchmark.js --iterations 3
```

## 백엔드 기준 성능 체크

### End-to-end HTTP baseline

먼저 서버 실행:

```powershell
python backend/server.py
```

다른 터미널:

```powershell
python tools/http_perf_baseline.py `
  --dataset-name local-sample `
  --discover-count 1 `
  --ctrlpp off,on `
  --live-ai off `
  --defer-excel off,on `
  --iterations 3 `
  --flush-excel
```

판단 대상:
- full request latency
- report / Excel 비용
- optional dependency overhead

### Heuristic same-build baseline

```powershell
python tools/http_perf_baseline.py `
  --focus heuristic `
  --selected-files GoldenTime.ctl `
  --iterations 3
```

판단 규칙:
- `same_findings=true`
- `with_context_avg_ms <= without_context_avg_ms`

## 주요 백엔드 timing field

주요 필드:
- `metrics.timings_ms.total`
- `metrics.timings_ms.collect`
- `metrics.timings_ms.analyze`
- `metrics.timings_ms.heuristic`
- `metrics.timings_ms.report`
- `metrics.timings_ms.excel`

해석 원칙:
- release 관점: `total`
- scan-path 관점: `analyze`, `heuristic`
- report / Excel 비용이 큰 변경은 `report`, `excel`도 따로 본다

## 권장 threshold

- UI benchmark: `p95` drift 20% 이상이면 의심
- HTTP baseline: `total`, `analyze`, `report` drift 20% 이상이면 확인
- heuristic same-build baseline:
  - `same_findings=true`
  - `with_context_avg_ms <= without_context_avg_ms`

## 노이즈 처리

- 최소 `3`회 반복
- 같은 머신 profile에서 비교
- `live_ai`, `ctrlpp`, `defer_excel_reports`, selected file set을 맞춤
- 단발 spike는 재실행 후 판단

## 산출물 저장 위치

- `docs/perf_baselines/`
- `tools/benchmark_results/`
- `tools/integration_results/`

권장 확인 순서:
1. `npm run test:frontend`
2. `node tools/playwright_ui_real_smoke.js`
3. `node tools/playwright_ui_benchmark.js`
4. `python tools/http_perf_baseline.py`
5. heuristic same-build baseline
