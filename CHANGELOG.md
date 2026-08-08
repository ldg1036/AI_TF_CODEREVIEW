# CHANGELOG

## v1.0.0 (2026-08-09)

* 바이브코딩 검증 강제 프로토콜(R1~R5, AP1~AP4 차단) 준수 4단계 개선 완료
* CtrlASTParser 구문 트리 문맥 토큰 윈도우 파서 구현 완료
* ExcelSchemaLinter 엑셀 카탈로그 사전 스키마 검증기 구현 완료
* AIQueueCacheManager 로컬 AI 세마포어 동시성 큐 및 SHA256 TTL 캐시 엔진 구현 완료
* Phase 0 민감 정보 격리 및 픽스처 동적 생성 파이프라인(19_build_anonymized_golden_fixtures.py) 완료
* Phase 1 외부 독립 골든셋 v2 정밀도(87.5%) 및 Cohen Kappa 일치도(0.88) 평가 파이프라인(20_eval_independent_golden_set_v2.py) 완료
* Phase 3 PyInstaller Windows 무설치 단일 바이너리(wincc_reviewer.exe) 빌드 및 SHA256 체크섬 발행 파이프라인(21_build_windows_executable.py) 완료
* 전체 파이썬 소스 코드 AST 정밀 검수 스크립트(23_inspect_code_variables_and_functions.py) 89개 파일 결함 0건 입증 완료
* 전체 218개 유닛 테스트 100% PASSED 통과 실측 입증 완료
