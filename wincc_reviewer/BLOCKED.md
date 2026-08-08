# BLOCKED 및 전제조건 항목 관리 가이드

이 문서는 실무 적용 전 확정이 필요했던 항목들의 기본 정책 및 결정 사항을 기록합니다.

## 해결 및 표준화 완료 항목

| 항목 | 상태 | 결정 및 표준화 내용 | 담당 |
|---|---|---|---|
| WinMerge CLI 옵션 | Resolved | WinMergeU.exe CLI 옵션 (/e /x /u /or) 표준 확정 | 개발자 |
| 사내 코딩 컨벤션 | Resolved | 전역변수 접두사 g_ 사용, Deprecated 함수(dpGetAsynct 등) 정의 완료 | 개발자 |
| 운영 및 보안 정책 | Resolved | 외부 AI 전송 기본 차단(local/no ai 모드), 로그 보존 30일, UTF 8 및 EUC KR 호환 파서 확정 | 보안팀/개발자 |
| WinCC OA 실행 환경 | Resolved | WinCC OA v3.16 및 v3.18 기준, Initialize 및 ScopeLib 이벤트 파싱 지원 확정 | 개발자 |
| Excel 양식 구조 | Resolved | Client 33.3% 및 Server 30.0% 커버리지 계약 확정 | 개발자 |
| 실물 샘플 재검증 | Resolved | primary_data 실물 샘플 8종 및 골든셋 재검증 지표 측정 완료 | 개발자 |

## 세부 표준 가이드

* 개인정보 및 기밀정보 정책
  * SCADA 제어 로직 소스코드는 외부 클라우드 전송을 금지합니다.
  * 기본 AI 리뷰 모드는 local 또는 --no-ai 모드를 기본값으로 활성화합니다.
* 파일 인코딩 정책
  * WinCC OA 스크립트 파일은 UTF 8 인코딩을 기본으로 하며 EUC KR 호환 파싱을 자동 수행합니다.

