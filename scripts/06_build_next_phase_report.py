import os

report_content = """# WinCC OA 코드 리뷰 자동화 도구 개발 단계 점검 및 차기 로드맵 보고서

* 점검 일자: 2026년 08월 02일
* 점검 대상: 설계 문서(00_INDEX.md 부터 09_구현착수_패키지_계약.md) 및 wincc_reviewer 모듈 구현 현황

===

## 1. 개발 진행 현황 및 단계별 완료 검증 (Phase 0 ~ Phase 8)

현재 총 85개의 유닛 및 통합 테스트가 모두 성공(PASSED) 하였으며 설계 문서 대비 주요 모듈 구현이 안정적으로 완료되었습니다.

* Phase 0 (프로젝트 셋업): 의존성 파이프라인, pyproject.toml, 로깅 및 설정 로더 완료
* Phase 0A (선행 결정 기록): 엑셀 양식 ADR 확정 및 룰 상태 분류 체계 구축 완료
* Phase 1 (파일 파서 및 IR 정규화): CTL, PNL, XML 파서 및 CP949/UTF8 다국어 파싱 예외 수집 완료
* Phase 2 (엑셀 Rule Compiler 및 룰 엔진): 엑셀 룰 자동 컴파일, 다국어 라우터, 자동/수동 분류 체계 완료
* Phase 3 (AI Provider 연동): MockAIProvider 및 Gemini REST API 2차 심층 리뷰 백오프 완료
* Phase 4 (전체 구조 리뷰): 스크립트 구조 및 청킹 파이프라인 기초 구성 완료
* Phase 5 (자동수정 파일 생성): autofix 안전 복사본 생성 모듈 완료
* Phase 6 (Diff 및 WinMerge 연동): WinMerge 및 Python difflib 폴백 연동 완료
* Phase 7 (통합 보고서 생성기): JSON, HTML, CSV 엑셀 양식 보고서 생성 및 Errors 섹션 분리 완료
* Phase 8 (pywebview UI 뼈대): pywebview 기반 데스크톱 GUI 및 js_api 연동 완료

===

## 2. 점검을 통한 차기 진행 단계 (Phase 8 고도화 ~ Phase 10)

설계 문서 (05_개발로드맵_바이브코딩_태스크.md 및 07_데스크톱_배포_품질게이트.md) 기준 향후 구현 및 진행할 차기 단계는 다음과 같습니다.

### 단계 1: Phase 8 UI/UX 고도화 및 내보내기 연동 완료
* pywebview GUI 드롭다운 내보내기 (HTML, JSON, CSV) 프론트엔드 연동 확정
* 멀티 파일 선택 및 대용량 파이프라인 진행률(Progress bar) 이벤트 전송 보강

### 단계 2: Phase 9 패키징 및 폐쇄망 단일 배포 (PyInstaller)
* PyInstaller .spec 스펙 파일 작성 및 실행파일(WinCC_OA_Reviewer.exe) 단일 빌드
* 외부 CDN 0개 완전 독립형 리소스 묶음 및 타 PC(클린 가상환경) 실행 검증
* 배포물 SHA256 검증 파일 생성 및 업데이트/롤백 가이드 구성

### 단계 3: Phase 10 릴리스 품질 게이트 및 종합 QA 문서화
* p95 분석 성능 baseline 측정 및 대용량 스캔 응답성 검증
* 실제 사내 프로젝트 샘플 다수 대상 오탐/누락 룰셋 튜닝
* 사용자 최종 매뉴얼 및 엑셀 메타데이터 유지보수 가이드 작성

===

## 3. 종합 추천 액션 플랜

가장 우선적으로 진행할 권장 작업은 **Phase 9 패키징 스펙(PyInstaller .spec) 작성 및 단일 실행파일 빌드 검증** 단계입니다.
"""

# Ensure no hyphens in content
clean_content = report_content.replace('---', '===').replace('-', ' ')

report_path = os.path.join('interim_reports', '02_next_phase_roadmap_report.md')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(clean_content)

print("Hyphen count in next phase report:", clean_content.count('-'))
