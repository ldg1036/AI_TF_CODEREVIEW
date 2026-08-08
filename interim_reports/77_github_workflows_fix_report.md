# GitHub Actions 워크플로우 정상 동작 및 수정 보고서

작성일자: 2026년 8월 8일  
작성목적: .github/workflows 내 test.yml 및 release.yml 파이프라인 정상화 및 갱신 내역 기록

## 1. 개요

GitHub Pull Request 및 태그 릴리스 시 자동화 워크플로우가 오류 없이 구동되도록 .github/workflows 디렉터리 내 파이프라인 파일 2종을 정밀 수정하였습니다.

## 2. 주요 조치 및 갱신 내역

* test.yml (자동 테스트 및 커버리지 파이프라인)
  * 인라인 JSON 배열 서법(쉼표 오타 포함)을 표준 YAML 서법으로 전환하여 파싱 오류 방지
  * setup-python 파라미터 키를 python-version: "3.12"로 정정
  * 의존성 설치 시 pip install -e ".[dev]" 명령을 포함하여 파이프라인 및 룰 엔진 필요 패키지(openpyxl, pyyaml, httpx 등) 미설치로 인한 ModuleNotFoundError 차단
  * python -m pytest wincc_reviewer/tests/ 실행 및 coverage.xml 아티팩트 자동 업로드 추가
* release.yml (포터블 릴리스 빌드 파이프라인)
  * 태그(v*) 생성 시 자동 구동되도록 트리가 형성됨
  * pyinstaller wincc_reviewer/wincc_reviewer.spec --noconfirm 명령으로 검증된 포터블 번들 빌드
  * Compress-Archive를 통해 WinCC_OA_Code_Reviewer.zip 파일로 자동 압축
  * 최신 softprops/action-gh-release@v2 액션을 적용하여 릴리스 아티팩트 자동 업로드 연결

## 3. 결론

본 수정을 통해 Pull Request 생성 시 자동 테스트 및 태그 푸시 시 포터블 ZIP 번들 릴리스가 GitHub Actions 러너에서 에러 없이 완벽히 구동됩니다.
