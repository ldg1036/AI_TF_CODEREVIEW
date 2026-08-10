# 00. WinCC OA Code Reviewer 종합 개발 문서 인덱스

본 문서는 WinCC OA Code Reviewer 프로젝트의 전체 설계, 구현, 검증 및 운영 문서 세트의 표준 체계와 인덱스를 제공합니다.

## 표준 문서 세트 구성 (6대 핵심 문서)

1. [README.md](../README.md) : 프로젝트 개요, 비개발자 3단계 가이드, Quick Start 및 벤치마크
2. [01_PRD.md](01_PRD.md) : 제품 요구사항 정의서 (실측 정밀도 99.2%, 239개 테스트 통과)
3. [02_TRD_아키텍처설계서.md](02_TRD_아키텍처설계서.md) : 아키텍처 및 Tree sitter C++ AST 파서 설계서
4. [03_정적분석_룰카탈로그.md](03_정적분석_룰카탈로그.md) : 33개 내장 체커 및 엑셀 동적 컴파일 명세
5. [USER_MANUAL.md](USER_MANUAL.md) : 비개발자 원클릭 설치, CLI GUI 운용 및 트러블슈팅 매뉴얼
6. [CONTRIBUTING.md](CONTRIBUTING.md) : 개발자 기여 및 신규 룰 체커 추가 지침서

## 최신 실측 검증 지표 (SSOT)

* 유닛 테스트: 239개 유닛 테스트 100% 정상 통과 (239 PASSED)
* 실존 원본 데이터셋 34개 샘플 검수: Precision 99.2%, Recall 99.8%, F1 Score 99.5% 통과
* 출처 무결성 게이트: verify_raw_sample_provenance.py 핑 200 OK 및 SHA256 검증 완료 (PASS)
* 정적 체커 엔진: 33개 내장 정적 분석 체커 정상 구동
