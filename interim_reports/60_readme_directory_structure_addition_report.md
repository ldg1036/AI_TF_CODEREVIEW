# 60. README.md 프로젝트 폴더 구조 추가 및 원격 저장소 푸시 보고서

## 1. 개요
본 보고서는 `wincc_reviewer` 저장소의 [README.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/README.md)에 신규 개발자 및 사용자가 전체 코드베이스 구성을 한눈에 파악할 수 있도록 프로젝트 디렉토리 및 폴더 구조 텍스트 아키텍처 섹션을 추가하고 원격 저장소에 완벽히 동기화 완료한 보고서입니다.

## 2. 추가된 폴더 구조 명세

```
📁 AI_TF_CODEREVIEW (Project Root)
├── 📁 wincc_reviewer/              # 코드 리뷰 자동화 도구 코어
│   ├── 📁 app/                     # 파이프라인, 파서, 정적 룰 엔진, AI, GUI
│   ├── 📁 tests/                   # 193개 유닛 테스트 수트 및 픽스처
│   └── pyproject.toml              # 프로젝트 패키지 셋팅 및 의존성 명세
├── 📁 config/                      # Client/Server 엑셀 룰 카탈로그 및 settings.yaml
├── 📁 scripts/                     # Precision/Recall 평가 및 데이터 익명화 스크립트
├── 📁 interim_reports/             # 60종의 단계별 개발 및 검증 보고서
├── 📁 intermediate_results/        # 장기 품질 트렌드 DB 및 평가 결과 데이터
├── 📁 .github/workflows/          # CI/CD 자동화 파이프라인 (test.yml, release.yml)
├── DEVELOPMENT_ONBOARDING_GUIDE.md # 신규 개발자 인수인계 가이드
├── USER_MANUAL.md                  # 사용자 및 운영 매뉴얼
└── README.md                       # 프로젝트 대표 안내서
```

## 3. GitHub 원격 저장소 푸시 결과
* 원격 저장소 URL: `https://github.com/ldg1036/AI_TF_CODEREVIEW.git`
* 브랜치: `main`
* 커밋 및 푸시 이력: `207058a..0919c5d main -> main` (100% 원격 동기화 완료)
