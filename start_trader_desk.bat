@echo off
title ALPHA Quant Institutional Trader Desk Launcher
echo ============================================================================
echo   ALPHA QUANT — INSTITUTIONAL QUANTITATIVE TRADER DESK (BTC/USDT SPOT)
echo   Real-Time Binance Spot WebSocket + Multi-Strategy ATR Scanner + Paper Desk
echo ============================================================================
echo.

cd /d "%~dp0"

set PYTHON_EXE=python
if exist "%~dp0backend\.venv\Scripts\python.exe" (
    set PYTHON_EXE="%~dp0backend\.venv\Scripts\python.exe"
)

echo [1/3] Running database schema checks...
cd backend
%PYTHON_EXE% -m alembic upgrade head
cd ..

echo [2/3] Starting FastAPI Quantitative Engine and Unified Production Server on Port 8000...
start "ALPHA Quant Engine (Port 8000)" cmd /k "cd /d "%~dp0backend" && %PYTHON_EXE% -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [3/3] Starting Vite Live Trader Frontend on Port 5174...
start "ALPHA Quant Frontend (Port 5174)" cmd /k "cd /d "%~dp0frontend" && npx vite --port 5174 --host 0.0.0.0"

timeout /t 4 /nobreak >nul
echo Opening ALPHA Quant Trader Desk in default browser...
start http://localhost:5174

echo.
echo ============================================================================
echo   ALPHA Quant is LIVE!
echo   - Trader Desk UI (Dev/Hot-Reload): http://localhost:5174
echo   - Unified Production Server (LAN): http://localhost:8000
echo   - Interactive API Docs:            http://localhost:8000/docs
echo ============================================================================
pause
