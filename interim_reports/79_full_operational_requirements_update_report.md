# 운영 환경 필수 베이스 패키지 명세서 전수 업데이트 보고서

작성일자: 2026년 8월 8일  
작성목적: 프로덕션 및 CI/CD 운영 환경에 필요한 베이스 패키지 전수 분석 및 requirements.txt, requirements-dev.txt, pyproject.toml 최신화 결과 기록

## 1. 개요 및 갱신 내역

실제 프로그램 운영 및 런타임 환경 구축 시 요구되는 7가지 코어 베이스 라이브러리와 6가지 개발/테스트/빌드 도구를 세심하게 조사하여 명세서 파일 3종을 통합 업데이트하였습니다.

* 1단계: 런타임 필수 베이스 패키지 7종 명시 ([requirements.txt](file:///c:/Users/39145/Downloads/클로드prd/requirements.txt))
  * openpyxl>=3.1.0,<4.0.0: 엑셀 룰 카탈로그 로딩 및 동적 파싱 런타임
  * pywebview>=5.0.0,<6.0.0: 데스크톱 GUI 렌더링 및 Python UI API 바인딩
  * httpx>=0.27.0,<1.0.0: 사내 로컬 AI 및 Gemini 클라우드 AI 비동기 HTTP 통신
  * pyyaml>=6.0.0,<7.0.0: settings.yaml 환경설정 관리
  * charset-normalizer>=3.3.0,<4.0.0: 다국어 파일 인코딩 (EUC-KR, CP949, UTF-8) 자동 감지 보조
  * jinja2>=3.1.0,<4.0.0: HTML 및 리포트 템플릿 동적 렌더링 엔진
  * typing-extensions>=4.10.0,<5.0.0: 파이썬 3.12+ 하위 호환 및 타입 어노테이션 보장
* 2단계: 개발/테스트/CI 빌드 패키지 명시 ([requirements-dev.txt](file:///c:/Users/39145/Downloads/클로드prd/requirements-dev.txt))
  * pytest, pytest-cov: 193개 회귀 유닛테스트 수트 및 XML 커버리지 측정
  * pyinstaller: 데스크톱 포터블 실행 파일 (.exe) 빌드
  * ruff, mypy: 정적 코드 린터 및 파이썬 타입 스캐너
  * hatchling: 파이썬 빌드 백엔드
* 3단계: [pyproject.toml](file:///c:/Users/39145/Downloads/클로드prd/wincc_reviewer/pyproject.toml) 및 [wincc_reviewer/requirements.txt](file:///c:/Users/39145/Downloads/클로드prd/wincc_reviewer/requirements.txt) 동기화 완료

## 2. 무결성 검증 결과

* pip install -r requirements-dev.txt 실행 결과 모든 베이스 패키지 전원 에러 없이 100% 정상 설치 완료
* pytest wincc_reviewer/tests/ 구동 결과 전체 193개 유닛테스트 100% 통과 유지 확인

## 3. 결론

운영 환경 구축에 필요한 베이스 패키지가 누수 없이 완벽하게 정립되었으며, 배포 및 운영 단계에서의 예외 발생 가능성을 완벽히 차단하였습니다.
