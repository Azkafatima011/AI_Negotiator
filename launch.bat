@echo off
title AI Negotiator Server
echo ============================================
echo   AI Negotiator - Starting Server...
echo ============================================
echo.

cd /d "%~dp0backend"

REM --- Check that Python is available ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.10+ from python.org and tick "Add Python to PATH",
    echo         then run this file again.
    echo.
    pause
    exit /b 1
)

REM --- If the server is already running, just open the browser ---
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo Server is already running - opening http://localhost:8000 ...
    start "" http://localhost:8000
    timeout /t 3 /nobreak >nul
    exit /b 0
)

echo [1/3] Installing dependencies - first run can take a few minutes...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Installing dependencies failed - check your internet connection.
    echo.
    pause
    exit /b 1
)

echo [2/3] Preparing database...
python -c "import sqlite3; conn=sqlite3.connect('negotiation.db'); conn.execute('ALTER TABLE negotiations ADD COLUMN seller_approval_token VARCHAR(64)'); conn.commit()" 2>nul
echo      Done.

echo [3/3] Starting server on http://localhost:8000
echo.
echo ============================================
echo   Your browser will open automatically
echo   Keep this window OPEN while using the app
echo   Press Ctrl+C to stop the server
echo ============================================
echo.

REM Open the browser a few seconds after the server boots
start "" /min cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:8000"

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo Server stopped.
pause
