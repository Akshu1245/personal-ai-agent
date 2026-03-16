"""
============================================================
AKSHAY AI CORE — Core Module Tests
============================================================
"""

import pytest
from pathlib import Path


class TestConfig:
    """Tests for configuration system."""
    
    def test_settings_load(self):
        """Test settings load from environment."""
        from core.config import settings
        
        assert settings.APP_NAME == "AKSHAY AI CORE"
        assert settings.VERSION is not None
    
    def test_settings_defaults(self):
        """Test default settings values."""
        from core.config import settings
        
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000
        assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR"]
    
    def test_ai_config_helper(self):
        """Test AI configuration helper."""
        from core.config import settings
        
        config = settings.get_ai_config()
        
        assert "provider" in config
        assert "model" in config
        assert "temperature" in config


class TestEncryption:
    """Tests for encryption engine."""
    
    def test_encrypt_decrypt(self):
        """Test basic encryption/decryption."""
        from core.security.encryption import EncryptionEngine
        
        engine = EncryptionEngine()
        plaintext = "Hello, AKSHAY!"
        
        ciphertext = engine.encrypt(plaintext)
        decrypted = engine.decrypt(ciphertext)
        
        assert decrypted == plaintext
        assert ciphertext != plaintext
    
    def test_encrypt_with_password(self):
        """Test password-based encryption."""
        from core.security.encryption import EncryptionEngine
        
        engine = EncryptionEngine()
        plaintext = "Secret message"
        password = "my-secure-password"
        
        ciphertext = engine.encrypt_with_password(plaintext, password)
        decrypted = engine.decrypt_with_password(ciphertext, password)
        
        assert decrypted == plaintext
    
    def test_hash_data(self):
        """Test data hashing."""
        from core.security.encryption import EncryptionEngine
        
        engine = EncryptionEngine()
        data = "test data"
        
        hash1 = engine.hash_data(data)
        hash2 = engine.hash_data(data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest


class TestPermissions:
    """Tests for permission system."""
    
    def test_role_permissions(self):
        """Test role-based permissions."""
        from core.security.permissions import PermissionManager, Role, Permission
        
        manager = PermissionManager()
        
        # Admin should have all permissions
        admin_perms = manager.get_role_permissions(Role.ADMIN)
        assert Permission.ADMIN_ACCESS in admin_perms
        
        # Guest should have limited permissions
        guest_perms = manager.get_role_permissions(Role.GUEST)
        assert Permission.ADMIN_ACCESS not in guest_perms
    
    def test_check_permission(self):
        """Test permission checking."""
        from core.security.permissions import PermissionManager, Role, Permission
        
        manager = PermissionManager()
        
        # Create context
        ctx = manager.create_context(user_id="test", role=Role.ADMIN)
        
        # Admin should have AI access
        assert manager.check_permission(ctx, Permission.AI_CHAT)
    
    def test_permission_decorator(self):
        """Test permission decorator."""
        from core.security.permissions import require_permission, Permission
        
        @require_permission(Permission.AI_CHAT)
        async def protected_function():
            return "success"
        
        # Function should be decorated
        assert hasattr(protected_function, "__wrapped__")
