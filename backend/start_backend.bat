@echo off
title HRReport Backend Server (Port 8073)
cd /d "%~dp0"
echo ========================================================
echo Starting HRReport Backend on 0.0.0.0:8073
echo Target IP: 182.66.233.66:8073 / Local: 127.0.0.1:8073
echo ========================================================
.\venv\Scripts\python.exe run_server.py
pause
