# User Operations Guide

Last updated: 2026-03-23

## 목적

이 문서는 운영자와 리뷰 담당자가 개발 문서를 깊게 읽지 않고도 프로그램을 실행하고, 분석하고, 결과를 검토하는 데 필요한 현재 기준 사용 흐름을 정리합니다.

## 1. 시작 전 준비

필수:

- Windows 환경
- Python 3.10+
- `python -m pip install -r requirements-dev.txt`
- `npm install`

권장:

```powershell
npx playwright install chromium
```

선택 의존성:

- `CtrlppCheck`
- `Ollama`
- Playwright browser runtime

선택 의존성이 없어도 기본 분석은 fail-soft로 계속 동작합니다.

## 2. 실행 모드

### UI 모드

```powershell
python backend/server.py
```

기본 주소:

```text
http://127.0.0.1:8765
```

### CLI 모드

```powershell
python backend/main.py --selected-files CodeReview_Data\\GoldenTime.ctl
```

## 3. 현재 화면 구조

### 대시보드

- 상단 공통 분석 strip
- 프로젝트 요약 카드
- 최근 검증 / 운영 상태
- 작업공간으로 이어지는 개요 화면

### 작업공간

- 왼쪽 파일 영역
  - 외부 파일 추가
  - 폴더 선택
  - 세션 입력 요약
  - 파일 검색 / 파일 목록
- 상단 compact 분석 strip
  - 선택 파일 / 현재 표시 / 전체 검토 대상 요약
  - `선택 항목 분석`
  - `고급`
  - `Live AI 사용 (P3)`
- 메인 리뷰 영역
  - 코드뷰어
  - 결과 리스트
  - 이슈 상세 / AI 패널

### 설정

- dependency readiness
- rules health
- rules CRUD / import / rollback
- 운영 검증 상세

## 4. 기본 사용자 흐름

### 1) 입력 준비

- 왼쪽 파일 영역에서 `외부 파일 추가` 또는 `폴더 선택`
- 파일 목록에서 분석 대상을 확인

### 2) 분석 실행

- 상단 strip에서 `선택 항목 분석`
- 필요 시 `Live AI 사용 (P3)` 활성화
- `고급` 패널에서 추가 옵션 사용

### 3) 결과 검토

- 코드뷰어에서 코드 문맥 확인
- 결과 리스트에서 이슈 탐색
- 상세 패널에서 검출 근거와 설명 확인

### 4) AI 제안 검토

- AI 제안 생성
- compare / prepare 결과 확인
- 적용 가능 여부 또는 차단 이유 확인

## 5. 작업공간 세부 동작

### 코드뷰어

- 현재 선택 이슈 기준으로 점프
- 코드 필터 사용 가능
- 결과 리스트와 높이 리사이즈 가능
- 현재 기준 동작:
  - 아래로 드래그하면 코드뷰어가 길어짐
  - 위로 드래그하면 코드뷰어가 줄어듦

### 결과 리스트

- preset 사용 가능
  - `기본 보기`
  - `P1만`
  - `치명/경고`
- 검색 조건으로 메시지 / 파일 / 규칙 기준 필터 가능

### 고급 패널

기본 화면에서는 닫혀 있고, 필요할 때만 floating panel로 열립니다.

포함 항목:

- `CtrlppCheck 사용 (P2)`
- `P3 모델`
- `AI 분석 강화 (추가 문맥 사용)`
- 검증 배지
- Excel 생성 / 다운로드 상태
- 운영 토글

## 6. P1 Triage

P1 triage 기능은 유지되지만, 일반 사용 흐름에서는 상세 패널보다 운영 경로에서 사용하는 것이 기본입니다.

기본 동작:

- 숨김 처리된 P1은 기본 결과 리스트에서 숨김
- `숨김 처리 포함`을 켜면 다시 보임
- 재분석 후에도 동일 fingerprint의 P1 이슈는 계속 숨김 유지

저장 위치:

- `workspace/runtime/triage/p1_triage_entries.json`

## 7. AI / Autofix 상태 해석

AI 패널에서는 현재 상태를 가능한 한 정직하게 표시합니다.

주요 상태:

- 모델 / 엔드포인트 미준비
- 생성 실패
- 생성 성공이지만 실질 리뷰 없음
- 수정안 준비 완료
- 적용 차단
- 적용 가능

차단 예:

- placeholder / example code 포함
- identifier reuse 실패
- no-op patch
- semantic guard 차단

## 8. Rules Manage 사용법

설정 화면에서 다음 작업을 수행할 수 있습니다.

- 규칙 목록 확인
- 새 규칙 생성
- 기존 규칙 수정 / 삭제
- export
- import preview (`merge`, `replace`)
- rollback latest

현재 rules write 응답은 revision 기반 검증 정보를 함께 제공합니다.

## 9. 권장 검증 명령

### 프런트 변경

```powershell
npm run test:frontend
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

### Live AI compare / prepare 경로

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

### 통합 gate

```powershell
python tools/release_gate.py --profile local --with-live-ai --with-live-ai-ui
```

## 10. 자주 발생하는 문제

### Playwright browser가 없음

- `npx playwright install chromium` 실행
- 또는 UI smoke를 skip하고 backend / unit test만 우선 수행

### CtrlppCheck가 없음

- `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
- fail-soft 경로로 현재 상태를 확인

### Ollama / Live AI가 준비되지 않음

- 기본 분석은 계속 가능
- AI 패널은 미준비 상태와 이유를 표시

### `.pnl` / `.xml` 입력이 바로 안 보임

- 현재 제품 정책은 canonical converted text 기준입니다
- `*_pnl.txt`, `*_xml.txt` 기준으로 분석 / 표시 / Excel / summary가 맞춰집니다
