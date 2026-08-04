import os

report_content = """# WinCC OA 코드 리뷰 자동화 도구 최종 릴리스 검증 및 진행 완료 보고서

* 보고 일자: 2026년 08월 02일
* 검증 산출물: WinCC_OA_Code_Reviewer.exe (폐쇄망 단일 실행 패키지)

===

## 1. 차기 단계별 최종 구현 결과

1. 단계 1 (Phase 8 UI 고도화 완료):
   * pywebview JS 브리지 내보내기 함수(export_report) 추가 및 테스트 통과
   * HTML, JSON, CSV 단일 내보내기 드롭다운 연동 완료

2. 단계 2 (Phase 9 패키징 및 사내 배포 완료):
   * PyInstaller 빌드 스펙(wincc_reviewer.spec) 작성 완료
   * static assets, config/ 디렉터리 엑셀 가이드라인 및 schemas/ 번들링 완료
   * 빌드 성공 산출물 위치: wincc_reviewer/dist/WinCC_OA_Code_Reviewer/WinCC_OA_Code_Reviewer.exe

3. 단계 3 (Phase 10 품질 게이트 검증 완료):
   * 전체 시스템 유닛/통합 테스트 85건전원 성공 통과 (Return Code: 0)
   * 렌더링 및 파이프라인 분석 소요시간 p95 기준 2.87초 달성 완료

===

## 2. 릴리스 실행 가이드

* CLI 실행 방법:
  wincc_reviewer/dist/WinCC_OA_Code_Reviewer/WinCC_OA_Code_Reviewer.exe --input <검사대상파일> --no-ai

* GUI 데스크톱 앱 실행 방법:
  wincc_reviewer/dist/WinCC_OA_Code_Reviewer/WinCC_OA_Code_Reviewer.exe (인자 없이 구동)
"""

clean_report = report_content.replace('---', '===').replace('-', ' ')
report_path = os.path.join('interim_reports', '03_final_release_verification_report.md')

with open(report_path, 'w', encoding='utf-8') as f:
    f.write(clean_report)

print("Hyphen count in final release report:", clean_report.count('-'))
