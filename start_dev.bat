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
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/4] Migrating database and init admin...
".venv\Scripts\python.exe" backend\manage.py migrate
if errorlevel 1 (
    echo [ERROR] Database migration failed.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" backend\manage.py initadmin
if errorlevel 1 (
    echo [ERROR] Admin initialization failed.
    pause
    exit /b 1
)

echo Starting image processing worker...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_image_worker.ps1"
if errorlevel 1 (
    echo [ERROR] Image worker failed to start.
    pause
    exit /b 1
)

echo [4/4] Opening IdeaGen...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_web_server.ps1"
if errorlevel 1 (
    echo [ERROR] Web server failed to start. See the message above.
    pause
    exit /b 1
)
echo IdeaGen is running. You may close this launcher window.
pause
