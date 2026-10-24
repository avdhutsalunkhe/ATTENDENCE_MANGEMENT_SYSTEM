@echo off
title Report - Frontend Server (Vite)
echo Starting Report Frontend on http://0.0.0.0:5173 ...
cd /d "%~dp0frontend"
npm run dev -- --host 0.0.0.0
pause
