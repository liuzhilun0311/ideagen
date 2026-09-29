@echo off
cd /d "%~dp0"

echo ============================================
echo   Frontend Build Script
echo ============================================

:: Install dependencies if node_modules missing
if not exist "node_modules" (
    echo [INFO] node_modules not found, installing dependencies...
    call pnpm install --frozen-lockfile
    if errorlevel 1 (
        echo [ERROR] pnpm install failed. Install pnpm 10.19.0 first.
        pause
        exit /b 1
    )
)

echo [INFO] Building frontend...
call pnpm build
set EXIT_CODE=%errorlevel%

echo.
echo ============================================
if %EXIT_CODE% equ 0 (
    echo [DONE] Build OK! Press Ctrl+F5 in browser to refresh.
) else (
    echo [FAILED] Build failed. See errors above.
)
echo ============================================
pause
