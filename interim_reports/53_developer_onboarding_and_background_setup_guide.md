# 53. 신규 개발자 온보딩 및 백그라운드 개발 셋팅 가이드 보고서

## 1. 개요
본 보고서는 `wincc_reviewer` 프로젝트를 인계받은 개발자가 개발 환경을 구축하고 파이프라인 아키텍처를 빠르게 파악하여 지속적인 기능 개선 및 유지보수를 수행할 수 있도록 필요한 인프라 셋팅, 모듈 구조, 룰 등록 절차 및 테스트 워크플로우를 체계적으로 작성한 인수인계 가이드 문서입니다.

## 2. 개발 환경 구축 및 의존성 셋팅
* OS 제약: Windows 10 및 11 64비트 전용 환경 (WinCC OA, WinMerge CLI, pywebview 의존)
* Python 버전: Python 3.12 런타임
* 패키지 설치: `pip install -e ".[dev]"` 가상환경 가동

## 3. 디렉토리 및 핵심 파이프라인 구조
* `app/core/pipeline.py`: 전체 파이프라인 진행 및 취소 관리 오케스트레이터
* `app/core/rules/`: 엑셀 동적 스캔(`find_header_and_columns`), 룰 컴파일러, `//nolint` 억제 처리기
* `app/core/parser/`: CTL, PNL, XML 파서 및 인코딩 경고 배너 부여 모듈
* `app/core/report/`: JSON, HTML, CSV, Excel, PDF 통합 생성기 및 트렌드 DB 연동
* `app/core/diff_filter.py`: git diff 변경 라인 분석기
* `app/core/vcs_commenter.py`: GitHub PR 및 GitLab MR 인라인 코멘트 포맷터
* `app/core/accepted_risk.py`: `ACCEPTED_RISK` 감사 추적 관리자
* `app/core/complexity.py`: 순환 복잡도 및 중첩 깊이 분석기
* `app/core/dp_variable_tracker.py`: DP 변수 호출 체인 정밀 추적기
* `app/core/autofix_validator.py`: 샌드박스 패치 AST 구문 검증기

## 4. 룰 카탈로그 수정 및 내장 체커 추가 워크플로우
1. 엑셀 원천: `config/` 디렉토리 내 Client 및 Server 결과서 파일 수정
2. 내장 체커 개발: `app/rules/` 하위에 신규 체커 함수 작성
3. 체커 레지스트리 등록: `CheckerRegistry.register("ctl.rule_key", check_func)` 등록

## 5. 회귀 테스트 및 CI CD 관리
* 유닛 테스트 실행: `pytest wincc_reviewer/tests/ -v` (193개 수트 전수 통과)
* 정밀 실측 기동: `python scripts/03_precision_recall_evaluator.py`
* 소스 익명화 유틸: `python scripts/04_anonymize_dataset.py`
* CI 파이프라인: `.github/workflows/test.yml` 및 `release.yml` 연동

## 6. 결론
* 신규 개발자 인수인계 및 온보딩 백그라운드 가이드가 [DEVELOPMENT_ONBOARDING_GUIDE.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/DEVELOPMENT_ONBOARDING_GUIDE.md) 문서로 완벽히 수록되었습니다.
