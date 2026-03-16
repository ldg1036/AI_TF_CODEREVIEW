# User Operations Guide

Last Updated: 2026-03-17

## 목적

이 문서는 운영자나 리뷰 담당자가 개발 문서를 깊게 읽지 않고도 프로그램을 안정적으로 실행하고 사용하는 데 필요한 현재 기준 사용 방법을 정리합니다.

## 1. 시작 전 준비

필수:
- Windows 환경
- Python 3.10+
- `python -m pip install -r requirements-dev.txt`
- 입력 파일이 `CodeReview_Data` 또는 외부 선택 경로에 준비됨

권장:
- `npm install`
- `npx playwright install chromium`

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

접속:

```text
http://127.0.0.1:8765
```

### CLI 모드

```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

## 3. 화면 구조

### 대시보드
- 프로젝트 요약
- 전체 이슈 / 현재 검토 대상 / 치명 / 경고
- 중복 정리 요약
- 우선 수정 추천
- compact 시스템 상태 요약

참고:
- 자세한 운영 검증과 규칙 관리는 더 이상 대시보드에 직접 나오지 않습니다.
- `설정에서 자세히 보기` 또는 좌측 `설정`으로 이동합니다.

### 작업공간
- 파일 목록 / 파일 검색
- 코드 뷰어
- 결과 리스트 / 결과 검색
- preset 버튼 (`기본 보기`, `P1만`, `치명/경고`)
- P1 triage
- AI / compare / autofix

작업공간 주요 동작:
- 코드 뷰어와 결과 리스트 사이 높이 드래그 조절
- 첫 결과 자동 선택
- `이전 이슈`, `다음 이슈`, `코드 보기`, `상세 탭`, `AI 탭`
- `숨김 처리 포함` 토글

### 설정
- 운영 검증 상세
  - UI benchmark
  - real UI smoke
  - Ctrlpp integration
- 규칙 / 의존성 관리
  - dependency readiness
  - rule list / create / replace / delete
  - import dry-run preview
  - rollback latest

## 4. 분석 흐름

UI 기본 분석은 비동기 경로를 사용합니다.

- `POST /api/analyze/start`
- `GET /api/analyze/status`

UI에서 보이는 항목:
- 진행률
- ETA
- 경과 시간
- 최종 결과 요약

필요 시 `/api/analyze` 동기 경로도 계속 지원됩니다.

## 5. P1 Triage 사용법

P1 항목은 triage를 통해 숨김 처리할 수 있습니다.

기본 동작:
- 숨김 처리된 P1은 기본 결과 리스트에서 숨김
- `숨김 처리 포함`을 켜면 다시 보임
- 재분석 후에도 동일 fingerprint의 P1 이슈는 계속 숨김 유지

상세 패널에서 가능한 작업:
- `숨김 처리`
- `숨김 해제`
- `사유`
- `메모`

저장 위치:
- `workspace/runtime/triage/p1_triage_entries.json`

## 6. Rules Manage 사용법

설정 화면에서 다음 작업을 할 수 있습니다.

- 규칙 목록 확인
- 새 규칙 생성
- 기존 규칙 수정 / 삭제
- `enabled` 토글 저장
- JSON export
- import preview (`merge`, `replace`)
- rollback latest

현재 편집 모델:
- detector / meta는 JSON 형태 편집
- 저장 전 validation 수행

## 7. 릴리스 게이트 단축 명령

빠른 게이트:

```powershell
python tools/run_local_quality_gate.py
```

확장 게이트:

```powershell
python tools/run_local_extended_gate.py
```

통합 게이트:

```powershell
python tools/release_gate.py
python tools/release_gate.py --profile ci
```

## 8. 자주 쓰는 검증

프론트 변경:

```powershell
npm run test:frontend
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

백엔드 / API 변경:

```powershell
python -m unittest backend.tests.test_api_and_reports -v
python backend/system_verification.py
```

rules / config 변경:

```powershell
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
```

## 9. 자주 발생하는 문제

### UI가 열리지 않음

확인:
- `python backend/server.py`가 실행 중인지
- `8765` 포트가 사용 가능한지

### 대시보드에 상세 운영 카드가 없음

정상입니다.

- 운영 검증 상세와 규칙 관리는 `설정` 화면으로 이동했습니다.

### 결과가 안 보임

확인:
- 파일 선택 여부
- source / severity 필터
- 결과 검색 입력
- `숨김 처리 포함` 상태
- triage로 P1이 숨겨졌는지

### rules / dependency가 degraded로 보임

주요 원인:
- `openpyxl` 미설치
- Playwright browser 미설치
- Ctrlpp binary 미설치

기본 정적 분석 자체가 자동으로 막히는 것은 아닙니다.

### UI smoke 또는 benchmark가 실패함

확인:
- `npm install`
- `npx playwright install chromium`
- 브라우저/머신 부하

## 10. 현재 범위에 없는 것

아직 포함하지 않은 것:
- detector-type 전용 rich form editor
- triage owner / history / expires_at
- 모바일 전용 반응형 재설계
- rules manage full history UI
