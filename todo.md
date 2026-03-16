# WinCC OA 코드 리뷰 프로그램 TODO

기준일: 2026-03-17

## 현재 기준 완료된 큰 축

- [x] backend entrypoint 분해
- [x] `heuristic_checker` 1차 분해
- [x] `autofix_mixin` 1차 분해
- [x] 대형 API 테스트 분해
- [x] `system_verification` 분해
- [x] frontend renderer 모듈 분해
- [x] dashboard / workspace / settings 3뷰 정리
- [x] frontend unit test 도입 (`vitest`)
- [x] GitHub Actions quality gate / extended smoke
- [x] rules import dry-run / rollback latest
- [x] P1 triage / suppress
- [x] P1 triage smoke round-trip
- [x] workspace UX 1차
- [x] dashboard 상세 관리 UI를 설정 화면으로 이동

## 현재 열려 있는 TODO

### 프론트 구조

- [ ] `autofix-ai.js` 추가 분해
- [ ] `style.css` 영역별 분리
- [ ] settings 화면 dense management UX 2차 정리
- [ ] dashboard summary copy / CTA 추가 다듬기

### 백엔드 구조

- [ ] `heuristic_checker.py` 내부 규칙 엔진 경계 추가 정리
- [ ] `autofix_apply_mixin.py` 세부 helper 추가 분해
- [ ] health / operations API helper 추가 정리

### 기능

- [ ] triage 2차
  - owner
  - history
  - expires_at
  - export / import
- [ ] rules manage rich editor
- [ ] saved analysis preset
- [ ] report queue / retry UX

### 문서 / 운영

- [ ] onboarding 문서 보강
- [ ] encoding / mixed text 가이드 확장
- [ ] release artifact 정리 자동화

## 유지보수 원칙

- [x] 새 기능은 작은 helper로 시작
- [x] controller 경계 안에서만 UI 기능 추가
- [x] 상태는 `app-state` 명시 필드로만 추가
- [x] 코드 변경과 함께 테스트를 같이 추가
- [x] 구조 변경 전 refactor backup 생성
