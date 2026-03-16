"""
============================================================
AKSHAY AI CORE — Plugin Base Classes
============================================================
Base classes and interfaces for creating plugins.
============================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum


class PluginStatus(str, Enum):
    """Plugin status enumeration."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginMetadata:
    """Plugin metadata information."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    email: str = ""
    website: str = ""
    license: str = "Proprietary"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    min_core_version: str = "1.0.0"


@dataclass
class PluginConfig:
    """Plugin configuration."""
    enabled: bool = True
    sandboxed: bool = True
    max_execution_time: int = 300  # seconds
    permissions: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """
    Base class for all plugins.
    
    Plugins must inherit from this class and implement
    the required abstract methods.
    
    Example:
        class MyPlugin(Plugin):
            metadata = PluginMetadata(
                name="my_plugin",
                version="1.0.0",
                description="My awesome plugin"
            )
            
            async def on_load(self):
                # Initialize plugin
                pass
            
            async def execute(self, command: str, params: dict) -> dict:
                # Handle command
                return {"status": "success"}
    """
    
    # Override these in subclass
    metadata: PluginMetadata = None
    config: PluginConfig = None
    
    def __init__(self):
        """Initialize the plugin."""
        if self.metadata is None:
            raise ValueError("Plugin must define metadata")
        
        if self.config is None:
            self.config = PluginConfig()
        
        self._status = PluginStatus.UNLOADED
        self._loaded_at: Optional[datetime] = None
        self._execution_count = 0
        self._last_executed: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._commands: Dict[str, Callable] = {}
    
    @property
    def id(self) -> str:
        """Get plugin ID (name in lowercase)."""
        return self.metadata.name.lower().replace(" ", "_")
    
    @property
    def status(self) -> PluginStatus:
        """Get current plugin status."""
        return self._status
    
    @property
    def is_loaded(self) -> bool:
        """Check if plugin is loaded."""
        return self._status in (PluginStatus.LOADED, PluginStatus.RUNNING)
    
    # =========================================
    # Lifecycle Methods
    # =========================================
    
    async def load(self) -> bool:
        """
        Load and initialize the plugin.
        
        Returns:
            True if loaded successfully
        """
        try:
            self._status = PluginStatus.LOADING
            await self.on_load()
            self._status = PluginStatus.LOADED
            self._loaded_at = datetime.utcnow()
            return True
        except Exception as e:
            self._status = PluginStatus.ERROR
            self._last_error = str(e)
            return False
    
    async def unload(self) -> bool:
        """
        Unload and cleanup the plugin.
        
        Returns:
            True if unloaded successfully
        """
        try:
            await self.on_unload()
            self._status = PluginStatus.UNLOADED
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def reload(self) -> bool:
        """
        Reload the plugin.
        
        Returns:
            True if reloaded successfully
        """
        await self.unload()
        return await self.load()
    
    # =========================================
    # Abstract Methods (Must Implement)
    # =========================================
    
    @abstractmethod
    async def on_load(self) -> None:
        """
        Called when plugin is loaded.
        
        Initialize resources, register commands, etc.
        """
        pass
    
    @abstractmethod
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a plugin command.
        
        Args:
            command: Command to execute
            params: Command parameters
            
        Returns:
            Execution result dictionary
        """
        pass
    
    # =========================================
    # Optional Lifecycle Methods
    # =========================================
    
    async def on_unload(self) -> None:
        """Called when plugin is unloaded. Override for cleanup."""
        pass
    
    async def on_enable(self) -> None:
        """Called when plugin is enabled."""
        pass
    
    async def on_disable(self) -> None:
        """Called when plugin is disabled."""
        pass
    
    async def on_config_change(self, old_config: PluginConfig, new_config: PluginConfig) -> None:
        """Called when plugin configuration changes."""
        pass
    
    # =========================================
    # Command Registration
    # =========================================
    
    def register_command(self, name: str, handler: Callable, description: str = "") -> None:
        """
        Register a command handler.
        
        Args:
            name: Command name
            handler: Async function to handle command
            description: Command description
        """
        self._commands[name] = {
            "handler": handler,
            "description": description,
        }
    
    def get_commands(self) -> List[Dict[str, str]]:
        """
        Get list of registered commands.
        
        Returns:
            List of command info dictionaries
        """
        return [
            {"name": name, "description": info["description"]}
            for name, info in self._commands.items()
        ]
    
    async def dispatch_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch a command to its handler.
        
        Args:
            command: Command name
            params: Command parameters
            
        Returns:
            Handler result
        """
        if command in self._commands:
            handler = self._commands[command]["handler"]
            return await handler(params)
        
        # Fall back to generic execute
        return await self.execute(command, params)
    
    # =========================================
    # Utility Methods
    # =========================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plugin info to dictionary."""
        return {
            "id": self.id,
            "name": self.metadata.name,
            "version": self.metadata.version,
            "description": self.metadata.description,
            "author": self.metadata.author,
            "status": self._status.value,
            "is_enabled": self.config.enabled,
            "is_builtin": False,
            "permissions": self.config.permissions,
            "execution_count": self._execution_count,
            "last_executed": self._last_executed,
            "last_error": self._last_error,
            "loaded_at": self._loaded_at,
            "commands": self.get_commands(),
        }
    
    def __repr__(self) -> str:
        return f"<Plugin {self.metadata.name} v{self.metadata.version} [{self._status.value}]>"


class BuiltinPlugin(Plugin):
    """Base class for built-in plugins."""
    
    @property
    def is_builtin(self) -> bool:
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["is_builtin"] = True
        return data
