<#
.SYNOPSIS
    AKSHAY AI CORE - Windows Installer
    
.DESCRIPTION
    Installs AKSHAY AI CORE on Windows 10/11 systems.
    Creates isolated environment, configures security, and sets up launchers.
    
.PARAMETER Demo
    Install in Demo Mode with restricted capabilities.
    
.PARAMETER Portable
    Portable installation - no PATH modification or shortcuts.
    
.PARAMETER InstallPath
    Custom installation path. Default: $env:USERPROFILE\AkshayAI
    
.PARAMETER Quiet
    Suppress non-essential output.
    
.PARAMETER Unattended
    Skip all prompts, use defaults.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Demo
    .\install.ps1 -Portable
    .\install.ps1 -InstallPath "D:\MyAI"
    
.NOTES
    Version: 1.0.0
    Author: AKSHAY AI CORE Team
#>

[CmdletBinding()]
param(
    [switch]$Demo,
    [switch]$Portable,
    [string]$InstallPath = "$env:USERPROFILE\AkshayAI",
    [switch]$Quiet,
    [switch]$Unattended
)

# ============================================================
# CONFIGURATION
# ============================================================

$script:Config = @{
    Version = "1.0.0"
    ProductName = "AKSHAY AI CORE"
    MinWindowsVersion = "10.0"
    MinPythonVersion = "3.10"
    MaxPythonVersion = "3.13"  # 3.14+ may lack prebuilt wheels
    WarnPythonVersion = "3.14" # Warn but allow
    MinPowerShellVersion = "5.1"
    MinDiskSpaceGB = 2
    MinRAMGB = 4
    RequiredPythonModules = @("pip", "venv")
}

$script:InstallState = @{
    StartTime = Get-Date
    Success = $false
    CreatedFolders = @()
    PathModified = $false
    ShortcutsCreated = @()
    VenvCreated = $false
    LogFile = $null
    Errors = @()
}

$script:Colors = @{
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "Cyan"
    Highlight = "Magenta"
    Dim = "DarkGray"
}

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

function Write-Banner {
    $banner = @"

    ================================================================
    |                                                              |
    |     AKSHAY AI CORE                                           |
    |                                                              |
    |     Personal AI Operating System                             |
    |                                                              |
    |                    INSTALLER v$($script:Config.Version)                            |
    |                                                              |
    ================================================================

"@
    Write-Host $banner -ForegroundColor Cyan
}

function Write-Step {
    param(
        [string]$Message,
        [string]$Status = "INFO",
        [switch]$NoNewline
    )
    
    $icon = switch ($Status) {
        "OK"      { "[OK]"; $color = $script:Colors.Success }
        "FAIL"    { "[X]"; $color = $script:Colors.Error }
        "WARN"    { "[!]"; $color = $script:Colors.Warning }
        "INFO"    { "[*]"; $color = $script:Colors.Info }
        "SKIP"    { "[-]"; $color = $script:Colors.Dim }
        default   { "[*]"; $color = $script:Colors.Info }
    }
    
    if ($NoNewline) {
        Write-Host "  $icon $Message" -ForegroundColor $color -NoNewline
    } else {
        Write-Host "  $icon $Message" -ForegroundColor $color
    }
}

function Write-Progress-Bar {
    param(
        [int]$Current,
        [int]$Total,
        [string]$Activity
    )
    
    $percent = [math]::Round(($Current / $Total) * 100)
    $filled = [math]::Round($percent / 5)
    $empty = 20 - $filled
    
    $bar = "#" * $filled + "-" * $empty
    
    Write-Host "`r  [$bar] $percent% - $Activity" -NoNewline -ForegroundColor Cyan
    
    if ($Current -eq $Total) {
        Write-Host ""
    }
}

function Write-Section {
    param([string]$Title)
    
    Write-Host ""
    Write-Host "  ----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  $Title" -ForegroundColor White
    Write-Host "  ----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ""
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    
    if ($script:InstallState.LogFile) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $logEntry = "[$timestamp] [$Level] $Message"
        Add-Content -Path $script:InstallState.LogFile -Value $logEntry -ErrorAction SilentlyContinue
    }
}

function Initialize-Logging {
    # Create temp log location first, move to install dir later
    $tempLogDir = Join-Path $env:TEMP "AkshayAI_Install"
    if (-not (Test-Path $tempLogDir)) {
        New-Item -ItemType Directory -Path $tempLogDir -Force | Out-Null
    }
    
    $script:InstallState.LogFile = Join-Path $tempLogDir "install_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
    
    Write-Log "Installation started"
    Write-Log "Install Path: $InstallPath"
    Write-Log "Mode: $(if ($Demo) {'Demo'} elseif ($Portable) {'Portable'} else {'Normal'})"
    Write-Log "PowerShell Version: $($PSVersionTable.PSVersion)"
    Write-Log "OS: $([System.Environment]::OSVersion.VersionString)"
}

function Get-UserConfirmation {
    param(
        [string]$Message,
        [bool]$Default = $true
    )
    
    if ($Unattended) {
        return $Default
    }
    
    $defaultText = if ($Default) { "[Y/n]" } else { "[y/N]" }
    Write-Host "  $Message $defaultText " -NoNewline -ForegroundColor Yellow
    
    $response = Read-Host
    
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $Default
    }
    
    return $response -match '^[Yy]'
}

# ============================================================
# PREFLIGHT CHECK FUNCTIONS
# ============================================================

function Test-WindowsVersion {
    Write-Step "Checking Windows version..." -Status "INFO" -NoNewline
    
    try {
        $os = [System.Environment]::OSVersion
        $version = $os.Version
        
        # Windows 10 is version 10.0.x
        $isValid = $version.Major -ge 10
        
        if ($isValid) {
            $buildNumber = (Get-CimInstance Win32_OperatingSystem).BuildNumber
            $osName = (Get-CimInstance Win32_OperatingSystem).Caption
            Write-Host " $osName (Build $buildNumber)" -ForegroundColor Green
            Write-Log "Windows version check passed: $osName Build $buildNumber"
            return $true
        } else {
            Write-Host " Windows $($version.Major).$($version.Minor) - UNSUPPORTED" -ForegroundColor Red
            Write-Log "Windows version check failed: $($version.Major).$($version.Minor)" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Log "Windows version check error: $_" -Level "ERROR"
        return $false
    }
}

function Test-PowerShellVersion {
    Write-Step "Checking PowerShell version..." -Status "INFO" -NoNewline
    
    try {
        $version = $PSVersionTable.PSVersion
        $minVersion = [Version]$script:Config.MinPowerShellVersion
        
        if ($version -ge $minVersion) {
            Write-Host " $version" -ForegroundColor Green
            Write-Log "PowerShell version check passed: $version"
            return $true
        } else {
            Write-Host " $version - REQUIRES $($script:Config.MinPowerShellVersion)+" -ForegroundColor Red
            Write-Log "PowerShell version check failed: $version < $minVersion" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Log "PowerShell version check error: $_" -Level "ERROR"
        return $false
    }
}

function Test-PythonInstallation {
    Write-Step "Checking Python installation..." -Status "INFO" -NoNewline
    
    try {
        # Try py launcher with specific versions first (more control)
        $pythonCommands = @("py -3.13", "py -3.12", "py -3.11", "py -3.10", "python", "python3", "py -3")
        $pythonInvocation = $null
        $pythonDisplay = $null
        $pythonVersion = $null
        $minVersion = [Version]$script:Config.MinPythonVersion
        $maxVersion = [Version]$script:Config.MaxPythonVersion
        $warnVersion = [Version]$script:Config.WarnPythonVersion
        
        foreach ($cmd in $pythonCommands) {
            try {
                # Store python invocation as an array to avoid issues with multi-part commands
                # like "py -3.13".
                if ($cmd -match '^py\s+(-\d+(?:\.\d+)?)$') {
                    $candidateInvocation = @('py', $Matches[1])
                } else {
                    $candidateInvocation = @($cmd)
                }

                $exe = $candidateInvocation[0]
                $exeArgs = @()
                if ($candidateInvocation.Count -gt 1) {
                    $exeArgs = $candidateInvocation[1..($candidateInvocation.Count - 1)]
                }

                $output = & $exe @exeArgs --version 2>&1
                
                if ($output -match 'Python (\d+\.\d+\.\d+)') {
                    $pythonVersion = [Version]$Matches[1]
                    $majorMinor = [Version]"$($pythonVersion.Major).$($pythonVersion.Minor)"
                    
                    # Prefer versions within recommended range
                    if ($majorMinor -ge $minVersion -and $majorMinor -le $maxVersion) {
                        $pythonInvocation = $candidateInvocation
                        $pythonDisplay = ($candidateInvocation -join ' ')
                        break
                    }
                    # Accept newer versions with warning
                    elseif ($majorMinor -ge $minVersion -and -not $pythonInvocation) {
                        $pythonInvocation = $candidateInvocation
                        $pythonDisplay = ($candidateInvocation -join ' ')
                        $script:PythonVersionWarning = $true
                        # Keep looking for better version
                    }
                }
            } catch {
                continue
            }
        }
        
        if ($pythonInvocation) {
            if ($script:PythonVersionWarning) {
                Write-Host " Python $pythonVersion ($pythonDisplay) [EXPERIMENTAL]" -ForegroundColor Yellow
                Write-Log "Python check passed with warning: $pythonVersion via $pythonDisplay (may lack prebuilt wheels)" -Level "WARN"
            } else {
                Write-Host " Python $pythonVersion ($pythonDisplay)" -ForegroundColor Green
                Write-Log "Python check passed: $pythonVersion via $pythonDisplay"
            }
            $script:PythonInvocation = $pythonInvocation
            $script:PythonDisplay = $pythonDisplay
            return $true
        } else {
            Write-Host " NOT FOUND or version < $($script:Config.MinPythonVersion)" -ForegroundColor Red
            Write-Log "Python check failed: Not found or version too low" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
        Write-Log "Python check error: $_" -Level "ERROR"
        return $false
    }
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $inv = $script:PythonInvocation
    if (-not $inv -or $inv.Count -lt 1) {
        throw "Python invocation is not initialized"
    }

    $exe = $inv[0]
    $exeArgs = @()
    if ($inv.Count -gt 1) {
        $exeArgs = $inv[1..($inv.Count - 1)]
    }

    return & $exe @exeArgs @Args
}

function Test-PythonModules {
    Write-Step "Checking Python modules..." -Status "INFO" -NoNewline
    
    try {
        $missing = @()

        # Check pip (attempt to repair with ensurepip if missing)
        $pipCheck = Invoke-Python -Args @('-m', 'pip', '--version') 2>&1
        if ($LASTEXITCODE -ne 0) {
            $ensurePip = Invoke-Python -Args @('-m', 'ensurepip', '--upgrade') 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pipCheck = Invoke-Python -Args @('-m', 'pip', '--version') 2>&1
            }
        }
        if ($LASTEXITCODE -ne 0) {
            $missing += "pip"
            Write-Log "pip check output: $pipCheck" -Level "ERROR"
        }

        # Check venv
        $venvCheck = Invoke-Python -Args @('-c', 'import venv') 2>&1
        if ($LASTEXITCODE -ne 0) {
            $missing += "venv"
            Write-Log "venv check output: $venvCheck" -Level "ERROR"
        }
        
        if ($missing.Count -eq 0) {
            Write-Host " pip, venv" -ForegroundColor Green
            Write-Log "Python modules check passed: pip, venv available"
            return $true
        } else {
            Write-Host " MISSING: $($missing -join ', ')" -ForegroundColor Red
            Write-Log "Python modules check failed: Missing $($missing -join ', ')" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Log "Python modules check error: $_" -Level "ERROR"
        return $false
    }
}

function Test-DiskSpace {
    Write-Step "Checking disk space..." -Status "INFO" -NoNewline
    
    try {
        # Get the drive from install path
        $drive = Split-Path -Qualifier $InstallPath
        if (-not $drive) {
            $drive = "C:"
        }
        
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$drive'"
        
        if ($disk) {
            $freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 2)
            $requiredGB = $script:Config.MinDiskSpaceGB
            
            if ($freeSpaceGB -ge $requiredGB) {
                Write-Host " ${freeSpaceGB}GB free on $drive (need ${requiredGB}GB)" -ForegroundColor Green
                Write-Log "Disk space check passed: ${freeSpaceGB}GB free on $drive"
                return $true
            } else {
                Write-Host " ${freeSpaceGB}GB free - NEED ${requiredGB}GB" -ForegroundColor Red
                Write-Log "Disk space check failed: ${freeSpaceGB}GB < ${requiredGB}GB" -Level "ERROR"
                return $false
            }
        } else {
            Write-Host " Cannot determine disk space for $drive" -ForegroundColor Yellow
            Write-Log "Disk space check warning: Cannot determine for $drive" -Level "WARN"
            return $true  # Proceed with warning
        }
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Log "Disk space check error: $_" -Level "ERROR"
        return $false
    }
}

function Test-SystemMemory {
    Write-Step "Checking system memory..." -Status "INFO" -NoNewline
    
    try {
        $memory = Get-CimInstance Win32_ComputerSystem
        $totalRAMGB = [math]::Round($memory.TotalPhysicalMemory / 1GB, 2)
        $requiredGB = $script:Config.MinRAMGB
        
        if ($totalRAMGB -ge $requiredGB) {
            Write-Host " ${totalRAMGB}GB RAM (need ${requiredGB}GB)" -ForegroundColor Green
            Write-Log "Memory check passed: ${totalRAMGB}GB RAM"
            return $true
        } else {
            Write-Host " ${totalRAMGB}GB RAM - NEED ${requiredGB}GB" -ForegroundColor Red
            Write-Log "Memory check failed: ${totalRAMGB}GB < ${requiredGB}GB" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Log "Memory check error: $_" -Level "ERROR"
        return $false
    }
}

function Test-AdminRights {
    Write-Step "Checking administrator rights..." -Status "INFO" -NoNewline
    
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        
        if ($isAdmin) {
            Write-Host " Administrator" -ForegroundColor Green
            Write-Log "Admin check: Running as administrator"
            $script:IsAdmin = $true
        } else {
            Write-Host " Standard User (some features limited)" -ForegroundColor Yellow
            Write-Log "Admin check: Running as standard user" -Level "WARN"
            $script:IsAdmin = $false
        }
        
        return $true  # Not a failure, just informational
    } catch {
        Write-Host " Cannot determine" -ForegroundColor Yellow
        Write-Log "Admin check error: $_" -Level "WARN"
        $script:IsAdmin = $false
        return $true
    }
}

function Test-ExistingInstallation {
    Write-Step "Checking for existing installation..." -Status "INFO" -NoNewline
    
    if (Test-Path $InstallPath) {
        $versionFile = Join-Path $InstallPath ".akshay\version.txt"
        
        if (Test-Path $versionFile) {
            $existingVersion = Get-Content $versionFile -Raw
            Write-Host " Found v$($existingVersion.Trim())" -ForegroundColor Yellow
            Write-Log "Existing installation found: v$($existingVersion.Trim())" -Level "WARN"
            $script:ExistingInstall = $true
        } else {
            Write-Host " Folder exists but incomplete" -ForegroundColor Yellow
            Write-Log "Existing folder found but incomplete" -Level "WARN"
            $script:ExistingInstall = $false
        }
    } else {
        Write-Host " Clean install" -ForegroundColor Green
        Write-Log "No existing installation found"
        $script:ExistingInstall = $false
    }
    
    return $true
}

function Test-NetworkConnectivity {
    Write-Step "Checking network connectivity..." -Status "INFO" -NoNewline
    
    try {
        $testUrls = @("https://pypi.org", "https://files.pythonhosted.org")
        $connected = $false
        
        foreach ($url in $testUrls) {
            try {
                $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    $connected = $true
                    break
                }
            } catch {
                continue
            }
        }
        
        if ($connected) {
            Write-Host " Connected (PyPI accessible)" -ForegroundColor Green
            Write-Log "Network check passed: PyPI accessible"
            $script:NetworkAvailable = $true
        } else {
            Write-Host " Limited (offline install possible)" -ForegroundColor Yellow
            Write-Log "Network check: PyPI not accessible, offline mode" -Level "WARN"
            $script:NetworkAvailable = $false
        }
        
        return $true  # Not a critical failure
    } catch {
        Write-Host " Unknown" -ForegroundColor Yellow
        Write-Log "Network check error: $_" -Level "WARN"
        $script:NetworkAvailable = $false
        return $true
    }
}

function Invoke-PreflightChecks {
    Write-Section "PREFLIGHT CHECKS"
    
    $checks = @(
        @{ Name = "Windows"; Function = { Test-WindowsVersion }; Critical = $true },
        @{ Name = "PowerShell"; Function = { Test-PowerShellVersion }; Critical = $true },
        @{ Name = "Python"; Function = { Test-PythonInstallation }; Critical = $true },
        @{ Name = "PythonModules"; Function = { Test-PythonModules }; Critical = $true },
        @{ Name = "DiskSpace"; Function = { Test-DiskSpace }; Critical = $true },
        @{ Name = "Memory"; Function = { Test-SystemMemory }; Critical = $true },
        @{ Name = "AdminRights"; Function = { Test-AdminRights }; Critical = $false },
        @{ Name = "ExistingInstall"; Function = { Test-ExistingInstallation }; Critical = $false },
        @{ Name = "Network"; Function = { Test-NetworkConnectivity }; Critical = $false }
    )
    
    $failedCritical = @()
    $warnings = @()
    
    foreach ($check in $checks) {
        $result = & $check.Function
        
        if (-not $result) {
            if ($check.Critical) {
                $failedCritical += $check.Name
            } else {
                $warnings += $check.Name
            }
        }
    }
    
    Write-Host ""
    
    if ($failedCritical.Count -gt 0) {
        Write-Step "PREFLIGHT FAILED: $($failedCritical -join ', ')" -Status "FAIL"
        Write-Log "Preflight failed: $($failedCritical -join ', ')" -Level "ERROR"
        return $false
    }
    
    if ($warnings.Count -gt 0) {
        Write-Step "Warnings: $($warnings -join ', ')" -Status "WARN"
    }
    
    Write-Step "All critical checks passed" -Status "OK"
    Write-Log "All preflight checks passed"
    return $true
}

# ============================================================
# FOLDER SETUP FUNCTIONS
# ============================================================

function New-InstallDirectory {
    param(
        [string]$Path,
        [string]$Description,
        [bool]$Hidden = $false,
        [bool]$ReadOnly = $false
    )
    
    try {
        if (-not (Test-Path $Path)) {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
            $script:InstallState.CreatedFolders += $Path
            Write-Log "Created directory: $Path"
        }
        
        # Set attributes
        $item = Get-Item $Path -Force
        
        if ($Hidden) {
            $item.Attributes = $item.Attributes -bor [System.IO.FileAttributes]::Hidden
            Write-Log "Set hidden attribute: $Path"
        }
        
        if ($ReadOnly) {
            $item.Attributes = $item.Attributes -bor [System.IO.FileAttributes]::ReadOnly
            Write-Log "Set read-only attribute: $Path"
        }
        
        return $true
    } catch {
        Write-Log "Failed to create directory $Path : $_" -Level "ERROR"
        $script:InstallState.Errors += "Failed to create $Description : $_"
        return $false
    }
}

function Set-DirectoryPermissions {
    param(
        [string]$Path,
        [string]$AccessLevel  # "ReadOnly", "ReadWrite", "Full"
    )
    
    try {
        $acl = Get-Acl $Path
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        
        switch ($AccessLevel) {
            "ReadOnly" {
                $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                    $currentUser,
                    "ReadAndExecute",
                    "ContainerInherit,ObjectInherit",
                    "None",
                    "Allow"
                )
            }
            "ReadWrite" {
                $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                    $currentUser,
                    "Modify",
                    "ContainerInherit,ObjectInherit",
                    "None",
                    "Allow"
                )
            }
            "Full" {
                $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                    $currentUser,
                    "FullControl",
                    "ContainerInherit,ObjectInherit",
                    "None",
                    "Allow"
                )
            }
        }
        
        $acl.SetAccessRule($rule)
        Set-Acl -Path $Path -AclObject $acl
        
        Write-Log "Set $AccessLevel permissions on: $Path"
        return $true
    } catch {
        Write-Log "Failed to set permissions on $Path : $_" -Level "WARN"
        return $false  # Non-critical, continue
    }
}

function Initialize-FolderStructure {
    Write-Section "CREATING FOLDER STRUCTURE"
    
    $folders = @(
        # Main installation directory
        @{ Path = $InstallPath; Desc = "Installation root"; Hidden = $false; ReadOnly = $false; Access = "Full" },
        
        # Core application (read-only after install)
        @{ Path = "$InstallPath\core"; Desc = "Application code"; Hidden = $false; ReadOnly = $false; Access = "ReadOnly" },
        
        # User-writable directories
        @{ Path = "$InstallPath\config"; Desc = "Configuration"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\data"; Desc = "User data"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\data\memory"; Desc = "AI memory"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\data\face_data"; Desc = "Face recognition"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\data\vault"; Desc = "Encrypted vault"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\data\vector_db"; Desc = "Vector database"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\logs"; Desc = "Logs"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\policies"; Desc = "Security policies"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\policies\custom"; Desc = "Custom policies"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\plugins"; Desc = "Plugins"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        @{ Path = "$InstallPath\plugins\custom"; Desc = "Custom plugins"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        
        # Demo mode assets
        @{ Path = "$InstallPath\demo"; Desc = "Demo assets"; Hidden = $false; ReadOnly = $false; Access = "ReadWrite" },
        
        # Internal state (hidden)
        @{ Path = "$InstallPath\.akshay"; Desc = "Internal state"; Hidden = $true; ReadOnly = $false; Access = "Full" },
        @{ Path = "$InstallPath\.akshay\sessions"; Desc = "Sessions"; Hidden = $true; ReadOnly = $false; Access = "Full" }
    )
    
    $totalFolders = $folders.Count
    $currentFolder = 0
    $success = $true
    
    foreach ($folder in $folders) {
        $currentFolder++
        Write-Progress-Bar -Current $currentFolder -Total $totalFolders -Activity $folder.Desc
        
        $created = New-InstallDirectory -Path $folder.Path -Description $folder.Desc -Hidden $folder.Hidden -ReadOnly $folder.ReadOnly
        
        if (-not $created) {
            $success = $false
            Write-Step "Failed to create: $($folder.Desc)" -Status "FAIL"
            continue
        }
        
        # Set permissions (non-critical)
        Set-DirectoryPermissions -Path $folder.Path -AccessLevel $folder.Access | Out-Null
        
        Start-Sleep -Milliseconds 100  # Visual feedback
    }
    
    Write-Host ""
    
    if ($success) {
        Write-Step "Folder structure created at: $InstallPath" -Status "OK"
        Write-Log "Folder structure created successfully"
    } else {
        Write-Step "Some folders could not be created" -Status "WARN"
        Write-Log "Folder structure partially created" -Level "WARN"
    }
    
    return $success
}

function Show-FolderSummary {
    Write-Host ""
    Write-Host "  Folder Structure:" -ForegroundColor White
    Write-Host "  -----------------" -ForegroundColor DarkGray
    
    $structure = @"
  $InstallPath\
    +-- core\          [Read-Only]  Application code
    +-- config\        [Read-Write] Settings & API keys
    +-- data\          [Read-Write] User data
    |   +-- memory\                 AI memory database
    |   +-- face_data\              Face recognition
    |   +-- vault\                  Encrypted secrets
    |   +-- vector_db\              Embeddings
    +-- logs\          [Read-Write] Application logs
    +-- policies\      [Read-Write] Security policies
    +-- plugins\       [Read-Write] Extensions
    +-- demo\          [Read-Write] Demo mode assets
    +-- .akshay\       [Hidden]     Internal state
"@
    
    Write-Host $structure -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================
# VIRTUAL ENVIRONMENT FUNCTIONS
# ============================================================

function Initialize-VirtualEnvironment {
    Write-Section "CREATING VIRTUAL ENVIRONMENT"
    
    $venvPath = Join-Path $InstallPath ".akshay\venv"
    
    Write-Step "Creating Python virtual environment..." -Status "INFO" -NoNewline
    
    try {
        # Create venv
        $result = Invoke-Python -Args @('-m', 'venv', $venvPath) 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Log "Failed to create venv: $result" -Level "ERROR"
            $script:InstallState.Errors += "Failed to create virtual environment"
            return $false
        }
        
        # Verify venv was created
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        if (-not (Test-Path $activateScript)) {
            Write-Host " FAILED (no activate script)" -ForegroundColor Red
            Write-Log "Venv created but no activate script found" -Level "ERROR"
            $script:InstallState.Errors += "Virtual environment incomplete"
            return $false
        }
        
        Write-Host " OK" -ForegroundColor Green
        Write-Log "Virtual environment created at: $venvPath"
        $script:InstallState.VenvCreated = $true
        $script:VenvPath = $venvPath
        
        # Upgrade pip
        Write-Step "Upgrading pip..." -Status "INFO" -NoNewline
        $pipPath = Join-Path $venvPath "Scripts\pip.exe"
        $pythonPath = Join-Path $venvPath "Scripts\python.exe"
        
        $upgradeResult = & $pythonPath -m pip install --upgrade pip 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK" -ForegroundColor Green
            Write-Log "Pip upgraded successfully"
        } else {
            Write-Host " WARN (continuing)" -ForegroundColor Yellow
            Write-Log "Pip upgrade warning: $upgradeResult" -Level "WARN"
        }
        
        return $true
    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
        Write-Log "Venv creation error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Virtual environment creation failed: $_"
        return $false
    }
}

function Install-Dependencies {
    Write-Section "INSTALLING DEPENDENCIES"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $pipPath = Join-Path $venvPath "Scripts\pip.exe"
    
    # Find requirements.txt - check multiple locations
    $requirementsLocations = @(
        (Join-Path $PSScriptRoot "..\requirements.txt"),
        (Join-Path $PSScriptRoot "requirements.txt"),
        (Join-Path $InstallPath "core\requirements.txt")
    )
    
    $requirementsFile = $null
    foreach ($loc in $requirementsLocations) {
        if (Test-Path $loc) {
            $requirementsFile = (Resolve-Path $loc).Path
            break
        }
    }
    
    if (-not $requirementsFile) {
        Write-Step "requirements.txt not found - skipping dependencies" -Status "WARN"
        Write-Log "No requirements.txt found" -Level "WARN"
        return $true  # Not a fatal error for now
    }
    
    Write-Step "Found requirements: $requirementsFile" -Status "INFO"
    Write-Log "Using requirements file: $requirementsFile"
    
    # Count dependencies for progress
    $deps = Get-Content $requirementsFile | Where-Object { $_ -match '^\w' -and $_ -notmatch '^#' }
    $totalDeps = $deps.Count
    
    # Warn about experimental Python version
    if ($script:PythonVersionWarning) {
        Write-Host ""
        Write-Step "NOTE: Using experimental Python version - some packages may need compilation" -Status "WARN"
        Write-Host ""
    }
    
    Write-Step "Installing $totalDeps packages (this may take several minutes)..." -Status "INFO"
    Write-Host ""
    
    # Install dependencies
    try {
        $errorFile = Join-Path $env:TEMP "pip_error.txt"
        $outputFile = Join-Path $env:TEMP "pip_output.txt"
        
        # Build argument string (Start-Process needs string, not array with quotes)
        $installArgsStr = "-m pip install -r `"$requirementsFile`" --prefer-binary --disable-pip-version-check"
        
        # Run pip install
        $process = Start-Process -FilePath $pythonPath -ArgumentList $installArgsStr -NoNewWindow -Wait -PassThru `
            -RedirectStandardError $errorFile -RedirectStandardOutput $outputFile
        
        if ($process.ExitCode -ne 0) {
            $pipError = ""
            if (Test-Path $errorFile) {
                $pipError = Get-Content $errorFile -Raw -ErrorAction SilentlyContinue
            }
            
            Write-Host ""
            Write-Step "Dependency installation failed (exit code: $($process.ExitCode))" -Status "FAIL"
            
            # Show more helpful error info
            if ($pipError -match "metadata-generation-failed|subprocess-exited-with-error") {
                Write-Host ""
                Write-Host "  Some packages require compilation but no compiler is available." -ForegroundColor Yellow
                Write-Host "  Options:" -ForegroundColor Yellow
                Write-Host "    1. Install Python 3.10-3.13 (recommended)" -ForegroundColor Cyan
                Write-Host "    2. Install Visual Studio Build Tools" -ForegroundColor Cyan
                Write-Host ""
            }
            
            Write-Log "Pip install failed with exit code $($process.ExitCode): $pipError" -Level "ERROR"
            $script:InstallState.Errors += "Dependency installation failed"
            return $false
        }
        
        Write-Host ""
        Write-Step "Dependencies installed successfully" -Status "OK"
        Write-Log "All dependencies installed"
        
        # Log installed packages
        Write-Step "Logging installed versions..." -Status "INFO" -NoNewline
        $freezeOutput = & $pythonPath -m pip freeze 2>&1
        $packageLog = Join-Path $InstallPath "logs\installed_packages.txt"
        $freezeOutput | Out-File -FilePath $packageLog -Force
        Write-Host " OK" -ForegroundColor Green
        Write-Log "Package list saved to: $packageLog"
        
        return $true
    } catch {
        Write-Host ""
        Write-Step "Error during dependency installation: $_" -Status "FAIL"
        Write-Log "Dependency installation error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Dependency installation exception: $_"
        return $false
    }
}

function Test-CoreImports {
    Write-Section "VERIFYING CORE IMPORTS"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    
    # Core modules to verify
    $coreModules = @(
        @{ Name = "fastapi"; Import = "import fastapi" },
        @{ Name = "uvicorn"; Import = "import uvicorn" },
        @{ Name = "pydantic"; Import = "import pydantic" },
        @{ Name = "sqlalchemy"; Import = "import sqlalchemy" },
        @{ Name = "cryptography"; Import = "from cryptography.hazmat.primitives import serialization" },
        @{ Name = "jwt"; Import = "import jwt" },
        @{ Name = "chromadb"; Import = "import chromadb" },
        @{ Name = "openai"; Import = "import openai" },
        @{ Name = "httpx"; Import = "import httpx" },
        @{ Name = "yaml"; Import = "import yaml" }
    )
    
    $allPassed = $true
    $failedImports = @()
    
    foreach ($module in $coreModules) {
        Write-Step "Checking $($module.Name)..." -Status "INFO" -NoNewline
        
        try {
            $testCmd = "$($module.Import); print('OK')"
            $result = & $pythonPath -c $testCmd 2>&1
            
            if ($result -match "OK") {
                Write-Host " OK" -ForegroundColor Green
                Write-Log "Import verified: $($module.Name)"
            } else {
                Write-Host " FAILED" -ForegroundColor Red
                Write-Log "Import failed: $($module.Name) - $result" -Level "ERROR"
                $allPassed = $false
                $failedImports += $module.Name
            }
        } catch {
            Write-Host " ERROR" -ForegroundColor Red
            Write-Log "Import error: $($module.Name) - $_" -Level "ERROR"
            $allPassed = $false
            $failedImports += $module.Name
        }
    }
    
    Write-Host ""
    
    if ($allPassed) {
        Write-Step "All core imports verified" -Status "OK"
        Write-Log "All core imports passed"
        return $true
    } else {
        Write-Step "Some imports failed: $($failedImports -join ', ')" -Status "FAIL"
        Write-Log "Failed imports: $($failedImports -join ', ')" -Level "ERROR"
        $script:InstallState.Errors += "Failed imports: $($failedImports -join ', ')"
        return $false
    }
}

function Copy-ApplicationCode {
    Write-Section "DEPLOYING APPLICATION CODE"
    
    $sourcePath = Split-Path $PSScriptRoot -Parent
    $targetPath = Join-Path $InstallPath "core"
    
    # Directories to copy
    $codeDirs = @("api", "automation", "core", "plugins", "ui")
    
    # Files to copy
    $codeFiles = @("main.py", "requirements.txt", "__init__.py")
    
    $totalItems = $codeDirs.Count + $codeFiles.Count
    $currentItem = 0
    
    try {
        # Copy directories
        foreach ($dir in $codeDirs) {
            $currentItem++
            $srcDir = Join-Path $sourcePath $dir
            $dstDir = Join-Path $targetPath $dir
            
            Write-Progress-Bar -Current $currentItem -Total $totalItems -Activity "Copying $dir"
            
            if (Test-Path $srcDir) {
                Copy-Item -Path $srcDir -Destination $dstDir -Recurse -Force -ErrorAction Stop
                Write-Log "Copied directory: $dir"
            } else {
                Write-Log "Source directory not found: $srcDir" -Level "WARN"
            }
            
            Start-Sleep -Milliseconds 100
        }
        
        # Copy files
        foreach ($file in $codeFiles) {
            $currentItem++
            $srcFile = Join-Path $sourcePath $file
            $dstFile = Join-Path $targetPath $file
            
            Write-Progress-Bar -Current $currentItem -Total $totalItems -Activity "Copying $file"
            
            if (Test-Path $srcFile) {
                Copy-Item -Path $srcFile -Destination $dstFile -Force -ErrorAction Stop
                Write-Log "Copied file: $file"
            } else {
                Write-Log "Source file not found: $srcFile" -Level "WARN"
            }
            
            Start-Sleep -Milliseconds 100
        }
        
        # Copy config templates
        $configSrc = Join-Path $sourcePath "config"
        $configDst = Join-Path $InstallPath "config"
        if (Test-Path $configSrc) {
            Copy-Item -Path "$configSrc\*" -Destination $configDst -Recurse -Force -ErrorAction SilentlyContinue
            Write-Log "Copied config templates"
        }
        
        Write-Host ""
        Write-Step "Application code deployed" -Status "OK"
        Write-Log "Application code copied successfully"
        
        return $true
    } catch {
        Write-Host ""
        Write-Step "Failed to copy application code: $_" -Status "FAIL"
        Write-Log "Code copy error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Failed to copy application code: $_"
        return $false
    }
}

# ============================================================
# SECURITY BOOTSTRAP FUNCTIONS
# ============================================================

function Initialize-DeviceIdentity {
    Write-Section "GENERATING DEVICE IDENTITY"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $bootstrapModule = Join-Path $InstallPath "core\core\security\bootstrap.py"
    
    # Determine install mode
    $installMode = "normal"
    if ($Demo) { $installMode = "demo" }
    elseif ($Portable) { $installMode = "portable" }
    
    Write-Step "Creating unique device identity..." -Status "INFO" -NoNewline
    
    try {
        $result = & $pythonPath $bootstrapModule `
            --install-path "$InstallPath" `
            --version "$($script:Config.Version)" `
            --mode "$installMode" `
            --action "device-id" `
            --output "json" 2>&1
        
        $jsonResult = $result | ConvertFrom-Json
        
        if ($jsonResult.success) {
            Write-Host " OK" -ForegroundColor Green
            Write-Log "Device identity created: $($jsonResult.device_identity.device_id)"
            
            # Store for later use
            $script:DeviceId = $jsonResult.device_identity.device_id
            $script:HardwareFingerprint = $jsonResult.device_identity.hardware_fingerprint
            
            Write-Host ""
            Write-Host "  Device ID: $($script:DeviceId)" -ForegroundColor Cyan
            Write-Host "  Hardware Fingerprint: $($script:HardwareFingerprint.Substring(0,16))..." -ForegroundColor DarkGray
            
            return $true
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Log "Device identity creation failed" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
        Write-Log "Device identity error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Device identity generation failed: $_"
        return $false
    }
}

function Initialize-RootKeypair {
    Write-Section "GENERATING ROOT KEYPAIR"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $bootstrapModule = Join-Path $InstallPath "core\core\security\bootstrap.py"
    
    $installMode = "normal"
    if ($Demo) { $installMode = "demo" }
    elseif ($Portable) { $installMode = "portable" }
    
    Write-Step "Generating Ed25519 root keypair..." -Status "INFO" -NoNewline
    
    try {
        $result = & $pythonPath $bootstrapModule `
            --install-path "$InstallPath" `
            --version "$($script:Config.Version)" `
            --mode "$installMode" `
            --action "keypair" `
            --output "json" 2>&1
        
        $jsonResult = $result | ConvertFrom-Json
        
        if ($jsonResult.success) {
            Write-Host " OK" -ForegroundColor Green
            Write-Log "Root keypair generated"
            
            # Store fingerprint
            $script:PublicKeyFingerprint = $jsonResult.fingerprint
            
            Write-Host ""
            Write-Host "  Private Key: .akshay\keys\root_private.key" -ForegroundColor Yellow
            Write-Host "  Public Key:  .akshay\keys\root_public.key" -ForegroundColor Cyan
            Write-Host "  Fingerprint: $($script:PublicKeyFingerprint.Substring(0,16))..." -ForegroundColor DarkGray
            Write-Host ""
            Write-Host "  [!] Private key is UNENCRYPTED until first-run wizard" -ForegroundColor Yellow
            
            return $true
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Log "Root keypair generation failed" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
        Write-Log "Root keypair error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Root keypair generation failed: $_"
        return $false
    }
}

function Initialize-DefaultPolicy {
    Write-Section "CREATING DEFAULT SECURITY POLICY"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $bootstrapModule = Join-Path $InstallPath "core\core\security\bootstrap.py"
    
    $installMode = "normal"
    if ($Demo) { $installMode = "demo" }
    elseif ($Portable) { $installMode = "portable" }
    
    Write-Step "Creating base security policy..." -Status "INFO" -NoNewline
    
    try {
        $result = & $pythonPath $bootstrapModule `
            --install-path "$InstallPath" `
            --version "$($script:Config.Version)" `
            --mode "$installMode" `
            --action "policy" `
            --output "json" 2>&1
        
        $jsonResult = $result | ConvertFrom-Json
        
        if ($jsonResult.success) {
            Write-Host " OK" -ForegroundColor Green
            Write-Log "Default policy created and signed"
            
            Write-Host ""
            Write-Host "  Base Policy:   policies\base.yaml" -ForegroundColor Cyan
            Write-Host "  Active Policy: policies\active.yaml" -ForegroundColor Cyan
            Write-Host "  Signature:     policies\active.yaml.sig" -ForegroundColor DarkGray
            Write-Host ""
            Write-Host "  [OK] Policy signed with ROOT key" -ForegroundColor Green
            
            return $true
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Log "Policy creation failed" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
        Write-Log "Policy creation error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Policy creation failed: $_"
        return $false
    }
}

function Initialize-AuditRecord {
    Write-Section "CREATING INSTALL AUDIT RECORD"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $bootstrapModule = Join-Path $InstallPath "core\core\security\bootstrap.py"
    
    $installMode = "normal"
    if ($Demo) { $installMode = "demo" }
    elseif ($Portable) { $installMode = "portable" }
    
    Write-Step "Writing audit trail..." -Status "INFO" -NoNewline
    
    try {
        $result = & $pythonPath $bootstrapModule `
            --install-path "$InstallPath" `
            --version "$($script:Config.Version)" `
            --mode "$installMode" `
            --action "audit" `
            --output "json" 2>&1
        
        $jsonResult = $result | ConvertFrom-Json
        
        if ($jsonResult.success) {
            Write-Host " OK" -ForegroundColor Green
            Write-Log "Audit record created"
            
            Write-Host ""
            Write-Host "  Audit File: logs\install_audit.json" -ForegroundColor Cyan
            
            return $true
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Log "Audit record creation failed" -Level "ERROR"
            return $false
        }
    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
        Write-Log "Audit record error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Audit record creation failed: $_"
        return $false
    }
}

function Test-SecurityBootstrap {
    Write-Section "VERIFYING SECURITY BOOTSTRAP"
    
    $venvPath = $script:VenvPath
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $bootstrapModule = Join-Path $InstallPath "core\core\security\bootstrap.py"
    
    $installMode = "normal"
    if ($Demo) { $installMode = "demo" }
    elseif ($Portable) { $installMode = "portable" }
    
    Write-Step "Verifying security components..." -Status "INFO"
    Write-Host ""
    
    try {
        $result = & $pythonPath $bootstrapModule `
            --install-path "$InstallPath" `
            --version "$($script:Config.Version)" `
            --mode "$installMode" `
            --action "verify" `
            --output "json" 2>&1
        
        $jsonResult = $result | ConvertFrom-Json
        
        # Check individual components
        $checks = @(
            @{ Name = "Device Identity"; Path = "$InstallPath\.akshay\device.json" },
            @{ Name = "Public Key"; Path = "$InstallPath\.akshay\keys\root_public.key" },
            @{ Name = "Private Key"; Path = "$InstallPath\.akshay\keys\root_private.key" },
            @{ Name = "Base Policy"; Path = "$InstallPath\policies\base.yaml" },
            @{ Name = "Active Policy"; Path = "$InstallPath\policies\active.yaml" },
            @{ Name = "Policy Signature"; Path = "$InstallPath\policies\active.yaml.sig" },
            @{ Name = "Audit Record"; Path = "$InstallPath\logs\install_audit.json" }
        )
        
        $allPassed = $true
        
        foreach ($check in $checks) {
            if (Test-Path $check.Path) {
                Write-Step "  $($check.Name)" -Status "OK"
            } else {
                Write-Step "  $($check.Name)" -Status "FAIL"
                $allPassed = $false
            }
        }
        
        Write-Host ""
        
        if ($jsonResult.success -and $allPassed) {
            Write-Step "Security bootstrap verified" -Status "OK"
            Write-Log "Security bootstrap verification passed"
            return $true
        } else {
            Write-Step "Security bootstrap verification FAILED" -Status "FAIL"
            
            if ($jsonResult.errors) {
                foreach ($err in $jsonResult.errors) {
                    Write-Log "Verification error: $err" -Level "ERROR"
                    $script:InstallState.Errors += $err
                }
            }
            
            return $false
        }
    } catch {
        Write-Host ""
        Write-Step "Verification error: $_" -Status "FAIL"
        Write-Log "Verification error: $_" -Level "ERROR"
        $script:InstallState.Errors += "Security verification failed: $_"
        return $false
    }
}

function Invoke-SecurityBootstrap {
    <#
    .SYNOPSIS
        Complete security bootstrap process.
    .DESCRIPTION
        Runs all security bootstrap steps in order:
        1. Device Identity
        2. Root Keypair
        3. Default Policy
        4. Audit Record
        5. Verification
    #>
    
    # Step 1: Device Identity
    $deviceOk = Initialize-DeviceIdentity
    if (-not $deviceOk) {
        return $false
    }
    
    # Step 2: Root Keypair
    $keypairOk = Initialize-RootKeypair
    if (-not $keypairOk) {
        return $false
    }
    
    # Step 3: Default Policy
    $policyOk = Initialize-DefaultPolicy
    if (-not $policyOk) {
        return $false
    }
    
    # Step 4: Audit Record
    $auditOk = Initialize-AuditRecord
    if (-not $auditOk) {
        return $false
    }
    
    # Step 5: Verification
    $verifyOk = Test-SecurityBootstrap
    if (-not $verifyOk) {
        return $false
    }
    
    return $true
}

# ============================================================
# ROLLBACK FUNCTIONS
# ============================================================

function Invoke-Rollback {
    Write-Section "ROLLING BACK INSTALLATION"
    Write-Log "Starting rollback" -Level "WARN"
    
    # Remove created folders (in reverse order)
    $foldersToRemove = $script:InstallState.CreatedFolders | Sort-Object -Descending
    
    foreach ($folder in $foldersToRemove) {
        try {
            if (Test-Path $folder) {
                Remove-Item -Path $folder -Recurse -Force -ErrorAction Stop
                Write-Step "Removed: $folder" -Status "OK"
                Write-Log "Rollback: Removed $folder"
            }
        } catch {
            Write-Step "Could not remove: $folder" -Status "WARN"
            Write-Log "Rollback: Failed to remove $folder - $_" -Level "WARN"
        }
    }
    
    # Remove PATH modification if made
    if ($script:InstallState.PathModified) {
        try {
            $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
            $newPath = ($currentPath -split ';' | Where-Object { $_ -ne $InstallPath }) -join ';'
            [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
            Write-Step "Restored PATH" -Status "OK"
            Write-Log "Rollback: Restored PATH"
        } catch {
            Write-Step "Could not restore PATH" -Status "WARN"
            Write-Log "Rollback: Failed to restore PATH - $_" -Level "WARN"
        }
    }
    
    # Remove shortcuts
    foreach ($shortcut in $script:InstallState.ShortcutsCreated) {
        try {
            if (Test-Path $shortcut) {
                Remove-Item -Path $shortcut -Force
                Write-Step "Removed shortcut: $shortcut" -Status "OK"
                Write-Log "Rollback: Removed shortcut $shortcut"
            }
        } catch {
            Write-Step "Could not remove shortcut: $shortcut" -Status "WARN"
            Write-Log "Rollback: Failed to remove shortcut - $_" -Level "WARN"
        }
    }
    
    Write-Host ""
    Write-Step "Rollback complete" -Status "OK"
    Write-Log "Rollback completed"
}

function Show-RecoveryInstructions {
    Write-Host ""
    Write-Host "  ================================================================" -ForegroundColor Red
    Write-Host "  |                    INSTALLATION FAILED                       |" -ForegroundColor Red
    Write-Host "  ================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  The installation could not be completed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Errors encountered:" -ForegroundColor White
    
    foreach ($err in $script:InstallState.Errors) {
        Write-Host "    - $err" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "  Recovery Steps:" -ForegroundColor White
    Write-Host "  ---------------" -ForegroundColor DarkGray
    Write-Host "  1. Ensure Python 3.10+ is installed: https://python.org/downloads" -ForegroundColor Cyan
    Write-Host "  2. Close any applications using the install folder" -ForegroundColor Cyan
    Write-Host "  3. Manually delete: $InstallPath (if exists)" -ForegroundColor Cyan
    Write-Host "  4. Re-run this installer as Administrator" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Log file: $($script:InstallState.LogFile)" -ForegroundColor DarkGray
    Write-Host ""
}

# ============================================================
# MAIN INSTALLATION FLOW
# ============================================================

function Start-Installation {
    # Initialize
    Clear-Host
    Write-Banner
    Initialize-Logging
    
    # Show mode
    if ($Demo) {
        Write-Host "  Mode: DEMO (Restricted capabilities)" -ForegroundColor Magenta
    } elseif ($Portable) {
        Write-Host "  Mode: PORTABLE (No system integration)" -ForegroundColor Magenta
    } else {
        Write-Host "  Mode: STANDARD" -ForegroundColor Cyan
    }
    Write-Host "  Target: $InstallPath" -ForegroundColor Cyan
    Write-Host ""
    
    # Run preflight checks
    $preflightPassed = Invoke-PreflightChecks
    
    if (-not $preflightPassed) {
        Show-RecoveryInstructions
        exit 1
    }
    
    # Handle existing installation
    if ($script:ExistingInstall) {
        Write-Host ""
        $proceed = Get-UserConfirmation "Existing installation found. Upgrade?"
        
        if (-not $proceed) {
            Write-Host ""
            Write-Step "Installation cancelled by user" -Status "SKIP"
            exit 0
        }
    }
    
    # Create folder structure
    $foldersCreated = Initialize-FolderStructure
    
    if (-not $foldersCreated) {
        Invoke-Rollback
        Show-RecoveryInstructions
        exit 1
    }
    
    # Show summary
    Show-FolderSummary
    
    # ============================================================
    # PHASE 2: VIRTUAL ENVIRONMENT SETUP
    # ============================================================
    
    $venvCreated = Initialize-VirtualEnvironment
    
    if (-not $venvCreated) {
        Invoke-Rollback
        Show-RecoveryInstructions
        exit 1
    }
    
    # ============================================================
    # PHASE 3: INSTALL DEPENDENCIES
    # ============================================================
    
    $depsInstalled = Install-Dependencies
    
    if (-not $depsInstalled) {
        Invoke-Rollback
        Show-RecoveryInstructions
        exit 1
    }
    
    # ============================================================
    # PHASE 4: VERIFY IMPORTS
    # ============================================================
    
    $importsVerified = Test-CoreImports
    
    if (-not $importsVerified) {
        Invoke-Rollback
        Show-RecoveryInstructions
        exit 1
    }
    
    # ============================================================
    # PHASE 5: COPY APPLICATION CODE
    # ============================================================
    
    $codeCopied = Copy-ApplicationCode
    
    if (-not $codeCopied) {
        Invoke-Rollback
        Show-RecoveryInstructions
        exit 1
    }
    
    # ============================================================
    # CHECKPOINT: VENV + DEPS COMPLETE
    # ============================================================
    
    Write-Section "CHECKPOINT: ENVIRONMENT READY"
    
    Write-Host "  +-------------------------------------------------------------+" -ForegroundColor Green
    Write-Host "  |   [OK] System requirements verified                         |" -ForegroundColor Green
    Write-Host "  |   [OK] Folder structure created                             |" -ForegroundColor Green
    Write-Host "  |   [OK] Virtual environment created                          |" -ForegroundColor Green
    Write-Host "  |   [OK] Dependencies installed                               |" -ForegroundColor Green
    Write-Host "  |   [OK] Core imports verified                                |" -ForegroundColor Green
    Write-Host "  |   [OK] Application code deployed                            |" -ForegroundColor Green
    Write-Host "  +-------------------------------------------------------------+" -ForegroundColor Green
    Write-Host ""
    
    Write-Log "Checkpoint: Virtual environment and dependencies complete"
    
    # ============================================================
    # PHASE 6: SECURITY BOOTSTRAP
    # ============================================================
    
    $securityOk = Invoke-SecurityBootstrap
    
    if (-not $securityOk) {
        Invoke-Rollback
        Show-RecoveryInstructions
        exit 1
    }
    
    # ============================================================
    # FINAL CHECKPOINT: SECURITY ESTABLISHED
    # ============================================================
    
    Write-Section "INSTALLATION CHECKPOINT"
    
    Write-Host "  +-------------------------------------------------------------+" -ForegroundColor Green
    Write-Host "  |                                                             |" -ForegroundColor Green
    Write-Host "  |   [OK] System requirements verified                         |" -ForegroundColor Green
    Write-Host "  |   [OK] Folder structure created                             |" -ForegroundColor Green
    Write-Host "  |   [OK] Virtual environment created                          |" -ForegroundColor Green
    Write-Host "  |   [OK] Dependencies installed                               |" -ForegroundColor Green
    Write-Host "  |   [OK] Core imports verified                                |" -ForegroundColor Green
    Write-Host "  |   [OK] Application code deployed                            |" -ForegroundColor Green
    Write-Host "  |   [OK] Device identity established                          |" -ForegroundColor Green
    Write-Host "  |   [OK] Root keypair generated                               |" -ForegroundColor Green
    Write-Host "  |   [OK] Security policy created and signed                   |" -ForegroundColor Green
    Write-Host "  |   [OK] Audit record initialized                             |" -ForegroundColor Green
    Write-Host "  |                                                             |" -ForegroundColor Green
    Write-Host "  |   ROOT KEY CREATED - System is now sovereign                |" -ForegroundColor Yellow
    Write-Host "  |                                                             |" -ForegroundColor Green
    Write-Host "  |   Next: First-run wizard + Launchers                        |" -ForegroundColor Green
    Write-Host "  |                                                             |" -ForegroundColor Green
    Write-Host "  +-------------------------------------------------------------+" -ForegroundColor Green
    Write-Host ""
    
    Write-Log "Security bootstrap complete - Root key created"
    
    # Show important paths
    Write-Host "  Key Files:" -ForegroundColor White
    Write-Host "  ----------" -ForegroundColor DarkGray
    Write-Host "    Device ID:    $InstallPath\.akshay\device.json" -ForegroundColor Cyan
    Write-Host "    Public Key:   $InstallPath\.akshay\keys\root_public.key" -ForegroundColor Cyan
    Write-Host "    Private Key:  $InstallPath\.akshay\keys\root_private.key" -ForegroundColor Yellow
    Write-Host "    Policy:       $InstallPath\policies\active.yaml" -ForegroundColor Cyan
    Write-Host "    Audit:        $InstallPath\logs\install_audit.json" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "  [!] IMPORTANT: Private key will be encrypted during first-run wizard" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "  Press any key to exit..." -ForegroundColor DarkGray
    
    if (-not $Unattended) {
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}

# ============================================================
# ENTRY POINT
# ============================================================

try {
    Start-Installation
} catch {
    Write-Host ""
    Write-Host "  FATAL ERROR: $_" -ForegroundColor Red
    Write-Log "Fatal error: $_" -Level "ERROR"
    
    if ($script:InstallState.CreatedFolders.Count -gt 0) {
        Invoke-Rollback
    }
    
    Show-RecoveryInstructions
    exit 1
}
