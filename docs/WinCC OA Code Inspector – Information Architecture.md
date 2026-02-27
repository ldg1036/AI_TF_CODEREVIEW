# WinCC OA Code Inspector 정보 구조(IA) 문서 (v3.0)

마지막 업데이트: 2026-02-27 (현재 구현 기준)

이 문서는 사용자가 프로그램을 사용할 때 보는 화면/정보 흐름과, 백엔드 API 및 데이터 구조의 연결 방식을 정리한다.

## 1. 사용자 관점 정보 구조

### 1.1 주요 화면 영역
- 파일 목록 패널: 분석 대상 선택
- 워크스페이스(결과 테이블): P1/P2/P3 위반 목록
- 코드 뷰어: 파일 내용 + 라인 하이라이트
- AI 리뷰 카드: 리뷰 텍스트 + 적용 액션
- Diff 패널: source autofix unified diff 표시
- Excel 지연생성 상태 패널(옵션)

### 1.2 주요 사용자 흐름
1. 파일 조회 및 선택
2. 분석 실행
3. 결과 필터링/탐색
4. 코드 라인 점프 확인
5. AI 리뷰 확인
6. `REVIEWED` 반영 또는 source autofix(diff 승인형) 적용

## 2. 백엔드 정보 흐름

### 2.1 파일/분석 흐름
- `GET /api/files`
  - 분석 가능한 파일 목록 제공
- `POST /api/analyze`
  - 동기 분석 실행
  - 응답: `summary`, `violations`, `output_dir`, `metrics`, `report_jobs`
- `POST /api/analyze/start` + `GET /api/analyze/status`
  - 프론트 기본 비동기 분석/진행률 조회 경로
- `GET /api/file-content`
  - 코드뷰어 표시용 파일 내용 조회 (`prefer_source` 지원)

### 2.2 AI 리뷰/자동수정 흐름
- `POST /api/ai-review/apply`
  - `*_REVIEWED.txt`에 AI 리뷰 반영
- `POST /api/autofix/prepare`
  - source patch proposal 생성
  - 응답에 `generator_type`, `generator_reason`, `quality_preview` 포함
- `GET /api/autofix/file-diff`
  - 최신 proposal unified diff 조회
- `POST /api/autofix/apply`
  - 승인된 source patch 적용
  - `quality_metrics`, `validation`, `reanalysis_summary` 반환
- `GET /api/autofix/stats`
  - 세션 기준 proposal/apply 통계 조회

## 3. 결과 데이터 구조(개념)

### 3.1 분석 응답
- `summary`
  - 총 위반 수, 심각도 집계, 점수, 파일 수 요약
- `violations`
  - `P1`: 내부 정적 규칙 그룹
  - `P2`: CtrlppCheck 결과
  - `P3`: AI 리뷰 항목
- `metrics`
  - 단계별 timing, 호출 수, cache hit/miss 등
- `report_jobs`
  - deferred Excel 상태 요약

### 3.2 자동수정 Proposal
- `proposal_id`, `file`, `base_hash`
- `unified_diff`, `hunks`
- `generator_type` (`llm` / `rule`)
- `generator_reason`
- `quality_preview`
- `status` (`Prepared`, `Applied`, `Rejected`)

### 3.3 자동수정 Apply 결과
- `validation`
  - hash/anchor/syntax/regression 결과
- `quality_metrics`
  - generator, 회귀 수, 실패 사유 등
- `backup_path`, `audit_log_path`
- `viewer_content`

## 4. 세션/저장 구조

- 분석 세션은 output dir 기준으로 식별
- 세션 캐시에 다음이 연결됨:
  - 파일별 분석 결과 캐시
  - AI 리뷰 상태
  - autofix proposal 목록
  - report job 상태

세션은 TTL/LRU 정책으로 정리된다.

## 5. 성능 관련 IA 고려사항

- 결과 테이블/코드뷰는 virtualization로 렌더링 비용 절감
- 대량 데이터에서도 사용자는 일부 visible row/line만 보게 설계
- 성능 기준선은 UI 벤치(Playwright)와 서버 metrics baseline으로 이중 관리

## 6. 운영 문서 연결

- 성능/임계치: `docs/performance.md`
- 자동수정 안전성: `docs/autofix_safety.md`
- 인코딩 정책: `docs/encoding_policy.md`

