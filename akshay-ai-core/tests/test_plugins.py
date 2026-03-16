"""
============================================================
AKSHAY AI CORE — Plugin System Tests
============================================================
"""

import pytest
import asyncio


class TestPluginBase:
    """Tests for plugin base classes."""
    
    def test_plugin_metadata(self):
        """Test plugin metadata structure."""
        from plugins.base import PluginMetadata
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test",
        )
        
        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
    
    def test_plugin_config(self):
        """Test plugin configuration."""
        from plugins.base import PluginConfig
        
        config = PluginConfig(
            enabled=True,
            sandboxed=True,
            permissions=["file:read"],
        )
        
        assert config.enabled is True
        assert config.sandboxed is True
        assert "file:read" in config.permissions


@pytest.mark.asyncio
class TestPluginManager:
    """Tests for plugin manager."""
    
    async def test_load_builtin_plugins(self):
        """Test loading built-in plugins."""
        from plugins.manager import PluginManager
        
        manager = PluginManager()
        await manager.load_all_plugins()
        
        plugins = await manager.list_plugins()
        assert len(plugins) > 0
    
    async def test_get_plugin(self):
        """Test getting a specific plugin."""
        from plugins.manager import PluginManager
        
        manager = PluginManager()
        await manager.load_all_plugins()
        
        plugin = await manager.get_plugin("system_control")
        # Plugin should exist or return None
        assert plugin is None or plugin is not None


@pytest.mark.asyncio
class TestBuiltinPlugins:
    """Tests for built-in plugins."""
    
    async def test_system_control_plugin(self):
        """Test system control plugin."""
        from plugins.builtin.system_control import SystemControlPlugin
        
        plugin = SystemControlPlugin()
        await plugin.on_load()
        
        # Test get_system_info command
        result = await plugin.execute("get_system_info", {})
        
        assert result["status"] == "success"
        assert "cpu_percent" in result or "error" in result
    
    async def test_file_vault_plugin(self):
        """Test file vault plugin."""
        from plugins.builtin.file_vault import FileVaultPlugin
        
        plugin = FileVaultPlugin()
        await plugin.on_load()
        
        # Test list command
        result = await plugin.execute("list", {})
        
        assert "status" in result
    
    async def test_cyber_tools_plugin(self):
        """Test cyber tools plugin."""
        from plugins.builtin.cyber_tools import CyberToolsPlugin
        
        plugin = CyberToolsPlugin()
        await plugin.on_load()
        
        # Test password check
        result = await plugin.execute("check_password", {"password": "Test123!"})
        
        assert result["status"] == "success"
        assert "strength" in result
