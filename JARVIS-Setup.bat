@echo off
setlocal EnableDelayedExpansion
title JARVIS v2.0 — Setup Installer
color 0B

echo.
echo  ============================================================
echo   JARVIS v2.0 — One-Click Installer
echo   Just A Rather Very Intelligent System
echo   Built for Akshay
echo  ============================================================
echo.

:: ── Admin check ──────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set "JARVIS_DIR=%~dp0"
set "JARVIS_DIR=%JARVIS_DIR:~0,-1%"
set "VENV_DIR=%JARVIS_DIR%\venv"
set "PYTHON_MIN=3.10"

echo  [1/7] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python not found. Opening download page...
    echo      Install Python 3.10 or later from:
    echo      https://www.python.org/downloads/
    echo.
    start https://www.python.org/downloads/
    echo  Press any key after installing Python, then re-run this setup.
    pause >nul
    exit /b 1
)

for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo  [OK] Python %PYVER% found

:: ── Check pip ──────────────────────────
echo.
echo  [2/7] Checking pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Installing pip...
    python -m ensurepip --upgrade
)
echo  [OK] pip ready

:: ── Virtual environment ───────────────
echo.
echo  [3/7] Setting up virtual environment...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
    echo  [OK] Virtual environment created
) else (
    echo  [OK] Using existing virtual environment
)

call "%VENV_DIR%\Scripts\activate.bat"

:: ── Install packages ──────────────────
echo.
echo  [4/7] Installing packages (this may take 2-3 minutes)...
pip install --upgrade pip --quiet --disable-pip-version-check 2>nul
pip install -r "%JARVIS_DIR%\requirements.txt" --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo  [!] Some packages failed. Retrying without quiet mode...
    pip install -r "%JARVIS_DIR%\requirements.txt" --no-warn-script-location
)
echo  [OK] All packages installed

:: ── Create directories ────────────────
echo.
echo  [5/7] Creating directories...
if not exist "%JARVIS_DIR%\logs"          mkdir "%JARVIS_DIR%\logs"
if not exist "%JARVIS_DIR%\memory\data"   mkdir "%JARVIS_DIR%\memory\data"
if not exist "%JARVIS_DIR%\memory\chroma_db" mkdir "%JARVIS_DIR%\memory\chroma_db"
if not exist "%JARVIS_DIR%\data"          mkdir "%JARVIS_DIR%\data"
if not exist "%JARVIS_DIR%\journal"       mkdir "%JARVIS_DIR%\journal"
echo  [OK] Directories ready

:: ── Environment setup ─────────────────
echo.
echo  [6/7] Configuring environment...
if not exist "%JARVIS_DIR%\.env" (
    if exist "%JARVIS_DIR%\.env.example" (
        copy "%JARVIS_DIR%\.env.example" "%JARVIS_DIR%\.env" >nul
        echo  [OK] .env created from template
    )
)

:: Prompt for API key if not set
set "APIKEY="
for /f "tokens=1,* delims==" %%A in ('findstr /i "GROQ_API_KEY" "%JARVIS_DIR%\.env" 2^>nul') do (
    if /i "%%A"=="GROQ_API_KEY" set "APIKEY=%%B"
)
if "!APIKEY!"=="" (
    echo.
    echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo   Groq API Key Required
    echo   Get a FREE key at: https://console.groq.com
    echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    set /p "APIKEY= Paste your key (gsk_...): "
    if not "!APIKEY!"=="" (
        powershell -Command "(Get-Content '%JARVIS_DIR%\.env') -replace 'gsk_your_key_here', '!APIKEY!' | Set-Content '%JARVIS_DIR%\.env'"
        echo  [OK] API key saved
    )
) else (
    echo  [OK] API key already configured
)

:: ── Desktop shortcut ──────────────────
echo.
echo  [7/7] Creating desktop shortcut...

set "SHORTCUT=%USERPROFILE%\Desktop\JARVIS.lnk"
set "LAUNCHER=%JARVIS_DIR%\Launch-JARVIS.bat"
set "ICON=%JARVIS_DIR%\ui\static\icons\favicon.ico"

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut('%SHORTCUT%'); ^
   $sc.TargetPath = '%LAUNCHER%'; ^
   $sc.WorkingDirectory = '%JARVIS_DIR%'; ^
   $sc.Description = 'JARVIS Personal AI Agent'; ^
   if (Test-Path '%ICON%') { $sc.IconLocation = '%ICON%' }; ^
   $sc.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  [OK] Desktop shortcut created
) else (
    echo  [!] Could not create shortcut - you can still run Launch-JARVIS.bat directly
)

:: ── Done ─────────────────────────────
echo.
echo  ============================================================
echo   JARVIS v2.0 installed successfully!
echo  ============================================================
echo.
echo   Desktop shortcut: JARVIS.lnk on your Desktop
echo   Or run manually:  Launch-JARVIS.bat
echo   Web interface:    http://localhost:5000
echo   Setup wizard:     http://localhost:5000/setup
echo.
set /p "LAUNCH= Launch JARVIS now? [Y/n]: "
if /i not "!LAUNCH!"=="n" (
    start "" "%LAUNCHER%"
)
echo.
echo  Press any key to close...
pause >nul
endlocal
