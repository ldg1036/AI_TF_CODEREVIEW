# Release Packaging Criteria

Last Updated: 2026-03-17

## 목적

최종 전달 패키지에 무엇을 포함하고, 무엇을 runtime 산출물로만 취급할지 정의합니다.

## 1. 최소 릴리스 수용 기준

아래가 충족되면 패키징 가능한 상태로 봅니다.

- `python tools/run_local_quality_gate.py` 통과
- 필요 시 `python tools/run_local_extended_gate.py` 통과
- 또는 `python tools/release_gate.py` 기준 통과
- 최신 gate JSON / Markdown 요약이 존재

## 2. 패키지에 포함할 것

기본 포함:
- `backend/`
- `frontend/`
- `tools/`
- `Config/`
- `docs/`
- `requirements-dev.txt`
- `package.json`
- `package-lock.json`
- `README.md`

상황에 따라 포함:
- `CodeReview_Data/` 샘플 또는 fixture 전달이 필요할 때
- `tools/CtrlppCheck/` 오프라인 환경일 때

## 3. 소스 패키지로 보지 않을 것

기본적으로 포함하지 않음:
- `CodeReview_Report/`
- 임시 로그
- ad-hoc benchmark 결과
- local cache
- `workspace/runtime/refactor_backups/`
- `workspace/runtime/triage/`
- `workspace/runtime/rule_backups/`

이들은 runtime / evidence 산출물입니다.

## 4. 선택 의존성 정책

### CtrlppCheck
- 기본은 optional
- 실제 납품 범위에 포함되면 smoke 결과를 같이 확인

### Live AI / Ollama
- 기본은 optional
- 실제 acceptance scope에 포함될 때만 필수 검증

### Playwright
- 정상 런타임 필수는 아님
- UI smoke / benchmark를 전달 범위에 포함할 때만 필요

## 5. 권장 패키징 프로필

### Clean source package

대상:
- 수신 측이 직접 설치 가능

포함:
- 소스
- 설정
- 문서
- 실행 wrapper

제외:
- runtime 리포트
- browser cache
- triage / rule backup / refactor backup

### Operator-ready local package

대상:
- 비개발자 운영자
- 반오프라인 / 통제된 환경

추가 고려:
- `tools/CtrlppCheck/`
- 필요 시 Playwright browser/runtime

## 6. 릴리스 노트에 남길 것

각 패키지마다 기록:
- release date
- gate JSON 경로
- gate Markdown 경로
- Live AI 포함 여부
- Ctrlpp 포함 여부
- 선택 의존성 제외 여부
- 현재 UI 구조
  - 대시보드: 요약
  - 작업공간: 리뷰 작업
  - 설정: 운영 / 규칙 관리

## 7. 최종 판단 규칙

간단한 기준:
- 약속한 기능이 실제 통과한 gate 범위에 포함되면 패키징
- 확인하지 않은 optional 기능은 release-ready라고 주장하지 않음
