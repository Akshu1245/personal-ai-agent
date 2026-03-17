@echo off
setlocal

REM ── Lock working directory to project folder ─────────────────────────────
pushd "%~dp0"

echo ============================================
echo   JARVIS - Database Fix and Restart
echo ============================================

echo Stopping any existing JARVIS processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1

echo Waiting for processes to stop...
timeout /t 2 >nul

echo Removing locked database...
if exist "%~dp0memory\data\conversations.db" (
    del "%~dp0memory\data\conversations.db"
    echo Database removed
)

echo Clearing ChromaDB cache...
if exist "%~dp0memory\chroma_db" (
    rmdir /s /q "%~dp0memory\chroma_db"
    echo ChromaDB cache cleared
)

echo Recreating directories...
if not exist "%~dp0memory\data" mkdir "%~dp0memory\data"
if not exist "%~dp0memory\chroma_db" mkdir "%~dp0memory\chroma_db"
if not exist "%~dp0logs" mkdir "%~dp0logs"
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0journal" mkdir "%~dp0journal"

REM ── Activate virtual environment ──────────────────────────────────────────
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

echo.
echo ============================================
echo   Starting JARVIS (fresh database)
echo   Open http://localhost:5000
echo ============================================
echo.

REM ── Start JARVIS (absolute path prevents System32 confusion) ─────────────
python "%~dp0main.py"

popd
pause
endlocal