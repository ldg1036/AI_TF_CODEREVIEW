# ADR-001: 실제 Client/Server Excel 양식 계약

## 상태

Accepted — 2026-08-02 실제 파일 분석 기준

## 결정 배경

현재 사용 중인 두 Excel 파일은 사람이 작성하는 체크리스트 결과서이며, 기존 문서의 `Checklist` 시트·2행 시작 가정과 다르다. 따라서 v2.0 양식은 레거시 입력으로 정확히 보존하고, 자동 checker 연결은 별도 확장 계약으로 분리한다.

## 분석 대상

| 구분 | 파일 | 시트명 | 파일 크기 |
|---|---|---|---:|
| Client | `(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx` | `(클라이언트) 코드 리뷰 결과서` | 97,665 bytes |
| Server | `(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx` | `(서버) 코드 리뷰 결과서` | 98,921 bytes |

## v2.0 확정 구조

### 공통 위치

- 헤더 행: 17행
- 데이터 시작 행: 18행
- 기본 데이터 열: B:H
- 숨김 열: 없음
- 고정 창: 없음
- 상단 문서 메타데이터: 4~9행
- 상단 요약 영역: 11~15행
- 병합셀: 대분류·중분류 값의 논리적 상속에 사용

| 열 | 실제 헤더 | 내부 필드 | 처리 기준 |
|---|---|---|---|
| B | 대분류 | `category` | 병합셀 값은 하위 행에 상속 |
| C | 중분류 | `subcategory` | 병합셀 값은 하위 행에 상속 |
| D | 소분류 | `check_item` | 체크리스트 식별의 핵심 값 |
| E | 검증 조건 | `condition` | 상세 검증 문장·체크포인트 원문 |
| F | 1차 검증 | `first_review_status` | 기존 양식의 초기 검토값, 요약 수식 기준 |
| G | 검증 결과 | `review_result` | 실제 검토 결과 입력 영역 |
| H | 비고 | `remark` | 예외·적용 조건·참고사항 |

### 파일별 데이터 범위

| 파일 | 논리 체크리스트 행 | 항목 수 | 제외 행 |
|---|---:|---:|---|
| Client | 18~32행 | 15개 | 33행 빈 행, 34행 안내 문구, 35행 이후 서식 영역 |
| Server | 18~37행 | 20개 | 38행 빈 행, 39행 안내 문구, 40행 이후 서식 영역 |

상단 요약 수식은 F열의 `N/A`, `OK`, `NG`, `SKIP` 값을 집계한다. 따라서 컴파일러는 상단 요약 수식과 17행 이전의 문서 메타데이터를 룰 행으로 읽지 않는다.

## v2.0 컴파일 정책

1. 현재 v2.0 파일에는 `rule_id`, `checker_type`, `checker_key`, `pattern`, `severity` 기술 메타데이터가 없다.
2. 컴파일러는 v2.0 행에서 `category/subcategory/check_item/condition`을 보존하고, `source_key`를 생성한다.
3. `source_key`가 승인된 `legacy_mapping_profile`에 등록된 경우에만 내장 checker 또는 정규식 checker를 연결한다.
4. 매핑되지 않은 행은 자동 PASS가 아닌 `MANUAL_REVIEW`로 컴파일한다.
5. F열의 `N/A`는 현재 양식의 초기 검토값이며, 정적 분석 결과의 PASS를 의미하지 않는다.
6. 병합셀·빈 행·안내 문구·수식·서식 영역은 룰 정의에서 제외한다.

## v2.1 기술 메타데이터 확장안

기존 B:H 시각적 양식을 유지하고, I열 이후에 기술 메타데이터를 추가한다. 실제 도입 전 복사본으로 마이그레이션 테스트를 수행한다.

| 열 | 필드 | 필수 조건 |
|---|---|---|
| I | `rule_id` | 자동 checker 행 필수, 중복 금지 |
| J | `enabled` | TRUE/FALSE, 기본 TRUE |
| K | `file_types` | CTL/PNL/XML 중 하나 이상 |
| L | `checker_type` | builtin/regex/manual |
| M | `checker_key` | builtin일 때 registry 필수 |
| N | `pattern` | regex일 때 필수 |
| O | `severity` | 자동 checker 행 권장 |
| P | `automation_mode` | auto_full/auto_violation_only/manual |
| Q | `required_rule_ids` | 복수 실행 룰은 쉼표 구분 |

v2.1을 도입해도 사용자는 Excel만 편집한다. 내부 JSON/YAML은 컴파일 캐시이며 직접 편집하지 않는다.

## 결과 및 재검토 조건

- 원본 파일 SHA256과 분석일을 컴파일 메타데이터에 저장한다.
- 양식 버전, 시트명, 헤더 행, 데이터 범위가 바뀌면 이 ADR을 갱신한다.
- Client 항목 수가 15개, Server 항목 수가 20개와 달라지면 커버리지 게이트 기준을 재검토한다.
- 실제 WinCC OA 샘플에서 `source_key` 충돌 또는 매핑 오탐이 발견되면 legacy mapping profile을 수정하고 회귀 fixture를 추가한다.
