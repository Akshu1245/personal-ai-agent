╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                         AKSHAY AI CORE v1.0.0                                ║
║                                                                              ║
║                   Your Personal AI Assistant System                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

================================================================================
 QUICK START
================================================================================

1. INSTALL
   --------
   Open PowerShell and run:
   
   > .\install\install.ps1
   
   This will:
   - Check system requirements
   - Create Python virtual environment
   - Install dependencies
   - Generate security keys
   - Sign default policies

2. FIRST RUN
   ----------
   Launch AKSHAY AI:
   
   > .\ai.ps1
   
   On first run, you'll complete the setup wizard:
   - Create admin account
   - Set your PIN (required for sensitive operations)
   - Configure voice settings
   - Select operating mode
   - Save your recovery key (IMPORTANT!)

3. DAILY USE
   ----------
   > .\ai.ps1              # Normal operation
   > .\ai.ps1 -Demo        # Demo mode (no real changes)
   > .\ai.ps1 -Safe        # Safe mode (voice disabled)
   > .\ai.ps1 -Status      # Check system status
   > .\ai.ps1 -Help        # Show all options


================================================================================
 OPERATING MODES
================================================================================

NORMAL MODE (default)
  Full functionality with all configured interfaces.
  
DEMO MODE (-Demo)
  • Mock devices and fake data
  • No real file system changes
  • No API key access
  • Perfect for demonstrations
  
SAFE MODE (-Safe)
  • Voice commands disabled
  • Text interface only
  • Full functionality otherwise
  
RECOVERY MODE (-Recovery)
  • Minimal policy loaded
  • Voice disabled
  • For troubleshooting


================================================================================
 SECURITY FEATURES
================================================================================

✓ PIN Protection
  Your sensitive operations require PIN verification.
  PIN is encrypted with military-grade scrypt + Fernet.

✓ Recovery Key
  Generated during first-run setup.
  Store it safely - it's your backup if you forget your PIN.

✓ Signed Policies
  All policies are cryptographically signed.
  Tampering is detected and blocked.

✓ Audit Logging
  All operations are logged with integrity protection.

✓ Trust Zones
  Different permission levels for SYSTEM, OPERATOR, USER, GUEST.


================================================================================
 UNINSTALLING
================================================================================

To remove AKSHAY AI CORE:

> .\uninstall.ps1

You'll need your PIN to authorize removal.
Keys are securely wiped (overwritten with random data 3x).

Options:
  -KeepUserData    Preserve your data files
  -KeepLogs        Preserve audit logs
  -Force           Skip confirmation prompts


================================================================================
 TROUBLESHOOTING
================================================================================

Q: "Python not found"
A: Ensure Python 3.10+ is installed and in PATH.
   Run: python --version

Q: "Virtual environment not found"
A: Run install.ps1 first.

Q: "PIN verification failed"
A: Use your recovery key to reset:
   > .\ai.ps1 -Recovery

Q: "Policy signature invalid"
A: Policies may have been tampered with.
   Reinstall or restore from backup.


================================================================================
 SUPPORT
================================================================================

Documentation:  docs/
Release Notes:  docs/RELEASE_REPORT.md
Audit Report:   docs/PRE_RELEASE_AUDIT.md


================================================================================
 LICENSE
================================================================================

AKSHAY AI CORE - Personal AI Assistant System
Copyright (c) 2025


================================================================================

        Thank you for using AKSHAY AI CORE!
        
        "I serve at your command."
        
================================================================================
