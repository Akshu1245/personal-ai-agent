@echo off
setlocal

REM Switch terminal to UTF-8 (required for JARVIS Unicode banner)
chcp 65001 >nul

REM ── Lock working directory to project folder ─────────────────────────────
pushd "%~dp0"

echo ============================================
echo   JARVIS - Personal AI Desktop Agent
echo   Quick Setup and Launch
echo ============================================
echo.

REM ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM ── Activate venv if available ────────────────────────────────────────────
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

REM ── Install dependencies ──────────────────────────────────────────────────
echo Installing dependencies...
python -m pip install --upgrade pip --disable-pip-version-check 2>nul
python -m pip install -r "%~dp0requirements.txt" --disable-pip-version-check 2>nul

REM ── Create required directories ───────────────────────────────────────────
if not exist "%~dp0logs" mkdir "%~dp0logs"
if not exist "%~dp0memory\data" mkdir "%~dp0memory\data"
if not exist "%~dp0memory\chroma_db" mkdir "%~dp0memory\chroma_db"
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0journal" mkdir "%~dp0journal"

REM ── Start JARVIS (absolute path prevents System32 confusion) ─────────────
echo.
echo Starting JARVIS...
echo Open http://localhost:5000 in your browser
echo.
python "%~dp0main.py"

popd
pause
endlocal