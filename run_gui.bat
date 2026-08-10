@echo off
chcp 65001 >nul
setlocal
title WinCC OA Code Reviewer
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [안내] 아직 설치가 진행되지 않았습니다.
    echo        먼저 setup.bat 파일을 더블클릭하여 설치를 완료해 주세요.
    echo.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo 프로그램을 실행합니다. 잠시 후 창이 열립니다...
echo (창이 뜨지 않고 이 화면만 계속 떠 있다면, 백신 프로그램이
echo  차단했는지 확인해 주세요.)
echo.

python wincc_reviewer\app\main.py --gui

if errorlevel 1 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다.
    echo        위에 표시된 오류 메시지 전체를 캡처하여
    echo        담당 개발자에게 전달해 주세요.
    echo.
    pause
)
