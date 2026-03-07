@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0restart_winccoa_server.ps1"
