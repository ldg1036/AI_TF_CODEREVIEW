# Tools Folder Guide

Last updated: 2026-03-23

`tools/`는 WinCC OA Code Inspector의 smoke, benchmark, gate, cleanup, Ctrlpp 보조 스크립트를 모아 둔 폴더입니다.

## 핵심 도구

### 게이트 / 운영

- `tools/release_gate.py`
- `tools/run_local_quality_gate.py`
- `tools/run_local_extended_gate.py`
- `tools/cleanup_runtime_artifacts.py`

### 프런트 검증

- `tools/playwright_ui_real_smoke.js`
- `tools/playwright_ui_benchmark.js`

### 성능

- `tools/http_perf_baseline.py`
- `tools/perf/autofix_apply_baseline.py`

### Ctrlpp

- `tools/run_ctrlpp_integration_smoke.py`
- `tools/ctrlppcheck_updater.py`
- `tools/ctrlppcheck_wrapper.py`

## 현재 기준 도구 역할

### `playwright_ui_real_smoke.js`

현재 smoke는 단순 DOM 확인이 아니라 실제 사용자 흐름 중심으로 동작합니다.

- dashboard / workspace 진입
- 왼쪽 파일 영역과 상단 분석 strip 확인
- 결과 row 렌더링
- code jump / detail / AI 경로 확인
- canonical txt / pnl parity 점검
- 선택 옵션으로 `Generate -> Compare -> Prepare patch` 실브라우저 검증
- 고급 패널 overlay, AI 상태, 주요 상호작용 회귀 기록

산출물은 `tools/integration_results/` 아래 JSON으로 저장됩니다.

### `playwright_ui_benchmark.js`

주요 목적:

- 결과 리스트 virtualization 확인
- 코드뷰어 jump / scroll 응답성 확인
- analyze 이후 UI 반응성 측정

### `release_gate.py`

현재 로컬 기준 권장 통합 검증 경로입니다.

- backend tests
- frontend tests
- 기본 smoke
- optional live AI smoke
- 규칙 / 성능 / 운영 상태 검증

## 자주 쓰는 실행 예시

### 빠른 로컬 검증

```powershell
python tools/run_local_quality_gate.py
```

### 확장 검증

```powershell
python tools/run_local_extended_gate.py
```

### 기본 UI smoke

```powershell
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

### Live AI compare / prepare smoke

```powershell
node tools/playwright_ui_real_smoke.js --timeout-ms 180000 --target-file BenchmarkP1Fixture.ctl --with-live-ai-compare-prepare
```

### UI benchmark

```powershell
node tools/playwright_ui_benchmark.js --iterations 3
```

### HTTP baseline

```powershell
python tools/http_perf_baseline.py --dataset-name local-sample --iterations 3
```

### Ctrlpp smoke

```powershell
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
```

### 통합 gate

```powershell
python tools/release_gate.py --profile local --with-live-ai --with-live-ai-ui
```

### runtime artifact cleanup

```powershell
python tools/cleanup_runtime_artifacts.py
python tools/cleanup_runtime_artifacts.py --apply
```

## Runtime Artifact Cleanup

`tools/cleanup_runtime_artifacts.py`는 오래된 산출물과 runtime 후보를 정리하는 내부 유지보수 도구입니다.

- 기본값: dry-run
- `--apply`: 오래된 후보를 `bk/runtime_cleanup/<timestamp>/`로 이동
- 잠긴 파일은 `skipped_locked`로 보고하고 실패로 보지 않음

## 결과 저장 위치

- `tools/benchmark_results/`
- `tools/integration_results/`

## Ctrlpp runtime

- `tools/CtrlppCheck/`는 CtrlppCheck runtime install / cache 경로입니다.
- 배포 형태에 따라 포함 또는 제외할 수 있습니다.
- Ctrlpp binary가 없어도 `--allow-missing-binary` 경로로 fail-soft smoke를 돌릴 수 있습니다.

## Optional Dependency Policy

아래 의존성은 기본적으로 optional입니다.

- `CtrlppCheck`
- `Ollama`
- Playwright browser runtime

없을 때 기본 정책:

- 정적 분석과 backend tests는 계속 진행
- Ctrlpp smoke는 fail-soft 경로 사용
- Playwright browser가 없으면 UI smoke prerequisites를 명확히 보고

## 호환성 entrypoint

아래 파일들은 기존 호출 경로 호환을 위해 계속 유지됩니다.

- `tools/http_perf_baseline.py`
- `tools/playwright_ui_benchmark.js`
- `tools/playwright_ui_real_smoke.js`
- `tools/run_ctrlpp_integration_smoke.py`
- `tools/ctrlppcheck_updater.py`
- `tools/ctrlppcheck_wrapper.py`
