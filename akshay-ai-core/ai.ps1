<#
.SYNOPSIS
    AKSHAY AI CORE — Launcher Script
    
.DESCRIPTION
    Launches AKSHAY AI CORE with proper environment activation and mode handling.
    
.PARAMETER Demo
    Start in Demo Mode (restricted capabilities, mock devices).
    
.PARAMETER Safe
    Start in Safe Mode (read-only operations only).
    
.PARAMETER Recovery
    Start in Recovery Mode (limited operations, no plugins).
    
.PARAMETER NoVoice
    Disable voice interface.
    
.PARAMETER Status
    Show system status without starting.

.EXAMPLE
    .\ai.ps1
    .\ai.ps1 -Demo
    .\ai.ps1 -Safe
    .\ai.ps1 -Recovery
    .\ai.ps1 -Status
#>

[CmdletBinding()]
param(
    [switch]$Demo,
    [switch]$Safe,
    [switch]$Recovery,
    [switch]$NoVoice,
    [switch]$Status,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# ============================================================
# CONFIGURATION
# ============================================================

$script:Config = @{
    Version = "1.0.0"
    ProductName = "AKSHAY AI CORE"
    InstallPath = $PSScriptRoot
    VenvPath = Join-Path $PSScriptRoot ".akshay\venv"
    FirstRunFlag = Join-Path $PSScriptRoot ".akshay\first_run.json"
    KeyStoreModule = Join-Path $PSScriptRoot "core\security\keystore.py"
    WizardModule = Join-Path $PSScriptRoot "core\security\wizard.py"
    MainModule = Join-Path $PSScriptRoot "main.py"
}

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

function Write-Banner {
    $banner = @"

    ╔═══════════════════════════════════════════════════════════════╗
    ║     █████╗ ██╗  ██╗███████╗██╗  ██╗ █████╗ ██╗   ██╗         ║
    ║    ██╔══██╗██║ ██╔╝██╔════╝██║  ██║██╔══██╗╚██╗ ██╔╝         ║
    ║    ███████║█████╔╝ ███████╗███████║███████║ ╚████╔╝          ║
    ║    ██╔══██║██╔═██╗ ╚════██║██╔══██║██╔══██║  ╚██╔╝           ║
    ║    ██║  ██║██║  ██╗███████║██║  ██║██║  ██║   ██║            ║
    ║    ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝            ║
    ║                      █████╗ ██╗                               ║
    ║                     ███████║██║     ██████╗ ██████╗ ██████╗ ███████╗
    ║                     ██╔══██║██║    ██╔════╝██╔═══██╗██╔══██╗██╔════╝
    ║                     ██║  ██║██║    ██║     ██║   ██║██████╔╝█████╗
    ║                     ╚═╝  ╚═╝╚═╝    ╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝
    ║                                                               ║
    ║         Personal AI Operating System v$($script:Config.Version)              ║
    ╚═══════════════════════════════════════════════════════════════╝

"@
    Write-Host $banner -ForegroundColor Cyan
}

function Write-DemoBanner {
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "  ║  🎮 DEMO MODE ACTIVE                                      ║" -ForegroundColor Yellow
    Write-Host "  ║  • Mock devices and filesystem                            ║" -ForegroundColor Yellow
    Write-Host "  ║  • No persistent changes                                  ║" -ForegroundColor Yellow
    Write-Host "  ║  • Restricted operations                                  ║" -ForegroundColor Yellow
    Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
}

function Write-SafeBanner {
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "  ║  🔒 SAFE MODE ACTIVE                                      ║" -ForegroundColor Red
    Write-Host "  ║  • Read-only operations only                              ║" -ForegroundColor Red
    Write-Host "  ║  • No file writes, no system changes                      ║" -ForegroundColor Red
    Write-Host "  ║  • Use: ai.ps1 to start normally                          ║" -ForegroundColor Red
    Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""
}

function Write-RecoveryBanner {
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "  ║  🔧 RECOVERY MODE                                         ║" -ForegroundColor Magenta
    Write-Host "  ║  • Limited operations                                     ║" -ForegroundColor Magenta
    Write-Host "  ║  • Plugins disabled                                       ║" -ForegroundColor Magenta
    Write-Host "  ║  • Available: status, audit, policy reset                 ║" -ForegroundColor Magenta
    Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
}

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    
    $icon = switch ($Status) {
        "OK"    { "[✓]"; $color = "Green" }
        "FAIL"  { "[✗]"; $color = "Red" }
        "WARN"  { "[!]"; $color = "Yellow" }
        "INFO"  { "[*]"; $color = "Cyan" }
        default { "[*]"; $color = "White" }
    }
    
    Write-Host "  $icon $Message" -ForegroundColor $color
}

function Test-VenvExists {
    $activateScript = Join-Path $script:Config.VenvPath "Scripts\Activate.ps1"
    return Test-Path $activateScript
}

function Test-FirstRunComplete {
    return Test-Path $script:Config.FirstRunFlag
}

function Get-PythonPath {
    $venvPython = Join-Path $script:Config.VenvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return "python"
}

function Test-KeyStoreStatus {
    $pythonPath = Get-PythonPath
    $keyStoreModule = $script:Config.KeyStoreModule
    
    if (-not (Test-Path $keyStoreModule)) {
        return @{ state = "missing"; needs_pin_setup = $false }
    }
    
    try {
        $result = & $pythonPath $keyStoreModule --install-path $script:Config.InstallPath --action status --output json 2>&1 | Out-String
        return $result | ConvertFrom-Json
    } catch {
        return @{ state = "error"; error = $_.Exception.Message }
    }
}

function Invoke-FirstRunWizard {
    $pythonPath = Get-PythonPath
    $wizardModule = $script:Config.WizardModule
    
    if (-not (Test-Path $wizardModule)) {
        Write-Status "First-run wizard module not found" "FAIL"
        return $false
    }
    
    Write-Host ""
    Write-Host "  ════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "                    FIRST-RUN SETUP WIZARD" -ForegroundColor Cyan
    Write-Host "  ════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    
    try {
        & $pythonPath $wizardModule --install-path $script:Config.InstallPath
        return $LASTEXITCODE -eq 0
    } catch {
        Write-Status "Wizard failed: $_" "FAIL"
        return $false
    }
}

function Start-AkshayAI {
    param(
        [switch]$Demo,
        [switch]$Safe,
        [switch]$Recovery,
        [switch]$NoVoice
    )
    
    $pythonPath = Get-PythonPath
    $mainModule = $script:Config.MainModule
    
    # Build environment variables
    $env:AKSHAY_INSTALL_PATH = $script:Config.InstallPath
    
    if ($Demo) {
        $env:AKSHAY_MODE = "demo"
        $env:AKSHAY_DEMO_MODE = "true"
    } elseif ($Safe) {
        $env:AKSHAY_MODE = "safe"
        $env:AKSHAY_SAFE_MODE = "true"
    } elseif ($Recovery) {
        $env:AKSHAY_MODE = "recovery"
        $env:AKSHAY_RECOVERY_MODE = "true"
        $env:AKSHAY_SAFE_MODE = "true"  # Recovery implies safe mode
    } else {
        $env:AKSHAY_MODE = "normal"
    }
    
    if ($NoVoice) {
        $env:VOICE_INTERFACE_ENABLED = "false"
    }
    
    # Start the system
    try {
        & $pythonPath $mainModule run
    } catch {
        Write-Status "Failed to start: $_" "FAIL"
        return $false
    }
    
    return $true
}

function Show-SystemStatus {
    Write-Banner
    
    Write-Host "  System Status" -ForegroundColor White
    Write-Host "  ─────────────" -ForegroundColor DarkGray
    
    # Check venv
    if (Test-VenvExists) {
        Write-Status "Virtual environment: OK" "OK"
    } else {
        Write-Status "Virtual environment: Missing" "FAIL"
        Write-Status "Run install.ps1 to set up" "INFO"
        return
    }
    
    # Check first-run
    if (Test-FirstRunComplete) {
        Write-Status "First-run setup: Complete" "OK"
    } else {
        Write-Status "First-run setup: Pending" "WARN"
    }
    
    # Check key store
    $keyStatus = Test-KeyStoreStatus
    
    switch ($keyStatus.state) {
        "unlocked" {
            if ($keyStatus.needs_pin_setup) {
                Write-Status "Key store: Needs PIN setup" "WARN"
            } else {
                Write-Status "Key store: Unlocked" "OK"
            }
        }
        "locked" {
            Write-Status "Key store: Locked (PIN required)" "INFO"
        }
        "safe_mode" {
            $remaining = $keyStatus.lockout_remaining
            Write-Status "Key store: SAFE MODE (lockout: ${remaining}s)" "FAIL"
        }
        "missing" {
            Write-Status "Key store: Module not found" "FAIL"
        }
        default {
            Write-Status "Key store: $($keyStatus.state)" "WARN"
        }
    }
    
    # Check main files
    if (Test-Path $script:Config.MainModule) {
        Write-Status "Main module: OK" "OK"
    } else {
        Write-Status "Main module: Missing" "FAIL"
    }
    
    Write-Host ""
}

function Show-Help {
    Write-Banner
    
    Write-Host "  Usage: .\ai.ps1 [options]" -ForegroundColor White
    Write-Host ""
    Write-Host "  Options:" -ForegroundColor Yellow
    Write-Host "    (none)        Start in Normal Mode"
    Write-Host "    -Demo         Start in Demo Mode (mock devices, restricted)"
    Write-Host "    -Safe         Start in Safe Mode (read-only operations)"
    Write-Host "    -Recovery     Start in Recovery Mode (diagnostics only)"
    Write-Host "    -NoVoice      Disable voice interface"
    Write-Host "    -Status       Show system status"
    Write-Host "    -Help         Show this help"
    Write-Host ""
    Write-Host "  Examples:" -ForegroundColor Yellow
    Write-Host "    .\ai.ps1                  # Normal startup"
    Write-Host "    .\ai.ps1 -Demo            # Demo mode for testing"
    Write-Host "    .\ai.ps1 -Recovery        # Recovery mode"
    Write-Host ""
}

# ============================================================
# MAIN ENTRY POINT
# ============================================================

function Main {
    # Handle help
    if ($Help) {
        Show-Help
        return
    }
    
    # Handle status
    if ($Status) {
        Show-SystemStatus
        return
    }
    
    Write-Banner
    
    # Check venv exists
    if (-not (Test-VenvExists)) {
        Write-Status "Virtual environment not found" "FAIL"
        Write-Status "Please run install.ps1 first" "INFO"
        Write-Host ""
        exit 1
    }
    
    # Activate venv
    $activateScript = Join-Path $script:Config.VenvPath "Scripts\Activate.ps1"
    . $activateScript
    
    Write-Status "Virtual environment activated" "OK"
    
    # Check if first-run is needed
    if (-not (Test-FirstRunComplete)) {
        Write-Status "First-run setup required" "WARN"
        
        $wizardSuccess = Invoke-FirstRunWizard
        
        if (-not $wizardSuccess) {
            Write-Status "First-run setup failed or cancelled" "FAIL"
            Write-Host ""
            exit 1
        }
        
        Write-Status "First-run setup complete" "OK"
    }
    
    # Check key store state (for non-demo mode)
    if (-not $Demo) {
        $keyStatus = Test-KeyStoreStatus
        
        if ($keyStatus.state -eq "safe_mode") {
            Write-Status "System in SAFE MODE due to failed PIN attempts" "FAIL"
            Write-Status "Wait $($keyStatus.lockout_remaining) seconds or use recovery" "INFO"
            Write-Host ""
            
            if (-not $Recovery) {
                Write-Host "  Starting in Recovery Mode automatically..." -ForegroundColor Yellow
                $Recovery = $true
            }
        }
    }
    
    # Show mode banner
    if ($Demo) {
        Write-DemoBanner
    } elseif ($Safe) {
        Write-SafeBanner
    } elseif ($Recovery) {
        Write-RecoveryBanner
    }
    
    Write-Status "Starting AKSHAY AI CORE..." "INFO"
    Write-Host ""
    
    # Start the system
    Start-AkshayAI -Demo:$Demo -Safe:$Safe -Recovery:$Recovery -NoVoice:$NoVoice
}

# Run
Main
