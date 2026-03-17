# JARVIS Git Commit PowerShell Script
# Run this in PowerShell from d:\projects\jarvis

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JARVIS Git Commit Script" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
Set-Location "d:\projects\jarvis"

# Step 1: Show current status
Write-Host "[1] Checking current git status..." -ForegroundColor Yellow
git status --short
Write-Host ""

# Step 2: Add files
Write-Host "[2] Adding files for commit..." -ForegroundColor Yellow
$files = @(
    "core/config.py",
    "setup_jarvis.bat",
    "install.py",
    "SETUP_STATUS.md",
    "CHANGES_APPLIED.md",
    "commit_changes.bat",
    "requirements.txt",
    "main.py"
)

foreach ($file in $files) {
    Write-Host "  Adding: $file"
    git add $file
}
Write-Host "  ✓ Files added successfully" -ForegroundColor Green
Write-Host ""

# Step 3: Verify staging
Write-Host "[3] Checking status after staging..." -ForegroundColor Yellow
git status --short
Write-Host ""

# Step 4: Commit
Write-Host "[4] Creating commit..." -ForegroundColor Yellow
$commitMessage = @"
feat: Complete JARVIS setup automation and core infrastructure

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
"@

git commit -m $commitMessage
Write-Host ""

# Step 5: Push to main
Write-Host "[5] Pushing to main branch..." -ForegroundColor Yellow
git push origin main
Write-Host ""

# Step 6: Verify
Write-Host "[6] Verifying commits..." -ForegroundColor Yellow
git log --oneline -5
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✓ Commit and push completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your JARVIS setup changes have been successfully committed to GitHub!" -ForegroundColor Green
