@echo off
setlocal

REM Switch terminal to UTF-8 (required for JARVIS Unicode banner)
chcp 65001 >nul

REM ── Lock working directory to project folder ─────────────────────────────
pushd "%~dp0"

echo ============================================
echo   JARVIS - Manual Setup and Launch
echo ============================================
echo.

REM ── Create virtual environment if it doesn't exist ───────────────────────
if not exist "%~dp0.venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv "%~dp0.venv"
)

REM ── Activate virtual environment ──────────────────────────────────────────
call "%~dp0.venv\Scripts\activate.bat"

echo Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r "%~dp0requirements.txt" --quiet

REM ── Create required directories ───────────────────────────────────────────
if not exist "%~dp0logs" mkdir "%~dp0logs"
if not exist "%~dp0memory\data" mkdir "%~dp0memory\data"
if not exist "%~dp0memory\chroma_db" mkdir "%~dp0memory\chroma_db"
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0journal" mkdir "%~dp0journal"

echo.
echo ============================================
echo   Starting JARVIS on http://localhost:5000
echo   Close this window to stop the server
echo ============================================
echo.

REM ── Start JARVIS (absolute path prevents System32 confusion) ─────────────
python "%~dp0main.py"

popd
pause
endlocal