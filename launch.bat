@echo off
title AI Negotiator Server
echo ============================================
echo   AI Negotiator - Starting Server...
echo ============================================
echo.

cd /d "%~dp0backend"

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet 2>nul

echo [2/3] Preparing database...
python -c "import sqlite3; conn=sqlite3.connect('negotiation.db'); conn.execute('ALTER TABLE negotiations ADD COLUMN seller_approval_token VARCHAR(64)'); conn.commit()" 2>nul
echo      Done.

echo [3/3] Starting server on http://localhost:8000
echo.
echo ============================================
echo   Open http://localhost:8000 in your browser
echo   Press Ctrl+C to stop the server
echo ============================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
