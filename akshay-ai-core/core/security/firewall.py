"""
============================================================
AKSHAY AI CORE — Permission Firewall
============================================================
Central security gate that ALL actions MUST pass through.
Enforces permissions, validates contexts, and logs all
security-relevant decisions.

SECURITY PRINCIPLE: DENY BY DEFAULT
Every action is denied unless explicitly permitted.
============================================================
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union
from collections import defaultdict
import threading

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.permissions import (
    Permission,
    Role,
    PermissionContext,
    PermissionManager,
    ROLE_PERMISSIONS,
)

logger = get_logger("security.firewall")

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


class SecurityDecision(Enum):
    """Result of a security evaluation."""
    ALLOW = auto()
    DENY = auto()
    DENY_RATE_LIMITED = auto()
    DENY_PERMISSION = auto()
    DENY_CONTEXT = auto()
    DENY_RESOURCE = auto()
    DENY_TIME_RESTRICTED = auto()
    DENY_BLOCKED = auto()
    DENY_SUSPENDED = auto()
    ESCALATE = auto()  # Requires additional approval


class ThreatLevel(Enum):
    """Threat assessment levels."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SecurityContext:
    """
    Extended security context for firewall decisions.
    
    Contains all information needed to make security decisions,
    including user identity, permissions, request metadata,
    and environmental factors.
    """
    user_id: str
    role: Role
    permissions: Set[Permission]
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Request context
    action: str = ""
    resource_type: str = ""
    resource_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Environmental factors
    is_automation: bool = False
    is_plugin: bool = False
    plugin_name: Optional[str] = None
    calling_module: Optional[str] = None
    
    # Trust indicators
    mfa_verified: bool = False
    recent_auth_time: Optional[datetime] = None
    
    def __post_init__(self):
        """Generate unique context fingerprint."""
        self.fingerprint = self._compute_fingerprint()
    
    def _compute_fingerprint(self) -> str:
        """Create unique fingerprint for this context."""
        data = f"{self.user_id}:{self.session_id}:{self.ip_address}:{self.action}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "user_id": self.user_id,
            "role": self.role.value if self.role else None,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "is_automation": self.is_automation,
            "is_plugin": self.is_plugin,
            "plugin_name": self.plugin_name,
            "mfa_verified": self.mfa_verified,
            "fingerprint": self.fingerprint,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SecurityDecisionResult:
    """
    Complete result of a security decision.
    
    Includes the decision, reasoning, and any additional
    context needed for auditing and response.
    """
    decision: SecurityDecision
    reason: str
    context: SecurityContext
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Detailed breakdown
    permission_check_passed: bool = False
    rate_limit_check_passed: bool = False
    context_check_passed: bool = False
    resource_check_passed: bool = False
    
    # Additional info
    required_permissions: Set[Permission] = field(default_factory=set)
    missing_permissions: Set[Permission] = field(default_factory=set)
    threat_level: ThreatLevel = ThreatLevel.NONE
    
    # For escalation
    escalation_reason: Optional[str] = None
    approval_required_from: Optional[str] = None
    
    @property
    def allowed(self) -> bool:
        """Check if action is allowed."""
        return self.decision == SecurityDecision.ALLOW
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "decision": self.decision.name,
            "allowed": self.allowed,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "permission_check_passed": self.permission_check_passed,
            "rate_limit_check_passed": self.rate_limit_check_passed,
            "context_check_passed": self.context_check_passed,
            "resource_check_passed": self.resource_check_passed,
            "required_permissions": [p.value for p in self.required_permissions],
            "missing_permissions": [p.value for p in self.missing_permissions],
            "threat_level": self.threat_level.name,
            "context": self.context.to_dict() if self.context else None,
        }


class RateLimiter:
    """
    Token bucket rate limiter with sliding window.
    
    Tracks request rates per user/action combination
    and enforces configurable limits.
    """
    
    def __init__(self):
        # Format: {user_id: {action: [(timestamp, count)]}}
        self._buckets: Dict[str, Dict[str, List[Tuple[float, int]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = threading.Lock()
        
        # Default limits per action type (requests per minute)
        self._default_limits = {
            "query": 60,
            "memory_read": 120,
            "memory_write": 30,
            "plugin_execute": 20,
            "system_command": 10,
            "file_access": 30,
            "network_request": 20,
            "automation_trigger": 15,
            "sensitive_data_access": 5,
            "admin_action": 10,
        }
        
        # Elevated limits for certain roles
        self._role_multipliers = {
            Role.ADMIN: 2.0,
            Role.USER: 1.0,
            Role.GUEST: 0.5,
            Role.AUTOMATION: 1.5,
            Role.PLUGIN: 1.0,
        }
        
        # Blocked users (temporary bans)
        self._blocked: Dict[str, datetime] = {}
    
    def get_limit(self, action: str, role: Role) -> int:
        """Get rate limit for action and role."""
        base_limit = self._default_limits.get(action, 30)
        multiplier = self._role_multipliers.get(role, 1.0)
        return int(base_limit * multiplier)
    
    def check_rate_limit(
        self,
        user_id: str,
        action: str,
        role: Role,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        Check if user is within rate limit.
        
        Args:
            user_id: User identifier
            action: Action type
            role: User's role
            window_seconds: Time window for rate calculation
            
        Returns:
            Tuple of (allowed, remaining_requests, reset_time_seconds)
        """
        # Check if user is blocked
        if user_id in self._blocked:
            if datetime.utcnow() < self._blocked[user_id]:
                return False, 0, int((self._blocked[user_id] - datetime.utcnow()).total_seconds())
            else:
                del self._blocked[user_id]
        
        limit = self.get_limit(action, role)
        current_time = time.time()
        window_start = current_time - window_seconds
        
        with self._lock:
            # Clean old entries
            self._buckets[user_id][action] = [
                (ts, count) for ts, count in self._buckets[user_id][action]
                if ts > window_start
            ]
            
            # Count requests in window
            total_requests = sum(
                count for _, count in self._buckets[user_id][action]
            )
            
            if total_requests >= limit:
                # Calculate reset time
                if self._buckets[user_id][action]:
                    oldest_ts = min(ts for ts, _ in self._buckets[user_id][action])
                    reset_time = int(oldest_ts + window_seconds - current_time)
                else:
                    reset_time = window_seconds
                return False, 0, reset_time
            
            # Add current request
            self._buckets[user_id][action].append((current_time, 1))
            
            remaining = limit - total_requests - 1
            return True, remaining, window_seconds
    
    def block_user(self, user_id: str, duration_minutes: int = 15) -> None:
        """Temporarily block a user."""
        self._blocked[user_id] = datetime.utcnow() + timedelta(minutes=duration_minutes)
        logger.warning(
            "User blocked due to rate limit violations",
            user_id=user_id,
            duration_minutes=duration_minutes,
        )
    
    def unblock_user(self, user_id: str) -> None:
        """Remove user from block list."""
        if user_id in self._blocked:
            del self._blocked[user_id]


class ContextValidator:
    """
    Validates security contexts against policies.
    
    Enforces contextual rules like time-based access,
    IP restrictions, and environmental requirements.
    """
    
    def __init__(self):
        # Sensitive actions requiring recent auth
        self._sensitive_actions = {
            "delete_memory",
            "delete_user",
            "change_password",
            "revoke_session",
            "modify_permissions",
            "access_secrets",
            "system_shutdown",
            "plugin_install",
            "plugin_uninstall",
        }
        
        # Actions requiring MFA
        self._mfa_required_actions = {
            "delete_user",
            "modify_permissions",
            "access_secrets",
            "system_shutdown",
        }
        
        # Time-restricted actions (hour ranges in UTC)
        self._time_restrictions: Dict[str, Tuple[int, int]] = {}
        
        # IP allowlists per action
        self._ip_allowlists: Dict[str, Set[str]] = {}
        
        # Blocked IPs
        self._blocked_ips: Set[str] = set()
    
    def validate_context(self, context: SecurityContext) -> Tuple[bool, str]:
        """
        Validate security context against policies.
        
        Returns:
            Tuple of (valid, reason)
        """
        # Check blocked IP
        if context.ip_address and context.ip_address in self._blocked_ips:
            return False, f"IP address {context.ip_address} is blocked"
        
        # Check IP allowlist if action has one
        if context.action in self._ip_allowlists:
            if context.ip_address not in self._ip_allowlists[context.action]:
                return False, f"IP {context.ip_address} not in allowlist for {context.action}"
        
        # Check time restrictions
        if context.action in self._time_restrictions:
            start_hour, end_hour = self._time_restrictions[context.action]
            current_hour = datetime.utcnow().hour
            if not (start_hour <= current_hour < end_hour):
                return False, f"Action {context.action} restricted to hours {start_hour}-{end_hour} UTC"
        
        # Check MFA requirement
        if context.action in self._mfa_required_actions and not context.mfa_verified:
            return False, f"Action {context.action} requires MFA verification"
        
        # Check recent auth for sensitive actions
        if context.action in self._sensitive_actions:
            if context.recent_auth_time:
                auth_age = datetime.utcnow() - context.recent_auth_time
                if auth_age > timedelta(minutes=5):
                    return False, f"Action {context.action} requires re-authentication (last auth was {auth_age.seconds//60} minutes ago)"
            else:
                return False, f"Action {context.action} requires recent authentication"
        
        return True, "Context validation passed"
    
    def add_time_restriction(self, action: str, start_hour: int, end_hour: int) -> None:
        """Add time restriction for an action."""
        self._time_restrictions[action] = (start_hour, end_hour)
    
    def add_ip_allowlist(self, action: str, ips: Set[str]) -> None:
        """Add IP allowlist for an action."""
        self._ip_allowlists[action] = ips
    
    def block_ip(self, ip: str) -> None:
        """Block an IP address."""
        self._blocked_ips.add(ip)
    
    def unblock_ip(self, ip: str) -> None:
        """Unblock an IP address."""
        self._blocked_ips.discard(ip)


class ResourceAccessControl:
    """
    Controls access to specific resources.
    
    Manages resource-level permissions beyond role-based
    access, including ownership and sharing.
    """
    
    def __init__(self):
        # Resource ownership: {resource_type: {resource_id: owner_user_id}}
        self._ownership: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # Shared access: {resource_type: {resource_id: {user_id: Set[Permission]}}}
        self._shared_access: Dict[str, Dict[str, Dict[str, Set[Permission]]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        
        # Protected resources (require admin)
        self._protected_resources: Dict[str, Set[str]] = defaultdict(set)
    
    def set_owner(self, resource_type: str, resource_id: str, user_id: str) -> None:
        """Set resource ownership."""
        self._ownership[resource_type][resource_id] = user_id
    
    def get_owner(self, resource_type: str, resource_id: str) -> Optional[str]:
        """Get resource owner."""
        return self._ownership.get(resource_type, {}).get(resource_id)
    
    def share_resource(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
        permissions: Set[Permission],
    ) -> None:
        """Share resource with user."""
        self._shared_access[resource_type][resource_id][user_id] = permissions
    
    def revoke_share(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
    ) -> None:
        """Revoke shared access."""
        if resource_id in self._shared_access[resource_type]:
            self._shared_access[resource_type][resource_id].pop(user_id, None)
    
    def protect_resource(self, resource_type: str, resource_id: str) -> None:
        """Mark resource as protected (admin-only)."""
        self._protected_resources[resource_type].add(resource_id)
    
    def unprotect_resource(self, resource_type: str, resource_id: str) -> None:
        """Remove protection from resource."""
        self._protected_resources[resource_type].discard(resource_id)
    
    def check_access(
        self,
        context: SecurityContext,
        required_permission: Permission,
    ) -> Tuple[bool, str]:
        """
        Check if context has access to specified resource.
        
        Returns:
            Tuple of (allowed, reason)
        """
        resource_type = context.resource_type
        resource_id = context.resource_id
        user_id = context.user_id
        
        # If no specific resource, allow (general permission check handles it)
        if not resource_type or not resource_id:
            return True, "No specific resource to check"
        
        # Check if resource is protected
        if resource_id in self._protected_resources.get(resource_type, set()):
            if context.role != Role.ADMIN:
                return False, f"Resource {resource_type}/{resource_id} is protected (admin-only)"
        
        # Check ownership
        owner = self.get_owner(resource_type, resource_id)
        if owner == user_id:
            return True, "User is resource owner"
        
        # Check admin access
        if context.role == Role.ADMIN:
            return True, "Admin has full resource access"
        
        # Check shared access
        shared_perms = self._shared_access.get(resource_type, {}).get(resource_id, {}).get(user_id)
        if shared_perms and required_permission in shared_perms:
            return True, f"User has shared {required_permission.value} access"
        
        # No access
        return False, f"No access to resource {resource_type}/{resource_id}"


class PermissionFirewall:
    """
    Central Permission Firewall.
    
    ALL actions MUST pass through this firewall.
    It enforces permissions, validates contexts,
    manages rate limits, and logs all decisions.
    
    SECURITY PRINCIPLE: DENY BY DEFAULT
    """
    
    _instance: Optional["PermissionFirewall"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "PermissionFirewall":
        """Singleton pattern for global firewall."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # Core components
        self.permission_manager = PermissionManager()
        self.rate_limiter = RateLimiter()
        self.context_validator = ContextValidator()
        self.resource_access = ResourceAccessControl()
        
        # Action to permission mapping
        self._action_permissions: Dict[str, Set[Permission]] = {
            # Brain/Query actions
            "query": {Permission.AI_QUERY},
            "query_advanced": {Permission.AI_QUERY, Permission.AI_CONFIG},
            
            # Memory actions
            "memory_read": {Permission.AI_MEMORY_READ},
            "memory_write": {Permission.AI_MEMORY_WRITE},
            "memory_delete": {Permission.AI_MEMORY_DELETE},
            "memory_read_long_term": {Permission.AI_MEMORY_READ, Permission.AI_SECURE_MEMORY},
            "memory_write_long_term": {Permission.AI_MEMORY_WRITE, Permission.AI_SECURE_MEMORY},
            
            # Plugin actions
            "plugin_execute": {Permission.PLUGIN_EXECUTE},
            "plugin_execute_web": {Permission.PLUGIN_EXECUTE, Permission.TOOL_WEB_AUTOMATION},
            "plugin_execute_system": {Permission.PLUGIN_EXECUTE, Permission.TOOL_SYSTEM_CONTROL},
            "plugin_execute_files": {Permission.PLUGIN_EXECUTE, Permission.FILE_READ, Permission.FILE_WRITE},
            "plugin_execute_network": {Permission.PLUGIN_EXECUTE, Permission.NETWORK_EXTERNAL},
            "plugin_install": {Permission.PLUGIN_INSTALL},
            "plugin_uninstall": {Permission.PLUGIN_UNINSTALL},
            
            # Automation actions
            "automation_trigger": {Permission.AUTOMATION_EXECUTE},
            "automation_create": {Permission.AUTOMATION_CREATE},
            "automation_modify": {Permission.AUTOMATION_UPDATE},
            "automation_delete": {Permission.AUTOMATION_DELETE},
            "automation_view": {Permission.AUTOMATION_READ},
            
            # System actions
            "system_command": {Permission.TOOL_SYSTEM_CONTROL},
            "system_config": {Permission.SYSTEM_CONFIG},
            "system_shutdown": {Permission.SYSTEM_SHUTDOWN},
            
            # Data actions
            "data_export": {Permission.FILE_READ},
            "data_import": {Permission.FILE_WRITE},
            "data_analyze": {Permission.TOOL_DATA_ANALYSIS},
            "sensitive_data_access": {Permission.AI_SECURE_MEMORY},
            
            # User management
            "user_view": {Permission.USER_READ},
            "user_manage": {Permission.USER_MANAGE},
            "permission_view": {Permission.USER_READ},
            "permission_modify": {Permission.USER_MANAGE},
            
            # Audit actions
            "audit_view": {Permission.SYSTEM_LOGS},
            "audit_export": {Permission.SYSTEM_LOGS, Permission.FILE_READ},
            
            # File operations
            "file_read": {Permission.FILE_READ},
            "file_write": {Permission.FILE_WRITE},
            "file_delete": {Permission.FILE_DELETE},
            "file_vault_access": {Permission.FILE_VAULT},
            
            # Network operations
            "network_request": {Permission.NETWORK_EXTERNAL},
            "api_access": {Permission.NETWORK_EXTERNAL},
            
            # IoT operations
            "iot_control": {Permission.NETWORK_IOT},
        }
        
        # Actions that require escalation for certain resources
        self._escalation_triggers: Dict[str, Set[str]] = {
            "memory_delete": {"long_term", "permanent"},
            "system_command": {"shutdown", "restart", "format"},
            "file_delete": {"system", "config"},
        }
        
        # Statistics
        self._stats = {
            "total_checks": 0,
            "allowed": 0,
            "denied": 0,
            "denied_permission": 0,
            "denied_rate_limit": 0,
            "denied_context": 0,
            "denied_resource": 0,
            "escalations": 0,
        }
        
        logger.info("Permission Firewall initialized")
    
    async def evaluate(
        self,
        context: SecurityContext,
        required_permissions: Optional[Set[Permission]] = None,
    ) -> SecurityDecisionResult:
        """
        Evaluate a security request.
        
        This is the main entry point for all security checks.
        
        Args:
            context: Security context with all request details
            required_permissions: Specific permissions to check (overrides action mapping)
            
        Returns:
            SecurityDecisionResult with decision and full context
        """
        self._stats["total_checks"] += 1
        
        # Get required permissions from action if not specified
        if required_permissions is None:
            required_permissions = self._action_permissions.get(context.action, set())
        
        # Create result template
        result = SecurityDecisionResult(
            decision=SecurityDecision.DENY,  # Default deny
            reason="Evaluation in progress",
            context=context,
            required_permissions=required_permissions,
        )
        
        try:
            # Step 1: Check rate limit
            rate_allowed, remaining, reset_time = self.rate_limiter.check_rate_limit(
                context.user_id,
                context.action,
                context.role,
            )
            
            if not rate_allowed:
                result.decision = SecurityDecision.DENY_RATE_LIMITED
                result.reason = f"Rate limit exceeded. Reset in {reset_time}s"
                self._stats["denied"] += 1
                self._stats["denied_rate_limit"] += 1
                await self._log_decision(result)
                return result
            
            result.rate_limit_check_passed = True
            
            # Step 2: Check context validity
            context_valid, context_reason = self.context_validator.validate_context(context)
            
            if not context_valid:
                result.decision = SecurityDecision.DENY_CONTEXT
                result.reason = context_reason
                self._stats["denied"] += 1
                self._stats["denied_context"] += 1
                await self._log_decision(result)
                return result
            
            result.context_check_passed = True
            
            # Step 3: Check permissions
            missing_permissions = set()
            for permission in required_permissions:
                if permission not in context.permissions:
                    missing_permissions.add(permission)
            
            if missing_permissions:
                result.decision = SecurityDecision.DENY_PERMISSION
                result.reason = f"Missing permissions: {[p.value for p in missing_permissions]}"
                result.missing_permissions = missing_permissions
                self._stats["denied"] += 1
                self._stats["denied_permission"] += 1
                await self._log_decision(result)
                return result
            
            result.permission_check_passed = True
            
            # Step 4: Check resource-level access
            if required_permissions:
                # Use first permission for resource check
                primary_permission = next(iter(required_permissions))
                resource_allowed, resource_reason = self.resource_access.check_access(
                    context,
                    primary_permission,
                )
                
                if not resource_allowed:
                    result.decision = SecurityDecision.DENY_RESOURCE
                    result.reason = resource_reason
                    self._stats["denied"] += 1
                    self._stats["denied_resource"] += 1
                    await self._log_decision(result)
                    return result
            
            result.resource_check_passed = True
            
            # Step 5: Check if escalation required
            if self._requires_escalation(context):
                result.decision = SecurityDecision.ESCALATE
                result.reason = f"Action {context.action} on resource requires approval"
                result.escalation_reason = "Sensitive operation on protected resource"
                result.approval_required_from = "admin"
                self._stats["escalations"] += 1
                await self._log_decision(result)
                return result
            
            # All checks passed - ALLOW
            result.decision = SecurityDecision.ALLOW
            result.reason = "All security checks passed"
            self._stats["allowed"] += 1
            await self._log_decision(result)
            return result
            
        except Exception as e:
            logger.error(
                "Security evaluation error",
                error=str(e),
                context=context.to_dict(),
            )
            result.decision = SecurityDecision.DENY
            result.reason = f"Security evaluation error: {str(e)}"
            result.threat_level = ThreatLevel.HIGH
            self._stats["denied"] += 1
            await self._log_decision(result)
            return result
    
    def _requires_escalation(self, context: SecurityContext) -> bool:
        """Check if action requires escalation."""
        triggers = self._escalation_triggers.get(context.action, set())
        
        # Check resource type against triggers
        if context.resource_type and context.resource_type in triggers:
            return True
        
        # Check parameters for trigger keywords
        for param_value in context.parameters.values():
            if isinstance(param_value, str) and param_value.lower() in triggers:
                return True
        
        return False
    
    async def _log_decision(self, result: SecurityDecisionResult) -> None:
        """Log security decision to audit log."""
        try:
            audit_logger.log(
                action=f"security_decision:{result.context.action}",
                user_id=result.context.user_id,
                resource_type=result.context.resource_type,
                resource_id=result.context.resource_id,
                details={
                    "decision": result.decision.name,
                    "reason": result.reason,
                    "required_permissions": [p.value for p in result.required_permissions],
                    "missing_permissions": [p.value for p in result.missing_permissions],
                    "threat_level": result.threat_level.name,
                    "rate_limit_passed": result.rate_limit_check_passed,
                    "context_passed": result.context_check_passed,
                    "permission_passed": result.permission_check_passed,
                    "resource_passed": result.resource_check_passed,
                },
                status="allowed" if result.allowed else "denied",
                ip_address=result.context.ip_address,
            )
        except Exception as e:
            logger.error("Failed to log security decision", error=str(e))
    
    def get_stats(self) -> Dict[str, int]:
        """Get firewall statistics."""
        return self._stats.copy()
    
    def get_action_permissions(self, action: str) -> Set[Permission]:
        """Get required permissions for an action."""
        return self._action_permissions.get(action, set())
    
    def register_action(self, action: str, permissions: Set[Permission]) -> None:
        """Register new action with required permissions."""
        self._action_permissions[action] = permissions
        logger.info(f"Registered action '{action}' with permissions: {[p.value for p in permissions]}")


# Global firewall instance
permission_firewall = PermissionFirewall()


def firewall_protected(
    action: Optional[str] = None,
    permissions: Optional[Set[Permission]] = None,
    resource_type: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Decorator to protect functions with firewall checks.
    
    Usage:
        @firewall_protected(action="memory_read")
        async def read_memory(context: SecurityContext, key: str):
            ...
    
        @firewall_protected(permissions={Permission.ADMIN_SETTINGS})
        async def admin_function(context: SecurityContext):
            ...
    
    Args:
        action: Action name for permission lookup
        permissions: Specific permissions to require
        resource_type: Type of resource being accessed
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract security context from args/kwargs
            context = None
            
            # Check kwargs first
            if "context" in kwargs:
                context = kwargs["context"]
            elif "security_context" in kwargs:
                context = kwargs["security_context"]
            else:
                # Check positional args
                for arg in args:
                    if isinstance(arg, SecurityContext):
                        context = arg
                        break
            
            if not context:
                raise ValueError(
                    f"Function {func.__name__} requires SecurityContext but none provided"
                )
            
            # Set action and resource type if provided
            if action:
                context.action = action
            if resource_type:
                context.resource_type = resource_type
            
            # Evaluate through firewall
            result = await permission_firewall.evaluate(context, permissions)
            
            if not result.allowed:
                raise PermissionError(
                    f"Access denied: {result.reason} (Decision: {result.decision.name})"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


def sync_firewall_protected(
    action: Optional[str] = None,
    permissions: Optional[Set[Permission]] = None,
    resource_type: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Synchronous version of firewall_protected decorator.
    
    For use with non-async functions.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract security context
            context = None
            
            if "context" in kwargs:
                context = kwargs["context"]
            elif "security_context" in kwargs:
                context = kwargs["security_context"]
            else:
                for arg in args:
                    if isinstance(arg, SecurityContext):
                        context = arg
                        break
            
            if not context:
                raise ValueError(
                    f"Function {func.__name__} requires SecurityContext but none provided"
                )
            
            if action:
                context.action = action
            if resource_type:
                context.resource_type = resource_type
            
            # Run async evaluation in event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create new loop for sync context
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        permission_firewall.evaluate(context, permissions)
                    )
                    result = future.result()
            else:
                result = loop.run_until_complete(
                    permission_firewall.evaluate(context, permissions)
                )
            
            if not result.allowed:
                raise PermissionError(
                    f"Access denied: {result.reason} (Decision: {result.decision.name})"
                )
            
            return func(*args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


class FirewallContextManager:
    """
    Context manager for firewall-protected code blocks.
    
    Usage:
        async with FirewallContextManager(context, action="memory_read"):
            # Protected code here
            pass
    """
    
    def __init__(
        self,
        context: SecurityContext,
        action: Optional[str] = None,
        permissions: Optional[Set[Permission]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        self.context = context
        self.action = action
        self.permissions = permissions
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.result: Optional[SecurityDecisionResult] = None
    
    async def __aenter__(self) -> SecurityDecisionResult:
        """Enter context with security check."""
        if self.action:
            self.context.action = self.action
        if self.resource_type:
            self.context.resource_type = self.resource_type
        if self.resource_id:
            self.context.resource_id = self.resource_id
        
        self.result = await permission_firewall.evaluate(self.context, self.permissions)
        
        if not self.result.allowed:
            raise PermissionError(
                f"Access denied: {self.result.reason} (Decision: {self.result.decision.name})"
            )
        
        return self.result
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context, log any errors."""
        if exc_type is not None:
            logger.error(
                "Error in firewall-protected block",
                action=self.context.action,
                error_type=exc_type.__name__,
                error=str(exc_val),
                user_id=self.context.user_id,
            )
        return False  # Don't suppress exceptions


def create_security_context(
    user_id: str,
    role: Role,
    action: str = "",
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
    resource_type: str = "",
    resource_id: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    is_automation: bool = False,
    is_plugin: bool = False,
    plugin_name: Optional[str] = None,
    mfa_verified: bool = False,
) -> SecurityContext:
    """
    Factory function to create SecurityContext with role permissions.
    
    Automatically populates permissions based on role.
    """
    permissions = ROLE_PERMISSIONS.get(role, set())
    
    return SecurityContext(
        user_id=user_id,
        role=role,
        permissions=permissions,
        session_id=session_id,
        ip_address=ip_address,
        request_id=request_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        parameters=parameters or {},
        is_automation=is_automation,
        is_plugin=is_plugin,
        plugin_name=plugin_name,
        mfa_verified=mfa_verified,
    )
