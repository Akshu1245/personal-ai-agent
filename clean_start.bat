@echo off
echo ============================================
echo   JARVIS Complete Reset and Start
echo ============================================

cd /d "%~dp0"

echo [1] Killing any Python processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1

echo [2] Removing all databases and cache...
if exist "memory\data\conversations.db" del "memory\data\conversations.db"
if exist "memory\chroma_db" rmdir /s /q "memory\chroma_db"
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "core\__pycache__" rmdir /s /q "core\__pycache__"
if exist "tools\__pycache__" rmdir /s /q "tools\__pycache__"

echo [3] Recreating directories...
if not exist "memory\data" mkdir "memory\data"
if not exist "memory\chroma_db" mkdir "memory\chroma_db"
if not exist "logs" mkdir "logs"

echo [4] Backup original projects.json...
if exist "data\projects.json" (
    copy "data\projects.json" "data\projects.json.backup" >nul
)

echo [5] Creating minimal projects.json...
echo [] > "data\projects.json"

REM Activate virtual environment
call venv\Scripts\activate.bat

echo [6] Starting JARVIS with clean slate...
echo.
echo ==========================================
echo   JARVIS should start at http://localhost:5000
echo ==========================================
echo.

python main.py

pause