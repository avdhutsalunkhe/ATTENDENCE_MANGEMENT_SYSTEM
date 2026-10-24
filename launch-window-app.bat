@echo off
title Report - Windows Application Launcher
cd /d "%~dp0"

set "EXE_PATH=%~dp0frontend\dist_electron\win-unpacked\Report.exe"
if not exist "%EXE_PATH%" set "EXE_PATH=%~dp0frontend\dist_electron\win-unpacked\HRReport.exe"

if exist "%EXE_PATH%" (
    echo Starting Report Windows Desktop App...
    start "" "%EXE_PATH%"
) else (
    echo [ERROR] Application executable not found at %EXE_PATH%
    echo Please run 'npm run electron:pack' inside frontend folder first.
    pause
)
