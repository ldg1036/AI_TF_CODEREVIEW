@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title WinCC OA Code Reviewer - 최초 설치 (Setup)
cd /d "%~dp0"

echo ============================================================
echo   WinCC OA Code Reviewer - 최초 설치를 시작합니다.
echo   이 창을 닫지 마시고 "설치가 완료되었습니다" 메시지가
echo   나올 때까지 기다려 주세요. (보통 2~5분 소요)
echo ============================================================
echo.

REM --- 1. Python 설치 여부 확인 -------------------------------
echo [1/5] Python 설치 여부를 확인합니다...
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [오류] Python이 설치되어 있지 않거나, 설치 시 PATH 등록을
    echo        하지 않으셨습니다.
    echo.
    echo   해결 방법:
    echo   1^) 아래 주소에서 Python 3.12 를 내려받아 설치하세요.
    echo      https://www.python.org/downloads/windows/
    echo   2^) 설치 화면 맨 아래의
    echo      "Add python.exe to PATH" 체크박스를 반드시 선택하세요.
    echo   3^) 설치가 끝나면 이 setup.bat 파일을 다시 더블클릭하세요.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo       Python %PYVER% 확인 완료.
echo.

REM --- 2. 가상환경(.venv) 생성 ---------------------------------
echo [2/5] 독립 실행 환경(.venv)을 준비합니다...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [오류] 가상환경 생성에 실패했습니다. 위 오류 메시지를
        echo        캡처하여 담당자에게 문의해 주세요.
        pause
        exit /b 1
    )
) else (
    echo       기존 .venv 를 재사용합니다.
)
echo.

REM --- 3. 패키지 설치 -------------------------------------------
echo [3/5] 필요한 패키지를 설치합니다. 인터넷 상황에 따라
echo       몇 분 정도 걸릴 수 있습니다...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul 2>nul

if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    pip install -e ".[dev]"
)
if errorlevel 1 (
    echo.
    echo [오류] 패키지 설치 중 문제가 발생했습니다.
    echo   - 사내망이라면 방화벽/프록시 설정을 확인해 주세요.
    echo   - 잠시 후 setup.bat 을 다시 실행해 보세요.
    pause
    exit /b 1
)

REM app 패키지를 어디서든 인식하도록 편집 가능 모드로 등록
pip install -e . --no-deps >nul 2>nul
echo       패키지 설치 완료.
echo.

REM --- 4. 기본 설정 파일 준비 ------------------------------------
echo [4/5] 기본 설정 파일을 준비합니다...
if not exist "config\settings.yaml" (
    if exist "config\settings.yaml.example" (
        copy /y "config\settings.yaml.example" "config\settings.yaml" >nul
        echo       config\settings.yaml 파일을 생성했습니다.
        echo       (사내 AI 서버 연동이 필요 없다면 그대로 두셔도 됩니다.)
    )
) else (
    echo       config\settings.yaml 이 이미 존재합니다. 건드리지 않습니다.
)
echo.

REM --- 5. 완료 안내 ------------------------------------------------
echo [5/5] 설치가 완료되었습니다!
echo.
echo ============================================================
echo   이제 다음 파일을 더블클릭하면 프로그램을 실행할 수 있습니다.
echo.
echo   - run_gui.bat    : 화면(창)이 있는 프로그램으로 실행
echo   - run_check.bat  : 검사할 폴더를 끌어다 놓아 바로 검사
echo ============================================================
echo.
pause
