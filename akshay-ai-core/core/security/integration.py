"""
============================================================
AKSHAY AI CORE — Security Integration
============================================================
Integrates Permission Firewall and Tool Dispatcher into
all existing components.

This module provides:
- Secure wrappers for plugin execution
- Secure wrappers for command routing
- API middleware integration
- Automation security hooks
- Memory access security layer
============================================================
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.permissions import Permission, Role, ROLE_PERMISSIONS
from core.security.firewall import (
    PermissionFirewall,
    SecurityContext,
    SecurityDecision,
    SecurityDecisionResult,
    permission_firewall,
    create_security_context,
    firewall_protected,
    FirewallContextManager,
)
from core.security.dispatcher import (
    ToolDispatcher,
    ToolDefinition,
    ToolCategory,
    ExecutionRequest,
    ExecutionResult,
    ExecutionPriority,
    tool_dispatcher,
    register_tool,
    execute_tool,
)

logger = get_logger("security.integration")

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# PLUGIN EXECUTION SECURITY
# =============================================================================

class SecurePluginExecutor:
    """
    Secure wrapper for plugin execution.
    
    ALL plugin execution MUST go through this class.
    """
    
    def __init__(self, plugin_manager: Any):
        self.plugin_manager = plugin_manager
        self._register_plugin_tools()
    
    def _register_plugin_tools(self) -> None:
        """Register all plugin commands as dispatcher tools."""
        # This will be called after plugins are loaded
        pass
    
    async def register_plugin_as_tool(
        self,
        plugin_id: str,
        plugin_metadata: Dict[str, Any],
    ) -> None:
        """
        Register a plugin's commands as tools in the dispatcher.
        
        Args:
            plugin_id: Plugin identifier
            plugin_metadata: Plugin metadata including commands and permissions
        """
        commands = plugin_metadata.get("commands", [])
        plugin_permissions = plugin_metadata.get("permissions", [])
        
        # Convert string permissions to Permission enum
        required_perms = set()
        for perm_str in plugin_permissions:
            try:
                required_perms.add(Permission(perm_str))
            except ValueError:
                logger.warning(f"Unknown permission: {perm_str}")
        
        # Add execute_plugins permission
        required_perms.add(Permission.EXECUTE_PLUGINS)
        
        # Determine category based on plugin ID
        category_map = {
            "web_automation": ToolCategory.NETWORK,
            "system_control": ToolCategory.SYSTEM,
            "esp32_iot": ToolCategory.IOT,
            "file_vault": ToolCategory.FILE,
            "cyber_tools": ToolCategory.SYSTEM,
            "data_analysis": ToolCategory.DATA,
        }
        category = category_map.get(plugin_id, ToolCategory.PLUGIN)
        
        for command in commands:
            tool_name = f"{plugin_id}:{command}"
            
            # Create handler for this command
            async def make_handler(pid: str, cmd: str):
                async def handler(context: SecurityContext, **params) -> Dict[str, Any]:
                    return await self._execute_plugin_command(pid, cmd, params, context)
                return handler
            
            handler = await make_handler(plugin_id, command)
            
            # Determine additional settings based on command
            is_destructive = command in {"delete", "remove", "shutdown", "restart", "format"}
            requires_confirmation = is_destructive
            allow_network = plugin_id in {"web_automation", "esp32_iot"}
            allow_filesystem = plugin_id in {"file_vault", "system_control"}
            
            tool_def = ToolDefinition(
                name=tool_name,
                category=category,
                description=f"Plugin {plugin_id} command: {command}",
                handler=handler,
                required_permissions=required_perms,
                timeout_seconds=settings.PLUGINS_MAX_EXECUTION_TIME,
                sandbox_enabled=settings.PLUGINS_SANDBOX_ENABLED,
                allow_network=allow_network,
                allow_filesystem=allow_filesystem,
                requires_confirmation=requires_confirmation,
                is_destructive=is_destructive,
            )
            
            tool_dispatcher.register_tool(tool_def)
            logger.debug(f"Registered plugin tool: {tool_name}")
    
    async def execute(
        self,
        plugin_id: str,
        command: str,
        params: Dict[str, Any],
        user_id: str,
        role: Role = Role.USER,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a plugin command securely.
        
        Routes through the Tool Dispatcher which enforces:
        - Permission checks via Firewall
        - Rate limiting
        - Sandboxing
        - Audit logging
        
        Args:
            plugin_id: Plugin identifier
            command: Command to execute
            params: Command parameters
            user_id: User ID executing the command
            role: User's role
            session_id: Session ID
            ip_address: Client IP address
            
        Returns:
            Execution result
        """
        tool_name = f"{plugin_id}:{command}"
        
        # Create security context
        context = create_security_context(
            user_id=user_id,
            role=role,
            action=f"plugin_execute:{plugin_id}:{command}",
            session_id=session_id,
            ip_address=ip_address,
            resource_type="plugin",
            resource_id=plugin_id,
            parameters=params,
            is_plugin=True,
            plugin_name=plugin_id,
        )
        
        # Execute through dispatcher
        result = await execute_tool(
            tool_name=tool_name,
            context=context,
            parameters=params,
        )
        
        if result.success:
            return result.data
        else:
            raise RuntimeError(f"Plugin execution failed: {result.error}")
    
    async def _execute_plugin_command(
        self,
        plugin_id: str,
        command: str,
        params: Dict[str, Any],
        context: SecurityContext,
    ) -> Dict[str, Any]:
        """Internal method to execute plugin command after security checks."""
        # Get the actual plugin manager and execute
        plugin = self.plugin_manager._plugins.get(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        if not plugin.config.enabled:
            raise ValueError(f"Plugin is disabled: {plugin_id}")
        
        return await plugin.dispatch_command(command, params)


# =============================================================================
# COMMAND ROUTING SECURITY
# =============================================================================

class SecureCommandRouter:
    """
    Secure wrapper for command routing.
    
    ALL command routing MUST go through this class.
    """
    
    def __init__(self, command_router: Any, plugin_executor: SecurePluginExecutor):
        self.command_router = command_router
        self.plugin_executor = plugin_executor
    
    async def route_and_execute(
        self,
        text: str,
        user_id: str,
        role: Role = Role.USER,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Route a command and execute it securely.
        
        Steps:
        1. Parse and route the command
        2. Check permissions for target plugins
        3. Execute through secure plugin executor
        4. Return results
        
        Args:
            text: User input text
            user_id: User ID
            role: User's role
            session_id: Session ID
            ip_address: Client IP address
            context: Additional context
            
        Returns:
            Execution result
        """
        # Create security context for routing
        security_context = create_security_context(
            user_id=user_id,
            role=role,
            action="command_route",
            session_id=session_id,
            ip_address=ip_address,
        )
        
        # Step 1: Route the command
        routing_result = await self.command_router.route(
            text=text,
            context=context,
            user_id=user_id,
        )
        
        # Step 2: If fallback to LLM, check LLM permission
        if routing_result.fallback_to_llm:
            llm_check = await permission_firewall.evaluate(
                security_context,
                {Permission.QUERY_AI},
            )
            
            if not llm_check.allowed:
                return {
                    "success": False,
                    "error": f"Permission denied: {llm_check.reason}",
                    "intent": routing_result.intent.action,
                }
            
            return {
                "success": True,
                "fallback_to_llm": True,
                "intent": routing_result.intent.action,
                "category": routing_result.intent.category.value,
            }
        
        # Step 3: Execute targets through secure plugin executor
        results = []
        
        for target in routing_result.targets:
            try:
                result = await self.plugin_executor.execute(
                    plugin_id=target.plugin_id,
                    command=target.command,
                    params=target.params,
                    user_id=user_id,
                    role=role,
                    session_id=session_id,
                    ip_address=ip_address,
                )
                results.append({
                    "plugin": target.plugin_id,
                    "command": target.command,
                    "success": True,
                    "result": result,
                })
            except PermissionError as e:
                results.append({
                    "plugin": target.plugin_id,
                    "command": target.command,
                    "success": False,
                    "error": str(e),
                })
            except Exception as e:
                results.append({
                    "plugin": target.plugin_id,
                    "command": target.command,
                    "success": False,
                    "error": str(e),
                })
        
        return {
            "success": all(r["success"] for r in results),
            "intent": routing_result.intent.action,
            "category": routing_result.intent.category.value,
            "results": results,
        }


# =============================================================================
# MEMORY ACCESS SECURITY
# =============================================================================

class SecureMemoryAccess:
    """
    Secure wrapper for memory operations.
    
    ALL memory access MUST go through this class.
    """
    
    def __init__(self, memory_manager: Any):
        self.memory_manager = memory_manager
        self._namespace_owners: Dict[str, str] = {}  # namespace -> user_id
        self._shared_namespaces: Dict[str, Set[str]] = {}  # namespace -> set of user_ids
    
    def set_namespace_owner(self, namespace: str, user_id: str) -> None:
        """Set ownership of a namespace."""
        self._namespace_owners[namespace] = user_id
    
    def share_namespace(self, namespace: str, user_ids: Set[str]) -> None:
        """Share namespace with other users."""
        self._shared_namespaces[namespace] = user_ids
    
    def _check_namespace_access(
        self,
        user_id: str,
        namespace: str,
        write: bool = False,
    ) -> bool:
        """Check if user can access namespace."""
        # System namespace is accessible to all for reading
        if namespace == "system" and not write:
            return True
        
        # Owner has full access
        if self._namespace_owners.get(namespace) == user_id:
            return True
        
        # Check shared access (read-only unless specifically granted)
        if not write and user_id in self._shared_namespaces.get(namespace, set()):
            return True
        
        # User's own namespace (format: user:<user_id>)
        if namespace.startswith(f"user:{user_id}"):
            return True
        
        return False
    
    async def store(
        self,
        key: str,
        content: str,
        memory_type: str,
        user_id: str,
        role: Role = Role.USER,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        namespace: str = "default",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Securely store memory.
        
        Args:
            key: Memory key
            content: Content to store
            memory_type: Type of memory
            user_id: User ID
            role: User's role
            session_id: Session ID
            ip_address: Client IP
            namespace: Memory namespace
            metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        # Create security context
        context = create_security_context(
            user_id=user_id,
            role=role,
            action="memory_write",
            session_id=session_id,
            ip_address=ip_address,
            resource_type="memory",
            resource_id=f"{namespace}:{key}",
        )
        
        # Determine required permissions
        required_perms = {Permission.WRITE_MEMORY}
        if memory_type == "LONG_TERM":
            required_perms.add(Permission.ACCESS_LONG_TERM_MEMORY)
        
        # Check through firewall
        result = await permission_firewall.evaluate(context, required_perms)
        
        if not result.allowed:
            raise PermissionError(f"Memory write denied: {result.reason}")
        
        # Check namespace access
        if not self._check_namespace_access(user_id, namespace, write=True):
            raise PermissionError(f"No write access to namespace: {namespace}")
        
        # Store with namespace prefix
        namespaced_key = f"{namespace}:{key}"
        
        # Add security metadata
        secure_metadata = metadata or {}
        secure_metadata.update({
            "created_by": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "namespace": namespace,
            "security_context": context.fingerprint,
        })
        
        return await self.memory_manager.store(
            key=namespaced_key,
            content=content,
            memory_type=memory_type,
            metadata=secure_metadata,
        )
    
    async def recall(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        user_id: str = "",
        role: Role = Role.USER,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        namespace: str = "default",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Securely recall memories.
        
        Args:
            query: Search query
            memory_types: Types to search
            user_id: User ID
            role: User's role
            session_id: Session ID
            ip_address: Client IP
            namespace: Memory namespace
            limit: Max results
            
        Returns:
            List of memory results
        """
        # Create security context
        context = create_security_context(
            user_id=user_id,
            role=role,
            action="memory_read",
            session_id=session_id,
            ip_address=ip_address,
            resource_type="memory",
            resource_id=f"{namespace}:*",
        )
        
        # Determine required permissions
        required_perms = {Permission.READ_MEMORY}
        if memory_types and "LONG_TERM" in memory_types:
            required_perms.add(Permission.ACCESS_LONG_TERM_MEMORY)
        
        # Check through firewall
        result = await permission_firewall.evaluate(context, required_perms)
        
        if not result.allowed:
            raise PermissionError(f"Memory read denied: {result.reason}")
        
        # Check namespace access
        if not self._check_namespace_access(user_id, namespace, write=False):
            raise PermissionError(f"No read access to namespace: {namespace}")
        
        # Recall with namespace filter
        memories = await self.memory_manager.recall(
            query=query,
            memory_types=memory_types,
            filters={"namespace": namespace},
            limit=limit,
        )
        
        # Filter out any memories from inaccessible namespaces
        filtered = []
        for memory in memories:
            mem_namespace = memory.get("metadata", {}).get("namespace", "default")
            if self._check_namespace_access(user_id, mem_namespace, write=False):
                filtered.append(memory)
        
        return filtered
    
    async def delete(
        self,
        memory_id: str,
        user_id: str,
        role: Role = Role.USER,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Securely delete memory.
        
        Args:
            memory_id: Memory ID to delete
            user_id: User ID
            role: User's role
            session_id: Session ID
            ip_address: Client IP
            
        Returns:
            True if deleted
        """
        # Create security context
        context = create_security_context(
            user_id=user_id,
            role=role,
            action="memory_delete",
            session_id=session_id,
            ip_address=ip_address,
            resource_type="memory",
            resource_id=memory_id,
        )
        
        # Delete requires write permission
        required_perms = {Permission.DELETE_MEMORY}
        
        # Check through firewall
        result = await permission_firewall.evaluate(context, required_perms)
        
        if not result.allowed:
            raise PermissionError(f"Memory delete denied: {result.reason}")
        
        # Get memory to check ownership
        memory = await self.memory_manager.get(memory_id)
        if not memory:
            return False
        
        # Check if user owns this memory
        creator = memory.get("metadata", {}).get("created_by")
        namespace = memory.get("metadata", {}).get("namespace", "default")
        
        if creator != user_id and not self._check_namespace_access(user_id, namespace, write=True):
            if role != Role.ADMIN:
                raise PermissionError("Cannot delete memory created by another user")
        
        return await self.memory_manager.delete(memory_id)


# =============================================================================
# API SECURITY MIDDLEWARE
# =============================================================================

async def extract_security_context(request: Any) -> SecurityContext:
    """
    Extract SecurityContext from FastAPI request.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        SecurityContext populated from request
    """
    # Get user info from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", "anonymous")
    role_str = getattr(request.state, "role", "guest")
    session_id = getattr(request.state, "session_id", None)
    
    # Convert role string to Role enum
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.GUEST
    
    # Get client IP
    ip_address = None
    if hasattr(request, "client") and request.client:
        ip_address = request.client.host
    
    # Get request ID
    request_id = getattr(request.state, "request_id", None)
    
    return create_security_context(
        user_id=user_id,
        role=role,
        session_id=session_id,
        ip_address=ip_address,
        request_id=request_id,
    )


def api_protected(
    action: str,
    permissions: Optional[Set[Permission]] = None,
    resource_type: str = "",
) -> Callable:
    """
    Decorator for protecting FastAPI endpoints.
    
    Usage:
        @router.post("/memory")
        @api_protected(action="memory_write", permissions={Permission.WRITE_MEMORY})
        async def create_memory(request: Request, data: MemoryCreate):
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Extract security context
            context = await extract_security_context(request)
            context.action = action
            context.resource_type = resource_type
            
            # Check through firewall
            result = await permission_firewall.evaluate(context, permissions)
            
            if not result.allowed:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Permission denied",
                        "reason": result.reason,
                        "decision": result.decision.name,
                    }
                )
            
            # Inject context into kwargs
            kwargs["security_context"] = context
            
            return await func(request, *args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


# =============================================================================
# AUTOMATION SECURITY
# =============================================================================

class SecureAutomationExecutor:
    """
    Secure wrapper for automation/scheduled task execution.
    
    ALL automation execution MUST go through this class.
    """
    
    def __init__(self, scheduler: Any):
        self.scheduler = scheduler
        self._automation_user = "automation_service"
        self._automation_role = Role.AUTOMATION
    
    async def execute_rule(
        self,
        rule_id: str,
        trigger_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Execute an automation rule securely.
        
        Args:
            rule_id: Rule to execute
            trigger_context: Context from trigger
            
        Returns:
            Execution result
        """
        # Create security context for automation
        context = create_security_context(
            user_id=self._automation_user,
            role=self._automation_role,
            action="automation_trigger",
            resource_type="automation_rule",
            resource_id=rule_id,
            is_automation=True,
        )
        
        # Check permission (automation service should have trigger permission)
        result = await permission_firewall.evaluate(
            context,
            {Permission.TRIGGER_AUTOMATIONS},
        )
        
        if not result.allowed:
            logger.warning(
                "Automation execution denied",
                rule_id=rule_id,
                reason=result.reason,
            )
            return {
                "success": False,
                "error": f"Permission denied: {result.reason}",
            }
        
        try:
            # Execute the rule
            rule_result = await self.scheduler.execute_rule(
                rule_id,
                trigger_context=trigger_context,
            )
            
            return {
                "success": True,
                "result": rule_result,
            }
            
        except Exception as e:
            logger.error(
                "Automation execution failed",
                rule_id=rule_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e),
            }


# =============================================================================
# GLOBAL INTEGRATION INSTANCE
# =============================================================================

class SecurityIntegration:
    """
    Central security integration point.
    
    Provides unified access to all secure wrappers.
    """
    
    _instance: Optional["SecurityIntegration"] = None
    
    def __new__(cls) -> "SecurityIntegration":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self.firewall = permission_firewall
        self.dispatcher = tool_dispatcher
        
        self.plugin_executor: Optional[SecurePluginExecutor] = None
        self.command_router: Optional[SecureCommandRouter] = None
        self.memory_access: Optional[SecureMemoryAccess] = None
        self.automation_executor: Optional[SecureAutomationExecutor] = None
    
    def initialize(
        self,
        plugin_manager: Any = None,
        command_router: Any = None,
        memory_manager: Any = None,
        automation_scheduler: Any = None,
    ) -> None:
        """
        Initialize security integration with application components.
        
        Args:
            plugin_manager: PluginManager instance
            command_router: CommandRouter instance
            memory_manager: MemoryManager instance
            automation_scheduler: AutomationScheduler instance
        """
        if plugin_manager:
            self.plugin_executor = SecurePluginExecutor(plugin_manager)
        
        if command_router and self.plugin_executor:
            self.command_router = SecureCommandRouter(command_router, self.plugin_executor)
        
        if memory_manager:
            self.memory_access = SecureMemoryAccess(memory_manager)
        
        if automation_scheduler:
            self.automation_executor = SecureAutomationExecutor(automation_scheduler)
        
        logger.info("Security integration initialized")
    
    async def register_plugins(self, plugin_manager: Any) -> None:
        """Register all loaded plugins with the dispatcher."""
        if not self.plugin_executor:
            self.plugin_executor = SecurePluginExecutor(plugin_manager)
        
        for plugin_id, plugin in plugin_manager._plugins.items():
            await self.plugin_executor.register_plugin_as_tool(
                plugin_id=plugin_id,
                plugin_metadata={
                    "commands": list(plugin._commands.keys()),
                    "permissions": [p.value for p in plugin.metadata.permissions],
                }
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        return {
            "firewall": self.firewall.get_stats(),
            "dispatcher": self.dispatcher.get_stats(),
        }


# Global instance
security_integration = SecurityIntegration()


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    # Classes
    "SecurePluginExecutor",
    "SecureCommandRouter",
    "SecureMemoryAccess",
    "SecureAutomationExecutor",
    "SecurityIntegration",
    
    # Functions
    "extract_security_context",
    "api_protected",
    
    # Global instances
    "security_integration",
    "permission_firewall",
    "tool_dispatcher",
    
    # Context creation
    "create_security_context",
    
    # Types from firewall
    "SecurityContext",
    "SecurityDecision",
    "SecurityDecisionResult",
    
    # Types from dispatcher
    "ToolDefinition",
    "ToolCategory",
    "ExecutionRequest",
    "ExecutionResult",
]
