@echo off
title Report - Master Launcher
cd /d "%~dp0"
echo ========================================================
echo   Starting Report (Backend :8073 + Desktop App)
echo ========================================================
echo.

start "Report Backend" cmd /k "call start-backend.bat"
echo Waiting for backend server to initialize...
ping -n 4 127.0.0.1 >nul

set "EXE_PATH=%~dp0frontend\dist_electron\win-unpacked\Report.exe"
if not exist "%EXE_PATH%" set "EXE_PATH=%~dp0frontend\dist_electron\win-unpacked\HRReport.exe"
if exist "%EXE_PATH%" (
    echo Launching Report Desktop Window App (.exe)...
    start "" "%EXE_PATH%"
) else (
    echo Starting web frontend fallback...
    start "Report Frontend" cmd /k "call start-frontend.bat"
)

echo.
echo ========================================================
echo - Public Endpoint: http://182.66.233.66:8073
echo - Local Endpoint:  http://127.0.0.1:8073
echo - Swagger Docs:    http://127.0.0.1:8073/docs
echo ========================================================
echo.
