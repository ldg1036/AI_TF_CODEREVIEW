# 63. 사내 Open WebUI 및 타 IP 로컬 AI 서버 연동 가이드 보고서

## 1. 개요
본 보고서는 사내 네트워크 환경에서 Open WebUI 및 타 IP 기반의 로컬 AI 서버를 연동하여 코드 리뷰를 수행할 때 `wincc_reviewer` 애플리케이션의 환경 설정(`settings.yaml` 및 GUI 설정)에서 확인 및 수정해야 할 항목과 네트워크 연동 파라미터를 정리한 가이드입니다.

## 2. 사내 Open WebUI 연동 시 필수 확인 및 수정 필드 5가지

### 2.1 호스트 IP (Host)
* **기본값**: `127.0.0.1` (내 PC)
* **수정값**: 사내 네트워크의 Open WebUI 서버 IP 주소 (예: `10.100.20.15` 또는 `192.168.1.100`)
* **특이사항**: HTTPS 통신 환경인 경우 `https://10.100.20.15` 형식으로 입력 가능

### 2.2 포트 번호 (Port)
* **기본값**: `8000`
* **수정값**: Open WebUI 기본 서비스 포트인 `3000` (또는 사내 구축 환경에 따라 `8080`, `80`, `443`)으로 수정

### 2.3 API 엔드포인트 (Endpoint)
* **기본값**: `/v1/chat/completions`
* **Open WebUI 지원 경로**: OpenAI 호환 API인 `/v1/chat/completions` 또는 `/api/chat/completions`
* **Ollama 직결 경로**: `/api/chat`

### 2.4 인증 API 키 (API Key)
* **기본값**: (비어있음)
* **수정값**: 사내 Open WebUI 웹 화면의 `Settings > Account > API Keys` 메뉴에서 발급받은 API 키 입력
* **동작 원리**: 입력 시 HTTP 헤더에 `Authorization: Bearer <API_KEY>`가 자동으로 첨부됨

### 2.5 모델 ID (Model ID)
* **기본값**: `sane_local_llm`
* **수정값**: Open WebUI에 탑재되어 실행 중인 모델명 (예: `llama3:8b`, `qwen2.5:72b`, `mistral` 등)
* **편의 기능**: GUI 화면의 `🔄 모델 조회` 버튼을 누르면 서버에서 지원하는 모델 목록을 실시간으로 가져와 선택 가능

## 3. 사내 네트워크 환경 체크리스트
1. **방화벽 및 포트 통신**: 본인 PC에서 사내 Open WebUI IP 및 포트(`3000` 등)로 핑/통신이 가능한지 확인
2. **CORS 허용**: 사내 Open WebUI 설정에서 외부 API 클라이언트 요청 수신이 허용되어 있는지 확인
