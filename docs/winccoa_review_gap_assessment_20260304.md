# WinCC OA 자동 코드리뷰 프로그램 보완 기능 테스트 검토 (2026-03-04, 2026-03-08 업데이트 반영)

## 초기 관찰과 현재 상태

2026-03-04 시점에 드러났던 핵심 리스크는 다음 두 가지였다.

- 선택 의존성 상태가 운영자 관점에서 충분히 보이지 않음
- 성능과 운영 검증 결과를 비교해서 읽는 경로가 부족함

2026-03-08 기준으로 아래 항목은 해소되거나 크게 줄었다.

- dependency preflight: `GET /api/health/deps`
- benchmark / smoke 비교 뷰
- 최근 2회 분석 결과 diff 비교
- typed exception 기반 fail-soft 분류 강화
- 대용량 heuristic 스캔 최적화 1차

## 현재 기준 남은 리스크

### 운영 리스크

- 규칙 활성/비활성 상태를 UI에서 직관적으로 보기 어렵다
- Python / `openpyxl` / Playwright / Ctrlpp 상태를 처음 셋업하는 사용자를 위한 부트스트랩 가이드가 부족하다

### 성능 리스크

- 현재 HTTP baseline은 heuristic 개선과 report/Excel 비용을 완전히 분리하지 못한다
- 더 큰 체감 개선을 위해서는 heuristic 단계와 report 단계를 분리한 baseline 체계가 필요하다

### 확장성 리스크

- 규칙 관리 UI가 없어 운영자가 웹에서 규칙을 직접 조정할 수 없다
- 분석 diff는 최근 2회 자동 비교만 지원한다

## 권장 후속 액션

1. heuristic 전용 baseline 문서와 비교 스크립트 정리
2. 운영 UI에 규칙 상태 / optional dependency 상태 패널 추가
3. 규칙 관리 UI와 선택형 diff 비교 기능 설계

## 결론

초기 갭 문서에서 지적한 구조 분리, fail-soft, 운영 smoke, benchmark 기반 검증은 현재 대부분 반영됐다. 남은 영역은 신규 기능 부족보다 운영 편의성과 성능 관찰성 정교화다.
