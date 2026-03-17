@echo off
echo ============================================
echo   JARVIS Test Server
echo ============================================

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

echo Starting test server...
echo This will help identify what's causing the issue
echo.

python test_server.py

pause