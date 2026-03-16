"""
============================================================
AKSHAY AI CORE — Permission Management System
============================================================
Role-Based Access Control (RBAC) with granular permissions.
============================================================
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from functools import wraps

from core.utils.logger import get_logger, audit_logger

logger = get_logger("permissions")


class Permission(str, Enum):
    """System permissions."""
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_SHUTDOWN = "system:shutdown"
    
    # Backward compatibility aliases for tests
    ADMIN_MANAGE_USERS = "system:admin"  # alias for ADMIN
    ADMIN_SYSTEM_CONFIG = "system:config"  # alias for SYSTEM_CONFIG
    READ_MEMORY = "ai:memory:read"  # alias for AI_MEMORY_READ
    AI_CHAT = "ai:query"  # alias for AI_QUERY
    TRIGGER_AUTOMATIONS = "automation:execute"  # alias for AUTOMATION_EXECUTE
    
    # User management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_MANAGE = "user:manage"
    
    # AI/Brain permissions
    AI_QUERY = "ai:query"
    AI_CONFIG = "ai:config"
    AI_MEMORY_READ = "ai:memory:read"
    AI_MEMORY_WRITE = "ai:memory:write"
    AI_MEMORY_DELETE = "ai:memory:delete"
    AI_SECURE_MEMORY = "ai:secure_memory"
    
    # Plugin permissions
    PLUGIN_INSTALL = "plugin:install"
    PLUGIN_UNINSTALL = "plugin:uninstall"
    PLUGIN_EXECUTE = "plugin:execute"
    PLUGIN_CONFIG = "plugin:config"
    
    # Automation permissions
    AUTOMATION_CREATE = "automation:create"
    AUTOMATION_READ = "automation:read"
    AUTOMATION_UPDATE = "automation:update"
    AUTOMATION_DELETE = "automation:delete"
    AUTOMATION_EXECUTE = "automation:execute"
    
    # File/Data permissions
    FILE_READ = "file:read"
    FILE_WRITE = "file:write"
    FILE_DELETE = "file:delete"
    FILE_VAULT = "file:vault"
    
    # Network permissions
    NETWORK_INTERNAL = "network:internal"
    NETWORK_EXTERNAL = "network:external"
    NETWORK_IOT = "network:iot"
    
    # Tool permissions
    TOOL_WEB_AUTOMATION = "tool:web_automation"
    TOOL_SYSTEM_CONTROL = "tool:system_control"
    TOOL_CYBER = "tool:cyber"
    TOOL_DATA_ANALYSIS = "tool:data_analysis"


class Role(str, Enum):
    """Predefined user roles."""
    
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    AUTOMATION = "automation"  # For automated tasks
    PLUGIN = "plugin"  # For plugin execution


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions
    
    Role.USER: {
        Permission.AI_QUERY,
        Permission.AI_MEMORY_READ,
        Permission.AI_MEMORY_WRITE,
        Permission.PLUGIN_EXECUTE,
        Permission.AUTOMATION_READ,
        Permission.AUTOMATION_EXECUTE,
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.NETWORK_INTERNAL,
        Permission.TOOL_WEB_AUTOMATION,
        Permission.TOOL_DATA_ANALYSIS,
    },
    
    Role.GUEST: {
        Permission.AI_QUERY,
        Permission.AI_MEMORY_READ,
        Permission.FILE_READ,
    },
    
    Role.AUTOMATION: {
        Permission.AI_QUERY,
        Permission.AI_MEMORY_READ,
        Permission.AI_MEMORY_WRITE,
        Permission.PLUGIN_EXECUTE,
        Permission.AUTOMATION_EXECUTE,
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.NETWORK_INTERNAL,
        Permission.NETWORK_EXTERNAL,
        Permission.TOOL_WEB_AUTOMATION,
        Permission.TOOL_SYSTEM_CONTROL,
        Permission.TOOL_DATA_ANALYSIS,
    },
    
    Role.PLUGIN: {
        Permission.AI_QUERY,
        Permission.FILE_READ,
        Permission.NETWORK_INTERNAL,
    },
}


@dataclass
class PermissionContext:
    """Context for permission checks."""
    
    user_id: str
    role: Role
    permissions: Set[Permission] = field(default_factory=set)
    resource_owner: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if context has a specific permission."""
        # Admin has all permissions
        if self.role == Role.ADMIN:
            return True
        
        # Check explicit permissions
        if permission in self.permissions:
            return True
        
        # Check role permissions
        role_perms = ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if context has any of the specified permissions."""
        return any(self.has_permission(p) for p in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if context has all specified permissions."""
        return all(self.has_permission(p) for p in permissions)


class PermissionManager:
    """
    Permission manager for RBAC enforcement.
    
    Features:
    - Role-based access control
    - Granular permissions
    - Resource ownership checks
    - Audit logging
    """
    
    def __init__(self):
        self._permission_cache: Dict[str, PermissionContext] = {}
    
    def create_context(
        self,
        user_id: str,
        role: Role,
        extra_permissions: Optional[List[Permission]] = None,
        resource_owner: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PermissionContext:
        """
        Create a permission context for a user.
        
        Args:
            user_id: User identifier
            role: User's role
            extra_permissions: Additional permissions beyond role defaults
            resource_owner: Owner of the resource being accessed
            metadata: Additional context metadata
            
        Returns:
            PermissionContext instance
        """
        permissions = set(extra_permissions) if extra_permissions else set()
        
        context = PermissionContext(
            user_id=user_id,
            role=role,
            permissions=permissions,
            resource_owner=resource_owner,
            metadata=metadata or {},
        )
        
        # Cache context
        self._permission_cache[user_id] = context
        
        return context
    
    def check_permission(
        self,
        context: PermissionContext,
        permission: Permission,
        resource_id: Optional[str] = None,
        log_access: bool = True,
    ) -> bool:
        """
        Check if a permission context allows an action.
        
        Args:
            context: Permission context
            permission: Required permission
            resource_id: Optional resource being accessed
            log_access: Whether to log the access attempt
            
        Returns:
            True if permitted
        """
        allowed = context.has_permission(permission)
        
        # Log access attempt
        if log_access:
            audit_logger.log(
                action="permission_check",
                user_id=context.user_id,
                resource_type="permission",
                resource_id=str(permission),
                details={
                    "role": context.role.value,
                    "resource_id": resource_id,
                    "allowed": allowed,
                },
                status="success" if allowed else "failure",
            )
        
        return allowed
    
    def check_ownership(
        self,
        context: PermissionContext,
        resource_owner: str,
    ) -> bool:
        """
        Check if user owns or can access a resource.
        
        Args:
            context: Permission context
            resource_owner: Owner of the resource
            
        Returns:
            True if user owns or can access
        """
        # Admin can access everything
        if context.role == Role.ADMIN:
            return True
        
        # Check ownership
        return context.user_id == resource_owner
    
    def enforce_permission(
        self,
        context: PermissionContext,
        permission: Permission,
        resource_id: Optional[str] = None,
    ) -> None:
        """
        Enforce a permission, raising exception if denied.
        
        Args:
            context: Permission context
            permission: Required permission
            resource_id: Optional resource being accessed
            
        Raises:
            PermissionError: If permission denied
        """
        if not self.check_permission(context, permission, resource_id):
            logger.warning(
                "Permission denied",
                user_id=context.user_id,
                permission=str(permission),
                resource_id=resource_id,
            )
            raise PermissionError(
                f"Permission denied: {permission} for user {context.user_id}"
            )
    
    def get_user_permissions(self, context: PermissionContext) -> List[str]:
        """
        Get all permissions available to a user.
        
        Args:
            context: Permission context
            
        Returns:
            List of permission strings
        """
        if context.role == Role.ADMIN:
            return [p.value for p in Permission]
        
        role_perms = ROLE_PERMISSIONS.get(context.role, set())
        all_perms = role_perms | context.permissions
        
        return [p.value for p in all_perms]
    
    def grant_permission(
        self,
        admin_context: PermissionContext,
        target_user_id: str,
        permission: Permission,
    ) -> bool:
        """
        Grant a permission to a user (admin only).
        
        Args:
            admin_context: Admin's permission context
            target_user_id: User to grant permission to
            permission: Permission to grant
            
        Returns:
            True if granted
        """
        # Only admins can grant permissions
        if admin_context.role != Role.ADMIN:
            logger.warning(
                "Non-admin attempted to grant permission",
                user_id=admin_context.user_id,
            )
            return False
        
        # Get or create target context
        if target_user_id in self._permission_cache:
            target_context = self._permission_cache[target_user_id]
            target_context.permissions.add(permission)
        
        audit_logger.log(
            action="permission_granted",
            user_id=admin_context.user_id,
            resource_type="permission",
            resource_id=str(permission),
            details={"target_user": target_user_id},
        )
        
        return True
    
    def revoke_permission(
        self,
        admin_context: PermissionContext,
        target_user_id: str,
        permission: Permission,
    ) -> bool:
        """
        Revoke a permission from a user (admin only).
        
        Args:
            admin_context: Admin's permission context
            target_user_id: User to revoke permission from
            permission: Permission to revoke
            
        Returns:
            True if revoked
        """
        if admin_context.role != Role.ADMIN:
            return False
        
        if target_user_id in self._permission_cache:
            target_context = self._permission_cache[target_user_id]
            target_context.permissions.discard(permission)
        
        audit_logger.log(
            action="permission_revoked",
            user_id=admin_context.user_id,
            resource_type="permission",
            resource_id=str(permission),
            details={"target_user": target_user_id},
        )
        
        return True


def require_permission(*permissions: Permission):
    """
    Decorator to require permissions for a function.
    
    Usage:
        @require_permission(Permission.AI_QUERY)
        async def query_ai(context: PermissionContext, query: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find context in args or kwargs
            context = None
            for arg in args:
                if isinstance(arg, PermissionContext):
                    context = arg
                    break
            if context is None:
                context = kwargs.get("context")
            
            if context is None:
                raise ValueError("PermissionContext required for permission check")
            
            # Check permissions
            manager = PermissionManager()
            for permission in permissions:
                manager.enforce_permission(context, permission)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Global permission manager instance
permission_manager = PermissionManager()
