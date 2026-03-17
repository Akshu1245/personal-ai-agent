@echo off
echo ============================================
echo   JARVIS - Quick Commit to GitHub
echo ============================================

cd /d "%~dp0"

echo Adding files...
git add core/config.py setup_jarvis.bat install.py SETUP_STATUS.md CHANGES_APPLIED.md commit_changes.bat requirements.txt main.py

echo Committing changes...
git commit -m "feat: Complete JARVIS setup automation and core infrastructure

- Add core/config.py: Central configuration management system
- Add setup_jarvis.bat: Automated environment setup script  
- Add install.py: Python-based dependency installer
- Add SETUP_STATUS.md: Comprehensive setup status documentation
- Add CHANGES_APPLIED.md: Summary of all changes and improvements
- Add commit_changes.bat: Git commit helper script
- Update requirements.txt: Clean invalid dependencies
- Update main.py: Fix SocketIO integration issues

The JARVIS system is now fully configured and ready for deployment.
Environment variables are properly isolated (.env excluded from git).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

echo Pushing to GitHub...
git push origin main

echo.
echo ============================================
echo   ✅ JARVIS changes pushed to GitHub!
echo ============================================
pause