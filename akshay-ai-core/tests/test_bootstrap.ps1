<#
.SYNOPSIS
    AKSHAY AI CORE - Security Bootstrap Test Suite

.DESCRIPTION
    Tests for the security bootstrap system including:
    - Device identity generation
    - Root keypair creation
    - Policy creation and signing
    - Verification
    - Recovery key functionality
#>

param(
    [string]$TestPath = "$env:TEMP\AkshayAI_Bootstrap_Test_$([System.Guid]::NewGuid().ToString().Substring(0,8))"
)

# ============================================================
# TEST FRAMEWORK
# ============================================================

$script:TestResults = @{
    Passed = 0
    Failed = 0
    Skipped = 0
}

function Write-TestSection {
    param([string]$Title)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
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
    }
}

function Write-TestSkipped {
    param([string]$TestName, [string]$Reason)
    Write-Host "  [SKIP] $TestName - $Reason" -ForegroundColor Yellow
    $script:TestResults.Skipped++
}

# ============================================================
# SETUP
# ============================================================

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "        AKSHAY AI CORE - SECURITY BOOTSTRAP TEST SUITE" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Test directory: $TestPath" -ForegroundColor DarkGray
Write-Host ""

# Create test directory structure
New-Item -ItemType Directory -Path $TestPath -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\.akshay" -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\.akshay\keys" -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\policies" -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\logs" -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\core\core\security" -Force | Out-Null

# Copy bootstrap module
$sourceBootstrap = Join-Path $PSScriptRoot "..\core\security\bootstrap.py"
$destBootstrap = Join-Path $TestPath "core\core\security\bootstrap.py"
if (Test-Path $sourceBootstrap) {
    Copy-Item -Path $sourceBootstrap -Destination $destBootstrap -Force
}

# Find Python
$pythonPath = $null
$pythonCommands = @("python", "python3", "py")
foreach ($cmd in $pythonCommands) {
    try {
        $output = & $cmd --version 2>&1
        if ($output -match 'Python') {
            $pythonPath = $cmd
            break
        }
    } catch { continue }
}

if (-not $pythonPath) {
    Write-Host "  [ERROR] Python not found. Skipping Python-based tests." -ForegroundColor Red
    exit 1
}

Write-Host "  Using Python: $pythonPath" -ForegroundColor DarkGray
Write-Host ""

# ============================================================
# DEVICE IDENTITY TESTS
# ============================================================

Write-TestSection "DEVICE IDENTITY TESTS"

# Test: Device identity generation
try {
    $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
    
    if (Test-Path $bootstrapScript) {
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action device-id --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        $deviceFile = Join-Path $TestPath ".akshay\device.json"
        $deviceExists = Test-Path $deviceFile
        $hasDeviceId = $json.device_identity.device_id -match '^[a-f0-9-]{36}$'
        $hasFingerprint = $json.device_identity.hardware_fingerprint.Length -eq 64
        
        Write-TestResult "Device identity file created" $deviceExists
        Write-TestResult "Device ID is valid UUID" $hasDeviceId
        Write-TestResult "Hardware fingerprint is SHA-256" $hasFingerprint
    } else {
        Write-TestSkipped "Device identity generation" "Bootstrap module not found"
    }
} catch {
    Write-TestResult "Device identity generation" $false "Error: $_"
}

# Test: Device identity persistence
try {
    $deviceFile = Join-Path $TestPath ".akshay\device.json"
    if (Test-Path $deviceFile) {
        $deviceData = Get-Content $deviceFile -Raw | ConvertFrom-Json
        
        $hasCreatedAt = $deviceData.created_at -ne $null
        $hasPythonVersion = $deviceData.python_version -ne $null
        
        Write-TestResult "Device identity has timestamp" $hasCreatedAt
        Write-TestResult "Device identity has Python version" $hasPythonVersion
    } else {
        Write-TestSkipped "Device identity persistence" "Device file not created"
    }
} catch {
    Write-TestResult "Device identity persistence" $false "Error: $_"
}

# ============================================================
# ROOT KEYPAIR TESTS
# ============================================================

Write-TestSection "ROOT KEYPAIR TESTS"

# Test: Keypair generation
try {
    $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
    
    if (Test-Path $bootstrapScript) {
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action keypair --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        $privateKeyFile = Join-Path $TestPath ".akshay\keys\root_private.key"
        $publicKeyFile = Join-Path $TestPath ".akshay\keys\root_public.key"
        
        $privateExists = Test-Path $privateKeyFile
        $publicExists = Test-Path $publicKeyFile
        $hasFingerprint = $json.fingerprint.Length -eq 64
        
        Write-TestResult "Private key file created" $privateExists
        Write-TestResult "Public key file created" $publicExists
        Write-TestResult "Public key fingerprint generated" $hasFingerprint
    } else {
        Write-TestSkipped "Keypair generation" "Bootstrap module not found"
    }
} catch {
    Write-TestResult "Keypair generation" $false "Error: $_"
}

# Test: Key format verification
try {
    $privateKeyFile = Join-Path $TestPath ".akshay\keys\root_private.key"
    $publicKeyFile = Join-Path $TestPath ".akshay\keys\root_public.key"
    
    if ((Test-Path $privateKeyFile) -and (Test-Path $publicKeyFile)) {
        $privateContent = Get-Content $privateKeyFile -Raw
        $publicContent = Get-Content $publicKeyFile -Raw
        
        $privateIsPem = $privateContent -match "-----BEGIN PRIVATE KEY-----"
        $publicIsPem = $publicContent -match "-----BEGIN PUBLIC KEY-----"
        
        Write-TestResult "Private key is PEM format" $privateIsPem
        Write-TestResult "Public key is PEM format" $publicIsPem
    } else {
        Write-TestSkipped "Key format verification" "Key files not found"
    }
} catch {
    Write-TestResult "Key format verification" $false "Error: $_"
}

# Test: Unencrypted private key detection
try {
    $privateKeyFile = Join-Path $TestPath ".akshay\keys\root_private.key"
    
    if (Test-Path $privateKeyFile) {
        $privateContent = Get-Content $privateKeyFile -Raw
        
        # Unencrypted key should NOT have AKSHAY_ENCRYPTED marker
        $isUnencrypted = -not ($privateContent -match "AKSHAY_ENCRYPTED")
        
        Write-TestResult "Private key is unencrypted (bootstrap stage)" $isUnencrypted
    } else {
        Write-TestSkipped "Unencrypted private key detection" "Private key file not found"
    }
} catch {
    Write-TestResult "Unencrypted private key detection" $false "Error: $_"
}

# ============================================================
# POLICY TESTS
# ============================================================

Write-TestSection "POLICY TESTS"

# Test: Policy creation
try {
    $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
    
    if (Test-Path $bootstrapScript) {
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action policy --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        $basePolicyFile = Join-Path $TestPath "policies\base.yaml"
        $activePolicyFile = Join-Path $TestPath "policies\active.yaml"
        $signatureFile = Join-Path $TestPath "policies\active.yaml.sig"
        
        $baseExists = Test-Path $basePolicyFile
        $activeExists = Test-Path $activePolicyFile
        $sigExists = Test-Path $signatureFile
        
        Write-TestResult "Base policy file created" $baseExists
        Write-TestResult "Active policy file created" $activeExists
        Write-TestResult "Policy signature file created" $sigExists
    } else {
        Write-TestSkipped "Policy creation" "Bootstrap module not found"
    }
} catch {
    Write-TestResult "Policy creation" $false "Error: $_"
}

# Test: Policy content validation
try {
    $activePolicyFile = Join-Path $TestPath "policies\active.yaml"
    
    if (Test-Path $activePolicyFile) {
        $policyContent = Get-Content $activePolicyFile -Raw
        
        $hasVersion = $policyContent -match "version:"
        $hasTrustZones = $policyContent -match "trust_zones:"
        $hasPermissions = $policyContent -match "permissions:"
        $hasSafeMode = $policyContent -match "safe_mode:"
        
        Write-TestResult "Policy has version field" $hasVersion
        Write-TestResult "Policy has trust zones" $hasTrustZones
        Write-TestResult "Policy has permissions" $hasPermissions
        Write-TestResult "Policy has safe mode config" $hasSafeMode
    } else {
        Write-TestSkipped "Policy content validation" "Policy file not found"
    }
} catch {
    Write-TestResult "Policy content validation" $false "Error: $_"
}

# Test: Signature is base64
try {
    $signatureFile = Join-Path $TestPath "policies\active.yaml.sig"
    
    if (Test-Path $signatureFile) {
        $sigContent = Get-Content $signatureFile -Raw
        
        # Base64 encoded Ed25519 signature should be ~90 chars
        $isBase64 = $sigContent -match "^[A-Za-z0-9+/=]+$"
        $validLength = $sigContent.Trim().Length -ge 80
        
        Write-TestResult "Signature is base64 encoded" $isBase64
        Write-TestResult "Signature has valid length" $validLength
    } else {
        Write-TestSkipped "Signature validation" "Signature file not found"
    }
} catch {
    Write-TestResult "Signature validation" $false "Error: $_"
}

# ============================================================
# AUDIT TESTS
# ============================================================

Write-TestSection "AUDIT TESTS"

# Test: Audit record creation
try {
    $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
    
    if (Test-Path $bootstrapScript) {
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action audit --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        $auditFile = Join-Path $TestPath "logs\install_audit.json"
        $auditExists = Test-Path $auditFile
        
        Write-TestResult "Audit record file created" $auditExists
    } else {
        Write-TestSkipped "Audit record creation" "Bootstrap module not found"
    }
} catch {
    Write-TestResult "Audit record creation" $false "Error: $_"
}

# Test: Audit record content
try {
    $auditFile = Join-Path $TestPath "logs\install_audit.json"
    
    if (Test-Path $auditFile) {
        $auditData = Get-Content $auditFile -Raw | ConvertFrom-Json
        
        $hasTimestamp = $auditData.timestamp -ne $null
        $hasDeviceId = $auditData.device_id -ne $null
        $hasPolicyHash = $auditData.policy_hash.Length -eq 64
        $hasFingerprint = $auditData.public_key_fingerprint.Length -eq 64
        $hasEvents = $auditData.events.Count -gt 0
        
        Write-TestResult "Audit has timestamp" $hasTimestamp
        Write-TestResult "Audit has device ID" $hasDeviceId
        Write-TestResult "Audit has policy hash" $hasPolicyHash
        Write-TestResult "Audit has key fingerprint" $hasFingerprint
        Write-TestResult "Audit has bootstrap events" $hasEvents
    } else {
        Write-TestSkipped "Audit record content" "Audit file not found"
    }
} catch {
    Write-TestResult "Audit record content" $false "Error: $_"
}

# ============================================================
# VERIFICATION TESTS
# ============================================================

Write-TestSection "VERIFICATION TESTS"

# Test: Full verification
try {
    $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
    
    if (Test-Path $bootstrapScript) {
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action verify --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        Write-TestResult "Full bootstrap verification" $json.success
        
        if (-not $json.success -and $json.errors) {
            foreach ($err in $json.errors) {
                Write-Host "         Error: $err" -ForegroundColor Yellow
            }
        }
    } else {
        Write-TestSkipped "Full verification" "Bootstrap module not found"
    }
} catch {
    Write-TestResult "Full verification" $false "Error: $_"
}

# ============================================================
# FULL BOOTSTRAP TEST
# ============================================================

Write-TestSection "FULL BOOTSTRAP TEST"

# Test: Complete bootstrap flow
try {
    # Create fresh test directory
    $freshTestPath = "$env:TEMP\AkshayAI_Bootstrap_Fresh_$([System.Guid]::NewGuid().ToString().Substring(0,8))"
    New-Item -ItemType Directory -Path $freshTestPath -Force | Out-Null
    New-Item -ItemType Directory -Path "$freshTestPath\.akshay\keys" -Force | Out-Null
    New-Item -ItemType Directory -Path "$freshTestPath\policies" -Force | Out-Null
    New-Item -ItemType Directory -Path "$freshTestPath\logs" -Force | Out-Null
    New-Item -ItemType Directory -Path "$freshTestPath\core\core\security" -Force | Out-Null
    
    # Copy bootstrap module
    if (Test-Path $sourceBootstrap) {
        Copy-Item -Path $sourceBootstrap -Destination "$freshTestPath\core\core\security\bootstrap.py" -Force
    }
    
    $bootstrapScript = Join-Path $freshTestPath "core\core\security\bootstrap.py"
    
    if (Test-Path $bootstrapScript) {
        $result = & $pythonPath $bootstrapScript --install-path $freshTestPath --action bootstrap --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        Write-TestResult "Complete bootstrap flow succeeds" $json.success
        
        # Verify all files exist
        $allFiles = @(
            "$freshTestPath\.akshay\device.json",
            "$freshTestPath\.akshay\keys\root_private.key",
            "$freshTestPath\.akshay\keys\root_public.key",
            "$freshTestPath\policies\base.yaml",
            "$freshTestPath\policies\active.yaml",
            "$freshTestPath\policies\active.yaml.sig",
            "$freshTestPath\logs\install_audit.json"
        )
        
        $allExist = $true
        foreach ($file in $allFiles) {
            if (-not (Test-Path $file)) {
                $allExist = $false
                Write-Host "         Missing: $file" -ForegroundColor Yellow
            }
        }
        
        Write-TestResult "All security files created" $allExist
    } else {
        Write-TestSkipped "Complete bootstrap flow" "Bootstrap module not found"
    }
    
    # Cleanup
    Remove-Item -Path $freshTestPath -Recurse -Force -ErrorAction SilentlyContinue
} catch {
    Write-TestResult "Complete bootstrap flow" $false "Error: $_"
}

# ============================================================
# CORRUPT KEY DETECTION TEST
# ============================================================

Write-TestSection "CORRUPT KEY DETECTION TEST"

# Test: Corrupt signature detection
try {
    $signatureFile = Join-Path $TestPath "policies\active.yaml.sig"
    
    if (Test-Path $signatureFile) {
        # Backup original
        $originalSig = Get-Content $signatureFile -Raw
        
        # Corrupt signature
        "CORRUPTED_SIGNATURE_DATA" | Out-File -FilePath $signatureFile -Force
        
        # Try to verify
        $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action verify --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        # Should fail verification
        $detectsCorruption = -not $json.success
        
        Write-TestResult "Detects corrupted policy signature" $detectsCorruption
        
        # Restore original
        $originalSig | Out-File -FilePath $signatureFile -Force
    } else {
        Write-TestSkipped "Corrupt signature detection" "Signature file not found"
    }
} catch {
    Write-TestResult "Corrupt signature detection" $false "Error: $_"
}

# ============================================================
# REINSTALL OVER EXISTING TEST
# ============================================================

Write-TestSection "REINSTALL OVER EXISTING TEST"

# Test: Reinstall preserves device ID
try {
    $deviceFile = Join-Path $TestPath ".akshay\device.json"
    
    if (Test-Path $deviceFile) {
        # Get original device ID
        $originalDevice = Get-Content $deviceFile -Raw | ConvertFrom-Json
        $originalId = $originalDevice.device_id
        
        # Run device-id action again (should load existing)
        $bootstrapScript = Join-Path $TestPath "core\core\security\bootstrap.py"
        $result = & $pythonPath $bootstrapScript --install-path $TestPath --action device-id --output json 2>&1 | Out-String
        $json = $result | ConvertFrom-Json
        
        $preservedId = $json.device_identity.device_id -eq $originalId
        
        Write-TestResult "Reinstall preserves existing device ID" $preservedId
    } else {
        Write-TestSkipped "Reinstall over existing" "Device file not found"
    }
} catch {
    Write-TestResult "Reinstall over existing" $false "Error: $_"
}

# ============================================================
# CLEANUP
# ============================================================

Write-Host ""
Write-Host "  Cleaning up test directory..." -ForegroundColor DarkGray
Remove-Item -Path $TestPath -Recurse -Force -ErrorAction SilentlyContinue

# ============================================================
# TEST SUMMARY
# ============================================================

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " TEST SUMMARY" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Passed:  $($script:TestResults.Passed)" -ForegroundColor Green
Write-Host "  Failed:  $($script:TestResults.Failed)" -ForegroundColor $(if ($script:TestResults.Failed -gt 0) { "Red" } else { "Green" })
Write-Host "  Skipped: $($script:TestResults.Skipped)" -ForegroundColor Yellow
Write-Host "  Total:   $($script:TestResults.Passed + $script:TestResults.Failed + $script:TestResults.Skipped)" -ForegroundColor White
Write-Host ""

if ($script:TestResults.Failed -eq 0) {
    Write-Host "  [OK] ALL TESTS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  [FAIL] SOME TESTS FAILED" -ForegroundColor Red
    exit 1
}
