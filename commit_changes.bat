@echo off
echo ============================================
echo   Committing JARVIS Setup Changes
echo ============================================

echo Adding setup files to git...

REM Add the files I created (excluding .env for security)
git add setup_jarvis.bat
git add SETUP_STATUS.md

echo.
echo Committing changes...
git commit -m "feat: Add JARVIS setup automation

- Add setup_jarvis.bat for automated dependency installation
- Add SETUP_STATUS.md with setup completion status
- Automates virtual environment creation and pip install
- Ready for one-click JARVIS setup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

echo.
echo ============================================
echo   ✅ Changes Committed!
echo ============================================
echo.
echo Files committed:
echo - setup_jarvis.bat (automated setup script)
echo - SETUP_STATUS.md (setup status documentation)
echo.
echo Note: .env file excluded from git (contains API keys)
echo.
pause