# ============================================================
# AKSHAY AI CORE — Key Store Test Suite
# ============================================================
# Tests PIN encryption, unlock, lockout, and recovery
# ============================================================

param(
    [switch]$Verbose,
    [string]$TestPath = "$env:TEMP\AkshayAI_KeyStore_Test_$([System.Guid]::NewGuid().ToString().Substring(0,8))"
)

$ErrorActionPreference = "Continue"
$script:PassCount = 0
$script:FailCount = 0
$script:SkipCount = 0

# ============================================================
# Test Utilities
# ============================================================

function Write-TestHeader {
    param([string]$Title)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "        AKSHAY AI CORE - KEY STORE TEST SUITE" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Test directory: $TestPath" -ForegroundColor Gray
}

function Write-TestSection {
    param([string]$Name)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor White
    Write-Host " $Name" -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor White
    Write-Host ""
}

function Write-TestResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Details = ""
    )
    
    if ($Passed) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:PassCount++
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        if ($Details) {
            Write-Host "         $Details" -ForegroundColor Yellow
        }
        $script:FailCount++
    }
}

function Write-TestSkipped {
    param(
        [string]$Name,
        [string]$Reason = ""
    )
    Write-Host "  [SKIP] $Name" -ForegroundColor Yellow
    if ($Reason) {
        Write-Host "         Reason: $Reason" -ForegroundColor Gray
    }
    $script:SkipCount++
}

# ============================================================
# Test Setup
# ============================================================

Write-TestHeader

# Detect Python
$pythonPath = "python"

# Find the keystore module
$sourceKeyStore = "D:\jarvis\akshay-ai-core\core\security\keystore.py"
$sourceBootstrap = "D:\jarvis\akshay-ai-core\core\security\bootstrap.py"

if (-not (Test-Path $sourceKeyStore)) {
    Write-Host "  [ERROR] KeyStore module not found at: $sourceKeyStore" -ForegroundColor Red
    exit 1
}

# Create test directory structure
Write-Host "  Setting up test environment..." -ForegroundColor Gray
New-Item -ItemType Directory -Path $TestPath -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\.akshay\keys" -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\policies" -Force | Out-Null
New-Item -ItemType Directory -Path "$TestPath\logs" -Force | Out-Null

# Bootstrap keys first (creates unencrypted keys)
Write-Host "  Bootstrapping security keys..." -ForegroundColor Gray
$bootstrapResult = & $pythonPath $sourceBootstrap --install-path $TestPath --action bootstrap --output json 2>&1 | Out-String
try {
    $bootstrapJson = $bootstrapResult | ConvertFrom-Json
    if (-not $bootstrapJson.success) {
        Write-Host "  [ERROR] Bootstrap failed: $($bootstrapJson.errors -join ', ')" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Bootstrap complete." -ForegroundColor Gray
} catch {
    Write-Host "  [ERROR] Failed to parse bootstrap result: $_" -ForegroundColor Red
    Write-Host "  Output: $bootstrapResult" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# ============================================================
# INITIAL STATE TESTS
# ============================================================

Write-TestSection "INITIAL STATE TESTS"

# Test: Status before PIN setup
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action status --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Initial state is correct" ($json.state -eq "unlocked")
    Write-TestResult "Needs PIN setup detected" ($json.needs_pin_setup -eq $true)
    Write-TestResult "Not in safe mode initially" ($json.is_safe_mode -eq $false)
    Write-TestResult "Has public key" ($json.has_public_key -eq $true)
    Write-TestResult "No encrypted key yet" ($json.has_encrypted_key -eq $false)
} catch {
    Write-TestResult "Initial status check" $false "Error: $_"
}

# ============================================================
# PIN VALIDATION TESTS
# ============================================================

Write-TestSection "PIN VALIDATION TESTS"

# Test: PIN too short
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action setup-pin --pin "123" --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Rejects PIN too short" (-not $json.success -and $json.error -like "*at least*")
} catch {
    Write-TestResult "PIN too short validation" $false "Error: $_"
}

# Test: PIN with letters
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action setup-pin --pin "123abc" --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Rejects PIN with letters" (-not $json.success -and $json.error -like "*only digits*")
} catch {
    Write-TestResult "PIN with letters validation" $false "Error: $_"
}

# Test: Weak PIN (all same digit)
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action setup-pin --pin "777777" --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Rejects weak PIN (all same)" (-not $json.success -and ($json.error -like "*same digit*"))
} catch {
    Write-TestResult "Weak PIN validation" $false "Error: $_"
}

# Test: Common PIN
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action setup-pin --pin "123456" --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Rejects common PIN" (-not $json.success -and $json.error -like "*too common*")
} catch {
    Write-TestResult "Common PIN validation" $false "Error: $_"
}

# ============================================================
# PIN SETUP TESTS
# ============================================================

Write-TestSection "PIN SETUP TESTS"

$testPin = "847291"  # Good PIN for testing

# Test: Setup PIN successfully
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action setup-pin --pin $testPin --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "PIN setup succeeds" $json.success
} catch {
    Write-TestResult "PIN setup" $false "Error: $_"
}

# Test: Encrypted key file exists
$encryptedKeyFile = Join-Path $TestPath ".akshay\keys\root_private.enc"
$unencryptedKeyFile = Join-Path $TestPath ".akshay\keys\root_private.key"

Write-TestResult "Encrypted key file created" (Test-Path $encryptedKeyFile)
Write-TestResult "Unencrypted key removed" (-not (Test-Path $unencryptedKeyFile))

# Test: Encrypted key has marker
try {
    $keyContent = Get-Content $encryptedKeyFile -Raw -Encoding Byte
    $marker = [System.Text.Encoding]::ASCII.GetString($keyContent[0..19])
    
    Write-TestResult "Encrypted key has marker" ($marker -eq "AKSHAY_ENCRYPTED_V1`n")
} catch {
    Write-TestResult "Encrypted key marker" $false "Error: $_"
}

# Test: State file created
$stateFile = Join-Path $TestPath ".akshay\keys\keystore.json"
Write-TestResult "State file created" (Test-Path $stateFile)

# Test: State shows locked
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action status --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "State is locked after setup" ($json.state -eq "locked")
    Write-TestResult "No longer needs PIN setup" ($json.needs_pin_setup -eq $false)
    Write-TestResult "Has encrypted key" ($json.has_encrypted_key -eq $true)
} catch {
    Write-TestResult "Post-setup state" $false "Error: $_"
}

# ============================================================
# UNLOCK TESTS
# ============================================================

Write-TestSection "UNLOCK TESTS"

# Test: Unlock with wrong PIN
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action unlock --pin "000000" --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Wrong PIN rejected" (-not $json.success)
    Write-TestResult "Wrong PIN shows attempts remaining" ($json.error -like "*attempts remaining*")
} catch {
    Write-TestResult "Wrong PIN handling" $false "Error: $_"
}

# Test: Unlock with correct PIN
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action unlock --pin $testPin --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Correct PIN unlocks" $json.success
    Write-TestResult "State is unlocked" ($json.state -eq "unlocked")
} catch {
    Write-TestResult "Correct PIN unlock" $false "Error: $_"
}

# Test: Lock again
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action lock --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Lock succeeds" $json.success
    Write-TestResult "State is locked" ($json.state -eq "locked")
} catch {
    Write-TestResult "Lock operation" $false "Error: $_"
}

# ============================================================
# LOCKOUT TESTS
# ============================================================

Write-TestSection "LOCKOUT TESTS"

# Create fresh test environment for lockout
$lockoutTestPath = "$env:TEMP\AkshayAI_Lockout_Test_$([System.Guid]::NewGuid().ToString().Substring(0,8))"
New-Item -ItemType Directory -Path $lockoutTestPath -Force | Out-Null
New-Item -ItemType Directory -Path "$lockoutTestPath\.akshay\keys" -Force | Out-Null
New-Item -ItemType Directory -Path "$lockoutTestPath\policies" -Force | Out-Null
New-Item -ItemType Directory -Path "$lockoutTestPath\logs" -Force | Out-Null

# Bootstrap
& $pythonPath $sourceBootstrap --install-path $lockoutTestPath --action bootstrap --output json 2>&1 | Out-Null

# Setup PIN
& $pythonPath $sourceKeyStore --install-path $lockoutTestPath --action setup-pin --pin "192837" --output json 2>&1 | Out-Null

Write-Host "  Testing lockout (5 wrong attempts)..." -ForegroundColor Gray

# Make 5 wrong attempts
$wrongPin = "000000"
$lastResult = $null
for ($i = 1; $i -le 5; $i++) {
    $result = & $pythonPath $sourceKeyStore --install-path $lockoutTestPath --action unlock --pin $wrongPin --output json 2>&1 | Out-String
    $lastResult = $result | ConvertFrom-Json
    
    if ($Verbose) {
        Write-Host "    Attempt $i`: $($lastResult.error)" -ForegroundColor Gray
    }
}

# Test: Safe mode triggered
try {
    $result = & $pythonPath $sourceKeyStore --install-path $lockoutTestPath --action status --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Safe mode triggered after 5 attempts" ($json.is_safe_mode -eq $true)
    Write-TestResult "Lockout time remaining" ($json.lockout_remaining -gt 0)
    Write-TestResult "Zero attempts remaining" ($json.attempts_remaining -eq 0)
} catch {
    Write-TestResult "Safe mode status" $false "Error: $_"
}

# Test: Correct PIN rejected in safe mode
try {
    $result = & $pythonPath $sourceKeyStore --install-path $lockoutTestPath --action unlock --pin "192837" --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Correct PIN rejected in safe mode" (-not $json.success -and $json.error_type -eq "safe_mode")
} catch {
    Write-TestResult "Safe mode rejection" $false "Error: $_"
}

# Cleanup lockout test
Remove-Item -Path $lockoutTestPath -Recurse -Force -ErrorAction SilentlyContinue

# ============================================================
# CHANGE PIN TESTS
# ============================================================

Write-TestSection "CHANGE PIN TESTS"

$newPin = "293847"

# Test: Change PIN
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action change-pin --pin $testPin --new-pin $newPin --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "PIN change succeeds" $json.success
} catch {
    Write-TestResult "PIN change" $false "Error: $_"
}

# Test: Old PIN no longer works
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action unlock --pin $testPin --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "Old PIN rejected after change" (-not $json.success)
} catch {
    Write-TestResult "Old PIN rejection" $false "Error: $_"
}

# Test: New PIN works
try {
    $result = & $pythonPath $sourceKeyStore --install-path $TestPath --action unlock --pin $newPin --output json 2>&1 | Out-String
    $json = $result | ConvertFrom-Json
    
    Write-TestResult "New PIN works" $json.success
} catch {
    Write-TestResult "New PIN unlock" $false "Error: $_"
}

# ============================================================
# AUDIT LOG TESTS
# ============================================================

Write-TestSection "AUDIT LOG TESTS"

$auditLog = Join-Path $TestPath "logs\keystore_audit.log"

Write-TestResult "Audit log exists" (Test-Path $auditLog)

if (Test-Path $auditLog) {
    try {
        $auditContent = Get-Content $auditLog -Raw
        
        Write-TestResult "Audit log has PIN_SETUP event" ($auditContent -like "*PIN_SETUP*")
        Write-TestResult "Audit log has UNLOCK event" ($auditContent -like "*UNLOCK*")
        Write-TestResult "Audit log has LOCK event" ($auditContent -like "*LOCK*")
        Write-TestResult "Audit log has PIN_CHANGE event" ($auditContent -like "*PIN_CHANGE*")
        Write-TestResult "Audit log has failed attempt" ($auditContent -like "*FAILURE*")
    } catch {
        Write-TestResult "Audit log content" $false "Error: $_"
    }
}

# ============================================================
# ENCRYPTION SECURITY TESTS
# ============================================================

Write-TestSection "ENCRYPTION SECURITY TESTS"

# Test: Encrypted key cannot be read as PEM
try {
    $encContent = Get-Content $encryptedKeyFile -Raw
    $isPEM = $encContent -like "*-----BEGIN*"
    
    Write-TestResult "Encrypted key is not plain PEM" (-not $isPEM)
} catch {
    Write-TestResult "Encrypted key format" $false "Error: $_"
}

# Test: Different PINs produce different encrypted keys
$secTestPath = "$env:TEMP\AkshayAI_Sec_Test_$([System.Guid]::NewGuid().ToString().Substring(0,8))"
New-Item -ItemType Directory -Path $secTestPath -Force | Out-Null
New-Item -ItemType Directory -Path "$secTestPath\.akshay\keys" -Force | Out-Null
New-Item -ItemType Directory -Path "$secTestPath\policies" -Force | Out-Null
New-Item -ItemType Directory -Path "$secTestPath\logs" -Force | Out-Null

& $pythonPath $sourceBootstrap --install-path $secTestPath --action bootstrap --output json 2>&1 | Out-Null
& $pythonPath $sourceKeyStore --install-path $secTestPath --action setup-pin --pin "567890" --output json 2>&1 | Out-Null

try {
    $enc1 = Get-Content $encryptedKeyFile -Raw
    $enc2 = Get-Content (Join-Path $secTestPath ".akshay\keys\root_private.enc") -Raw
    
    Write-TestResult "Different PINs produce different ciphertext" ($enc1 -ne $enc2)
} catch {
    Write-TestResult "Encryption uniqueness" $false "Error: $_"
}

Remove-Item -Path $secTestPath -Recurse -Force -ErrorAction SilentlyContinue

# ============================================================
# CLEANUP
# ============================================================

Write-Host ""
Write-Host "  Cleaning up test directory..." -ForegroundColor Gray
Remove-Item -Path $TestPath -Recurse -Force -ErrorAction SilentlyContinue

# ============================================================
# TEST SUMMARY
# ============================================================

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " TEST SUMMARY" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Passed:  $script:PassCount" -ForegroundColor Green
Write-Host "  Failed:  $script:FailCount" -ForegroundColor Red
Write-Host "  Skipped: $script:SkipCount" -ForegroundColor Yellow
Write-Host "  Total:   $($script:PassCount + $script:FailCount + $script:SkipCount)" -ForegroundColor White
Write-Host ""

if ($script:FailCount -eq 0) {
    Write-Host "  [OK] ALL TESTS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  [FAIL] SOME TESTS FAILED" -ForegroundColor Red
    exit 1
}
