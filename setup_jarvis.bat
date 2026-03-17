@echo off
echo ============================================
echo   JARVIS Setup - Installing Dependencies
echo ============================================

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ Setup Complete!
echo ============================================
echo Dependencies installed in virtual environment
echo .env file created with your GROQ API key
echo.
echo To run JARVIS: start_jarvis.bat
echo.
pause