# AKSHAY AI CORE — Security Architecture

## Overview

The AKSHAY AI CORE security architecture implements defense-in-depth with multiple layers of protection. All operations must pass through security checkpoints before execution.

```
┌─────────────────────────────────────────────────────────────────┐
│                     SECURITY ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   REQUEST   │───▶│  FIREWALL   │───▶│ DISPATCHER  │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                            │                  │                 │
│                            ▼                  ▼                 │
│                     ┌─────────────┐    ┌─────────────┐        │
│                     │   AUDIT     │    │  SANDBOX    │        │
│                     │    LOG      │    │ EXECUTION   │        │
│                     └─────────────┘    └─────────────┘        │
│                                               │                 │
│  ┌─────────────┐    ┌─────────────┐          │                 │
│  │   MEMORY    │◀───│  SECRETS    │◀─────────┘                 │
│  │ GOVERNANCE  │    │  MANAGER    │                            │
│  └─────────────┘    └─────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Security Principles

1. **Deny by Default** - All access is denied unless explicitly granted
2. **Audit Everything** - Every security decision is logged
3. **Defense in Depth** - Multiple layers of protection
4. **Least Privilege** - Minimum permissions required
5. **Fail Secure** - Errors result in denied access

---

## 1. Permission Firewall

**Location:** `core/security/firewall.py`

The Permission Firewall is the central gate for all permission checks.

### Permission Model

```python
class Permission(Enum):
    # Memory Operations
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    DELETE_MEMORY = "delete_memory"
    
    # Plugin Operations
    EXECUTE_PLUGINS = "execute_plugins"
    INSTALL_PLUGINS = "install_plugins"
    MANAGE_PLUGINS = "manage_plugins"
    
    # Automation
    VIEW_AUTOMATIONS = "view_automations"
    CREATE_AUTOMATIONS = "create_automations"
    TRIGGER_AUTOMATIONS = "trigger_automations"
    
    # Admin
    ADMIN_MANAGE_USERS = "admin_manage_users"
    ADMIN_SYSTEM_CONFIG = "admin_system_config"
    ADMIN_VIEW_LOGS = "admin_view_logs"
```

### Role Hierarchy

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| **ADMIN** | Full system access | All permissions |
| **USER** | Standard user | Memory R/W, Plugins, Automations |
| **GUEST** | Limited access | Read-only memory |
| **AUTOMATION** | System automation | Plugin execution |
| **PLUGIN** | Plugin context | Scoped to plugin |

### Usage

```python
from core.security import permission_firewall, create_security_context

# Create context
context = create_security_context(
    user_id="user123",
    role=Role.USER,
    action="read_data",
    resource_type="memory",
    resource_id="user_namespace",
)

# Check permission
result = await permission_firewall.evaluate(
    context,
    {Permission.READ_MEMORY}
)

if result.allowed:
    # Proceed with operation
    pass
else:
    # Access denied
    raise PermissionError(result.reason)
```

### Rate Limiting

The firewall includes built-in rate limiting:

| Category | Limit |
|----------|-------|
| Per User | 100 requests/minute |
| Per Action | 30 requests/minute |
| Global | 1000 requests/minute |

---

## 2. Tool Dispatcher

**Location:** `core/security/dispatcher.py`

All tool/plugin executions must go through the Tool Dispatcher.

### Execution Pipeline

```
1. INTENT VALIDATION
   └─▶ Verify request structure and parameters

2. PERMISSION CHECK
   └─▶ Firewall evaluation for required permissions

3. RATE LIMIT CHECK
   └─▶ Ensure within execution limits

4. CONFIRMATION (for destructive actions)
   └─▶ Require confirmation token

5. SANDBOX EXECUTION
   └─▶ Execute in isolated environment

6. RESULT VALIDATION
   └─▶ Verify output meets security requirements

7. AUDIT LOG
   └─▶ Record execution details

8. RESPONSE
   └─▶ Return result to caller
```

### Tool Registration

```python
from core.security import tool_dispatcher, ToolDefinition

tool = ToolDefinition(
    tool_id="send_email",
    name="Send Email",
    description="Send an email",
    permissions_required={Permission.EXECUTE_PLUGINS},
    destructive=False,
    requires_confirmation=False,
    timeout_seconds=30,
    rate_limit_per_minute=10,
    handler=email_handler,
)

tool_dispatcher.register_tool(tool)
```

### Destructive Actions

Tools marked as `destructive=True` require:
1. Explicit `requires_confirmation=True`
2. Confirmation token in execution request
3. Additional audit logging

---

## 3. Memory Governance

**Location:** `core/security/memory_governance.py`

Controls all memory access with namespace isolation.

### Memory Classification

| Level | Description | Encryption |
|-------|-------------|------------|
| **PUBLIC** | Anyone can read | No |
| **INTERNAL** | Authenticated users | No |
| **CONFIDENTIAL** | Specific users/roles | Optional |
| **RESTRICTED** | Owner only | Yes |
| **PRIVATE** | Owner only, no sharing | Yes |

### Namespace Isolation

Each user has their own namespace:
- `system:*` - System-level data
- `user:{user_id}:*` - User-specific data
- `plugin:{plugin_id}:*` - Plugin data
- `shared:*` - Shared data

### Usage

```python
from core.security import memory_governance, MemoryClassification

# Create namespace
ns = memory_governance.create_namespace(
    namespace_id="user:123:private",
    owner_id="user123",
    classification=MemoryClassification.PRIVATE,
)

# Store with encryption
await memory_governance.store(
    namespace_id="user:123:private",
    key="api_key",
    value="secret_value",
    user_id="user123",
    encrypt=True,
    ttl_seconds=3600,  # Auto-expire after 1 hour
)

# Retrieve (only owner can access)
value = await memory_governance.retrieve(
    namespace_id="user:123:private",
    key="api_key",
    user_id="user123",
)
```

### Quotas

| Quota Type | Default Limit |
|------------|---------------|
| Items per namespace | 10,000 |
| Bytes per namespace | 100 MB |
| Total namespaces per user | 100 |

---

## 4. Immutable Audit Log

**Location:** `core/security/audit_log.py`

Tamper-evident logging with cryptographic hash chains.

### Hash Chain Structure

```
Entry N:
├── entry_hash = SHA256(content + previous_hash)
├── previous_hash (links to Entry N-1)
├── signature = HMAC(entry_hash, secret)
└── content (event data)
```

### Event Types

```python
class AuditEventType(Enum):
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILURE = "auth.failure"
    AUTH_MFA = "auth.mfa"
    
    # Authorization
    AUTHZ_GRANTED = "authz.granted"
    AUTHZ_DENIED = "authz.denied"
    
    # Data Operations
    DATA_CREATE = "data.create"
    DATA_READ = "data.read"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    
    # Security Events
    SECURITY_ALERT = "security.alert"
    SECURITY_VIOLATION = "security.violation"
```

### Severity Levels

| Level | Description |
|-------|-------------|
| DEBUG | Development info |
| INFO | Normal operations |
| NOTICE | Notable events |
| WARNING | Potential issues |
| ERROR | Errors occurred |
| CRITICAL | Critical failures |
| ALERT | Immediate action needed |
| EMERGENCY | System unusable |

### Usage

```python
from core.security import immutable_audit_log, AuditEventType, AuditSeverity

# Log security event
immutable_audit_log.log(
    event_type=AuditEventType.AUTH_LOGIN,
    severity=AuditSeverity.INFO,
    action="user_login",
    user_id="user123",
    ip_address="192.168.1.100",
    details={"method": "password"},
)

# Query logs
entries = immutable_audit_log.query(
    user_id="user123",
    event_type=AuditEventType.AUTH_LOGIN,
    start_time=datetime.utcnow() - timedelta(days=7),
    limit=100,
)

# Verify integrity
is_valid, errors = immutable_audit_log.verify_integrity()
```

### Compliance Export

```python
# Export for compliance audit
report = immutable_audit_log.export_compliance(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
    format="json",
)
```

---

## 5. Automation Safety Layer

**Location:** `core/security/automation_safety.py`

Controls and limits automation execution.

### Safety Controls

| Control | Description |
|---------|-------------|
| **Rate Limits** | Max executions per hour/day |
| **Quotas** | Resource consumption limits |
| **Kill Switch** | Emergency stop all automation |
| **Dry-Run Mode** | Test without execution |
| **Approval Workflows** | Require approval for sensitive actions |

### Kill Switch

```python
from core.security import automation_safety

# Activate emergency stop
automation_safety.activate_kill_switch(
    reason="Security incident detected",
    activated_by="admin",
)

# Deactivate after resolution
automation_safety.deactivate_kill_switch(deactivated_by="admin")
```

### Approval Workflow

```python
# Rule requiring approval
rule = SafeAutomationRule(
    id="delete_old_data",
    name="Delete Old Data",
    requires_approval=True,
    approval_roles={Role.ADMIN},
)

# Request creates approval pending
record = await automation_safety.execute_rule(rule_id, context)
# Returns: "Approval required. Request ID: xyz"

# Admin approves
await automation_safety.approve_request(
    request_id="xyz",
    approved_by="admin",
    approver_role=Role.ADMIN,
)
```

### Quota Configuration

```python
quota = AutomationQuota(
    max_executions_per_hour=60,
    max_executions_per_day=1000,
    max_concurrent_executions=5,
    max_memory_mb=256,
    max_cpu_seconds=60,
    max_execution_time_seconds=300,
    min_interval_seconds=1,
)
```

---

## 6. Security Hardening

**Location:** `core/security/hardening.py`

Production security controls.

### Secrets Manager

Encrypted storage for sensitive credentials.

```python
from core.security import secrets_manager, SecretType

# Store secret
secrets_manager.store_secret(
    name="openai_api_key",
    value="sk-...",
    secret_type=SecretType.API_KEY,
    expires_at=datetime.utcnow() + timedelta(days=90),
    created_by="admin",
)

# Retrieve secret
api_key = secrets_manager.get_secret("openai_api_key", accessor="system")

# Rotate secret
secrets_manager.rotate_secret(
    name="openai_api_key",
    new_value="sk-new...",
    rotated_by="admin",
)
```

### Session Manager

Secure session lifecycle management.

```python
from core.security import session_manager

# Create session
session = session_manager.create_session(
    user_id="user123",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0...",
)

# Validate session
session = session_manager.get_session(
    session.session_id,
    ip_address="192.168.1.100",  # IP binding validation
)

# Elevate for sensitive operations
session_manager.elevate_session(
    session.session_id,
    verification_method="mfa",
)

# Invalidate on logout
session_manager.invalidate_session(session.session_id)
```

### Input Sanitization

```python
from core.security import input_sanitizer

# XSS prevention
safe = input_sanitizer.html_escape('<script>alert("XSS")</script>')

# SQL injection check
is_safe, pattern = input_sanitizer.check_sql_injection(user_input)

# Path traversal check
is_safe, pattern = input_sanitizer.check_path_traversal(file_path)

# Safe filename
safe_name = input_sanitizer.sanitize_filename("../../../etc/passwd")

# Comprehensive check
result = input_sanitizer.comprehensive_check(user_input)
```

### Plugin Sandbox

Isolated execution environment for plugins.

```python
from core.security import PluginSandbox, SandboxViolation

sandbox = PluginSandbox(
    allow_network=False,
    allow_filesystem=False,
    max_memory_mb=256,
    max_time_seconds=60,
)

try:
    result = await sandbox.execute(plugin_code, local_vars)
except SandboxViolation as e:
    # Sandbox policy violated
    logger.error(f"Sandbox violation: {e}")
```

### HTTP Security Headers

```python
from core.security import get_security_headers

headers = get_security_headers()
# Returns:
# - X-Content-Type-Options: nosniff
# - X-XSS-Protection: 1; mode=block
# - X-Frame-Options: DENY
# - Content-Security-Policy: ...
# - Strict-Transport-Security: ...
# - Referrer-Policy: strict-origin-when-cross-origin
```

---

## Configuration

### Environment Variables

```bash
# Secrets Manager
SECRETS_MASTER_KEY=<base64-encoded-key>
SECRETS_STORAGE_PATH=/data/secrets

# Session Manager
SESSION_TIMEOUT_MINUTES=30
MAX_SESSIONS_PER_USER=5
ELEVATION_TIMEOUT_MINUTES=15
SESSION_BIND_IP=true

# Audit Log
AUDIT_LOG_DIR=/data/audit
AUDIT_HASH_SECRET=<secret-key>
AUDIT_LOG_ROTATION_SIZE_MB=100

# Rate Limiting
RATE_LIMIT_PER_USER=100
RATE_LIMIT_PER_ACTION=30
RATE_LIMIT_GLOBAL=1000
```

### Security Checklist

- [ ] Set strong `SECRETS_MASTER_KEY`
- [ ] Configure `AUDIT_HASH_SECRET` for audit integrity
- [ ] Enable `SESSION_BIND_IP` in production
- [ ] Set appropriate rate limits
- [ ] Configure log rotation
- [ ] Review default permissions
- [ ] Test kill switch procedure
- [ ] Verify audit log integrity regularly

---

## Security Testing

Run the security test suite:

```bash
pytest tests/test_security.py -v
```

### Test Categories

1. **Permission Bypass Tests** - Verify firewall denies unauthorized access
2. **Rate Limit Tests** - Verify limits are enforced
3. **Audit Tampering Tests** - Verify hash chain integrity
4. **Sandbox Escape Tests** - Verify isolation is maintained
5. **Session Security Tests** - Verify session controls
6. **Input Validation Tests** - Verify sanitization

---

## Incident Response

### Kill Switch Activation

1. Identify the threat
2. Activate kill switch: `automation_safety.activate_kill_switch(reason, admin_id)`
3. Investigate audit logs
4. Remediate issue
5. Deactivate kill switch: `automation_safety.deactivate_kill_switch(admin_id)`

### Audit Log Tampering Detection

1. Run integrity check: `immutable_audit_log.verify_integrity()`
2. If tampering detected, investigate:
   - Check file system permissions
   - Review access logs
   - Export pre-tamper logs from backup
3. Report incident

### Session Hijacking Response

1. Invalidate all user sessions: `session_manager.invalidate_all_user_sessions(user_id)`
2. Force password reset
3. Review audit logs for suspicious activity
4. Enable additional MFA requirements

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2024 | Complete security layer implementation |
| 1.0.0 | 2024 | Initial release |
