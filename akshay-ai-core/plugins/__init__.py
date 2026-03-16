"""
============================================================
AKSHAY AI CORE — Plugin System Package
============================================================
"""

from plugins.manager import PluginManager, plugin_manager
from plugins.base import Plugin, PluginConfig, PluginMetadata

__all__ = [
    "PluginManager",
    "plugin_manager",
    "Plugin",
    "PluginConfig",
    "PluginMetadata",
]
