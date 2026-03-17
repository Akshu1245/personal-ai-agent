@echo off
setlocal
title JARVIS v2.0
color 0B

set "JARVIS_DIR=%~dp0"
set "JARVIS_DIR=%JARVIS_DIR:~0,-1%"
set "VENV_DIR=%JARVIS_DIR%\venv"
set "PORT=5000"
set "URL=http://localhost:%PORT%"

:: ── Activate venv if available ────────
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [!] venv not found. Run JARVIS-Setup.bat first.
    timeout /t 3 >nul
    start "" "%JARVIS_DIR%\JARVIS-Setup.bat"
    exit /b
)

:: ── Load .env ─────────────────────────
if exist "%JARVIS_DIR%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%JARVIS_DIR%\.env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

echo.
echo  ╔════════════════════════════════════╗
echo  ║   JARVIS v2.0 is starting...      ║
echo  ║   http://localhost:5000            ║
echo  ╚════════════════════════════════════╝
echo.
echo  Close this window to stop JARVIS.
echo.

:: ── Wait for server then open browser ─
start /min "" powershell -Command ^
  "Start-Sleep 3; Start-Process '%URL%'"

:: ── Start JARVIS ──────────────────────
cd /d "%JARVIS_DIR%"
gunicorn -c gunicorn.conf.py wsgi:application

endlocal
