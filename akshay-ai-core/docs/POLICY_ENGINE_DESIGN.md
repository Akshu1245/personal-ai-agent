# AKSHAY AI CORE — Policy Engine Design Specification

## Overview

The Policy Engine is the **authoritative decision layer** that operates independently of the LLM. Every action in the system must pass through policy evaluation before execution.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      POLICY ENGINE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POLICY STORE (Versioned)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │ v1.0.0      │  │ v1.1.0      │  │ v1.2.0      │  ← Current       │   │
│  │  │ (archived)  │  │ (archived)  │  │ (active)    │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POLICY LOADER                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │   Parse     │─▶│  Verify     │─▶│  Validate   │                  │   │
│  │  │   YAML      │  │  Signature  │  │   Schema    │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RULE ENGINE                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │   Context   │─▶│   Match     │─▶│  Decision   │                  │   │
│  │  │  Builder    │  │   Rules     │  │   Output    │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│           ┌──────────────────┼──────────────────┐                          │
│           ▼                  ▼                  ▼                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │  Permission │    │    Tool     │    │   Audit     │                    │
│  │  Firewall   │    │ Dispatcher  │    │    Log      │                    │
│  └─────────────┘    └─────────────┘    └─────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. FORMAL POLICY SCHEMA

### 1.1 Policy Document Structure

```yaml
# AKSHAY AI CORE Policy Document v1.0
# =====================================

# HEADER (Required)
# -----------------
apiVersion: policy.akshay.ai/v1
kind: PolicyDocument

# METADATA (Required)
# -------------------
metadata:
  # Unique policy identifier
  name: production-security-policy
  
  # Semantic version (MAJOR.MINOR.PATCH)
  version: "1.2.0"
  
  # Human-readable description
  description: "Production security policy for AKSHAY AI CORE"
  
  # Policy author
  author: admin
  
  # Creation timestamp (ISO 8601)
  created_at: "2026-01-19T10:30:00Z"
  
  # Last modified timestamp
  updated_at: "2026-01-19T10:30:00Z"
  
  # Policy inheritance (optional)
  inherits: base-policy  # References another policy by name
  
  # Labels for organization
  labels:
    environment: production
    team: security
    
# SIGNATURE (Required for enforcement)
# ------------------------------------
signature:
  # Signing algorithm
  algorithm: ed25519  # or hmac-sha256
  
  # Key identifier (public key fingerprint)
  key_id: "admin_key_2026"
  
  # Timestamp of signing
  signed_at: "2026-01-19T10:30:00Z"
  
  # Base64-encoded signature of policy body
  value: "BASE64_SIGNATURE_HERE"

# TRUST ZONES (Required)
# ----------------------
zones:
  - name: AI_CORE
    trust_level: 0
    description: "AI brain and memory - highest trust"
    
  - name: SYSTEM
    trust_level: 1
    description: "System components - high trust"
    
  - name: USER
    trust_level: 2
    description: "User interactions - medium trust"
    
  - name: DEVICE
    trust_level: 3
    description: "IoT and mobile devices - low-medium trust"
    
  - name: NETWORK
    trust_level: 4
    description: "External network operations - lowest trust"

# ALLOWLISTS (Optional)
# ---------------------
allowlists:
  web_domains:
    type: domain
    entries:
      - "*.github.com"
      - "*.google.com"
      - "api.openai.com"
      - "localhost"
      - "127.0.0.1"
      
  iot_devices:
    type: device
    entries:
      - id: "esp32-living-room-001"
        name: "Living Room Controller"
        capabilities: [light_control, sensor_read]
      - id: "esp32-bedroom-001"
        name: "Bedroom Controller"
        capabilities: [fan_control, temperature_read]
        
  trusted_plugins:
    type: plugin
    entries:
      - "core.memory"
      - "core.search"
      - "web.automation"
      
# RULES (Required - at least one)
# -------------------------------
rules:
  # Each rule has a unique ID and is evaluated in priority order
  - id: "DENY-001"
    description: "Default deny for unmatched requests"
    priority: 0  # Lowest priority - evaluated last
    enabled: true
    match:
      # Empty match = matches everything
      any: true
    action:
      type: DENY
      reason_code: DEFAULT_DENY
      reason_message: "No matching allow rule found"
      log_level: warning
      
  - id: "WEB-001"
    description: "Block web automation to unknown domains"
    priority: 100
    enabled: true
    match:
      tool:
        equals: "web_automation"
      domain:
        not_in: "@allowlists.web_domains"
    action:
      type: DENY
      reason_code: DOMAIN_NOT_ALLOWED
      reason_message: "Domain not in allowlist"
      log_level: warning
      alert: true
      
  - id: "WEB-002"
    description: "Allow web automation to allowed domains"
    priority: 99
    enabled: true
    match:
      tool:
        equals: "web_automation"
      domain:
        in: "@allowlists.web_domains"
    action:
      type: ALLOW
      require_confirmation: false
      log_level: info
      
  - id: "IOT-001"
    description: "Allow IoT control for registered devices"
    priority: 90
    enabled: true
    match:
      tool:
        equals: "iot_control"
      device_id:
        in: "@allowlists.iot_devices"
      trust_zone:
        equals: "DEVICE"
    action:
      type: ALLOW
      require_confirmation: true
      confirmation_message: "Allow AI to control {device_id}?"
      log_level: info
      
  - id: "CYBER-001"
    description: "Cyber lab requires legal acknowledgment"
    priority: 95
    enabled: true
    match:
      tool:
        in: ["network_scan", "port_scan", "vulnerability_scan"]
      environment:
        equals: "cyber_lab"
    conditions:
      - field: "context.legal_acknowledged"
        equals: true
      - field: "context.user_role"
        in: ["admin", "security_researcher"]
    action:
      type: ALLOW
      require_confirmation: true
      confirmation_message: "Confirm you have authorization to scan target?"
      log_level: notice
      audit_detailed: true
      
  - id: "TIME-001"
    description: "Block automation outside business hours"
    priority: 50
    enabled: true
    match:
      tool:
        in: ["web_automation", "bulk_email"]
    conditions:
      - field: "time.hour"
        not_between: [9, 18]
      - field: "time.weekday"
        in: [1, 2, 3, 4, 5]  # Monday-Friday
    action:
      type: DENY
      reason_code: OUTSIDE_BUSINESS_HOURS
      reason_message: "Automation blocked outside 9am-6pm Mon-Fri"
      log_level: info
      
  - id: "RATE-001"
    description: "Rate limit external API calls"
    priority: 80
    enabled: true
    match:
      tool:
        equals: "external_api"
    action:
      type: RATE_LIMIT
      limit:
        requests: 100
        period_seconds: 60
      exceed_action: DENY
      reason_code: RATE_LIMIT_EXCEEDED
      
  - id: "ZONE-001"
    description: "Block cross-zone access without elevation"
    priority: 200
    enabled: true
    match:
      source_zone:
        trust_level_gt: 2  # USER or lower
      target_zone:
        trust_level_lt: 2  # SYSTEM or AI_CORE
    conditions:
      - field: "session.elevated"
        equals: false
    action:
      type: DENY
      reason_code: CROSS_ZONE_DENIED
      reason_message: "Cannot access higher trust zone without elevation"
      log_level: warning
      alert: true

# FAILURE MODE (Required)
# -----------------------
failure_mode:
  # What to do if policy engine fails
  default_action: DENY
  
  # Safe mode permissions
  safe_mode:
    allowed_actions:
      - "memory.read"
      - "system.status"
      - "system.emergency_lock"
    blocked_actions:
      - "*"  # Everything else
```

### 1.2 Schema Field Types

| Field Type | Format | Example |
|------------|--------|---------|
| `string` | Plain text | `"web_automation"` |
| `string[]` | Array of strings | `["admin", "user"]` |
| `int` | Integer | `100` |
| `int[]` | Array of integers | `[1, 2, 3, 4, 5]` |
| `bool` | Boolean | `true` / `false` |
| `datetime` | ISO 8601 | `"2026-01-19T10:30:00Z"` |
| `duration` | Go-style | `"60s"`, `"5m"`, `"1h"` |
| `allowlist_ref` | Reference | `"@allowlists.web_domains"` |
| `zone_ref` | Zone name | `"DEVICE"` |
| `semver` | Semantic version | `"1.2.0"` |

### 1.3 Match Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match | `equals: "admin"` |
| `not_equals` | Not equal | `not_equals: "guest"` |
| `in` | Value in list | `in: ["admin", "user"]` |
| `not_in` | Value not in list | `not_in: ["blocked"]` |
| `contains` | String contains | `contains: "api"` |
| `not_contains` | String doesn't contain | `not_contains: "test"` |
| `starts_with` | String prefix | `starts_with: "/api/"` |
| `ends_with` | String suffix | `ends_with: ".json"` |
| `matches` | Regex match | `matches: "^[a-z]+$"` |
| `not_matches` | Regex doesn't match | `not_matches: "\\d+"` |
| `gt` / `greater_than` | Numeric > | `gt: 5` |
| `gte` | Numeric >= | `gte: 5` |
| `lt` / `less_than` | Numeric < | `lt: 10` |
| `lte` | Numeric <= | `lte: 10` |
| `between` | Numeric range | `between: [5, 10]` |
| `not_between` | Outside range | `not_between: [9, 18]` |
| `trust_level_gt` | Zone trust > | `trust_level_gt: 2` |
| `trust_level_lt` | Zone trust < | `trust_level_lt: 2` |
| `any` | Match anything | `any: true` |

### 1.4 Action Types

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `ALLOW` | Permit the action | `log_level` |
| `DENY` | Block the action | `reason_code`, `reason_message` |
| `RATE_LIMIT` | Apply rate limiting | `limit.requests`, `limit.period_seconds` |
| `REQUIRE_CONFIRMATION` | Ask user to confirm | `confirmation_message` |
| `REQUIRE_MFA` | Require MFA verification | `mfa_timeout_seconds` |
| `REQUIRE_ELEVATION` | Require elevated session | `elevation_reason` |
| `AUDIT_ONLY` | Allow but log detailed | `audit_fields` |

### 1.5 Reason Codes (Standardized)

```python
class PolicyReasonCode(Enum):
    # Deny reasons
    DEFAULT_DENY = "DEFAULT_DENY"
    DOMAIN_NOT_ALLOWED = "DOMAIN_NOT_ALLOWED"
    DEVICE_NOT_REGISTERED = "DEVICE_NOT_REGISTERED"
    PLUGIN_NOT_TRUSTED = "PLUGIN_NOT_TRUSTED"
    CROSS_ZONE_DENIED = "CROSS_ZONE_DENIED"
    OUTSIDE_BUSINESS_HOURS = "OUTSIDE_BUSINESS_HOURS"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    LEGAL_NOT_ACKNOWLEDGED = "LEGAL_NOT_ACKNOWLEDGED"
    ROLE_NOT_PERMITTED = "ROLE_NOT_PERMITTED"
    MFA_REQUIRED = "MFA_REQUIRED"
    ELEVATION_REQUIRED = "ELEVATION_REQUIRED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_REJECTED = "CONFIRMATION_REJECTED"
    POLICY_SIGNATURE_INVALID = "POLICY_SIGNATURE_INVALID"
    POLICY_EXPIRED = "POLICY_EXPIRED"
    SAFE_MODE_ACTIVE = "SAFE_MODE_ACTIVE"
    
    # Allow reasons
    RULE_MATCHED = "RULE_MATCHED"
    ALLOWLIST_MATCHED = "ALLOWLIST_MATCHED"
    ELEVATED_SESSION = "ELEVATED_SESSION"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"
```

---

## 2. SIGNATURE FORMAT

### 2.1 Signature Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    POLICY SIGNATURE FORMAT                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNED DATA = CANONICAL(policy_body)                           │
│                                                                 │
│  Where policy_body excludes the 'signature' block itself        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Canonical Format:                                       │   │
│  │  1. Sort all keys alphabetically                         │   │
│  │  2. Remove whitespace/comments                           │   │
│  │  3. UTF-8 encode                                         │   │
│  │  4. Hash with SHA-256                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  SIGNATURE = SIGN(HASH, private_key)                            │
│                                                                 │
│  Algorithms Supported:                                          │
│  - Ed25519 (recommended for production)                         │
│  - HMAC-SHA256 (for testing/development)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Management

```yaml
# Key Configuration File: /config/policy_keys.yaml
# NOTE: Private keys should be in secure storage, not this file

keys:
  admin_key_2026:
    algorithm: ed25519
    # Public key in base64
    public_key: "BASE64_PUBLIC_KEY"
    # Key fingerprint (first 16 chars of SHA256 of public key)
    fingerprint: "a1b2c3d4e5f67890"
    created_at: "2026-01-01T00:00:00Z"
    expires_at: "2027-01-01T00:00:00Z"
    allowed_operations:
      - sign_policy
      - verify_policy
    
  backup_key_2026:
    algorithm: ed25519
    public_key: "BASE64_PUBLIC_KEY"
    fingerprint: "1234567890abcdef"
    created_at: "2026-01-01T00:00:00Z"
    expires_at: "2027-01-01T00:00:00Z"
    allowed_operations:
      - verify_policy  # Cannot sign, only verify

# Key rotation schedule
rotation:
  frequency: yearly
  advance_notice_days: 30
  require_dual_signature_during_transition: true
```

### 2.3 Signature Verification Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                SIGNATURE VERIFICATION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. EXTRACT                                                     │
│     ├─ Read policy file                                         │
│     ├─ Extract signature block                                  │
│     └─ Extract policy body (without signature)                  │
│                                                                 │
│  2. LOOKUP KEY                                                  │
│     ├─ Get key_id from signature                                │
│     ├─ Load public key from key store                           │
│     ├─ Check key not expired                                    │
│     └─ Check key allowed for verify_policy                      │
│                                                                 │
│  3. VERIFY                                                      │
│     ├─ Canonicalize policy body                                 │
│     ├─ Hash with SHA-256                                        │
│     ├─ Verify signature with public key                         │
│     └─ Return VALID or INVALID                                  │
│                                                                 │
│  4. ON INVALID                                                  │
│     ├─ Log security alert                                       │
│     ├─ Reject policy load                                       │
│     ├─ Keep current policy active                               │
│     └─ Alert administrators                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. INTEGRATION POINTS

### 3.1 System Integration Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POLICY ENGINE INTEGRATION MAP                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      POLICY ENGINE                                   │   │
│  │                    (Central Authority)                               │   │
│  └───────────┬───────────┬───────────┬───────────┬───────────┬─────────┘   │
│              │           │           │           │           │              │
│              ▼           ▼           ▼           ▼           ▼              │
│  ┌───────────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ │
│  │  Permission   │ │   Tool    │ │  Memory   │ │Automation │ │  Bridge   │ │
│  │   Firewall    │ │Dispatcher │ │Governance │ │  Safety   │ │  Router   │ │
│  │ (Phase 2)     │ │ (Phase 2) │ │ (Phase 2) │ │ (Phase 2) │ │ (Phase 3) │ │
│  └───────────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ │
│         │               │              │             │             │        │
│         └───────────────┴──────────────┴─────────────┴─────────────┘        │
│                                    │                                        │
│                                    ▼                                        │
│                          ┌─────────────────┐                                │
│                          │   AUDIT LOG     │                                │
│                          │  (All decisions)│                                │
│                          └─────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Integration Point Details

| Component | Integration Method | Policy Check Point |
|-----------|-------------------|-------------------|
| **Permission Firewall** | Pre-evaluation hook | Before RBAC check |
| **Tool Dispatcher** | Pre-execution hook | Before tool invocation |
| **Memory Governance** | Access check hook | Before read/write |
| **Automation Safety** | Rule evaluation hook | Before automation execute |
| **Mobile Bridge** | Action filter | Before command relay |
| **IoT Bridge** | Device command filter | Before device command |
| **Cyber Lab** | Operation gate | Before any scan/analysis |
| **Web Automation** | Domain/action filter | Before browser action |

### 3.3 Integration Interface

```python
# Policy evaluation interface that all components must use
class PolicyEvaluationRequest:
    """Request for policy evaluation."""
    # Action context
    tool: str                      # Tool being invoked
    action: str                    # Specific action
    params: Dict[str, Any]         # Action parameters
    
    # User context
    user_id: str
    user_role: str
    session_id: str
    session_elevated: bool
    mfa_verified: bool
    
    # Trust context
    source_zone: str               # Where request originates
    target_zone: str               # What zone it targets
    
    # Device context (optional)
    device_id: Optional[str]
    device_type: Optional[str]
    
    # Environment context
    environment: str               # production, development, cyber_lab
    timestamp: datetime
    
    # Additional context
    extra: Dict[str, Any]          # Bridge-specific context


class PolicyEvaluationResult:
    """Result of policy evaluation."""
    # Decision
    decision: Literal["ALLOW", "DENY", "REQUIRE_CONFIRMATION", "RATE_LIMITED"]
    
    # Rule that matched
    matched_rule_id: Optional[str]
    matched_rule_priority: int
    
    # Reason
    reason_code: str               # Machine-readable code
    reason_message: str            # Human-readable message
    
    # Requirements (if not denied)
    requires_confirmation: bool
    confirmation_message: Optional[str]
    requires_mfa: bool
    requires_elevation: bool
    
    # Rate limit info (if rate limited)
    rate_limit_remaining: Optional[int]
    rate_limit_reset_at: Optional[datetime]
    
    # Audit
    should_log: bool
    log_level: str
    should_alert: bool
    
    # Metadata
    evaluation_time_ms: float
    policy_version: str
```

### 3.4 Failure Mode Behavior

```
┌─────────────────────────────────────────────────────────────────┐
│                    FAILURE MODE BEHAVIOR                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  IF policy engine fails to:                                     │
│  - Load policy file                                             │
│  - Verify signature                                             │
│  - Evaluate rules (exception/timeout)                           │
│                                                                 │
│  THEN system enters SAFE MODE:                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SAFE MODE PERMISSIONS                                   │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  ✓ ALLOWED                                               │   │
│  │    - memory.read (read-only memory access)              │   │
│  │    - system.status (check system health)                │   │
│  │    - system.emergency_lock (lock system)                │   │
│  │    - audit.read (view audit logs)                       │   │
│  │                                                         │   │
│  │  ✗ BLOCKED                                              │   │
│  │    - ALL tool executions                                │   │
│  │    - ALL automation triggers                            │   │
│  │    - ALL bridge operations                              │   │
│  │    - ALL memory writes                                  │   │
│  │    - ALL plugin installs                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  RECOVERY:                                                      │
│  1. Admin fixes policy file                                     │
│  2. Admin signs with valid key                                  │
│  3. Admin triggers policy reload                                │
│  4. System verifies and exits safe mode                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. FILE STRUCTURE

```
core/policy/
├── __init__.py           # Public API exports
├── schema.py             # Pydantic models for policy schema
├── errors.py             # Custom exceptions
├── loader.py             # YAML parsing and loading
├── signer.py             # Policy signing utilities
├── verifier.py           # Signature verification
├── engine.py             # Rule evaluation engine
├── simulator.py          # Dry-run simulation
├── store.py              # Versioned policy storage
├── integration.py        # Integration hooks for other components
├── safe_mode.py          # Safe mode controller
└── cli.py                # Command-line tools

config/
├── policies/
│   ├── base-policy.yaml      # Base policy (inherited)
│   ├── production.yaml       # Production policy
│   ├── development.yaml      # Development policy
│   └── cyber-lab.yaml        # Cyber lab policy
├── policy_keys.yaml          # Public keys for verification
└── allowlists/
    ├── web_domains.yaml
    ├── iot_devices.yaml
    └── trusted_plugins.yaml

tests/
└── test_policy/
    ├── test_schema.py
    ├── test_loader.py
    ├── test_signer.py
    ├── test_verifier.py
    ├── test_engine.py
    ├── test_simulator.py
    ├── test_integration.py
    └── test_safe_mode.py
```

---

## 5. CLI COMMANDS

```bash
# Sign a policy
akshay policy sign policy.yaml --key admin_key_2026 --output policy.signed.yaml

# Verify a policy signature
akshay policy verify policy.signed.yaml

# Validate policy schema (no signature check)
akshay policy validate policy.yaml

# Simulate a decision
akshay policy simulate --action action.json --policy policy.yaml

# List policy versions
akshay policy versions

# Rollback to previous version
akshay policy rollback --version 1.1.0

# Reload active policy
akshay policy reload

# Show current policy status
akshay policy status

# Enter/exit safe mode manually
akshay policy safe-mode --enable --reason "Manual maintenance"
akshay policy safe-mode --disable
```

---

## 6. APPROVAL CHECKPOINT

### Questions for Review

1. **Schema Completeness**
   - Are all necessary match operators included?
   - Should we add more action types?
   - Is the allowlist reference format (`@allowlists.name`) acceptable?

2. **Signature Algorithm**
   - Ed25519 for production, HMAC-SHA256 for development?
   - Should we support key rotation with dual signatures?

3. **Integration Depth**
   - Should policy check happen before or after Permission Firewall?
   - Should bridges have their own policy namespaces?

4. **Failure Mode**
   - Is the safe mode permission set appropriate?
   - Should safe mode auto-recover on policy fix?

5. **Storage Format**
   - Store signed policies as single YAML files?
   - Version history in separate directory or database?

### Sign-off Required

- [ ] Policy schema approved
- [ ] Signature format approved
- [ ] Integration points approved
- [ ] Failure mode behavior approved

---

**Awaiting approval before implementation.**

Upon approval, I will implement in this order:
1. `schema.py` + `errors.py` (~300 lines)
2. `signer.py` + `verifier.py` (~400 lines)
3. `loader.py` + `store.py` (~350 lines)
4. `engine.py` (~500 lines)
5. `simulator.py` + `cli.py` (~300 lines)
6. `integration.py` + `safe_mode.py` (~400 lines)
7. Tests (~600 lines)
