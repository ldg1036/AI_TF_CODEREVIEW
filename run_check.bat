@echo off
chcp 65001 >nul
setlocal
title WinCC OA Code Reviewer - 코드 검사
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [안내] 아직 설치가 진행되지 않았습니다.
    echo        먼저 setup.bat 파일을 더블클릭하여 설치를 완료해 주세요.
    echo.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

if "%~1"=="" (
    echo ============================================================
    echo   검사할 폴더 또는 파일을 이 아이콘 위로 끌어다 놓아주세요.
    echo   ^(마우스로 폴더를 잡아서 run_check.bat 위에 놓으면 됩니다^)
    echo.
    echo   지금 이대로 아무 키나 누르면, 예제 샘플 코드로
    echo   테스트 검사를 실행합니다.
    echo ============================================================
    pause
    set "TARGET=primary_data"
) else (
    set "TARGET=%~1"
)

echo.
echo "%TARGET%" 경로를 검사합니다. 잠시만 기다려 주세요...
echo.

python wincc_reviewer\app\main.py --input "%TARGET%" --output output --no-ai

echo.
echo ============================================================
echo   검사가 끝났습니다.
echo   이 폴더 안의 "output" 폴더를 열어, 가장 최근에 생성된
echo   ".html" 파일을 더블클릭하면 결과 보고서를 볼 수 있습니다.
echo ============================================================
echo.
pause
