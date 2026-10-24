@echo off
setlocal enabledelayedexpansion
title Report - Enterprise System Setup & Installer
cd /d "%~dp0"

cls
echo ===============================================================================
echo                REPORT - ATTENDANCE INTELLIGENCE SYSTEM
echo                       Master Setup & Installer
echo ===============================================================================
echo.

:: 1. Check Python
echo [1/5] Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do set "PY_VER=%%v"
echo   - Found: %PY_VER%

:: 2. Check Node.js and NPM
echo.
echo [2/5] Checking Node.js & npm environment...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed or not in your system PATH.
    echo Please install Node.js (LTS) from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set "NODE_VER=%%v"
for /f "tokens=*" %%v in ('npm --version') do set "NPM_VER=%%v"
echo   - Found Node: %NODE_VER%
echo   - Found npm:  v%NPM_VER%

:: 3. Setup Python Backend Virtual Environment
echo.
echo [3/5] Configuring Python Backend...
if not exist "%~dp0backend\venv" (
    echo   - Creating virtual environment in backend\venv ...
    python -m venv "%~dp0backend\venv"
) else (
    echo   - Virtual environment backend\venv already exists.
)

echo   - Installing backend dependencies from requirements.txt...
"%~dp0backend\venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
"%~dp0backend\venv\Scripts\pip.exe" install -r "%~dp0backend\requirements.txt" --quiet

echo   - Initializing database and default shifts/admin...
"%~dp0backend\venv\Scripts\python.exe" -c "from app.core.init_shifts import init_all_shifts; from app.core.init_users import init_default_users; init_all_shifts(); init_default_users(); print('Database verified and initialized successfully.')"

:: 4. Setup Frontend & Build
echo.
echo [4/5] Configuring Frontend...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo   - Installing frontend node dependencies...
    call npm install
) else (
    echo   - node_modules found.
)

echo   - Compiling frontend production bundle (Vite)...
call npm run build
cd /d "%~dp0"

:: 5. Create Desktop Shortcut for Quick Launch
echo.
echo [5/5] Generating Desktop Launcher Shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Report Attendance.lnk')); $s.TargetPath = '%~dp0start-all.bat'; $s.WorkingDirectory = '%~dp0'; $ico = '%~dp0frontend\public\icon.ico'; if (Test-Path $ico) { $s.IconLocation = $ico }; $s.Save()" >nul 2>&1
echo   - Desktop shortcut 'Report Attendance' created/updated!

echo.
echo ===============================================================================
echo                     SETUP COMPLETED SUCCESSFULLY!
echo ===============================================================================
echo.
echo Available Launch Options:
echo   [1] Start System Now (Backend + Frontend/Desktop Window)
echo   [2] Build Windows Setup Installer (.exe installer)
echo   [3] Build Portable Desktop App (.exe)
echo   [0] Exit Setup
echo.

set /p CHOICE="Enter your selection (1/2/3/0) [Default: 1]: "
if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="1" (
    echo Starting Report system...
    start "" "%~dp0start-all.bat"
    exit /b 0
)

if "%CHOICE%"=="2" (
    echo Building Windows Setup Installer...
    cd /d "%~dp0frontend"
    call npm run build:setup
    echo.
    echo Installer built in: %~dp0frontend\dist_electron
    pause
    exit /b 0
)

if "%CHOICE%"=="3" (
    echo Building Portable Windows Executable...
    cd /d "%~dp0frontend"
    call npm run build:exe
    echo.
    echo Portable executable built in: %~dp0frontend\dist_electron
    pause
    exit /b 0
)

echo Exiting setup.
exit /b 0
