@echo off
chcp 936 >nul 2>&1
title Doubao2api

echo ========================================
echo   Doubao2api
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check dependencies
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    python -m pip install -r requirements.txt -q
)

:: Check cookies
if not exist "cookies.txt" (
    echo [INFO] No cookies.txt found
    echo [INFO] Starting QR login...
    echo.
    python cookie_helper.py
    if errorlevel 1 (
        echo [ERROR] QR login failed
        pause
        exit /b 1
    )
)

:: Start server
echo.
echo ========================================
echo   Server starting at http://localhost:9876
echo   Press Ctrl+C to stop
echo ========================================
echo.
python main.py
pause
