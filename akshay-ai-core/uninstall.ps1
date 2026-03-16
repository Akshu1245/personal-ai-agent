<# 
.SYNOPSIS
    AKSHAY AI CORE — Uninstaller
    Secure removal with PIN verification and clean wipe.

.DESCRIPTION
    Safely uninstalls AKSHAY AI CORE:
    - Verifies admin PIN before proceeding
    - Stops running services
    - Securely wipes cryptographic keys
    - Removes all configuration and data
    - Cleans PATH variable
    - Optional: preserves user data

.PARAMETER Force
    Skip confirmation prompts (PIN still required)

.PARAMETER KeepUserData
    Preserve user data in data/ directory

.PARAMETER KeepLogs
    Preserve audit logs for compliance

.PARAMETER SkipPinCheck
    Emergency removal without PIN (requires local admin rights)

.EXAMPLE
    .\uninstall.ps1
    # Interactive uninstall with PIN verification

.EXAMPLE
    .\uninstall.ps1 -Force -KeepLogs
    # Force uninstall but preserve logs

.NOTES
    Version: 1.0.0
    Author: AKSHAY AI CORE System
#>

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$KeepUserData,
    [switch]$KeepLogs,
    [switch]$SkipPinCheck
)

# ============================================================
# Configuration
# ============================================================

$ErrorActionPreference = "Stop"
$AkshayRoot = Split-Path $PSScriptRoot -Parent
if (-not $AkshayRoot -or $AkshayRoot -eq $PSScriptRoot) {
    $AkshayRoot = $PSScriptRoot
}
$VenvPath = Join-Path $AkshayRoot ".venv"
$ConfigPath = Join-Path $AkshayRoot "config"
$DataPath = Join-Path $AkshayRoot "data"
$KeysPath = Join-Path $AkshayRoot ".akshay"
$LogsPath = Join-Path $AkshayRoot "logs"

# ============================================================
# Banner
# ============================================================

function Write-UninstallBanner {
    $banner = @"

╔══════════════════════════════════════════════════════════════╗
║     AKSHAY AI CORE — UNINSTALLER                             ║
║                                                              ║
║     ⚠ WARNING: This will remove AKSHAY AI from this system  ║
╚══════════════════════════════════════════════════════════════╝

"@
    Write-Host $banner -ForegroundColor Red
}

# ============================================================
# Helper Functions
# ============================================================

function Write-Step {
    param([string]$Message, [string]$Status = "INFO")
    $color = switch ($Status) {
        "OK"      { "Green" }
        "WARN"    { "Yellow" }
        "ERROR"   { "Red" }
        "SKIP"    { "DarkGray" }
        default   { "Cyan" }
    }
    $symbol = switch ($Status) {
        "OK"      { "[✓]" }
        "WARN"    { "[!]" }
        "ERROR"   { "[✗]" }
        "SKIP"    { "[-]" }
        default   { "[•]" }
    }
    Write-Host "$symbol $Message" -ForegroundColor $color
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

function Verify-AdminPIN {
    <#
    .SYNOPSIS
        Verify admin PIN using the KeyStore
    #>
    
    $pythonPath = Get-PythonPath
    if (-not $pythonPath) {
        Write-Step "Python environment not found. Cannot verify PIN." "WARN"
        return $false
    }
    
    Write-Host ""
    $pin = Read-Host "Enter Admin PIN to authorize uninstall" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pin)
    $plainPin = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    
    if ([string]::IsNullOrWhiteSpace($plainPin)) {
        Write-Step "No PIN entered" "ERROR"
        return $false
    }
    
    # Verify PIN using Python
    $verifyScript = @"
import sys
sys.path.insert(0, r'$AkshayRoot')
try:
    from core.security.keystore import KeyStore
    ks = KeyStore(r'$KeysPath')
    if ks.verify_pin('$plainPin'):
        print('PIN_VERIFIED')
    else:
        print('PIN_INVALID')
except Exception as e:
    print(f'PIN_ERROR:{e}')
"@
    
    $result = $verifyScript | & $pythonPath -
    
    # Clear PIN from memory
    $plainPin = $null
    [System.GC]::Collect()
    
    if ($result -eq "PIN_VERIFIED") {
        Write-Step "PIN verified successfully" "OK"
        return $true
    } elseif ($result -eq "PIN_INVALID") {
        Write-Step "Invalid PIN" "ERROR"
        return $false
    } else {
        Write-Step "PIN verification failed: $result" "ERROR"
        return $false
    }
}

function Stop-AkshayServices {
    <#
    .SYNOPSIS
        Stop any running AKSHAY services
    #>
    
    Write-Step "Stopping AKSHAY services..." "INFO"
    
    # Find and stop Python processes running AKSHAY
    $processes = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmdLine -match "akshay" -or $cmdLine -match "main\.py"
        } catch {
            $false
        }
    }
    
    if ($processes) {
        foreach ($proc in $processes) {
            try {
                Write-Step "  Stopping process: $($proc.Name) (PID: $($proc.Id))" "INFO"
                $proc | Stop-Process -Force -ErrorAction SilentlyContinue
                Start-Sleep -Milliseconds 500
            } catch {
                Write-Step "  Could not stop process $($proc.Id)" "WARN"
            }
        }
        Write-Step "Services stopped" "OK"
    } else {
        Write-Step "No AKSHAY services running" "SKIP"
    }
}

function Secure-WipeKeys {
    <#
    .SYNOPSIS
        Securely wipe cryptographic keys by overwriting with random data
    #>
    
    Write-Step "Securely wiping cryptographic keys..." "INFO"
    
    if (-not (Test-Path $KeysPath)) {
        Write-Step "No keys directory found" "SKIP"
        return
    }
    
    $keyFiles = @(
        "private.key",
        "private.key.enc",
        "keystore.json",
        "recovery.key",
        "device.id",
        "*.pem",
        "*.key"
    )
    
    $wipedCount = 0
    
    foreach ($pattern in $keyFiles) {
        $files = Get-ChildItem -Path $KeysPath -Filter $pattern -Recurse -ErrorAction SilentlyContinue
        foreach ($file in $files) {
            try {
                # Overwrite with random data 3 times
                $size = $file.Length
                if ($size -gt 0) {
                    $random = New-Object byte[] $size
                    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
                    
                    for ($i = 0; $i -lt 3; $i++) {
                        $rng.GetBytes($random)
                        [System.IO.File]::WriteAllBytes($file.FullName, $random)
                    }
                    
                    $rng.Dispose()
                }
                
                # Delete the file
                Remove-Item $file.FullName -Force
                $wipedCount++
                Write-Step "  Wiped: $($file.Name)" "OK"
            } catch {
                Write-Step "  Could not wipe: $($file.Name)" "WARN"
            }
        }
    }
    
    if ($wipedCount -eq 0) {
        Write-Step "No key files found to wipe" "SKIP"
    } else {
        Write-Step "Securely wiped $wipedCount key file(s)" "OK"
    }
}

function Remove-Configuration {
    <#
    .SYNOPSIS
        Remove configuration files
    #>
    
    Write-Step "Removing configuration files..." "INFO"
    
    if (Test-Path $ConfigPath) {
        Remove-Item $ConfigPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Step "Configuration removed" "OK"
    } else {
        Write-Step "No configuration found" "SKIP"
    }
}

function Remove-UserData {
    <#
    .SYNOPSIS
        Remove user data (unless KeepUserData is set)
    #>
    
    if ($KeepUserData) {
        Write-Step "Preserving user data (--KeepUserData)" "SKIP"
        return
    }
    
    Write-Step "Removing user data..." "INFO"
    
    if (Test-Path $DataPath) {
        Remove-Item $DataPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Step "User data removed" "OK"
    } else {
        Write-Step "No user data found" "SKIP"
    }
}

function Remove-Logs {
    <#
    .SYNOPSIS
        Remove log files (unless KeepLogs is set)
    #>
    
    if ($KeepLogs) {
        Write-Step "Preserving logs (--KeepLogs)" "SKIP"
        return
    }
    
    Write-Step "Removing log files..." "INFO"
    
    if (Test-Path $LogsPath) {
        Remove-Item $LogsPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Step "Logs removed" "OK"
    } else {
        Write-Step "No logs found" "SKIP"
    }
}

function Remove-VirtualEnvironment {
    <#
    .SYNOPSIS
        Remove Python virtual environment
    #>
    
    Write-Step "Removing virtual environment..." "INFO"
    
    if (Test-Path $VenvPath) {
        Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Step "Virtual environment removed" "OK"
    } else {
        Write-Step "No virtual environment found" "SKIP"
    }
}

function Remove-KeysDirectory {
    <#
    .SYNOPSIS
        Remove the .akshay directory after key wipe
    #>
    
    Write-Step "Removing keys directory..." "INFO"
    
    if (Test-Path $KeysPath) {
        Remove-Item $KeysPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Step "Keys directory removed" "OK"
    } else {
        Write-Step "Keys directory already removed" "SKIP"
    }
}

function Remove-FromPath {
    <#
    .SYNOPSIS
        Remove AKSHAY from system PATH
    #>
    
    Write-Step "Removing from PATH..." "INFO"
    
    try {
        $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        if ($userPath -and $userPath -match [regex]::Escape($AkshayRoot)) {
            $newPath = ($userPath -split ";" | Where-Object { 
                $_ -and $_ -notmatch [regex]::Escape($AkshayRoot) 
            }) -join ";"
            [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
            Write-Step "Removed from user PATH" "OK"
        } else {
            Write-Step "Not found in user PATH" "SKIP"
        }
    } catch {
        Write-Step "Could not modify PATH: $_" "WARN"
    }
}

function Remove-EnvironmentVariables {
    <#
    .SYNOPSIS
        Remove AKSHAY environment variables
    #>
    
    Write-Step "Removing environment variables..." "INFO"
    
    $vars = @(
        "AKSHAY_HOME",
        "AKSHAY_MODE",
        "AKSHAY_DEMO_MODE",
        "AKSHAY_SAFE_MODE",
        "AKSHAY_RECOVERY_MODE",
        "AKSHAY_NO_VOICE",
        "AKSHAY_CONFIG"
    )
    
    $removedCount = 0
    
    foreach ($var in $vars) {
        $value = [Environment]::GetEnvironmentVariable($var, "User")
        if ($value) {
            [Environment]::SetEnvironmentVariable($var, $null, "User")
            $removedCount++
        }
    }
    
    if ($removedCount -gt 0) {
        Write-Step "Removed $removedCount environment variable(s)" "OK"
    } else {
        Write-Step "No environment variables found" "SKIP"
    }
}

function Write-AuditEntry {
    <#
    .SYNOPSIS
        Write final audit entry before uninstall completes
    #>
    
    if (-not $KeepLogs) {
        return
    }
    
    Write-Step "Writing final audit entry..." "INFO"
    
    $auditFile = Join-Path $LogsPath "uninstall_audit.json"
    $auditEntry = @{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        event = "UNINSTALL"
        details = @{
            keep_user_data = $KeepUserData.IsPresent
            keep_logs = $KeepLogs.IsPresent
            forced = $Force.IsPresent
            pin_verified = (-not $SkipPinCheck.IsPresent)
        }
        host = $env:COMPUTERNAME
        user = $env:USERNAME
    }
    
    try {
        if (-not (Test-Path $LogsPath)) {
            New-Item -ItemType Directory -Path $LogsPath -Force | Out-Null
        }
        $auditEntry | ConvertTo-Json -Depth 10 | Set-Content $auditFile -Encoding UTF8
        Write-Step "Audit entry written" "OK"
    } catch {
        Write-Step "Could not write audit entry" "WARN"
    }
}

function Show-Summary {
    <#
    .SYNOPSIS
        Display uninstall summary
    #>
    
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host " AKSHAY AI CORE has been uninstalled successfully." -ForegroundColor Green
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host ""
    
    if ($KeepUserData) {
        Write-Host "  📁 User data preserved in: $DataPath" -ForegroundColor Yellow
    }
    
    if ($KeepLogs) {
        Write-Host "  📋 Logs preserved in: $LogsPath" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "  • Cryptographic keys have been securely wiped" -ForegroundColor Gray
    Write-Host "  • Configuration has been removed" -ForegroundColor Gray
    Write-Host "  • PATH and environment variables cleaned" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  To fully remove, delete the installation folder:" -ForegroundColor Gray
    Write-Host "  $AkshayRoot" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================
# Main
# ============================================================

function Main {
    Write-UninstallBanner
    
    # Pre-flight checks
    if (-not (Test-Path $AkshayRoot)) {
        Write-Step "AKSHAY AI installation not found at: $AkshayRoot" "ERROR"
        exit 1
    }
    
    # Confirmation
    if (-not $Force) {
        Write-Host "This will permanently remove AKSHAY AI CORE from this system." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "The following will be deleted:" -ForegroundColor Yellow
        Write-Host "  • All cryptographic keys (securely wiped)" -ForegroundColor Red
        Write-Host "  • Configuration files" -ForegroundColor Red
        if (-not $KeepUserData) {
            Write-Host "  • User data" -ForegroundColor Red
        }
        if (-not $KeepLogs) {
            Write-Host "  • Audit logs" -ForegroundColor Red
        }
        Write-Host "  • Python virtual environment" -ForegroundColor Red
        Write-Host ""
        
        $confirm = Read-Host "Are you sure you want to continue? (yes/no)"
        if ($confirm -ne "yes") {
            Write-Host ""
            Write-Host "Uninstall cancelled." -ForegroundColor Green
            exit 0
        }
    }
    
    # PIN verification
    if (-not $SkipPinCheck) {
        $keyStoreExists = Test-Path (Join-Path $KeysPath "keystore.json")
        
        if ($keyStoreExists) {
            Write-Host ""
            Write-Step "PIN verification required" "INFO"
            
            $attempts = 0
            $maxAttempts = 3
            $verified = $false
            
            while ($attempts -lt $maxAttempts -and -not $verified) {
                $attempts++
                $verified = Verify-AdminPIN
                
                if (-not $verified -and $attempts -lt $maxAttempts) {
                    Write-Host "  Attempts remaining: $($maxAttempts - $attempts)" -ForegroundColor Yellow
                }
            }
            
            if (-not $verified) {
                Write-Host ""
                Write-Step "PIN verification failed after $maxAttempts attempts" "ERROR"
                Write-Host ""
                Write-Host "If you have lost your PIN, you can:" -ForegroundColor Yellow
                Write-Host "  1. Use recovery key to reset PIN" -ForegroundColor Gray
                Write-Host "  2. Run with -SkipPinCheck (requires local admin)" -ForegroundColor Gray
                Write-Host ""
                exit 1
            }
        } else {
            Write-Step "No KeyStore found, skipping PIN verification" "SKIP"
        }
    } else {
        Write-Step "PIN check skipped (emergency mode)" "WARN"
        
        # Verify local admin for emergency mode
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if (-not $isAdmin) {
            Write-Step "Emergency uninstall requires administrator privileges" "ERROR"
            Write-Host ""
            Write-Host "Run PowerShell as Administrator and try again." -ForegroundColor Yellow
            exit 1
        }
        Write-Step "Running with administrator privileges" "OK"
    }
    
    Write-Host ""
    Write-Host "Starting uninstallation..." -ForegroundColor Cyan
    Write-Host ""
    
    # Write audit entry first (if keeping logs)
    Write-AuditEntry
    
    # Perform uninstallation steps
    Stop-AkshayServices
    Secure-WipeKeys
    Remove-Configuration
    Remove-UserData
    Remove-Logs
    Remove-VirtualEnvironment
    Remove-KeysDirectory
    Remove-FromPath
    Remove-EnvironmentVariables
    
    # Show summary
    Show-Summary
}

# Run
Main
