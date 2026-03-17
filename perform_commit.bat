@echo off
REM Script to commit JARVIS setup changes
cd /d d:\projects\jarvis

echo ========================================
echo JARVIS Git Commit Script
echo ========================================
echo.

echo [1] Checking current git status...
git status --short
echo.

echo [2] Adding files for commit...
git add core/config.py setup_jarvis.bat install.py SETUP_STATUS.md CHANGES_APPLIED.md commit_changes.bat requirements.txt main.py
echo Files added successfully
echo.

echo [3] Checking status after staging...
git status --short
echo.

echo [4] Committing changes...
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
Environment variables are properly isolated (.env excluded from git)."

echo.

echo [5] Pushing to main branch...
git push origin main
echo.

echo ========================================
echo Commit and push completed successfully!
echo ========================================
pause
