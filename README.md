# WinCC OA Code Inspector

Last validated: 2026-03-23

## 개요

`WinCC OA Code Inspector`는 WinCC OA 프로젝트 코드 리뷰를 자동화하는 데스크톱형 분석 도구입니다.  
핵심 흐름은 아래 4단계입니다.

1. 파일 업로드 또는 폴더 선택
2. 규칙 기반 자동 코드리뷰 실행
3. 코드뷰어와 결과 리스트에서 문제 확인
4. 선택적으로 Live AI 제안 비교, 준비, 적용

## 분석 축

- `P1`: 정적 규칙 기반 분석
- `P2`: `CtrlppCheck` 연동 분석
- `P3`: 선택형 Live AI 리뷰

## 지원 입력

- `.ctl`
- `.pnl`, `.xml`에서 변환된 텍스트
  - 제품 정책: `converted only`
  - UI와 분석은 canonical `*_pnl.txt`, `*_xml.txt` 기준으로 동작
- raw `.txt`
  - CLI의 `--allow-raw-txt` 또는 UI 경로에서 허용되는 경우만 사용

## 주요 출력

- 대시보드 / 작업공간 / 설정 UI
- HTML 리포트
- Excel 리포트
- Annotated TXT (`*_REVIEWED.txt`)
- autofix diff / apply 결과

## 현재 UI 구조

### 대시보드

- 상단 공통 분석 strip
- 운영 요약 카드
- 최근 검증 / 산출물 / 상태 요약

### 작업공간

- 왼쪽 파일 영역
  - 외부 파일 추가
  - 폴더 선택
  - 세션 입력 요약
  - 파일 검색 / 파일 목록
- 상단 compact 분석 strip
  - 선택 요약
  - `선택 항목 분석`
  - `고급`
  - `Live AI 사용 (P3)`
- 메인 리뷰 영역
  - 코드뷰어
  - 결과 리스트
  - 이슈 상세 / AI 제안 패널
- 부가 기능
  - 결과 이동
  - 코드 jump
  - compare / prepare / apply
  - 세로 리사이즈

### 설정

- dependency readiness
- rules health
- rules CRUD / import dry-run / rollback
- 운영 검증 상태

## 주요 기능

### 분석

- `POST /api/analyze`
- `POST /api/analyze/start`
- `GET /api/analyze/status?job_id=...`
- bounded parallel 분석
- canonical input normalization
- mixed encoding read fallback

### Autofix

- `POST /api/autofix/prepare`
- `POST /api/autofix/apply`
- `GET /api/autofix/file-diff`
- prepare 단계의 quality gate
- compare / prepare / apply 계약 분리
- `allow_apply` 기준 conservative apply

### Triage

- `GET /api/triage/p1`
- `POST /api/triage/p1/upsert`
- `POST /api/triage/p1/delete`
- suppressed P1 유지 / 재표시

### Rules Manage

- list / create / update / delete
- export
- import merge / replace
- import dry-run preview
- rollback latest
- revision-based write verification

### 운영 / 검증

- dependency health
- latest operations
- latest verification
- release gate
- UI real smoke
- UI benchmark
- Ctrlpp integration smoke

## 빠른 시작

### 필수 준비

```powershell
python -m pip install -r requirements-dev.txt
npm install
```

선택 의존성:

- `CtrlppCheck`
- `Ollama`
- Playwright browser

```powershell
npx playwright install chromium
```

선택 의존성이 없어도 기본 분석과 대부분의 검증은 fail-soft로 계속 동작합니다.

### UI 서버 실행

```powershell
python backend/server.py
```

기본 주소:

```text
http://127.0.0.1:8765
```

### CLI 분석 실행

```powershell
python backend/main.py --selected-files CodeReview_Data\\GoldenTime.ctl
python backend/main.py --selected-files CodeReview_Data\\BenchmarkP1Fixture.ctl --enable-ctrlppcheck
```

## 권장 검증 명령

### 프런트 변경

```powershell
npm run test:frontend
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

### Live AI / compare / prepare 경로

```powershell
node tools/playwright_ui_real_smoke.js --timeout-ms 180000 --target-file BenchmarkP1Fixture.ctl --with-live-ai-compare-prepare
```

### 백엔드 / API 변경

```powershell
python -m unittest backend.tests.test_api_and_reports -v
python -m unittest backend.tests.test_winccoa_context_server -v
```

### rules / config 변경

```powershell
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
```

### 통합 게이트

```powershell
python tools/release_gate.py --profile local --with-live-ai --with-live-ai-ui
```

## UI 사용 흐름

### 1. 입력 준비

- 왼쪽 파일 영역에서 `외부 파일 추가` 또는 `폴더 선택`
- 파일 목록에서 분석 대상 확인

### 2. 분석 실행

- 상단 strip에서 `선택 항목 분석`
- 필요 시 `Live AI 사용 (P3)` 활성화
- 추가 옵션은 `고급` 패널에서 사용

### 3. 결과 검토

- 코드뷰어에서 맥락 확인
- 결과 리스트에서 이슈 탐색
- 상세 패널에서 검출 근거 확인

### 4. AI 제안

- AI 제안 생성
- compare / prepare 결과 확인
- 차단 이유 또는 적용 가능 여부 확인

## 입력/인코딩 정책

- 새 파일은 UTF-8 기준으로 작성
- 기존 WinCC OA 입력은 `utf-8-sig -> utf-8 -> cp949 -> euc-kr` 순으로 읽기 시도
- `.pnl`, `.xml`은 변환된 canonical 텍스트 기준으로 분석 / 표시 / Excel / summary가 일치하도록 유지

## 참고 문서

- [사용자 운영 가이드](/D:/AI_TF_CODEREVIEW-main/docs/user_operations_guide.md)
- [도구 폴더 가이드](/D:/AI_TF_CODEREVIEW-main/tools/README.md)
- [Encoding Policy](/D:/AI_TF_CODEREVIEW-main/docs/encoding_policy.md)
- [Release Gate Checklist](/D:/AI_TF_CODEREVIEW-main/docs/release_gate_checklist.md)
