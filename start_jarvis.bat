@echo off
echo ============================================
echo   JARVIS - Personal AI Desktop Agent
echo   Starting...
echo ============================================

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies if needed
pip install -r requirements.txt

REM Set API keys (edit .env file for permanent settings)
if not exist ".env" (
    copy .env.example .env
    echo Created .env file - please add your API keys
)

REM Start JARVIS
echo.
echo Starting JARVIS...
echo.
python main.py

pause
