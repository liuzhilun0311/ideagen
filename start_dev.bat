@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo  IdeaGen (Django) - Local Dev Launcher
echo ========================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Please install Python 3.11 first.
        pause
        exit /b 1
    )
)

echo [2/4] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/4] Migrating database and init admin...
".venv\Scripts\python.exe" backend\manage.py migrate
".venv\Scripts\python.exe" backend\manage.py initadmin

echo [4/4] Starting server at http://127.0.0.1:12398
rem Open browser automatically after 3s (use 127.0.0.1, NOT localhost, to avoid IPv6 ::1 timeout)
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:12398"
".venv\Scripts\python.exe" backend\manage.py runserver 0.0.0.0:12398
pause
