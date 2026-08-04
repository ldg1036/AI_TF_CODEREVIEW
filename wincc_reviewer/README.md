# WinCC OA Code Reviewer (코드 리뷰 자동화 도구)

WinCC OA (SCADA) 프로젝트의 `.ctl`, `.pnl`, `.xml` 소스 코드에 대해 엑셀 기반 표준 리뷰 가이드라인을 정적 분석하고 리포트를 생성하는 자동화 도구입니다.

---

## 🚀 주요 기능

1. **엑셀 기반 정적 룰 컴파일 및 검사**:
   - `Client` (15개 항목) 및 `Server` (20개 항목) 표준 리뷰 양식 엑셀 파일 전수 자동 파싱 및 라우팅
2. **다국어 인코딩 및 안전 파싱**:
   - UTF-8 및 CP949(EUC-KR) 다국어 인코딩 자동 감지 및 파싱 실패 시 `parse_failed` 독립 수집
3. **📊 파일별 요약 리포트 (File Summary) 탭**:
   - 각 스캔 대상 파일별 미흡/검토 건수, 심각도(Critical/High 등) 분포, 미흡 지적 룰 ID 및 핵심 원인 요약 표(Table)로 한눈에 보는 직관적인 대시보드 리포트 제공
4. **📥 단일 통합 Export 드롭다운**:
   - **`📥 Export 리포트 ▼`** 단일 드롭다운 버튼을 통해 `📄 HTML 보고서 (*.html)`, `🔍 JSON 데이터 (*.json)`, `📊 CSV 엑셀 포맷 (*.csv, utf-8-sig)`을 자유롭게 선택 파일 내보내기 지원
5. **사내 폐쇄망 지원**:
   - 외부 CDN 호출 0개의 단일 HTML 리포트 생성 및 데스크톱 GUI 애플리케이션 지원 (`pywebview`)

---

## 🛠️ 실행 방법

### CLI 모드
```bash
# 기본 정적 리뷰 실행 (JSON/HTML 자동 내보내기)
python -m app.main --input <검사대상경로> --no-ai
```

### GUI 모드 (데스크톱 앱)
```bash
python -m app.ui.app
```

---

## 🧪 테스트 실행
```bash
pytest tests/ -v
```
