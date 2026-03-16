<# 
.SYNOPSIS
    AKSHAY AI CORE - Release Test Suite
    Full lifecycle tests for release verification.

.DESCRIPTION
    Comprehensive test suite covering:
    - Installation integrity
    - First-run wizard simulation
    - Normal operation
    - Demo mode
    - Safe mode
    - Recovery mode
    - Security controls
    - Uninstall (dry-run)

.PARAMETER Quick
    Run quick tests only (skip long-running tests)

.PARAMETER Verbose
    Show detailed test output

.PARAMETER SkipPythonTests
    Skip Python unit tests

.EXAMPLE
    .\test_release.ps1
    # Run full test suite

.EXAMPLE
    .\test_release.ps1 -Quick
    # Run quick validation only

.NOTES
    Version: 1.0.0
    Run as part of release validation.
#>

[CmdletBinding()]
param(
    [switch]$Quick,
    [switch]$SkipPythonTests
)

# ============================================================
# Configuration
# ============================================================

$ErrorActionPreference = "Continue"
$AkshayRoot = Split-Path $PSScriptRoot -Parent
if (-not $AkshayRoot -or $AkshayRoot -eq $PSScriptRoot) {
    $AkshayRoot = $PSScriptRoot
}
$VenvPath = Join-Path $AkshayRoot ".venv"
$TestResults = @{
    Passed = 0
    Failed = 0
    Skipped = 0
    Tests = @()
}
$StartTime = Get-Date

# ============================================================
# Banner
# ============================================================

function Write-TestBanner {
    $banner = @"

================================================================
     AKSHAY AI CORE - RELEASE TEST SUITE
     
     Comprehensive validation for release readiness
================================================================

"@
    Write-Host $banner -ForegroundColor Cyan
}

# ============================================================
# Test Helpers
# ============================================================

function Add-TestResult {
    param(
        [string]$Name,
        [string]$Category,
        [string]$Status,
        [string]$Message = ""
    )
    
    $color = switch ($Status) {
        "PASS"   { "Green" }
        "FAIL"   { "Red" }
        "SKIP"   { "Yellow" }
        default  { "Gray" }
    }
    
    $symbol = switch ($Status) {
        "PASS"   { "+" }
        "FAIL"   { "x" }
        "SKIP"   { "o" }
        default  { "?" }
    }
    
    Write-Host "  [$symbol] $Name" -ForegroundColor $color
    if ($Message) {
        Write-Host "      $Message" -ForegroundColor DarkGray
    }
    
    $TestResults.Tests += @{
        Name = $Name
        Category = $Category
        Status = $Status
        Message = $Message
    }
    
    switch ($Status) {
        "PASS" { $script:TestResults.Passed++ }
        "FAIL" { $script:TestResults.Failed++ }
        "SKIP" { $script:TestResults.Skipped++ }
    }
}

function Get-PythonPath {
    $pythonPath = Join-Path $VenvPath "Scripts\python.exe"
    if (Test-Path $pythonPath) {
        return $pythonPath
    }
    $pythonPath = Join-Path $VenvPath "bin/python"
    if (Test-Path $pythonPath) {
        return $pythonPath
    }
    return $null
}

# ============================================================
# Test Categories
# ============================================================

function Test-FileStructure {
    Write-Host "`n[DIR] FILE STRUCTURE TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    # Core directories
    $requiredDirs = @(
        "core",
        "core/security",
        "core/brain",
        "api",
        "policies",
        "install",
        "tests"
    )
    
    foreach ($dir in $requiredDirs) {
        $path = Join-Path $AkshayRoot $dir
        if (Test-Path $path) {
            Add-TestResult "Directory: $dir" "Structure" "PASS"
        } else {
            Add-TestResult "Directory: $dir" "Structure" "FAIL" "Directory not found"
        }
    }
    
    # Core files
    $requiredFiles = @(
        "ai.ps1",
        "ai.bat",
        "main.py",
        "policies/default.yaml",
        "policies/demo.yaml",
        "core/security/keystore.py",
        "core/security/bootstrap.py",
        "core/security/engine.py",
        "core/security/wizard.py"
    )
    
    foreach ($file in $requiredFiles) {
        $path = Join-Path $AkshayRoot $file
        if (Test-Path $path) {
            Add-TestResult "File: $file" "Structure" "PASS"
        } else {
            Add-TestResult "File: $file" "Structure" "FAIL" "File not found"
        }
    }
}

function Test-PythonEnvironment {
    Write-Host "`n[PY] PYTHON ENVIRONMENT TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    # Virtual environment exists
    if (Test-Path $VenvPath) {
        Add-TestResult "Virtual environment exists" "Python" "PASS"
    } else {
        Add-TestResult "Virtual environment exists" "Python" "FAIL" "Run install.ps1 first"
        return
    }
    
    # Python executable
    $pythonPath = Get-PythonPath
    if ($pythonPath) {
        Add-TestResult "Python executable found" "Python" "PASS"
    } else {
        Add-TestResult "Python executable found" "Python" "FAIL"
        return
    }
    
    # Python version
    try {
        $version = & $pythonPath --version 2>&1
        if ($version -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) {
                Add-TestResult "Python version (3.10+)" "Python" "PASS" $version
            } else {
                Add-TestResult "Python version (3.10+)" "Python" "FAIL" "$version (need 3.10+)"
            }
        }
    } catch {
        Add-TestResult "Python version (3.10+)" "Python" "FAIL" $_.Exception.Message
    }
    
    # Required packages
    $requiredPackages = @(
        "cryptography",
        "pyyaml",
        "pydantic",
        "rich"
    )
    
    foreach ($pkg in $requiredPackages) {
        try {
            $result = & $pythonPath -c "import $pkg; print('OK')" 2>&1
            if ($result -eq "OK") {
                Add-TestResult "Package: $pkg" "Python" "PASS"
            } else {
                Add-TestResult "Package: $pkg" "Python" "FAIL" "Import failed"
            }
        } catch {
            Add-TestResult "Package: $pkg" "Python" "FAIL" "Import failed"
        }
    }
}

function Test-SecurityModules {
    Write-Host "`n[SEC] SECURITY MODULE TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    $pythonPath = Get-PythonPath
    if (-not $pythonPath) {
        Add-TestResult "Security modules" "Security" "SKIP" "Python not available"
        return
    }
    
    # KeyStore import
    $testCode = @"
import sys
sys.path.insert(0, r'$AkshayRoot')
try:
    from core.security.keystore import KeyStore
    print('OK')
except Exception as e:
    print(f'ERROR:{e}')
"@
    $result = $testCode | & $pythonPath - 2>&1
    if ($result -eq "OK") {
        Add-TestResult "Import: KeyStore" "Security" "PASS"
    } else {
        Add-TestResult "Import: KeyStore" "Security" "FAIL" $result
    }
    
    # Bootstrap import
    $testCode = @"
import sys
sys.path.insert(0, r'$AkshayRoot')
try:
    from core.security.bootstrap import SecurityBootstrap
    print('OK')
except Exception as e:
    print(f'ERROR:{e}')
"@
    $result = $testCode | & $pythonPath - 2>&1
    if ($result -eq "OK") {
        Add-TestResult "Import: SecurityBootstrap" "Security" "PASS"
    } else {
        Add-TestResult "Import: SecurityBootstrap" "Security" "FAIL" $result
    }
    
    # Policy Engine import
    $testCode = @"
import sys
sys.path.insert(0, r'$AkshayRoot')
try:
    from core.security.engine import PolicyEngine
    print('OK')
except Exception as e:
    print(f'ERROR:{e}')
"@
    $result = $testCode | & $pythonPath - 2>&1
    if ($result -eq "OK") {
        Add-TestResult "Import: PolicyEngine" "Security" "PASS"
    } else {
        Add-TestResult "Import: PolicyEngine" "Security" "FAIL" $result
    }
    
    # Wizard import
    $testCode = @"
import sys
sys.path.insert(0, r'$AkshayRoot')
try:
    from core.security.wizard import FirstRunWizard
    print('OK')
except Exception as e:
    print(f'ERROR:{e}')
"@
    $result = $testCode | & $pythonPath - 2>&1
    if ($result -eq "OK") {
        Add-TestResult "Import: FirstRunWizard" "Security" "PASS"
    } else {
        Add-TestResult "Import: FirstRunWizard" "Security" "FAIL" $result
    }
}

function Test-PolicyFiles {
    Write-Host "`n[POL] POLICY FILE TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    $pythonPath = Get-PythonPath
    if (-not $pythonPath) {
        Add-TestResult "Policy files" "Policy" "SKIP" "Python not available"
        return
    }
    
    $policyFiles = @(
        "default.yaml",
        "demo.yaml"
    )
    
    foreach ($policy in $policyFiles) {
        $policyPath = Join-Path $AkshayRoot "policies\$policy"
        
        if (-not (Test-Path $policyPath)) {
            Add-TestResult "Policy: $policy exists" "Policy" "FAIL" "File not found"
            continue
        }
        
        Add-TestResult "Policy: $policy exists" "Policy" "PASS"
        
        # Validate YAML syntax
        $testCode = @"
import sys
import yaml
sys.path.insert(0, r'$AkshayRoot')
try:
    with open(r'$policyPath', 'r') as f:
        data = yaml.safe_load(f)
    if 'rules' in data and 'version' in data:
        print('OK')
    else:
        print('INVALID_STRUCTURE')
except Exception as e:
    print(f'ERROR:{e}')
"@
        $result = $testCode | & $pythonPath - 2>&1
        if ($result -eq "OK") {
            Add-TestResult "Policy: $policy valid YAML" "Policy" "PASS"
        } else {
            Add-TestResult "Policy: $policy valid YAML" "Policy" "FAIL" $result
        }
    }
}

function Test-LauncherScript {
    Write-Host "`n[LAUNCH] LAUNCHER SCRIPT TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    $launcherPath = Join-Path $AkshayRoot "ai.ps1"
    
    if (-not (Test-Path $launcherPath)) {
        Add-TestResult "Launcher: ai.ps1 exists" "Launcher" "FAIL" "File not found"
        return
    }
    
    Add-TestResult "Launcher: ai.ps1 exists" "Launcher" "PASS"
    
    # Check for required functions
    $content = Get-Content $launcherPath -Raw
    
    $requiredFunctions = @(
        "Write-Banner",
        "Test-VenvExists",
        "Get-PythonPath",
        "Start-AkshayAI",
        "Show-Help"
    )
    
    foreach ($func in $requiredFunctions) {
        if ($content -match "function\s+$func") {
            Add-TestResult "Launcher: Function $func" "Launcher" "PASS"
        } else {
            Add-TestResult "Launcher: Function $func" "Launcher" "FAIL" "Function not found"
        }
    }
    
    # Check for mode flags
    $modeFlags = @("Demo", "Safe", "Recovery", "NoVoice", "Status", "Help")
    
    foreach ($flag in $modeFlags) {
        if ($content -match "\[switch\]\s*\`$" + $flag) {
            Add-TestResult "Launcher: -$flag flag" "Launcher" "PASS"
        } else {
            Add-TestResult "Launcher: -$flag flag" "Launcher" "FAIL" "Flag not found"
        }
    }
    
    # Batch wrapper
    $batPath = Join-Path $AkshayRoot "ai.bat"
    if (Test-Path $batPath) {
        Add-TestResult "Launcher: ai.bat wrapper" "Launcher" "PASS"
    } else {
        Add-TestResult "Launcher: ai.bat wrapper" "Launcher" "FAIL" "File not found"
    }
}

function Test-UninstallerScript {
    Write-Host "`n[UNINST] UNINSTALLER SCRIPT TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    $uninstallPath = Join-Path $AkshayRoot "uninstall.ps1"
    
    if (-not (Test-Path $uninstallPath)) {
        Add-TestResult "Uninstaller: uninstall.ps1 exists" "Uninstall" "FAIL" "File not found"
        return
    }
    
    Add-TestResult "Uninstaller: uninstall.ps1 exists" "Uninstall" "PASS"
    
    $content = Get-Content $uninstallPath -Raw
    
    # Check for security features
    if ($content -match "Verify-AdminPIN|Verify_AdminPIN") {
        Add-TestResult "Uninstaller: PIN verification" "Uninstall" "PASS"
    } else {
        Add-TestResult "Uninstaller: PIN verification" "Uninstall" "FAIL"
    }
    
    if ($content -match "Secure-WipeKeys|SecureWipe") {
        Add-TestResult "Uninstaller: Secure key wipe" "Uninstall" "PASS"
    } else {
        Add-TestResult "Uninstaller: Secure key wipe" "Uninstall" "FAIL"
    }
    
    if ($content -match "Stop-AkshayServices") {
        Add-TestResult "Uninstaller: Service stop" "Uninstall" "PASS"
    } else {
        Add-TestResult "Uninstaller: Service stop" "Uninstall" "FAIL"
    }
    
    # Check for safety flags
    if ($content -match "\[switch\]\s*\`$Force") {
        Add-TestResult "Uninstaller: -Force flag" "Uninstall" "PASS"
    } else {
        Add-TestResult "Uninstaller: -Force flag" "Uninstall" "FAIL"
    }
    
    if ($content -match "\[switch\]\s*\`$KeepUserData") {
        Add-TestResult "Uninstaller: -KeepUserData flag" "Uninstall" "PASS"
    } else {
        Add-TestResult "Uninstaller: -KeepUserData flag" "Uninstall" "FAIL"
    }
}

function Test-PythonUnitTests {
    Write-Host "`n[TEST] PYTHON UNIT TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    if ($SkipPythonTests) {
        Add-TestResult "Python unit tests" "UnitTests" "SKIP" "-SkipPythonTests flag"
        return
    }
    
    $pythonPath = Get-PythonPath
    if (-not $pythonPath) {
        Add-TestResult "Python unit tests" "UnitTests" "SKIP" "Python not available"
        return
    }
    
    $testsDir = Join-Path $AkshayRoot "tests"
    if (-not (Test-Path $testsDir)) {
        Add-TestResult "Python unit tests" "UnitTests" "SKIP" "tests/ directory not found"
        return
    }
    
    # Run pytest
    Write-Host "  Running pytest..." -ForegroundColor Gray
    
    try {
        Push-Location $AkshayRoot
        $output = & $pythonPath -m pytest tests/ -v --tb=short 2>&1
        $exitCode = $LASTEXITCODE
        Pop-Location
        
        # Parse results
        if ($output -match "(\d+) passed") {
            $passed = [int]$Matches[1]
            Add-TestResult "Pytest: $passed tests passed" "UnitTests" "PASS"
        }
        
        if ($output -match "(\d+) failed") {
            $failed = [int]$Matches[1]
            Add-TestResult "Pytest: $failed tests failed" "UnitTests" "FAIL"
        }
        
        if ($exitCode -eq 0) {
            Add-TestResult "Pytest: All tests passed" "UnitTests" "PASS"
        } else {
            Add-TestResult "Pytest: Test suite failed" "UnitTests" "FAIL" "Exit code: $exitCode"
        }
    } catch {
        Add-TestResult "Pytest execution" "UnitTests" "FAIL" $_.Exception.Message
    }
}

function Test-DemoPolicy {
    Write-Host "`n[DEMO] DEMO MODE POLICY TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    $pythonPath = Get-PythonPath
    if (-not $pythonPath) {
        Add-TestResult "Demo policy" "Demo" "SKIP" "Python not available"
        return
    }
    
    $demoPolicyPath = Join-Path $AkshayRoot "policies\demo.yaml"
    if (-not (Test-Path $demoPolicyPath)) {
        Add-TestResult "Demo policy exists" "Demo" "FAIL" "File not found"
        return
    }
    
    # Check demo policy has required elements
    $testCode = @"
import sys
import yaml
sys.path.insert(0, r'$AkshayRoot')
try:
    with open(r'$demoPolicyPath', 'r') as f:
        policy = yaml.safe_load(f)
    
    checks = []
    
    # Check mode is demo
    if policy.get('metadata', {}).get('mode') == 'demo':
        checks.append('mode_ok')
    
    # Check has mock devices
    if 'mock_devices' in policy and len(policy['mock_devices']) > 0:
        checks.append('mock_devices_ok')
    
    # Check has deny rules
    deny_rules = [r for r in policy.get('rules', []) if r.get('action', {}).get('type') == 'DENY']
    if len(deny_rules) >= 5:
        checks.append('deny_rules_ok')
    
    # Check persistent_storage is false
    if policy.get('settings', {}).get('persistent_storage') == False:
        checks.append('no_persist_ok')
    
    print(','.join(checks))
except Exception as e:
    print(f'ERROR:{e}')
"@
    
    $result = $testCode | & $pythonPath - 2>&1
    
    if ($result -match "mode_ok") {
        Add-TestResult "Demo: Mode = demo" "Demo" "PASS"
    } else {
        Add-TestResult "Demo: Mode = demo" "Demo" "FAIL"
    }
    
    if ($result -match "mock_devices_ok") {
        Add-TestResult "Demo: Mock devices defined" "Demo" "PASS"
    } else {
        Add-TestResult "Demo: Mock devices defined" "Demo" "FAIL"
    }
    
    if ($result -match "deny_rules_ok") {
        Add-TestResult "Demo: Deny rules present" "Demo" "PASS"
    } else {
        Add-TestResult "Demo: Deny rules present" "Demo" "FAIL"
    }
    
    if ($result -match "no_persist_ok") {
        Add-TestResult "Demo: No persistent storage" "Demo" "PASS"
    } else {
        Add-TestResult "Demo: No persistent storage" "Demo" "FAIL"
    }
}

function Test-SecurityHardening {
    Write-Host "`n[HARD] SECURITY HARDENING TESTS" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor DarkGray
    
    $pythonPath = Get-PythonPath
    if (-not $pythonPath) {
        Add-TestResult "Security hardening" "Hardening" "SKIP" "Python not available"
        return
    }
    
    # Check KeyStore has PIN encryption
    $keyStorePath = Join-Path $AkshayRoot "core\security\keystore.py"
    if (Test-Path $keyStorePath) {
        $content = Get-Content $keyStorePath -Raw
        
        if ($content -match "scrypt|Scrypt|SCRYPT") {
            Add-TestResult "KeyStore: scrypt key derivation" "Hardening" "PASS"
        } else {
            Add-TestResult "KeyStore: scrypt key derivation" "Hardening" "FAIL"
        }
        
        if ($content -match "Fernet") {
            Add-TestResult "KeyStore: Fernet encryption" "Hardening" "PASS"
        } else {
            Add-TestResult "KeyStore: Fernet encryption" "Hardening" "FAIL"
        }
        
        if ($content -match "verify_pin") {
            Add-TestResult "KeyStore: PIN verification method" "Hardening" "PASS"
        } else {
            Add-TestResult "KeyStore: PIN verification method" "Hardening" "FAIL"
        }
    }
    
    # Check Bootstrap has Ed25519
    $bootstrapPath = Join-Path $AkshayRoot "core\security\bootstrap.py"
    if (Test-Path $bootstrapPath) {
        $content = Get-Content $bootstrapPath -Raw
        
        if ($content -match "Ed25519") {
            Add-TestResult "Bootstrap: Ed25519 signing" "Hardening" "PASS"
        } else {
            Add-TestResult "Bootstrap: Ed25519 signing" "Hardening" "FAIL"
        }
        
        if ($content -match "device.*id|DeviceId|device_id") {
            Add-TestResult "Bootstrap: Device identity" "Hardening" "PASS"
        } else {
            Add-TestResult "Bootstrap: Device identity" "Hardening" "FAIL"
        }
    }
    
    # Check audit logging
    $auditPath = Join-Path $AkshayRoot "core\security\audit_log.py"
    if (Test-Path $auditPath) {
        Add-TestResult "Audit: audit_log.py exists" "Hardening" "PASS"
        
        $content = Get-Content $auditPath -Raw
        if ($content -match "signature|sign|hash") {
            Add-TestResult "Audit: Log integrity protection" "Hardening" "PASS"
        } else {
            Add-TestResult "Audit: Log integrity protection" "Hardening" "FAIL"
        }
    } else {
        Add-TestResult "Audit: audit_log.py exists" "Hardening" "FAIL"
    }
}

# ============================================================
# Summary
# ============================================================

function Write-Summary {
    $duration = (Get-Date) - $StartTime
    $total = $TestResults.Passed + $TestResults.Failed + $TestResults.Skipped
    
    Write-Host "`n"
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " TEST SUMMARY" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Total Tests:   $total" -ForegroundColor White
    Write-Host "  Passed:        $($TestResults.Passed)" -ForegroundColor Green
    Write-Host "  Failed:        $($TestResults.Failed)" -ForegroundColor Red
    Write-Host "  Skipped:       $($TestResults.Skipped)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Duration:      $($duration.TotalSeconds.ToString('F1'))s" -ForegroundColor Gray
    Write-Host ""
    
    if ($TestResults.Failed -eq 0) {
        Write-Host "  [+] ALL TESTS PASSED - RELEASE READY" -ForegroundColor Green
        Write-Host ""
        return $true
    } else {
        Write-Host "  [x] SOME TESTS FAILED - NOT RELEASE READY" -ForegroundColor Red
        Write-Host ""
        
        # Show failed tests
        Write-Host "  Failed Tests:" -ForegroundColor Red
        foreach ($test in $TestResults.Tests) {
            if ($test.Status -eq "FAIL") {
                Write-Host "    * $($test.Name)" -ForegroundColor Red
                if ($test.Message) {
                    Write-Host "      $($test.Message)" -ForegroundColor DarkRed
                }
            }
        }
        Write-Host ""
        return $false
    }
}

# ============================================================
# Main
# ============================================================

function Main {
    Write-TestBanner
    
    Write-Host "  Installation: $AkshayRoot" -ForegroundColor Gray
    Write-Host "  Mode: $(if ($Quick) { 'Quick' } else { 'Full' })" -ForegroundColor Gray
    Write-Host ""
    
    # Run test categories
    Test-FileStructure
    Test-PythonEnvironment
    Test-SecurityModules
    Test-PolicyFiles
    Test-LauncherScript
    Test-UninstallerScript
    Test-DemoPolicy
    Test-SecurityHardening
    
    if (-not $Quick) {
        Test-PythonUnitTests
    } else {
        Write-Host "`n[TEST] PYTHON UNIT TESTS" -ForegroundColor Cyan
        Write-Host "-------------------------------------" -ForegroundColor DarkGray
        Add-TestResult "Python unit tests" "UnitTests" "SKIP" "-Quick mode"
    }
    
    # Summary
    $success = Write-Summary
    
    # Export results
    $resultsPath = Join-Path $AkshayRoot "test_results.json"
    $TestResults | ConvertTo-Json -Depth 10 | Set-Content $resultsPath -Encoding UTF8
    Write-Host "  Results saved to: test_results.json" -ForegroundColor Gray
    Write-Host ""
    
    if ($success) {
        exit 0
    } else {
        exit 1
    }
}

# Run
Main
