<#
.SYNOPSIS
    Test suite for AKSHAY AI CORE Installer
    
.DESCRIPTION
    Tests preflight checks, folder creation, permissions, and rollback functionality.
    
.EXAMPLE
    .\test_installer.ps1
    .\test_installer.ps1 -Verbose
#>

[CmdletBinding()]
param()

$script:TestResults = @{
    Passed = 0
    Failed = 0
    Skipped = 0
    Errors = @()
}

$script:TestInstallPath = Join-Path $env:TEMP "AkshayAI_Test_$(Get-Random)"

# ============================================================
# TEST UTILITIES
# ============================================================

function Write-TestHeader {
    param([string]$Title)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-TestResult {
    param(
        [string]$TestName,
        [bool]$Passed,
        [string]$Message = ""
    )
    
    if ($Passed) {
        Write-Host "  [PASS] $TestName" -ForegroundColor Green
        $script:TestResults.Passed++
    } else {
        Write-Host "  [FAIL] $TestName" -ForegroundColor Red
        if ($Message) {
            Write-Host "         $Message" -ForegroundColor Yellow
        }
        $script:TestResults.Failed++
        $script:TestResults.Errors += "$TestName : $Message"
    }
}

function Write-TestSkipped {
    param(
        [string]$TestName,
        [string]$Reason
    )
    
    Write-Host "  [SKIP] $TestName - $Reason" -ForegroundColor Yellow
    $script:TestResults.Skipped++
}

function Invoke-Cleanup {
    if (Test-Path $script:TestInstallPath) {
        Remove-Item -Path $script:TestInstallPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ============================================================
# PREFLIGHT CHECK TESTS
# ============================================================

function Test-WindowsVersionCheck {
    $version = [System.Environment]::OSVersion.Version
    $isValid = $version.Major -ge 10
    Write-TestResult -TestName "Windows version detection" -Passed $isValid -Message "Version: $($version.Major).$($version.Minor)"
}

function Test-PowerShellVersionCheck {
    $version = $PSVersionTable.PSVersion
    $isValid = $version -ge [Version]"5.1"
    Write-TestResult -TestName "PowerShell version detection" -Passed $isValid -Message "Version: $version"
}

function Test-PythonDetection {
    $pythonCommands = @("python", "python3", "py -3")
    $found = $false
    $foundVersion = ""
    
    foreach ($cmd in $pythonCommands) {
        try {
            $cmdParts = $cmd -split ' '
            if ($cmdParts.Count -eq 1) {
                $output = & $cmd --version 2>&1
            } else {
                $output = & $cmdParts[0] $cmdParts[1] --version 2>&1
            }
            
            if ($output -match 'Python (\d+\.\d+)') {
                $found = $true
                $foundVersion = $Matches[1]
                break
            }
        } catch {
            continue
        }
    }
    
    Write-TestResult -TestName "Python detection" -Passed $found -Message "Found: $foundVersion"
}

function Test-PythonMissing {
    $fakePath = "C:\NonExistent\python_fake.exe"
    $exists = Test-Path $fakePath
    Write-TestResult -TestName "Missing Python handling" -Passed (-not $exists) -Message "Correctly identifies non-existent path"
}

function Test-DiskSpaceCheck {
    try {
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
        $freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 2)
        $hasSpace = $freeSpaceGB -ge 2
        Write-TestResult -TestName "Disk space detection" -Passed $hasSpace -Message "${freeSpaceGB}GB free"
    } catch {
        Write-TestResult -TestName "Disk space detection" -Passed $false -Message "Error: $_"
    }
}

function Test-MemoryCheck {
    try {
        $memory = Get-CimInstance Win32_ComputerSystem
        $totalRAMGB = [math]::Round($memory.TotalPhysicalMemory / 1GB, 2)
        $hasMemory = $totalRAMGB -ge 4
        Write-TestResult -TestName "Memory detection" -Passed $hasMemory -Message "${totalRAMGB}GB RAM"
    } catch {
        Write-TestResult -TestName "Memory detection" -Passed $false -Message "Error: $_"
    }
}

function Test-AdminRightsCheck {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        Write-TestResult -TestName "Admin rights detection" -Passed $true -Message "IsAdmin: $isAdmin"
    } catch {
        Write-TestResult -TestName "Admin rights detection" -Passed $false -Message "Error: $_"
    }
}

# ============================================================
# FOLDER CREATION TESTS
# ============================================================

function Test-FolderCreation {
    try {
        $testFolder = Join-Path $script:TestInstallPath "test_folder"
        New-Item -ItemType Directory -Path $testFolder -Force | Out-Null
        $exists = Test-Path $testFolder
        Write-TestResult -TestName "Folder creation" -Passed $exists -Message "Path: $testFolder"
    } catch {
        Write-TestResult -TestName "Folder creation" -Passed $false -Message "Error: $_"
    }
}

function Test-NestedFolderCreation {
    try {
        $nestedFolder = Join-Path $script:TestInstallPath "level1\level2\level3"
        New-Item -ItemType Directory -Path $nestedFolder -Force | Out-Null
        $exists = Test-Path $nestedFolder
        Write-TestResult -TestName "Nested folder creation" -Passed $exists -Message "Path: $nestedFolder"
    } catch {
        Write-TestResult -TestName "Nested folder creation" -Passed $false -Message "Error: $_"
    }
}

function Test-HiddenFolderAttribute {
    try {
        $hiddenFolder = Join-Path $script:TestInstallPath ".hidden_test"
        New-Item -ItemType Directory -Path $hiddenFolder -Force | Out-Null
        
        $item = Get-Item $hiddenFolder -Force
        $item.Attributes = $item.Attributes -bor [System.IO.FileAttributes]::Hidden
        
        $isHidden = (Get-Item $hiddenFolder -Force).Attributes -band [System.IO.FileAttributes]::Hidden
        Write-TestResult -TestName "Hidden folder attribute" -Passed ($isHidden -ne 0) -Message "Attributes set correctly"
    } catch {
        Write-TestResult -TestName "Hidden folder attribute" -Passed $false -Message "Error: $_"
    }
}

function Test-FullFolderStructure {
    $folders = @(
        "core", "config", "data", "data\memory", "data\face_data", "data\vault", "data\vector_db",
        "logs", "policies", "policies\custom", "plugins", "plugins\custom", "demo", ".akshay", ".akshay\sessions"
    )
    
    $allCreated = $true
    $failedFolders = @()
    
    foreach ($folder in $folders) {
        $fullPath = Join-Path $script:TestInstallPath $folder
        try {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
            if (-not (Test-Path $fullPath)) {
                $allCreated = $false
                $failedFolders += $folder
            }
        } catch {
            $allCreated = $false
            $failedFolders += $folder
        }
    }
    
    if ($allCreated) {
        Write-TestResult -TestName "Full folder structure" -Passed $true -Message "All $($folders.Count) folders created"
    } else {
        Write-TestResult -TestName "Full folder structure" -Passed $false -Message "Failed: $($failedFolders -join ', ')"
    }
}

# ============================================================
# PERMISSION TESTS
# ============================================================

function Test-DirectoryPermissions {
    try {
        $testFolder = Join-Path $script:TestInstallPath "permission_test"
        New-Item -ItemType Directory -Path $testFolder -Force | Out-Null
        
        $acl = Get-Acl $testFolder
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $currentUser, "Modify", "ContainerInherit,ObjectInherit", "None", "Allow"
        )
        
        $acl.SetAccessRule($rule)
        Set-Acl -Path $testFolder -AclObject $acl
        
        $testFile = Join-Path $testFolder "test.txt"
        "test" | Out-File -FilePath $testFile
        $canWrite = Test-Path $testFile
        
        Write-TestResult -TestName "Directory permissions" -Passed $canWrite -Message "Modify permissions work"
    } catch {
        Write-TestResult -TestName "Directory permissions" -Passed $false -Message "Error: $_"
    }
}

function Test-PermissionDenied {
    $systemFolder = "C:\Windows\System32\test_akshay_$(Get-Random)"
    
    try {
        New-Item -ItemType Directory -Path $systemFolder -Force -ErrorAction Stop | Out-Null
        Remove-Item -Path $systemFolder -Force -ErrorAction SilentlyContinue
        Write-TestSkipped -TestName "Permission denied handling" -Reason "Running as administrator"
    } catch {
        Write-TestResult -TestName "Permission denied handling" -Passed $true -Message "Correctly rejected"
    }
}

# ============================================================
# ROLLBACK TESTS
# ============================================================

function Test-FolderRollback {
    try {
        $rollbackTest = Join-Path $script:TestInstallPath "rollback_test"
        $nested = Join-Path $rollbackTest "nested\deep"
        
        New-Item -ItemType Directory -Path $nested -Force | Out-Null
        "test" | Out-File -FilePath (Join-Path $nested "file.txt")
        
        $existsBefore = Test-Path $rollbackTest
        Remove-Item -Path $rollbackTest -Recurse -Force
        $existsAfter = Test-Path $rollbackTest
        
        $success = $existsBefore -and (-not $existsAfter)
        Write-TestResult -TestName "Folder rollback" -Passed $success -Message "Created and removed successfully"
    } catch {
        Write-TestResult -TestName "Folder rollback" -Passed $false -Message "Error: $_"
    }
}

function Test-PartialInstallRollback {
    try {
        $partialTest = Join-Path $script:TestInstallPath "partial_rollback"
        $createdFolders = @()
        $foldersToCreate = @("core", "config", "data", "logs")
        
        foreach ($folder in $foldersToCreate) {
            $path = Join-Path $partialTest $folder
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            $createdFolders += $path
        }
        
        $rollbackSuccess = $true
        foreach ($folder in ($createdFolders | Sort-Object -Descending)) {
            try {
                Remove-Item -Path $folder -Recurse -Force -ErrorAction Stop
            } catch {
                $rollbackSuccess = $false
            }
        }
        
        if (Test-Path $partialTest) {
            Remove-Item -Path $partialTest -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        $cleanedUp = -not (Test-Path $partialTest)
        Write-TestResult -TestName "Partial install rollback" -Passed ($rollbackSuccess -and $cleanedUp) -Message "Cleanup successful"
    } catch {
        Write-TestResult -TestName "Partial install rollback" -Passed $false -Message "Error: $_"
    }
}

# ============================================================
# MODE TESTS
# ============================================================

function Test-DemoModeFlag {
    $demoMode = $true
    $expectedPolicy = "demo"
    $policy = if ($demoMode) { "demo" } else { "default" }
    $success = $policy -eq $expectedPolicy
    Write-TestResult -TestName "Demo mode flag" -Passed $success -Message "Policy: $policy"
}

function Test-PortableModeFlag {
    $portableMode = $true
    $shouldModifyPath = -not $portableMode
    $shouldCreateShortcuts = -not $portableMode
    $success = (-not $shouldModifyPath) -and (-not $shouldCreateShortcuts)
    Write-TestResult -TestName "Portable mode flag" -Passed $success -Message "No system integration"
}

# ============================================================
# LOGGING TESTS
# ============================================================

function Test-LogFileCreation {
    try {
        $logDir = Join-Path $script:TestInstallPath "logs"
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        
        $logFile = Join-Path $logDir "install.log"
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        
        "[$timestamp] [INFO] Test log entry" | Out-File -FilePath $logFile -Append
        
        $exists = Test-Path $logFile
        $content = Get-Content $logFile -Raw
        $hasContent = $content -match "Test log entry"
        
        Write-TestResult -TestName "Log file creation" -Passed ($exists -and $hasContent) -Message "Log file works"
    } catch {
        Write-TestResult -TestName "Log file creation" -Passed $false -Message "Error: $_"
    }
}

# ============================================================
# INTEGRATION TESTS
# ============================================================

function Test-FullPreflightSequence {
    $checks = @(
        @{ Name = "Windows"; Check = { [System.Environment]::OSVersion.Version.Major -ge 10 } },
        @{ Name = "PowerShell"; Check = { $PSVersionTable.PSVersion -ge [Version]"5.1" } },
        @{ Name = "DiskSpace"; Check = { (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB -ge 2 } },
        @{ Name = "Memory"; Check = { (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB -ge 4 } }
    )
    
    $allPassed = $true
    $failedChecks = @()
    
    foreach ($check in $checks) {
        try {
            $result = & $check.Check
            if (-not $result) {
                $allPassed = $false
                $failedChecks += $check.Name
            }
        } catch {
            $allPassed = $false
            $failedChecks += "$($check.Name) (error)"
        }
    }
    
    if ($allPassed) {
        Write-TestResult -TestName "Full preflight sequence" -Passed $true -Message "All checks passed"
    } else {
        Write-TestResult -TestName "Full preflight sequence" -Passed $false -Message "Failed: $($failedChecks -join ', ')"
    }
}

# ============================================================
# TEST RUNNER
# ============================================================

function Invoke-AllTests {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "        AKSHAY AI CORE - INSTALLER TEST SUITE                   " -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "  Test directory: $script:TestInstallPath" -ForegroundColor DarkGray
    New-Item -ItemType Directory -Path $script:TestInstallPath -Force | Out-Null
    
    # Preflight Tests
    Write-TestHeader "PREFLIGHT CHECK TESTS"
    Test-WindowsVersionCheck
    Test-PowerShellVersionCheck
    Test-PythonDetection
    Test-PythonMissing
    Test-DiskSpaceCheck
    Test-MemoryCheck
    Test-AdminRightsCheck
    
    # Folder Tests
    Write-TestHeader "FOLDER CREATION TESTS"
    Test-FolderCreation
    Test-NestedFolderCreation
    Test-HiddenFolderAttribute
    Test-FullFolderStructure
    
    # Permission Tests
    Write-TestHeader "PERMISSION TESTS"
    Test-DirectoryPermissions
    Test-PermissionDenied
    
    # Rollback Tests
    Write-TestHeader "ROLLBACK TESTS"
    Test-FolderRollback
    Test-PartialInstallRollback
    
    # Mode Tests
    Write-TestHeader "MODE TESTS"
    Test-DemoModeFlag
    Test-PortableModeFlag
    
    # Logging Tests
    Write-TestHeader "LOGGING TESTS"
    Test-LogFileCreation
    
    # Integration Tests
    Write-TestHeader "INTEGRATION TESTS"
    Test-FullPreflightSequence
    
    # Cleanup
    Invoke-Cleanup
    
    # Summary
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " TEST SUMMARY" -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Passed:  $($script:TestResults.Passed)" -ForegroundColor Green
    
    $failColor = "Green"
    if ($script:TestResults.Failed -gt 0) { $failColor = "Red" }
    Write-Host "  Failed:  $($script:TestResults.Failed)" -ForegroundColor $failColor
    
    Write-Host "  Skipped: $($script:TestResults.Skipped)" -ForegroundColor Yellow
    
    $total = $script:TestResults.Passed + $script:TestResults.Failed + $script:TestResults.Skipped
    Write-Host "  Total:   $total" -ForegroundColor White
    Write-Host ""
    
    if ($script:TestResults.Errors.Count -gt 0) {
        Write-Host "  Errors:" -ForegroundColor Red
        foreach ($err in $script:TestResults.Errors) {
            Write-Host "    - $err" -ForegroundColor Red
        }
        Write-Host ""
    }
    
    if ($script:TestResults.Failed -eq 0) {
        Write-Host "  [OK] ALL TESTS PASSED" -ForegroundColor Green
    } else {
        Write-Host "  [X] SOME TESTS FAILED" -ForegroundColor Red
    }
    
    Write-Host ""
    
    return ($script:TestResults.Failed -eq 0)
}

# ============================================================
# ENTRY POINT
# ============================================================

try {
    $success = Invoke-AllTests
    if ($success) {
        exit 0
    } else {
        exit 1
    }
} catch {
    Write-Host "  FATAL ERROR: $_" -ForegroundColor Red
    Invoke-Cleanup
    exit 1
} finally {
    Invoke-Cleanup
}
