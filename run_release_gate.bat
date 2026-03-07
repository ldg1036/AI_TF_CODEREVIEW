@echo off
setlocal

set "MODE=%~1"
if "%MODE%"=="" set "MODE=default"

set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=python"
set "CMD_ARGS="

if /I "%MODE%"=="default" (
  set "CMD_ARGS="
) else if /I "%MODE%"=="live-ai" (
  set "CMD_ARGS=--with-live-ai --live-ai-with-context"
) else if /I "%MODE%"=="ci" (
  set "CMD_ARGS=--profile ci"
) else (
  echo Usage: %~nx0 [default^|live-ai^|ci]
  exit /b 2
)

pushd "%ROOT_DIR%"
echo [release-gate] mode=%MODE%
%PYTHON_EXE% tools\release_gate.py %CMD_ARGS%
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
  echo [release-gate] failed with exit code %EXIT_CODE%
) else (
  echo [release-gate] completed successfully
)

exit /b %EXIT_CODE%
