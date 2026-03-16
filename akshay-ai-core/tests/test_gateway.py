"""
AKSHAY AI CORE — Gateway Foundation Tests

Tests for:
- Trust zone mapping
- Session management (JWT, MFA, elevation)
- Rate limiting
- Confirmation flows
- Voice-specific restrictions
- Interface adapters
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.gateway.base import (
    InterfaceType,
    GatewayStatus,
    GatewayRequest,
    GatewayResponse,
    RequestContext,
    ConfidenceLevel,
    create_gateway_request,
    create_terminal_request,
    create_api_request,
    create_voice_request,
)
from core.gateway.trust_map import (
    TrustZone,
    TrustMapper,
    TRUST_LEVELS,
    INTERFACE_CONSTRAINTS,
    get_trust_mapper,
    map_interface_to_zone,
)
from core.gateway.session import (
    SessionData,
    SessionManager,
    SessionState,
    MFAMethod,
    RevokeReason,
    InMemorySessionStore,
    compute_device_fingerprint,
    ACCESS_TOKEN_EXPIRY,
)
from core.gateway.router import (
    GatewayRouter,
    GatewayRateLimiter,
    ConfirmationManager,
    GatewayAuditLogger,
    TerminalAdapter,
    APIAdapter,
    VoiceAdapter,
)
from core.gateway.errors import (
    GatewayError,
    GatewayErrorCode,
    InvalidTokenError,
    RateLimitedError,
    ActionBlockedError,
    ConfirmationRequiredError,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def trust_mapper():
    """Create a fresh trust mapper."""
    return TrustMapper()


@pytest.fixture
def session_manager():
    """Create a fresh session manager."""
    return SessionManager(
        secret_key="test-secret-key-for-testing",
        store=InMemorySessionStore(),
    )


@pytest.fixture
def rate_limiter():
    """Create a fresh rate limiter."""
    return GatewayRateLimiter()


@pytest.fixture
def confirmation_manager():
    """Create a fresh confirmation manager."""
    return ConfirmationManager(expiry_seconds=300)


@pytest.fixture
def audit_logger():
    """Create a fresh audit logger."""
    return GatewayAuditLogger()


@pytest.fixture
def mock_policy_engine():
    """Create a mock policy engine."""
    from core.policy.schema import Decision, ReasonCode
    from core.policy.engine import EngineEvaluationResult
    
    engine = AsyncMock()
    
    # Default allow response
    engine.evaluate = AsyncMock(return_value=EngineEvaluationResult(
        decision=Decision.ALLOW,
        rule_id="test-rule",
        reason_code=ReasonCode.RULE_MATCHED,
        priority=100,
        audit_record={"reason": "Test allow"},
        evaluation_time_ms=1.5,
        policy_version="1.0.0",
    ))
    
    return engine


@pytest.fixture
def gateway_router(mock_policy_engine, session_manager, trust_mapper, rate_limiter, confirmation_manager, audit_logger):
    """Create a gateway router with mocked policy engine."""
    return GatewayRouter(
        policy_engine=mock_policy_engine,
        session_manager=session_manager,
        trust_mapper=trust_mapper,
        rate_limiter=rate_limiter,
        confirmation_manager=confirmation_manager,
        audit_logger=audit_logger,
    )


# =============================================================================
# TRUST ZONE MAPPING TESTS
# =============================================================================

class TestTrustZoneMapping:
    """Tests for trust zone mapping."""
    
    def test_terminal_gets_system_zone(self, trust_mapper):
        """Terminal interface should get SYSTEM trust zone."""
        request = create_terminal_request(
            actor_id="user-1",
            command="system.status",
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=True)
        
        assert zone == TrustZone.SYSTEM
    
    def test_api_gets_user_zone(self, trust_mapper):
        """API interface should get USER trust zone by default."""
        request = create_api_request(
            actor_id="user-1",
            tool="memory",
            action="read",
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=True)
        
        assert zone == TrustZone.USER
    
    def test_voice_gets_user_zone(self, trust_mapper):
        """Voice interface should get USER trust zone."""
        request = create_voice_request(
            actor_id="user-1",
            text="turn on the lights",
            confidence=0.95,
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=True)
        
        assert zone == TrustZone.USER
    
    def test_unauthenticated_gets_guest_zone(self, trust_mapper):
        """Unauthenticated requests should get GUEST zone."""
        request = create_api_request(
            actor_id="user-1",
            tool="memory",
            action="read",
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=False)
        
        assert zone == TrustZone.GUEST
    
    def test_voice_low_confidence_downgrades_to_guest(self, trust_mapper):
        """Voice with low confidence should downgrade to GUEST."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete all files",
            confidence=0.3,  # Very low confidence
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=True)
        
        assert zone == TrustZone.GUEST
    
    def test_voice_public_network_downgrades_to_guest(self, trust_mapper):
        """Voice on public network should downgrade to GUEST."""
        request = create_voice_request(
            actor_id="user-1",
            text="turn on the lights",
            confidence=0.95,
        )
        # Modify context for public network
        request = GatewayRequest(
            **{**request.model_dump(), "context": RequestContext(
                confidence=0.95,
                is_public_network=True,
            )}
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=True)
        
        assert zone == TrustZone.GUEST
    
    def test_api_with_mfa_elevates_to_operator(self, trust_mapper):
        """API with MFA should elevate to OPERATOR zone."""
        request = create_api_request(
            actor_id="user-1",
            tool="policy",
            action="update",
        )
        
        zone = trust_mapper.get_trust_zone(
            request,
            is_authenticated=True,
            mfa_verified=True,
            session_elevated=True,
        )
        
        assert zone == TrustZone.OPERATOR
    
    def test_voice_cannot_elevate_beyond_user(self, trust_mapper):
        """Voice interface cannot elevate beyond USER even with MFA."""
        request = create_voice_request(
            actor_id="user-1",
            text="update policy",
            confidence=0.95,
        )
        
        zone = trust_mapper.get_trust_zone(
            request,
            is_authenticated=True,
            mfa_verified=True,
            session_elevated=True,
        )
        
        # Voice max is USER, not OPERATOR
        assert zone == TrustZone.USER
    
    def test_automation_gets_system_zone(self, trust_mapper):
        """Automation interface should get SYSTEM zone."""
        request = create_gateway_request(
            interface=InterfaceType.AUTOMATION,
            actor_id="automation-1",
            tool="system",
            action="backup",
        )
        
        zone = trust_mapper.get_trust_zone(request, is_authenticated=True)
        
        assert zone == TrustZone.SYSTEM
    
    def test_trust_level_hierarchy(self):
        """Trust levels should follow hierarchy."""
        assert TRUST_LEVELS[TrustZone.SYSTEM] > TRUST_LEVELS[TrustZone.OPERATOR]
        assert TRUST_LEVELS[TrustZone.OPERATOR] > TRUST_LEVELS[TrustZone.USER]
        assert TRUST_LEVELS[TrustZone.USER] > TRUST_LEVELS[TrustZone.GUEST]


# =============================================================================
# VOICE CONSTRAINT TESTS
# =============================================================================

class TestVoiceConstraints:
    """Tests for voice-specific constraints."""
    
    def test_voice_blocks_shutdown(self, trust_mapper):
        """Voice should block shutdown command."""
        request = create_voice_request(
            actor_id="user-1",
            text="shutdown the system",
            confidence=0.99,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "system", "action": "shutdown"})
        
        blocked, reason = trust_mapper.is_action_blocked(request)
        
        assert blocked is True
        assert "shutdown" in reason.lower()
    
    def test_voice_blocks_reboot(self, trust_mapper):
        """Voice should block reboot command."""
        request = create_voice_request(
            actor_id="user-1",
            text="reboot the system",
            confidence=0.99,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "system", "action": "reboot"})
        
        blocked, reason = trust_mapper.is_action_blocked(request)
        
        assert blocked is True
    
    def test_voice_blocks_policy_delete(self, trust_mapper):
        """Voice should block policy deletion."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete policy",
            confidence=0.99,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "policy", "action": "delete"})
        
        blocked, reason = trust_mapper.is_action_blocked(request)
        
        assert blocked is True
    
    def test_voice_requires_confirmation_for_iot(self, trust_mapper):
        """Voice should require confirmation for IoT control."""
        request = create_voice_request(
            actor_id="user-1",
            text="turn on the lights",
            confidence=0.95,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "iot", "action": "device_control"})
        
        needs_confirm, phrase = trust_mapper.requires_confirmation(request)
        
        assert needs_confirm is True
        assert phrase is not None
    
    def test_voice_requires_confirmation_for_file_delete(self, trust_mapper):
        """Voice should require confirmation for file deletion."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete the document",
            confidence=0.95,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "file", "action": "delete"})
        
        needs_confirm, phrase = trust_mapper.requires_confirmation(request)
        
        assert needs_confirm is True
    
    def test_voice_mfa_required_for_iot(self, trust_mapper):
        """Voice should require MFA for IoT control."""
        request = create_voice_request(
            actor_id="user-1",
            text="turn on the lights",
            confidence=0.95,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "iot", "action": "device_control"})
        
        needs_mfa = trust_mapper.requires_mfa(request, already_verified=False)
        
        assert needs_mfa is True
    
    def test_voice_mfa_not_required_if_already_verified(self, trust_mapper):
        """Voice should not require MFA if already verified."""
        request = create_voice_request(
            actor_id="user-1",
            text="turn on the lights",
            confidence=0.95,
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "iot", "action": "device_control"})
        
        needs_mfa = trust_mapper.requires_mfa(request, already_verified=True)
        
        assert needs_mfa is False
    
    def test_terminal_allows_shutdown(self, trust_mapper):
        """Terminal should allow shutdown command."""
        request = create_terminal_request(
            actor_id="admin",
            command="system.shutdown",
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "system", "action": "shutdown"})
        
        blocked, reason = trust_mapper.is_action_blocked(request)
        
        assert blocked is False


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================

class TestSessionManagement:
    """Tests for session management."""
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Should create a new session with tokens."""
        session, access_token, refresh_token = await session_manager.create_session(
            user_id="user-1",
            role="operator",
            interface=InterfaceType.API,
            ip_address="192.168.1.100",
        )
        
        assert session.user_id == "user-1"
        assert session.role == "operator"
        assert session.interface == InterfaceType.API
        assert session.state == SessionState.ACTIVE
        assert access_token is not None
        assert refresh_token is not None
    
    @pytest.mark.asyncio
    async def test_validate_access_token(self, session_manager):
        """Should validate a valid access token."""
        session, access_token, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        payload = await session_manager.verify_token(access_token)
        
        assert payload is not None
        assert payload.sub == "user-1"
        assert payload.session_id == session.session_id
    
    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, session_manager):
        """Should reject invalid tokens."""
        payload = await session_manager.verify_token("invalid.token.here")
        
        assert payload is None
    
    @pytest.mark.asyncio
    async def test_session_revocation(self, session_manager):
        """Should revoke a session."""
        session, access_token, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        # Revoke the session
        revoked = await session_manager.revoke_session(
            session.session_id,
            RevokeReason.USER_LOGOUT
        )
        
        assert revoked is True
        
        # Token should now be invalid
        payload = await session_manager.verify_token(access_token)
        assert payload is None
    
    @pytest.mark.asyncio
    async def test_refresh_tokens(self, session_manager):
        """Should refresh access token with refresh token."""
        session, _, refresh_token = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        result = await session_manager.refresh_tokens(refresh_token)
        
        assert result is not None
        new_access, new_refresh = result
        assert new_access is not None
        assert new_refresh is not None
        
        # Verify new access token works
        payload = await session_manager.verify_token(new_access)
        assert payload is not None
        assert payload.sub == "user-1"
    
    @pytest.mark.asyncio
    async def test_mfa_verification(self, session_manager):
        """Should track MFA verification."""
        session, _, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        # Initially not verified
        assert session.mfa_verified is False
        
        # Verify MFA
        verified = await session_manager.verify_mfa(
            session.session_id,
            MFAMethod.TOTP,
            {"code": "123456"}
        )
        
        assert verified is True
        
        # Check session updated
        updated_session = await session_manager.get_session(session.session_id)
        assert updated_session.mfa_verified is True
        assert updated_session.mfa_method == MFAMethod.TOTP
    
    @pytest.mark.asyncio
    async def test_session_elevation(self, session_manager):
        """Should elevate session after MFA."""
        session, _, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        # Verify MFA first
        await session_manager.verify_mfa(
            session.session_id,
            MFAMethod.TOTP,
            {"code": "123456"}
        )
        
        # Elevate session
        elevated = await session_manager.elevate_session(session.session_id)
        
        assert elevated is True
        
        # Check session is elevated
        updated_session = await session_manager.get_session(session.session_id)
        assert updated_session.is_elevated is True
        assert updated_session.is_elevated_valid() is True
    
    @pytest.mark.asyncio
    async def test_elevation_requires_mfa(self, session_manager):
        """Elevation should fail without MFA."""
        session, _, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        # Try to elevate without MFA
        elevated = await session_manager.elevate_session(session.session_id)
        
        assert elevated is False
    
    @pytest.mark.asyncio
    async def test_session_limit_enforcement(self, session_manager):
        """Should enforce maximum sessions per user."""
        user_id = "heavy-user"
        
        # Create 10 sessions (the limit)
        for i in range(10):
            await session_manager.create_session(
                user_id=user_id,
                role="user",
                interface=InterfaceType.API,
            )
        
        # Create one more - should revoke oldest
        session, _, _ = await session_manager.create_session(
            user_id=user_id,
            role="user",
            interface=InterfaceType.API,
        )
        
        # Should still only have 10 active sessions
        sessions = await session_manager.get_user_sessions(user_id)
        active = [s for s in sessions if s.is_valid()]
        assert len(active) <= 10
    
    def test_device_fingerprint(self):
        """Should compute consistent device fingerprints."""
        fp1 = compute_device_fingerprint(
            user_agent="Mozilla/5.0",
            accept_language="en-US",
        )
        fp2 = compute_device_fingerprint(
            user_agent="Mozilla/5.0",
            accept_language="en-US",
        )
        
        assert fp1 == fp2
        assert len(fp1) == 32
    
    def test_different_devices_different_fingerprints(self):
        """Different devices should have different fingerprints."""
        fp1 = compute_device_fingerprint(user_agent="Mozilla/5.0")
        fp2 = compute_device_fingerprint(user_agent="Chrome/120.0")
        
        assert fp1 != fp2


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

class TestRateLimiter:
    """Tests for rate limiting."""
    
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, rate_limiter):
        """Should allow requests under the limit."""
        allowed, remaining, _ = await rate_limiter.check(
            "user-1",
            InterfaceType.API,
            limit=100,
        )
        
        assert allowed is True
        assert remaining == 99
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, rate_limiter):
        """Should block requests over the limit."""
        # Exhaust the limit
        for _ in range(10):
            await rate_limiter.check("user-1", InterfaceType.API, limit=10)
        
        # Next request should be blocked
        allowed, remaining, reset_at = await rate_limiter.check(
            "user-1",
            InterfaceType.API,
            limit=10,
        )
        
        assert allowed is False
        assert remaining == 0
        assert reset_at > datetime.now(timezone.utc)
    
    @pytest.mark.asyncio
    async def test_different_interfaces_separate_limits(self, rate_limiter):
        """Different interfaces should have separate limits."""
        # Exhaust API limit
        for _ in range(5):
            await rate_limiter.check("user-1", InterfaceType.API, limit=5)
        
        # API should be blocked
        api_allowed, _, _ = await rate_limiter.check("user-1", InterfaceType.API, limit=5)
        assert api_allowed is False
        
        # Terminal should still work
        terminal_allowed, _, _ = await rate_limiter.check("user-1", InterfaceType.TERMINAL, limit=5)
        assert terminal_allowed is True
    
    @pytest.mark.asyncio
    async def test_reset_clears_limit(self, rate_limiter):
        """Reset should clear the rate limit."""
        # Exhaust limit
        for _ in range(5):
            await rate_limiter.check("user-1", InterfaceType.API, limit=5)
        
        # Reset
        await rate_limiter.reset("user-1", InterfaceType.API)
        
        # Should be allowed again
        allowed, _, _ = await rate_limiter.check("user-1", InterfaceType.API, limit=5)
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_get_usage(self, rate_limiter):
        """Should track current usage."""
        for _ in range(3):
            await rate_limiter.check("user-1", InterfaceType.API, limit=100)
        
        usage = await rate_limiter.get_usage("user-1", InterfaceType.API)
        
        assert usage == 3


# =============================================================================
# CONFIRMATION FLOW TESTS
# =============================================================================

class TestConfirmationFlow:
    """Tests for confirmation flows."""
    
    @pytest.mark.asyncio
    async def test_create_confirmation(self, confirmation_manager):
        """Should create a confirmation request."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete all files",
            confidence=0.95,
        )
        
        pending = await confirmation_manager.create_confirmation(
            request=request,
            prompt="Are you sure you want to delete all files?",
            confirmation_phrase="Delete confirmed",
        )
        
        assert pending.token is not None
        assert len(pending.token) > 20
        assert pending.confirmation_phrase == "Delete confirmed"
    
    @pytest.mark.asyncio
    async def test_validate_correct_confirmation(self, confirmation_manager):
        """Should validate correct confirmation phrase."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete all files",
            confidence=0.95,
        )
        
        pending = await confirmation_manager.create_confirmation(
            request=request,
            prompt="Are you sure?",
            confirmation_phrase="Yes, confirm",
        )
        
        valid, original, error = await confirmation_manager.validate_confirmation(
            pending.token,
            confirmation_text="Yes, confirm",
        )
        
        assert valid is True
        assert original is not None
        assert error is None
    
    @pytest.mark.asyncio
    async def test_reject_wrong_confirmation_phrase(self, confirmation_manager):
        """Should reject wrong confirmation phrase."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete all files",
            confidence=0.95,
        )
        
        pending = await confirmation_manager.create_confirmation(
            request=request,
            prompt="Are you sure?",
            confirmation_phrase="Yes, confirm",
        )
        
        valid, original, error = await confirmation_manager.validate_confirmation(
            pending.token,
            confirmation_text="No way!",
        )
        
        assert valid is False
        assert original is None
        assert "incorrect" in error.lower()
    
    @pytest.mark.asyncio
    async def test_reject_invalid_token(self, confirmation_manager):
        """Should reject invalid confirmation token."""
        valid, original, error = await confirmation_manager.validate_confirmation(
            "invalid-token-12345",
            confirmation_text="Yes",
        )
        
        assert valid is False
        assert "invalid or expired" in error.lower()
    
    @pytest.mark.asyncio
    async def test_confirmation_expires(self, confirmation_manager):
        """Confirmation should expire."""
        # Create manager with very short expiry
        short_manager = ConfirmationManager(expiry_seconds=0)
        
        request = create_voice_request(
            actor_id="user-1",
            text="delete",
            confidence=0.95,
        )
        
        pending = await short_manager.create_confirmation(
            request=request,
            prompt="Confirm?",
        )
        
        # Wait for expiry
        await asyncio.sleep(0.1)
        
        valid, _, error = await short_manager.validate_confirmation(pending.token)
        
        assert valid is False
        assert "expired" in error.lower()
    
    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, confirmation_manager):
        """Should reject after max attempts."""
        request = create_voice_request(
            actor_id="user-1",
            text="delete",
            confidence=0.95,
        )
        
        pending = await confirmation_manager.create_confirmation(
            request=request,
            prompt="Confirm?",
            confirmation_phrase="Yes",
        )
        
        # Use up all attempts with wrong phrase
        for _ in range(3):
            await confirmation_manager.validate_confirmation(
                pending.token,
                confirmation_text="Wrong",
            )
        
        # Should now be rejected
        valid, _, error = await confirmation_manager.validate_confirmation(
            pending.token,
            confirmation_text="Yes",  # Correct phrase, but too late
        )
        
        assert valid is False
        assert "exceeded" in error.lower() or "invalid" in error.lower()


# =============================================================================
# GATEWAY ROUTER TESTS
# =============================================================================

class TestGatewayRouter:
    """Tests for the gateway router."""
    
    @pytest.mark.asyncio
    async def test_route_api_request(self, gateway_router, session_manager):
        """Should route API request successfully."""
        # Create session
        session, access_token, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        request = create_api_request(
            actor_id="user-1",
            tool="memory",
            action="read",
        )
        
        response = await gateway_router.route(request, access_token)
        
        assert response.status == GatewayStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_route_terminal_request(self, gateway_router):
        """Should route terminal request without token."""
        request = create_terminal_request(
            actor_id="admin",
            command="system.status",
        )
        
        response = await gateway_router.route(request)
        
        # Terminal doesn't require auth token
        assert response.status == GatewayStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_voice_blocked_action(self, gateway_router, trust_mapper):
        """Should block dangerous voice commands."""
        request = create_voice_request(
            actor_id="user-1",
            text="shutdown the system",
            confidence=0.99,
        )
        # Add tool/action for the blocked command
        request = GatewayRequest(**{**request.model_dump(), "tool": "system", "action": "shutdown"})
        
        response = await gateway_router.route(request)
        
        assert response.status == GatewayStatus.DENIED
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, gateway_router):
        """Should enforce rate limiting."""
        request = create_api_request(
            actor_id="rate-test-user",
            tool="memory",
            action="read",
        )
        
        # Exhaust rate limit (API = 200/min)
        for _ in range(200):
            await gateway_router.route(request)
        
        # Next request should be rate limited
        response = await gateway_router.route(request)
        
        assert response.status == GatewayStatus.RATE_LIMITED
    
    @pytest.mark.asyncio
    async def test_confirmation_flow(self, gateway_router, trust_mapper):
        """Should handle confirmation flow."""
        request = create_voice_request(
            actor_id="user-1",
            text="turn on the lights",
            confidence=0.95,
            face_present=True,  # Face required for IoT
        )
        # This action requires confirmation for voice
        request = GatewayRequest(**{**request.model_dump(), "tool": "iot", "action": "device_control"})
        
        response = await gateway_router.route(request)
        
        # Should require confirmation (or MFA first)
        assert response.status in {GatewayStatus.REQUIRES_CONFIRMATION, GatewayStatus.REQUIRES_MFA}
    
    @pytest.mark.asyncio
    async def test_audit_logging(self, gateway_router, audit_logger):
        """Should log all requests to audit."""
        request = create_api_request(
            actor_id="audit-test",
            tool="memory",
            action="read",
        )
        
        await gateway_router.route(request)
        
        logs = await audit_logger.get_logs()
        
        assert len(logs) >= 1
        # Should have request log
        request_logs = [l for l in logs if l.get("event") == "request"]
        assert len(request_logs) >= 1


# =============================================================================
# INTERFACE ADAPTER TESTS
# =============================================================================

class TestInterfaceAdapters:
    """Tests for interface adapters."""
    
    @pytest.mark.asyncio
    async def test_terminal_adapter(self, gateway_router):
        """Terminal adapter should route commands."""
        adapter = TerminalAdapter(gateway_router)
        
        response = await adapter.execute(
            actor_id="admin",
            command="system.status check",
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_api_adapter(self, gateway_router, session_manager):
        """API adapter should route requests."""
        adapter = APIAdapter(gateway_router)
        
        session, access_token, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.API,
        )
        
        response = await adapter.handle(
            actor_id="user-1",
            tool="memory",
            action="read",
            access_token=access_token,
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_voice_adapter(self, gateway_router, session_manager):
        """Voice adapter should route voice commands."""
        adapter = VoiceAdapter(gateway_router)
        
        session, access_token, _ = await session_manager.create_session(
            user_id="user-1",
            role="user",
            interface=InterfaceType.VOICE,
        )
        
        response = await adapter.handle(
            actor_id="user-1",
            text="what time is it",
            confidence=0.95,
            access_token=access_token,
        )
        
        assert response is not None


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrors:
    """Tests for gateway errors."""
    
    def test_error_code_values(self):
        """Error codes should have correct values."""
        assert GatewayErrorCode.INVALID_TOKEN.value == "INVALID_TOKEN"
        assert GatewayErrorCode.RATE_LIMITED.value == "RATE_LIMITED"
        assert GatewayErrorCode.ACTION_BLOCKED.value == "ACTION_BLOCKED"
    
    def test_error_to_dict(self):
        """Errors should serialize to dictionary."""
        error = InvalidTokenError("Token is invalid")
        
        error_dict = error.to_dict()
        
        assert error_dict["error"] is True
        assert error_dict["code"] == "INVALID_TOKEN"
        assert "Token is invalid" in error_dict["message"]
    
    def test_error_with_context(self):
        """Errors should include context."""
        from core.gateway.errors import GatewayErrorContext
        
        context = GatewayErrorContext(
            request_id="req-123",
            actor_id="user-1",
            tool="memory",
        )
        
        error = ActionBlockedError(
            "Action blocked",
            context=context,
        )
        
        error_dict = error.to_dict()
        assert error_dict["context"]["request_id"] == "req-123"


# =============================================================================
# REQUEST/RESPONSE MODEL TESTS
# =============================================================================

class TestModels:
    """Tests for request/response models."""
    
    def test_gateway_request_validation(self):
        """Request should validate required fields."""
        # Should fail without text or tool
        with pytest.raises(ValueError):
            GatewayRequest(
                interface=InterfaceType.API,
                actor_id="user-1",
            )
    
    def test_gateway_request_fingerprint(self):
        """Request should generate consistent fingerprint."""
        request1 = create_api_request(
            actor_id="user-1",
            tool="memory",
            action="read",
        )
        request2 = create_api_request(
            actor_id="user-1",
            tool="memory",
            action="read",
        )
        
        assert request1.get_fingerprint() == request2.get_fingerprint()
    
    def test_gateway_response_factory_methods(self):
        """Response factory methods should work."""
        success = GatewayResponse.success("req-1", message="OK")
        assert success.status == GatewayStatus.SUCCESS
        
        denied = GatewayResponse.denied("req-2", "POLICY_DENY", "Denied by policy")
        assert denied.status == GatewayStatus.DENIED
        
        rate_limited = GatewayResponse.rate_limited("req-3", retry_after=60)
        assert rate_limited.status == GatewayStatus.RATE_LIMITED
    
    def test_confidence_level_computation(self):
        """Confidence level should be computed from score."""
        high = create_voice_request("u1", "test", confidence=0.95)
        assert high.context.confidence_level == ConfidenceLevel.HIGH
        
        medium = create_voice_request("u1", "test", confidence=0.8)
        assert medium.context.confidence_level == ConfidenceLevel.MEDIUM
        
        low = create_voice_request("u1", "test", confidence=0.6)
        assert low.context.confidence_level == ConfidenceLevel.LOW


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================

class TestIntegration:
    """Integration-style tests for complete flows."""
    
    @pytest.mark.asyncio
    async def test_complete_api_flow(self, gateway_router, session_manager):
        """Test complete API request flow."""
        # 1. Create session
        session, access_token, refresh_token = await session_manager.create_session(
            user_id="integration-user",
            role="user",
            interface=InterfaceType.API,
            ip_address="10.0.0.1",
        )
        
        # 2. Make a request
        request = create_api_request(
            actor_id="integration-user",
            tool="memory",
            action="read",
            params={"namespace": "public"},
        )
        
        response = await gateway_router.route(request, access_token)
        
        # 3. Verify response
        assert response.status == GatewayStatus.SUCCESS
        assert response.data is not None
    
    @pytest.mark.asyncio
    async def test_complete_voice_with_confirmation(self, gateway_router, session_manager):
        """Test complete voice flow with confirmation."""
        # 1. Create session
        session, access_token, _ = await session_manager.create_session(
            user_id="voice-user",
            role="user",
            interface=InterfaceType.VOICE,
        )
        
        # 2. Make voice request that requires confirmation
        request = create_voice_request(
            actor_id="voice-user",
            text="turn on the lights",
            confidence=0.95,
            face_present=True,  # Face required for IoT
        )
        request = GatewayRequest(**{**request.model_dump(), "tool": "iot", "action": "device_control"})
        
        response = await gateway_router.route(request, access_token)
        
        # 3. Should require MFA or confirmation (MFA first in the flow)
        assert response.status in {GatewayStatus.REQUIRES_CONFIRMATION, GatewayStatus.REQUIRES_MFA}
        
        # Test completed - IoT voice commands require MFA and confirmation
        # The full confirmation flow is tested in TestConfirmationFlow
    
    @pytest.mark.asyncio
    async def test_session_lifecycle(self, session_manager):
        """Test complete session lifecycle."""
        # 1. Create session
        session, access_token, refresh_token = await session_manager.create_session(
            user_id="lifecycle-user",
            role="user",
            interface=InterfaceType.API,
        )
        assert session.is_valid()
        
        # 2. Verify tokens work
        payload = await session_manager.verify_token(access_token)
        assert payload is not None
        
        # 3. Verify MFA
        await session_manager.verify_mfa(
            session.session_id,
            MFAMethod.TOTP,
            {"code": "123456"}
        )
        
        # 4. Elevate session
        elevated = await session_manager.elevate_session(session.session_id)
        assert elevated is True
        
        # 5. Refresh tokens
        new_tokens = await session_manager.refresh_tokens(refresh_token)
        assert new_tokens is not None
        
        # 6. Revoke session
        revoked = await session_manager.revoke_session(
            session.session_id,
            RevokeReason.USER_LOGOUT
        )
        assert revoked is True
        
        # 7. Tokens should no longer work
        payload = await session_manager.verify_token(new_tokens[0])
        assert payload is None
