# WinCC OA Code Review Program 개선 권고 현황

검토 기준일: 2026-03-17

## 현재 상태 요약

현재 프로그램은 다음 영역까지 구현되어 있습니다.

- 분해된 backend entrypoint / mixin 구조
- 분해된 frontend controller / helper 구조
- `대시보드 / 작업공간 / 설정` 3뷰
- P1 triage / suppress
- rules import dry-run / rollback latest
- frontend unit test (`vitest`)
- local quality gate / extended gate
- GitHub Actions quality gate / extended smoke
- real UI smoke / benchmark / Ctrlpp integration smoke

## 현재 강점

- 분석 기능 자체는 이미 실사용 가능한 수준
- optional dependency fail-soft가 일관적
- UI smoke, backend test, system verification까지 운영 검증선이 형성됨
- refactor backup 도구가 있어 구조 변경 시 회귀 추적이 쉬움

## 다음 우선 권고

### Priority 1

- `autofix-ai.js` 추가 분해
- `heuristic_checker.py` 내부 규칙 경계 추가 정리
- `style.css` 대형 스타일 분리
- triage history / owner / expires_at 같은 운영 메타데이터는 2차 설계 후 추가

### Priority 2

- rules manage rich editor
  - detector type별 입력 UI
  - sample match preview
  - validation diff
- dashboard / settings 정보 구조 추가 정리
  - 운영 카드 노이즈 최소화
  - CTA / 요약 문구 더 선명하게

### Priority 3

- 운영 문서와 onboarding 문서 보강
- encoding / cp949 / euc-kr 대응 가이드 강화
- release artifact 정리 자동화

## 기능 측면의 다음 후보

- triage 2차
  - owner
  - history
  - expires_at
  - export / import
- saved analysis preset
- report queue / retry UX
- detector rich editor

## 유지보수 관점의 핵심 메모

- 총 코드량보다 남은 큰 파일의 응집도가 더 중요
- 새 기능은 항상 `helper -> controller -> view wiring` 순으로 추가해야 함
- 기존 API shape는 안정적으로 유지하는 것이 우선
- smoke와 unit test를 같이 늘리는 방향이 가장 비용 대비 효과가 큼
