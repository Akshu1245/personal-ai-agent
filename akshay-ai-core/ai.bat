@echo off
REM ============================================================
REM AKSHAY AI CORE — Launcher (Batch Wrapper)
REM ============================================================
REM This batch file wraps ai.ps1 for command-line convenience.
REM Usage: ai [options]
REM ============================================================

setlocal EnableDelayedExpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Check for PowerShell
where powershell >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PowerShell is required but not found.
    echo Please install PowerShell or run ai.ps1 directly.
    exit /b 1
)

REM Forward all arguments to the PowerShell script
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%ai.ps1" %*

exit /b %ERRORLEVEL%
