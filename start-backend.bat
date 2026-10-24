@echo off
title Report - Backend Server (Port 8073)
cd /d "%~dp0backend"
echo ========================================================
echo   Starting Report Attendance Engine Backend
echo   Target IP / Port: 182.66.233.66:8073
echo   Binding Interface: 0.0.0.0:8073
echo   Local Address: http://127.0.0.1:8073
echo   LAN Address:   http://192.168.1.93:8073
echo   Swagger Docs:  http://127.0.0.1:8073/docs
echo ========================================================
echo.

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe run_server.py
) else if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe run_server.py
) else (
    python run_server.py
)
pause
