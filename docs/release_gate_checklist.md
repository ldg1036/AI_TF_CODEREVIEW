# Release Gate Checklist

Last Updated: 2026-03-17

## 목적

릴리스 가능한 빌드인지 판단하기 전에 최소한 확인해야 할 게이트를 정리합니다.

## 0. 환경 준비

```powershell
python --version
node --version
python -m pip install -r requirements-dev.txt
npm install
```

선택 UI 런타임:

```powershell
npx playwright install chromium
```

## 1. 빠른 코어 게이트

```powershell
python -m unittest backend.tests.test_api_and_reports -v
python backend/system_verification.py
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
npm run test:frontend
```

통과 기준:
- backend test green
- `system_verification` green
- config alignment mismatch `0`
- template coverage `Client 15/15`, `Server 20/20`
- frontend unit green

## 2. 문법 / 정적 게이트

```powershell
python -m py_compile backend/main.py backend/server.py
node --check frontend/renderer.js
```

필요 시 추가:

```powershell
node --check frontend/renderer/dashboard-panels.js
node --check frontend/renderer/workspace-view.js
```

## 3. UI 게이트

real smoke:

```powershell
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

benchmark:

```powershell
node tools/playwright_ui_benchmark.js --iterations 3
```

통과 기준:
- analyze 경로 정상
- workspace 진입 가능
- 결과 row 렌더링
- code jump / detail / AI 흐름 정상
- triage suppress / unsuppress smoke가 포함된 경우 round-trip 성공

## 4. 선택 의존성 게이트

### Ctrlpp

```powershell
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
```

실제 배포 범위에 Ctrlpp가 포함되면:

```powershell
python tools/run_ctrlpp_integration_smoke.py
```

### Live AI

대표 분석:

```powershell
python backend/main.py --selected-files BenchmarkP1Fixture.ctl --enable-live-ai --ai-with-context
```

통과 기준:
- optional dependency가 없더라도 fail-soft 유지
- 실제 포함 범위라면 analyze 완료

## 5. 운영 API 확인

최소 확인 대상:
- `GET /api/health/deps`
- `GET /api/operations/latest`
- `GET /api/rules/health`
- `GET /api/triage/p1`
- rules manage 관련 `/api/rules/*`

확인 포인트:
- dependency 상태 정확성
- 운영 검증 결과 payload 해석 가능
- rules health가 enabled / detector distribution을 정상 표시
- rules import dry-run / rollback latest 동작
- triage API가 빈 파일/정상 파일/삭제 경로에서 안전하게 동작

## 6. 화면 구조 확인

현재 UI 계약:
- 대시보드: 요약 중심
- 작업공간: 실제 리뷰 작업
- 설정: 운영 검증 상세 + 규칙 / 의존성 관리

확인 포인트:
- 대시보드에 규칙 관리 폼이 직접 보이지 않음
- `설정` nav 동작
- `설정에서 자세히 보기` CTA 동작

## 7. 게이트 단축 명령

빠른 로컬 게이트:

```powershell
python tools/run_local_quality_gate.py
```

확장 로컬 게이트:

```powershell
python tools/run_local_extended_gate.py
```

통합 게이트:

```powershell
python tools/release_gate.py
python tools/release_gate.py --profile ci
```

## 8. 보관할 산출물

최소 보관:
- `CodeReview_Report/release_gate_*.json`
- `CodeReview_Report/release_gate_*.md`
- `tools/integration_results/ui_real_smoke_*.json`
- `tools/benchmark_results/ui_benchmark_*.json`
- `tools/integration_results/ctrlpp_integration_*.json`

필요 시 추가:
- `CodeReview_Report/verification_summary_*.json`
- `CodeReview_Report/template_coverage_*.json`
- `CodeReview_Report/*/analysis_summary.json`

## 9. 최종 판단 기준

다음이면 release-ready로 판단 가능합니다.

- 약속한 범위의 기능이 현재 게이트로 확인됨
- 필수 게이트가 green
- 선택 기능은 실제 포함 범위일 때만 별도 확인됨
- fail-soft 기능을 필수 기능처럼 문서화하거나 주장하지 않음
