# AKSHAY AI CORE — Pre-Release Audit

## EXECUTION FLOW MAP

### 1. INSTALL FLOW
```
User Downloads → install.ps1
    │
    ├─► [PREFLIGHT CHECKS]
    │   ├── Test-WindowsVersion (Win 10/11)
    │   ├── Test-PowerShellVersion (5.1+)
    │   ├── Test-PythonInstallation (3.10-3.13)
    │   ├── Test-DiskSpace (2GB min)
    │   └── Test-Memory (4GB min)
    │
    ├─► [FOLDER CREATION]
    │   ├── $InstallPath/
    │   ├── .akshay/ (hidden)
    │   ├── .akshay/keys/
    │   ├── .akshay/sessions/
    │   ├── config/
    │   ├── data/
    │   ├── logs/
    │   ├── policies/
    │   ├── plugins/
    │   └── demo/
    │
    ├─► [VENV CREATION]
    │   ├── python -m venv .akshay/venv
    │   └── pip install -r requirements.txt
    │
    ├─► [SECURITY BOOTSTRAP] ← core/security/bootstrap.py
    │   ├── Step 1: Generate Device Identity (UUID + HW fingerprint)
    │   ├── Step 2: Generate Ed25519 Root Keypair (UNENCRYPTED)
    │   ├── Step 3: Create Default Policy (signed YAML)
    │   ├── Step 4: Create Audit Record
    │   └── Step 5: Verify Installation
    │
    ├─► [POST-INSTALL]
    │   ├── Write install_audit.json
    │   ├── Create launchers (ai.ps1, ai.bat) ← MISSING
    │   └── Show success screen
    │
    └─► EXIT (Key still unencrypted - waiting for first-run)
```

### 2. FIRST-RUN FLOW ← MISSING IMPLEMENTATION
```
User runs: ai.ps1
    │
    ├─► [CHECK FIRST_RUN]
    │   └── if .akshay/first_run.json missing → Launch Wizard
    │
    ├─► [WIZARD SCREENS] ← NOT IMPLEMENTED
    │   ├── Screen 1: Welcome
    │   ├── Screen 2: Create Admin User (name, role=ROOT)
    │   ├── Screen 3: Set PIN (6-12 digits, twice)
    │   │              └── core/security/keystore.py → setup_pin()
    │   │                  ├── Encrypt root_private.key → root_private.enc
    │   │                  └── Secure delete plaintext key
    │   ├── Screen 4: Voice Setup (optional)
    │   ├── Screen 5: Mode Select (Normal / Demo)
    │   ├── Screen 6: Recovery Key Display (ONE-TIME)
    │   └── Screen 7: Finish
    │
    ├─► [STORE CONFIG]
    │   ├── config/admin.json
    │   └── .akshay/first_run.json (marks completion)
    │
    └─► [LAUNCH SYSTEM]
        └── Start API gateway
```

### 3. NORMAL STARTUP FLOW ← MISSING LAUNCHER
```
User runs: ai.ps1 [--demo] [--safe] [--recovery] [--no-voice]
    │
    ├─► [ACTIVATE VENV]
    │   └── .akshay/venv/Scripts/Activate.ps1
    │
    ├─► [CHECK MODE]
    │   ├── --demo → Load demo policy, mock devices
    │   ├── --safe → SAFE MODE (read-only operations)
    │   ├── --recovery → Skip plugins, limited ops
    │   └── default → Normal mode
    │
    ├─► [START SERVICES]
    │   ├── API Gateway (uvicorn api.main:app)
    │   ├── Voice Service (optional)
    │   └── UI Bridge (optional)
    │
    └─► RUNNING
```

### 4. REQUEST PROCESSING FLOW
```
Request (Terminal/API/Voice/UI)
    │
    ├─► [INTERFACE ADAPTER]
    │   └── core/gateway/base.py → GatewayRequest
    │
    ├─► [SESSION VALIDATION]
    │   └── core/gateway/session.py
    │       ├── Validate JWT token
    │       ├── Check expiry
    │       └── Verify device fingerprint
    │
    ├─► [TRUST MAPPING]
    │   └── core/gateway/trust_map.py
    │       ├── TERMINAL → SYSTEM (100)
    │       ├── API → USER (50) → can elevate to OPERATOR (75)
    │       ├── VOICE → USER (50) → CANNOT elevate
    │       └── Voice has blocked_actions: shutdown, reboot, delete, wipe
    │
    ├─► [RATE LIMITING]
    │   └── core/gateway/router.py → GatewayRateLimiter
    │       ├── Per-interface limits
    │       └── Sliding window algorithm
    │
    ├─► [POLICY ENGINE]
    │   └── core/policy/engine.py
    │       ├── Check SAFE_MODE → only allow safe actions
    │       ├── Load FinalPolicy
    │       ├── Apply global rate limits
    │       ├── Sort rules by priority
    │       ├── Match tool/action
    │       ├── Evaluate conditions
    │       └── Return Decision (ALLOW/DENY/ASK)
    │
    ├─► [CONFIRMATION] (if required)
    │   └── core/gateway/router.py → ConfirmationManager
    │       ├── For destructive actions
    │       └── Voice ALWAYS requires confirmation
    │
    ├─► [TOOL DISPATCHER]
    │   └── core/security/dispatcher.py
    │       ├── Permission check (firewall.py)
    │       ├── Sandbox execution
    │       ├── Rate limit check
    │       ├── Execute
    │       ├── Validate output
    │       └── Log to audit
    │
    ├─► [AUDIT LOG]
    │   └── core/security/audit_log.py
    │       ├── Hash chain (tamper-evident)
    │       ├── Signature (non-repudiation)
    │       └── Append-only writes
    │
    └─► Response
```

### 5. DEMO MODE FLOW
```
ai.ps1 --demo
    │
    ├─► [LOAD DEMO POLICY]
    │   └── policies/demo.yaml ← MISSING
    │       ├── Restricted trust zones
    │       ├── Blocked: file writes, system ops, API keys
    │       └── Mock devices only
    │
    ├─► [MOCK SYSTEMS]
    │   ├── Mock filesystem (demo/mock_filesystem.yaml)
    │   ├── Mock devices (demo/mock_devices.yaml)
    │   └── Mock web (demo/mock_web.yaml)
    │
    ├─► [VISUAL INDICATOR]
    │   └── "🎮 DEMO MODE ACTIVE" banner
    │
    └─► [AUTO-RESET]
        └── On exit: clear demo state
```

### 6. RECOVERY MODE FLOW
```
ai.ps1 --recovery
    │
    ├─► [FORCE SAFE MODE]
    │   └── SAFE_MODE_ALLOWED actions only:
    │       ├── system.status
    │       ├── policy.status
    │       ├── memory.read (public only)
    │       ├── emergency.lock
    │       └── audit.read
    │
    ├─► [SKIP PLUGINS]
    │   └── No custom plugins loaded
    │
    ├─► [RECOVERY OPTIONS]
    │   ├── Reset PIN (with recovery key)
    │   ├── View audit logs
    │   └── Reset to safe policy
    │
    └─► EXIT
```

### 7. UNINSTALL FLOW ← MISSING IMPLEMENTATION
```
User runs: uninstall.ps1
    │
    ├─► [CONFIRM INTENT]
    │   └── "Are you sure? Type UNINSTALL to confirm"
    │
    ├─► [VERIFY PIN]
    │   └── core/security/keystore.py → unlock()
    │       └── Wrong PIN 5x → ABORT (require recovery)
    │
    ├─► [STOP SERVICES]
    │   ├── Stop API process
    │   ├── Stop voice service
    │   └── Stop background tasks
    │
    ├─► [CLEANUP]
    │   ├── Remove PATH entry
    │   ├── Remove shortcuts
    │   └── Remove Start Menu entries
    │
    ├─► [SECURE WIPE]
    │   ├── .akshay/keys/* (3-pass overwrite)
    │   ├── config/admin.json
    │   └── .akshay/sessions/*
    │
    ├─► [DELETE FILES]
    │   └── Remove entire InstallPath
    │
    ├─► [WRITE LOG]
    │   └── %TEMP%/AkshayAI_uninstall.log
    │
    └─► [CONFIRM CLEAN]
        └── "AKSHAY AI CORE has been completely removed"
```

---

## SECURITY THREAT CHECKLIST

### 1. PRIVATE KEY SECURITY
| Threat | Check | Status |
|--------|-------|--------|
| Plaintext key on disk after setup | After PIN setup, root_private.key deleted | ⚠️ NEEDS FIRST-RUN WIZARD |
| Key in memory after lock | KeyStore.lock() clears _private_key | ✅ |
| Weak PIN accepted | validate_pin_format() rejects <6 digits, common patterns | ✅ |
| Brute force PIN | 5 attempts → SAFE_MODE (5 min lockout) | ✅ |
| Key without encryption marker | AKSHAY_ENCRYPTED_V1 header required | ✅ |
| scrypt parameters too weak | N=2^14, r=8, p=1 (OWASP compliant) | ✅ |

### 2. SECRETS PROTECTION
| Threat | Check | Status |
|--------|-------|--------|
| PIN logged to files | PIN not logged in audit_log.py | ⚠️ NEEDS VERIFICATION |
| API keys in logs | Settings filtered in logger.py | ⚠️ NEEDS VERIFICATION |
| Recovery key exposed | Display once, hash stored, not retrievable | ✅ |
| JWT secret in logs | Should use HMAC_SECRET from env | ⚠️ CHECK |

### 3. POLICY ENGINE BYPASS
| Threat | Check | Status |
|--------|-------|--------|
| Direct tool access | All tools route through dispatcher.py | ✅ |
| Skip validation | Engine always validates request schema | ✅ |
| Exception leaks | All errors caught, converted to DENY | ✅ |
| LLM output trusted | Engine never depends on LLM output | ✅ |
| SAFE_MODE bypass | SAFE_MODE_ALLOWED is frozen set | ✅ |

### 4. DEMO MODE ESCALATION
| Threat | Check | Status |
|--------|-------|--------|
| Demo → Normal escalation | Demo policy should block escalation | ⚠️ MISSING DEMO POLICY |
| Demo file writes | Should be blocked | ⚠️ NEEDS DEMO POLICY |
| Demo API key access | Should be blocked | ⚠️ NEEDS DEMO POLICY |
| Demo network access | Should be mocked/blocked | ⚠️ NEEDS IMPLEMENTATION |

### 5. VOICE INTERFACE SECURITY
| Threat | Check | Status |
|--------|-------|--------|
| Voice admin actions | blocked_actions includes: shutdown, reboot, delete, wipe | ✅ |
| Voice elevation | max_zone = USER (cannot elevate to OPERATOR/SYSTEM) | ✅ |
| Voice confirmation skip | always_confirm_destructive = True | ✅ |
| Low confidence execution | min_confidence = 0.7, destructive = 0.9 | ✅ |
| Replay attack | require_wake_word = True | ✅ |
| No face presence | requires_face_for_sensitive = True | ✅ |

### 6. RECOVERY MODE RESTRICTIONS
| Threat | Check | Status |
|--------|-------|--------|
| Recovery signs policies | Recovery cannot access private key | ⚠️ NEEDS VERIFICATION |
| Recovery modifies data | SAFE_MODE_ALLOWED is read-only | ✅ |
| Recovery loads plugins | Should skip plugins | ⚠️ NEEDS IMPLEMENTATION |

### 7. RATE LIMITING
| Threat | Check | Status |
|--------|-------|--------|
| Rate limits enforced | GatewayRateLimiter per interface | ✅ |
| Memory exhaustion | Sliding window with cutoff | ✅ |
| Different limits per interface | TERMINAL=1000, API=200, VOICE=30 | ✅ |

### 8. SESSION SECURITY
| Threat | Check | Status |
|--------|-------|--------|
| Session expiry | ACCESS_TOKEN_EXPIRY = 1 hour | ✅ |
| Elevation timeout | ELEVATION_DURATION = 30 min | ✅ |
| Device binding | device_fingerprint checked | ✅ |
| Max sessions | MAX_SESSIONS_PER_USER = 10 | ✅ |

### 9. AUDIT LOG INTEGRITY
| Threat | Check | Status |
|--------|-------|--------|
| Log tampering | Hash chain + signatures | ✅ |
| Log deletion | Append-only file operations | ✅ |
| Missing entries | Sequence numbers tracked | ✅ |
| Unsigned entries | All entries get entry_hash | ✅ |

---

## CRITICAL GAPS IDENTIFIED

### Missing Components (Must Fix)
1. **ai.ps1 / ai.bat** - Launcher scripts don't exist
2. **First-Run Wizard** - UI for PIN setup, admin creation
3. **uninstall.ps1** - Uninstaller doesn't exist
4. **Demo Policy** - policies/demo.yaml not created
5. **tests/test_release.ps1** - Release test script needed

### Security Gaps (Must Fix)
1. **Plaintext Key Exposure** - Key remains unencrypted until first-run wizard runs
2. **Demo Mode Policy** - No demo.yaml policy to restrict demo operations
3. **Recovery Mode Implementation** - --recovery flag handling incomplete

### Verification Needed
1. **Secrets in Logs** - Verify PIN/keys never logged
2. **JWT Secret Storage** - Verify not hardcoded
3. **Recovery Key Operations** - Verify cannot sign policies

---

## RECOMMENDED BUILD ORDER

1. **Create Launcher** (ai.ps1, ai.bat) - Entry point
2. **Create First-Run Wizard** - PIN encryption trigger
3. **Create Demo Policy** - Demo mode restrictions
4. **Create Uninstaller** - Clean removal
5. **Create Release Tests** - Verify all flows
6. **Fix Identified Gaps** - Security hardening

---

*Audit prepared for approval before implementation*
