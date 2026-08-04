# 28차 중간 보고서: GitHub 원격 리포지토리 초기화 및 프로젝트 덮어쓰기 업로드 가이드

* 작성일자: 2026년 8월 5일
* 대상 원격지: `https://github.com/ldg1036/AI_TF_CODEREVIEW.git`
* 목적: 기존 깃허브 리포지토리를 완전 초기화하고 현재 검증 완료된 v2.0 프로젝트 소스 코드 및 문서 전체를 강제 푸시(Force Push)하여 업로드하는 절무 명세

***

## 1. 사전 확인 및 필요 조건

1. **원격 리포지토리 쓰기 권한**: 사용자 PC의 Git 환경에 `ldg1036` 계정의 Write 권한(Personal Access Token 또는 SSH Key, GitHub Desktop 인증)이 등록되어 있어야 합니다.
2. **기존 커밋 히스토리 삭제**: 강제 푸시(`--force` 옵션)를 수행하면 원격 리포지토리의 기존 히스토리가 제거되고 현재 프로젝트의 새 히스토리로 대체됩니다.

***

## 2. 터미널 명령을 통한 업로드 단계별 절차

현재 워크스페이스 디렉터리(`c:\Users\39145\Downloads\클로드prd`)에서 터미널을 열고 다음 명령을 순서대로 실행합니다.

### 1단계: Git 저장소 초기화 및 불필요 파일 제외 검토
```bash
git init
```
`.gitignore` 파일에 `cache`, `output`, `__pycache__` 등이 포함되어 대용량 임시 파일이 푸시되지 않도록 보장합니다.

### 2단계: 파일 스테이징 및 커밋 생성
```bash
git add .
git commit -m "Initial commit: WinCC OA Code Review Automation Tool v2.0 Complete System"
```

### 3단계: 기본 브랜치 설정 및 원격지 URL 연결
```bash
git branch -M main
git remote add origin https://github.com/ldg1036/AI_TF_CODEREVIEW.git
```
(이미 origin이 등록되어 있는 경우에는 `git remote set-url origin https://github.com/ldg1036/AI_TF_CODEREVIEW.git` 명령 수행)

### 4단계: 기존 원격 리포지토리 초기화 및 강제 푸시 (Force Push)
```bash
git push -u origin main --force
```

***

## 3. 업로드 검증 방법

푸시가 정상 완료되면 웹 브라우저에서 `https://github.com/ldg1036/AI_TF_CODEREVIEW` 페이지를 새로고침하여 다음 사항을 확인합니다:
* `00_INDEX.md`, `01_PRD.md` 등 프로젝트 문서 세트 렌더링 확인
* `wincc_reviewer/` 소스 코드 디렉터리 존재 확인
* `interim_reports/` 중간 보고서 28종 보존 확인
