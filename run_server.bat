@echo off
title TradeSense AI Backend Server

echo ========================================
echo    TradeSense AI Backend Server
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo Starting TradeSense AI Backend...
echo.
echo Backend will be available at:
echo - http://localhost:5000
echo - http://127.0.0.1:5000
echo.
echo Demo Credentials:
echo - Demo Trader: demo.trader@tradesense.ai / demo123456
echo - Admin: admin@tradesense.ai / admin123456
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start the Python server
python simple_server.py

echo.
echo Server stopped.
pause
