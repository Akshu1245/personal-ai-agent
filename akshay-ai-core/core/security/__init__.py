"""
============================================================
AKSHAY AI CORE — Security Module
============================================================
Comprehensive security layer for the AI operating system.

COMPONENTS:
- Permission Firewall: Central permission enforcement
- Tool Dispatcher: Mandatory tool execution pipeline
- Memory Governance: Namespace-based memory access control
- Immutable Audit Log: Tamper-evident logging
- Automation Safety: Rate limits, quotas, kill switch
- Security Hardening: Secrets, sessions, sandboxing

USAGE:
    from core.security import (
        permission_firewall,
        tool_dispatcher,
        memory_governance,
        immutable_audit_log,
        automation_safety,
        secrets_manager,
        session_manager,
    )

SECURITY PRINCIPLE: Deny by default, audit everything.
============================================================
"""

# Legacy security components
from core.security.encryption import EncryptionEngine
from core.security.auth_manager import AuthManager
from core.security.permissions import PermissionManager, Permission, Role, ROLE_PERMISSIONS

# Permission Firewall
from core.security.firewall import (
    permission_firewall,
    PermissionFirewall,
    SecurityContext,
    SecurityDecision,
    SecurityDecisionResult,
    RateLimiter,
    ContextValidator,
    ResourceAccessControl,
    firewall_protected,
    sync_firewall_protected,
    FirewallContextManager,
    create_security_context,
)

# Tool Dispatcher
from core.security.dispatcher import (
    tool_dispatcher,
    ToolDispatcher,
    ToolDefinition,
    ExecutionRequest,
    ExecutionResult,
    ExecutionSandbox,
    ConcurrencyManager,
    register_tool,
)

# Security Integration
from core.security.integration import (
    SecurePluginExecutor,
    SecureCommandRouter,
    SecureMemoryAccess,
    SecureAutomationExecutor,
    SecurityIntegration,
    api_protected,
    extract_security_context,
)

# Memory Governance
from core.security.memory_governance import (
    memory_governance,
    MemoryGovernanceLayer,
    MemoryNamespace,
    GovernedMemory,
    MemoryClassification,
    MemoryEncryption,
)

# Immutable Audit Log
from core.security.audit_log import (
    immutable_audit_log,
    ImmutableAuditLog,
    AuditEventType,
    AuditSeverity,
    AuditEntry,
    HashChainManager,
    AuditLogStorage,
)

# Automation Safety
from core.security.automation_safety import (
    automation_safety,
    AutomationSafetyLayer,
    AutomationState,
    AutomationQuota,
    SafeAutomationRule,
    ApprovalRequest,
    ApprovalStatus,
    RuleCategory,
    ExecutionRecord,
    RateLimitTracker,
    ConcurrencyTracker,
)

# Security Hardening
from core.security.hardening import (
    secrets_manager,
    SecretsManager,
    SecretType,
    SecretMetadata,
    session_manager,
    SessionManager,
    Session,
    input_sanitizer,
    InputSanitizer,
    PluginSandbox,
    SandboxViolation,
    get_security_headers,
)


__all__ = [
    # Legacy
    "EncryptionEngine",
    "AuthManager",
    "PermissionManager",
    
    # Firewall
    "permission_firewall",
    "PermissionFirewall",
    "SecurityContext",
    "SecurityDecision",
    "SecurityDecisionResult",
    "RateLimiter",
    "ContextValidator",
    "ResourceAccessControl",
    "firewall_protected",
    "sync_firewall_protected",
    "FirewallContextManager",
    "create_security_context",
    
    # Tool Dispatcher
    "tool_dispatcher",
    "ToolDispatcher",
    "ToolDefinition",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionSandbox",
    "ConcurrencyManager",
    "register_tool",
    
    # Integration
    "SecurePluginExecutor",
    "SecureCommandRouter",
    "SecureMemoryAccess",
    "SecureAutomationExecutor",
    "SecurityIntegration",
    "api_protected",
    "extract_security_context",
    
    # Memory Governance
    "memory_governance",
    "MemoryGovernanceLayer",
    "MemoryNamespace",
    "GovernedMemory",
    "MemoryClassification",
    "MemoryEncryption",
    
    # Audit Log
    "immutable_audit_log",
    "ImmutableAuditLog",
    "AuditEventType",
    "AuditSeverity",
    "AuditEntry",
    "HashChainManager",
    "AuditLogStorage",
    
    # Automation Safety
    "automation_safety",
    "AutomationSafetyLayer",
    "AutomationState",
    "AutomationQuota",
    "SafeAutomationRule",
    "ApprovalRequest",
    "ApprovalStatus",
    "RuleCategory",
    "ExecutionRecord",
    "RateLimitTracker",
    "ConcurrencyTracker",
    
    # Hardening
    "secrets_manager",
    "SecretsManager",
    "SecretType",
    "SecretMetadata",
    "session_manager",
    "SessionManager",
    "Session",
    "input_sanitizer",
    "InputSanitizer",
    "PluginSandbox",
    "SandboxViolation",
    "get_security_headers",
    
    # Permissions
    "Permission",
    "Role",
    "ROLE_PERMISSIONS",
]
