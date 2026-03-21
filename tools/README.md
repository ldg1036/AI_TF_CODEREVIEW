# Tools Folder Guide

Last Updated: 2026-03-17

`tools/`는 성능, smoke, Ctrlpp, 게이트 실행을 위한 보조 도구를 모아 둔 폴더입니다.

## 핵심 도구

### 게이트 / 운영
- `tools/release_gate.py`
- `tools/run_local_quality_gate.py`
- `tools/run_local_extended_gate.py`

### 프론트 검증
- `tools/playwright_ui_benchmark.js`
- `tools/playwright_ui_real_smoke.js`

### 성능
- `tools/http_perf_baseline.py`
- `tools/perf/autofix_apply_baseline.py`

### Ctrlpp
- `tools/run_ctrlpp_integration_smoke.py`
- `tools/ctrlppcheck_updater.py`
- `tools/ctrlppcheck_wrapper.py`

## 현재 smoke / benchmark 특징

### `playwright_ui_real_smoke.js`

현재 smoke는 단순 렌더링 확인만 하지 않습니다.

- dashboard/workspace 기본 진입
- 결과 row 렌더링
- code jump / detail / AI 경로
- P1 triage suppress / unsuppress round-trip
- 선택 플래그로 `Generate -> Compare -> Prepare patch` 실브라우저 검증 가능

또한 현재 fixture 특성상 기본 후보에서 결과가 없으면:
- 다른 target file 재시도
- 필요 시 Ctrlpp on 경로 재시도

즉, 실패해도 단순 DOM 미존재보다 더 많은 진단 정보를 JSON에 남깁니다.

### `playwright_ui_benchmark.js`

주요 용도:
- 결과 리스트 virtualization
- 코드 뷰어 jump / scroll
- analyze 이후 UI 반응성

## 결과 저장 위치

- `tools/benchmark_results/`
- `tools/integration_results/`

## Ctrlpp runtime

- `tools/CtrlppCheck/`는 CtrlppCheck runtime install/cache 경로입니다.
- 배포 범위에 따라 포함/제외할 수 있습니다.

## 권장 사용 순서

빠른 로컬 검증:

```powershell
python tools/run_local_quality_gate.py
```

확장 검증:

```powershell
python tools/run_local_extended_gate.py
```

개별 도구 직접 실행:

```powershell
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
node tools/playwright_ui_real_smoke.js --timeout-ms 180000 --target-file BenchmarkP1Fixture.ctl --with-live-ai-compare-prepare
node tools/playwright_ui_benchmark.js --iterations 3
python tools/http_perf_baseline.py --dataset-name local-sample --iterations 3
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
python tools/release_gate.py --profile local --with-live-ai --with-live-ai-ui
```

## 호환성 entrypoint

아래 파일들은 기존 경로 호환을 위해 유지됩니다.

- `tools/http_perf_baseline.py`
- `tools/playwright_ui_benchmark.js`
- `tools/playwright_ui_real_smoke.js`
- `tools/run_ctrlpp_integration_smoke.py`
- `tools/ctrlppcheck_updater.py`
- `tools/ctrlppcheck_wrapper.py`
