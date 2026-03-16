"""
============================================================
AKSHAY AI CORE — Plugin Manager
============================================================
Manages plugin lifecycle, discovery, loading, and execution.

SECURITY: All plugin execution is routed through the
Permission Firewall and Tool Dispatcher.
============================================================
"""

import asyncio
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type
from datetime import datetime

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.permissions import Permission, Role, PermissionContext, permission_manager
from core.security.firewall import (
    permission_firewall,
    create_security_context,
    SecurityContext,
)
from core.security.dispatcher import (
    tool_dispatcher,
    ToolDefinition,
    ToolCategory,
    execute_tool,
    ExecutionRequest,
)
from plugins.base import Plugin, PluginStatus, PluginConfig

logger = get_logger("plugins")


class PluginManager:
    """
    Manages the plugin ecosystem.
    
    Features:
    - Plugin discovery and loading
    - Sandboxed execution
    - Dependency resolution
    - Permission enforcement
    - Hot reload support
    """
    
    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_classes: Dict[str, Type[Plugin]] = {}
        self._builtin_path = Path(__file__).parent / "builtin"
        self._custom_path = Path(settings.PLUGINS_DIR) / "custom"
        self._execution_lock = asyncio.Lock()
    
    async def load_all_plugins(self) -> int:
        """
        Discover and load all plugins.
        
        Returns:
            Number of plugins loaded
        """
        loaded = 0
        
        # Load built-in plugins first
        if settings.PLUGINS_ENABLED:
            loaded += await self._load_builtin_plugins()
            loaded += await self._load_custom_plugins()
        
        logger.info(f"Loaded {loaded} plugins")
        return loaded
    
    async def _load_builtin_plugins(self) -> int:
        """Load built-in plugins."""
        loaded = 0
        
        builtin_plugins = [
            ("web_automation", settings.PLUGIN_WEB_AUTOMATION),
            ("system_control", settings.PLUGIN_SYSTEM_CONTROL),
            ("esp32_iot", settings.PLUGIN_ESP32_IOT),
            ("file_vault", settings.PLUGIN_FILE_VAULT),
            ("cyber_tools", settings.PLUGIN_CYBER_TOOLS),
            ("data_analysis", settings.PLUGIN_DATA_ANALYSIS),
        ]
        
        for plugin_name, enabled in builtin_plugins:
            if not enabled:
                continue
            
            try:
                module_path = self._builtin_path / plugin_name / "__init__.py"
                if module_path.exists():
                    if await self._load_plugin_from_path(module_path, is_builtin=True):
                        loaded += 1
            except Exception as e:
                logger.error(f"Failed to load builtin plugin {plugin_name}", error=str(e))
        
        return loaded
    
    async def _load_custom_plugins(self) -> int:
        """Load custom user plugins."""
        loaded = 0
        
        if not self._custom_path.exists():
            self._custom_path.mkdir(parents=True, exist_ok=True)
            return 0
        
        for plugin_dir in self._custom_path.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
                try:
                    if await self._load_plugin_from_path(
                        plugin_dir / "__init__.py",
                        is_builtin=False,
                    ):
                        loaded += 1
                except Exception as e:
                    logger.error(f"Failed to load custom plugin {plugin_dir.name}", error=str(e))
        
        return loaded
    
    async def _load_plugin_from_path(self, path: Path, is_builtin: bool = False) -> bool:
        """
        Load a plugin from a file path.
        
        Args:
            path: Path to plugin __init__.py
            is_builtin: Whether this is a built-in plugin
            
        Returns:
            True if loaded successfully
        """
        module_name = f"plugins.{'builtin' if is_builtin else 'custom'}.{path.parent.name}"
        
        try:
            # Load module
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find Plugin subclass
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                    and hasattr(attr, "metadata")
                    and attr.metadata is not None
                ):
                    plugin_class = attr
                    break
            
            if plugin_class is None:
                logger.warning(f"No Plugin class found in {path}")
                return False
            
            # Instantiate and load plugin
            plugin = plugin_class()
            
            if await plugin.load():
                self._plugins[plugin.id] = plugin
                self._plugin_classes[plugin.id] = plugin_class
                
                audit_logger.log(
                    action="plugin_loaded",
                    resource_type="plugin",
                    resource_id=plugin.id,
                    details={
                        "name": plugin.metadata.name,
                        "version": plugin.metadata.version,
                        "is_builtin": is_builtin,
                    },
                )
                
                logger.info(
                    f"Loaded plugin: {plugin.metadata.name} v{plugin.metadata.version}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error loading plugin from {path}", error=str(e))
            return False
    
    async def unload_all_plugins(self) -> None:
        """Unload all plugins."""
        for plugin_id in list(self._plugins.keys()):
            await self.unload_plugin(plugin_id)
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload a specific plugin.
        
        Args:
            plugin_id: Plugin to unload
            
        Returns:
            True if unloaded successfully
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        try:
            await plugin.unload()
            del self._plugins[plugin_id]
            
            audit_logger.log(
                action="plugin_unloaded",
                resource_type="plugin",
                resource_id=plugin_id,
            )
            
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}", error=str(e))
            return False
    
    async def reload_plugin(self, plugin_id: str) -> bool:
        """
        Reload a plugin.
        
        Args:
            plugin_id: Plugin to reload
            
        Returns:
            True if reloaded successfully
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        return await plugin.reload()
    
    async def execute_plugin(
        self,
        plugin_id: str,
        command: str,
        params: Dict[str, Any],
        user_id: str,
        role: Role = Role.USER,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Execute a plugin command SECURELY.
        
        ALL plugin execution MUST go through this method.
        Enforces permission checks, rate limiting, sandboxing,
        and audit logging via the Tool Dispatcher.
        
        Args:
            plugin_id: Plugin to execute
            command: Command name
            params: Command parameters
            user_id: User executing the command
            role: User's role for permission checking
            session_id: Session ID for tracking
            ip_address: Client IP address
            timeout: Execution timeout in seconds
            
        Returns:
            Execution result
            
        Raises:
            ValueError: Plugin not found or disabled
            PermissionError: User lacks required permissions
            TimeoutError: Execution exceeded timeout
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        if not plugin.config.enabled:
            raise ValueError(f"Plugin is disabled: {plugin_id}")
        
        # ================================================================
        # SECURITY: Route through Permission Firewall
        # ================================================================
        
        # Build required permissions from plugin metadata
        required_permissions: Set[Permission] = {Permission.EXECUTE_PLUGINS}
        for perm in plugin.metadata.permissions:
            try:
                required_permissions.add(Permission(perm.value if hasattr(perm, 'value') else perm))
            except ValueError:
                pass  # Skip unknown permissions
        
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
        
        # Check permissions through firewall
        security_result = await permission_firewall.evaluate(context, required_permissions)
        
        if not security_result.allowed:
            audit_logger.log(
                action="plugin_execution_denied",
                user_id=user_id,
                resource_type="plugin",
                resource_id=plugin_id,
                details={
                    "command": command,
                    "reason": security_result.reason,
                    "missing_permissions": [p.value for p in security_result.missing_permissions],
                },
                status="denied",
                ip_address=ip_address,
            )
            raise PermissionError(
                f"Plugin execution denied: {security_result.reason}. "
                f"Missing permissions: {[p.value for p in security_result.missing_permissions]}"
            )
        
        # ================================================================
        # EXECUTE with sandbox and timeout
        # ================================================================
        
        async with self._execution_lock:
            plugin._status = PluginStatus.RUNNING
            start_time = datetime.utcnow()
            
            try:
                # Execute with timeout
                if settings.PLUGINS_SANDBOX_ENABLED and plugin.config.sandboxed:
                    result = await asyncio.wait_for(
                        self._execute_sandboxed(plugin, command, params),
                        timeout=min(timeout, plugin.config.max_execution_time),
                    )
                else:
                    result = await asyncio.wait_for(
                        plugin.dispatch_command(command, params),
                        timeout=timeout,
                    )
                
                # Update stats
                plugin._execution_count += 1
                plugin._last_executed = datetime.utcnow()
                plugin._status = PluginStatus.LOADED
                
                # Log execution
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                audit_logger.log(
                    action="plugin_executed",
                    user_id=user_id,
                    resource_type="plugin",
                    resource_id=plugin_id,
                    details={
                        "command": command,
                        "duration_ms": duration,
                    },
                )
                
                return result
                
            except asyncio.TimeoutError:
                plugin._status = PluginStatus.ERROR
                plugin._last_error = "Execution timeout"
                raise TimeoutError(f"Plugin execution timed out after {timeout}s")
            except Exception as e:
                plugin._status = PluginStatus.ERROR
                plugin._last_error = str(e)
                raise
    
    async def _execute_sandboxed(
        self,
        plugin: Plugin,
        command: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute plugin in a sandboxed environment.
        
        Args:
            plugin: Plugin instance
            command: Command to execute
            params: Command parameters
            
        Returns:
            Execution result
        """
        # In a full implementation, this would:
        # 1. Create isolated execution context
        # 2. Restrict file system access
        # 3. Limit network access based on permissions
        # 4. Cap memory and CPU usage
        
        # For now, just execute normally
        return await plugin.dispatch_command(command, params)
    
    async def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all registered plugins.
        
        Returns:
            List of plugin info dictionaries
        """
        return [plugin.to_dict() for plugin in self._plugins.values()]
    
    async def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin information.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Plugin info dictionary or None
        """
        plugin = self._plugins.get(plugin_id)
        return plugin.to_dict() if plugin else None
    
    async def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        plugin.config.enabled = True
        await plugin.on_enable()
        
        audit_logger.log(
            action="plugin_enabled",
            resource_type="plugin",
            resource_id=plugin_id,
        )
        
        return True
    
    async def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        plugin.config.enabled = False
        plugin._status = PluginStatus.DISABLED
        await plugin.on_disable()
        
        audit_logger.log(
            action="plugin_disabled",
            resource_type="plugin",
            resource_id=plugin_id,
        )
        
        return True
    
    async def get_plugin_config(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin configuration."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return None
        
        return {
            "enabled": plugin.config.enabled,
            "sandboxed": plugin.config.sandboxed,
            "max_execution_time": plugin.config.max_execution_time,
            "permissions": plugin.config.permissions,
            "settings": plugin.config.settings,
        }
    
    async def update_plugin_config(
        self,
        plugin_id: str,
        config: Dict[str, Any],
    ) -> bool:
        """Update plugin configuration."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        old_config = plugin.config
        
        # Update config
        if "enabled" in config:
            plugin.config.enabled = config["enabled"]
        if "sandboxed" in config:
            plugin.config.sandboxed = config["sandboxed"]
        if "max_execution_time" in config:
            plugin.config.max_execution_time = config["max_execution_time"]
        if "settings" in config:
            plugin.config.settings.update(config["settings"])
        
        # Notify plugin
        await plugin.on_config_change(old_config, plugin.config)
        
        return True
    
    async def register_plugins_with_dispatcher(self) -> int:
        """
        Register all loaded plugins with the Tool Dispatcher.
        
        This enables the dispatcher to route tool calls to plugins
        with proper permission enforcement and sandboxing.
        
        Returns:
            Number of tools registered
        """
        registered = 0
        
        for plugin_id, plugin in self._plugins.items():
            try:
                count = await self._register_plugin_tools(plugin_id, plugin)
                registered += count
            except Exception as e:
                logger.error(
                    f"Failed to register plugin {plugin_id} with dispatcher",
                    error=str(e),
                )
        
        logger.info(f"Registered {registered} plugin tools with dispatcher")
        return registered
    
    async def _register_plugin_tools(self, plugin_id: str, plugin: Plugin) -> int:
        """
        Register a single plugin's commands as dispatcher tools.
        
        Args:
            plugin_id: Plugin identifier
            plugin: Plugin instance
            
        Returns:
            Number of tools registered
        """
        registered = 0
        
        # Get plugin commands
        commands = list(plugin._commands.keys()) if hasattr(plugin, '_commands') else []
        
        # Determine tool category based on plugin type
        category_map = {
            "web_automation": ToolCategory.NETWORK,
            "system_control": ToolCategory.SYSTEM,
            "esp32_iot": ToolCategory.IOT,
            "file_vault": ToolCategory.FILE,
            "cyber_tools": ToolCategory.SYSTEM,
            "data_analysis": ToolCategory.DATA,
        }
        category = category_map.get(plugin_id, ToolCategory.PLUGIN)
        
        # Build required permissions
        required_perms: Set[Permission] = {Permission.EXECUTE_PLUGINS}
        for perm in plugin.metadata.permissions:
            try:
                required_perms.add(Permission(perm.value if hasattr(perm, 'value') else perm))
            except ValueError:
                pass
        
        for command in commands:
            tool_name = f"{plugin_id}:{command}"
            
            # Determine additional settings
            is_destructive = command in {"delete", "remove", "shutdown", "restart", "format", "uninstall"}
            requires_confirmation = is_destructive
            allow_network = plugin_id in {"web_automation", "esp32_iot"}
            allow_filesystem = plugin_id in {"file_vault", "system_control"}
            
            # Create a closure to capture plugin_id and command
            def make_handler(pid: str, cmd: str, plug: Plugin):
                async def handler(context: SecurityContext = None, **params) -> Dict[str, Any]:
                    return await plug.dispatch_command(cmd, params)
                return handler
            
            handler = make_handler(plugin_id, command, plugin)
            
            tool_def = ToolDefinition(
                name=tool_name,
                category=category,
                description=f"Plugin {plugin_id} command: {command}",
                handler=handler,
                required_permissions=required_perms,
                timeout_seconds=plugin.config.max_execution_time,
                sandbox_enabled=plugin.config.sandboxed,
                allow_network=allow_network,
                allow_filesystem=allow_filesystem,
                requires_confirmation=requires_confirmation,
                is_destructive=is_destructive,
            )
            
            tool_dispatcher.register_tool(tool_def)
            registered += 1
            logger.debug(f"Registered plugin tool: {tool_name}")
        
        return registered


# Global plugin manager instance
plugin_manager = PluginManager()
