"""
AKSHAY AI CORE — Gateway Router

The unified routing layer that connects all interfaces to the Policy Engine.

MISSION:
Route ALL requests (Terminal, API, Voice, UI) through the same
security pipeline: Trust Mapping → Rate Limiting → Policy Engine →
Audit Logging.

SECURITY GUARANTEES:
- No interface bypasses policy evaluation
- All requests are rate-limited per interface
- All requests are audit-logged
- Voice requests have extra confirmation requirements
- Trust zones are enforced consistently

FLOW:
1. Receive GatewayRequest from interface adapter
2. Validate session (if token provided)
3. Apply trust zone based on interface + session
4. Check interface-level blocks
5. Apply rate limiting
6. Route to Policy Engine
7. Handle interactive flows (confirmation, MFA)
8. Log to audit trail
9. Return GatewayResponse

NO SHORTCUTS. NO EXCEPTIONS.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.gateway.base import (
    ConfidenceLevel,
    GatewayRequest,
    GatewayResponse,
    GatewayStatus,
    InterfaceType,
    RequestContext,
    RequestPriority,
)
from core.gateway.trust_map import (
    TrustZone,
    TrustMapper,
    TRUST_LEVELS,
    InterfaceConstraints,
    VoiceConstraints,
    get_trust_mapper,
    INTERFACE_CONSTRAINTS,
)
from core.gateway.session import (
    SessionData,
    SessionManager,
    SessionState,
    TokenPayload,
    get_session_manager,
    MFAMethod,
)
from core.policy.engine import (
    PolicyEngine,
    EngineEvaluationRequest,
    EngineEvaluationResult,
    SourceType,
)
from core.policy.schema import Decision, ReasonCode
from core.policy.loader import FinalPolicy


# =============================================================================
# CONSTANTS
# =============================================================================

# Confirmation token expiry (5 minutes)
CONFIRMATION_TOKEN_EXPIRY_SECONDS = 300

# MFA timeout (2 minutes)
MFA_TIMEOUT_SECONDS = 120

# Rate limit window
RATE_LIMIT_WINDOW_SECONDS = 60


# =============================================================================
# RATE LIMITER
# =============================================================================

class GatewayRateLimiter:
    """
    Per-interface rate limiting.
    
    Uses sliding window algorithm.
    """
    
    def __init__(self):
        # actor_id + interface -> [(timestamp, count)]
        self._windows: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    async def check(
        self,
        actor_id: str,
        interface: InterfaceType,
        limit: int,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> Tuple[bool, int, datetime]:
        """
        Check if request is within rate limit.
        
        Returns:
            (allowed, remaining, reset_at)
        """
        key = f"{actor_id}:{interface.value}"
        now = time.time()
        cutoff = now - window_seconds
        
        async with self._lock:
            # Get or create window
            if key not in self._windows:
                self._windows[key] = []
            
            # Remove old entries
            self._windows[key] = [
                ts for ts in self._windows[key]
                if ts > cutoff
            ]
            
            current = len(self._windows[key])
            
            if current >= limit:
                # Rate limited
                oldest = min(self._windows[key]) if self._windows[key] else now
                reset_at = datetime.fromtimestamp(oldest + window_seconds, tz=timezone.utc)
                return (False, 0, reset_at)
            
            # Record request
            self._windows[key].append(now)
            remaining = limit - current - 1
            reset_at = datetime.now(timezone.utc) + timedelta(seconds=window_seconds)
            
            return (True, remaining, reset_at)
    
    async def get_usage(
        self,
        actor_id: str,
        interface: InterfaceType,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> int:
        """Get current request count in window."""
        key = f"{actor_id}:{interface.value}"
        now = time.time()
        cutoff = now - window_seconds
        
        async with self._lock:
            if key not in self._windows:
                return 0
            
            self._windows[key] = [
                ts for ts in self._windows[key]
                if ts > cutoff
            ]
            
            return len(self._windows[key])
    
    async def reset(self, actor_id: str, interface: Optional[InterfaceType] = None) -> None:
        """Reset rate limit for actor."""
        async with self._lock:
            if interface:
                key = f"{actor_id}:{interface.value}"
                self._windows.pop(key, None)
            else:
                # Reset all interfaces for actor
                keys_to_remove = [
                    k for k in self._windows.keys()
                    if k.startswith(f"{actor_id}:")
                ]
                for k in keys_to_remove:
                    self._windows.pop(k, None)


# =============================================================================
# CONFIRMATION MANAGER
# =============================================================================

@dataclass
class PendingConfirmation:
    """A pending confirmation request."""
    
    token: str
    request: GatewayRequest
    prompt: str
    confirmation_phrase: Optional[str]
    created_at: datetime
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3


class ConfirmationManager:
    """Manages confirmation flows for destructive/sensitive actions."""
    
    def __init__(self, expiry_seconds: int = CONFIRMATION_TOKEN_EXPIRY_SECONDS):
        self._pending: Dict[str, PendingConfirmation] = {}
        self._expiry = expiry_seconds
        self._lock = asyncio.Lock()
    
    async def create_confirmation(
        self,
        request: GatewayRequest,
        prompt: str,
        confirmation_phrase: Optional[str] = None,
    ) -> PendingConfirmation:
        """Create a new confirmation request."""
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        
        pending = PendingConfirmation(
            token=token,
            request=request,
            prompt=prompt,
            confirmation_phrase=confirmation_phrase,
            created_at=now,
            expires_at=now + timedelta(seconds=self._expiry),
        )
        
        async with self._lock:
            self._pending[token] = pending
        
        return pending
    
    async def validate_confirmation(
        self,
        token: str,
        confirmation_text: Optional[str] = None,
    ) -> Tuple[bool, Optional[GatewayRequest], Optional[str]]:
        """
        Validate a confirmation response.
        
        Returns:
            (valid, original_request, error_message)
        """
        async with self._lock:
            pending = self._pending.get(token)
            
            if pending is None:
                return (False, None, "Invalid or expired confirmation token")
            
            # Check expiry
            if datetime.now(timezone.utc) > pending.expires_at:
                del self._pending[token]
                return (False, None, "Confirmation token expired")
            
            # Check attempts
            pending.attempts += 1
            if pending.attempts > pending.max_attempts:
                del self._pending[token]
                return (False, None, "Maximum confirmation attempts exceeded")
            
            # Check phrase if required
            if pending.confirmation_phrase:
                if not confirmation_text:
                    return (False, None, f"Please say: '{pending.confirmation_phrase}'")
                
                # Normalize and compare
                normalized_response = confirmation_text.lower().strip()
                normalized_phrase = pending.confirmation_phrase.lower().strip()
                
                if normalized_response != normalized_phrase:
                    return (
                        False, 
                        None, 
                        f"Incorrect confirmation. Please say: '{pending.confirmation_phrase}'"
                    )
            
            # Valid confirmation
            original = pending.request
            del self._pending[token]
            
            return (True, original, None)
    
    async def cleanup_expired(self) -> int:
        """Remove expired confirmations. Returns count removed."""
        now = datetime.now(timezone.utc)
        removed = 0
        
        async with self._lock:
            expired = [
                token for token, pending in self._pending.items()
                if now > pending.expires_at
            ]
            for token in expired:
                del self._pending[token]
                removed += 1
        
        return removed


# =============================================================================
# AUDIT LOGGER INTERFACE
# =============================================================================

class GatewayAuditLogger:
    """
    Gateway-level audit logging.
    
    Logs all requests and decisions for security monitoring.
    """
    
    def __init__(self):
        self._logs: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
    
    async def log_request(
        self,
        request: GatewayRequest,
        session: Optional[SessionData],
        trust_zone: TrustZone,
    ) -> None:
        """Log incoming request."""
        entry = {
            "event": "request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request.request_id,
            "interface": request.interface.value,
            "actor_id": request.actor_id,
            "tool": request.tool,
            "action": request.action,
            "trust_zone": trust_zone.value,
            "session_id": session.session_id if session else None,
            "mfa_verified": session.mfa_verified if session else False,
            "ip_address": request.context.ip_address,
        }
        
        async with self._lock:
            self._logs.append(entry)
    
    async def log_decision(
        self,
        request_id: str,
        decision: Decision,
        reason_code: str,
        rule_id: Optional[str] = None,
        evaluation_time_ms: float = 0.0,
    ) -> None:
        """Log policy decision."""
        entry = {
            "event": "decision",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "decision": decision.value,
            "reason_code": reason_code,
            "rule_id": rule_id,
            "evaluation_time_ms": evaluation_time_ms,
        }
        
        async with self._lock:
            self._logs.append(entry)
    
    async def log_blocked(
        self,
        request_id: str,
        reason: str,
        block_type: str,  # "rate_limit", "interface_block", "trust_violation"
    ) -> None:
        """Log blocked request."""
        entry = {
            "event": "blocked",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "reason": reason,
            "block_type": block_type,
        }
        
        async with self._lock:
            self._logs.append(entry)
    
    async def log_confirmation_required(
        self,
        request_id: str,
        confirmation_token: str,
    ) -> None:
        """Log confirmation requirement."""
        entry = {
            "event": "confirmation_required",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "confirmation_token": confirmation_token[:8] + "...",
        }
        
        async with self._lock:
            self._logs.append(entry)
    
    async def get_logs(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent audit logs."""
        async with self._lock:
            logs = self._logs
            if since:
                since_str = since.isoformat()
                logs = [l for l in logs if l["timestamp"] >= since_str]
            return logs[-limit:]


# =============================================================================
# GATEWAY ROUTER
# =============================================================================

class GatewayRouter:
    """
    The unified gateway router.
    
    Routes all requests through the security pipeline:
    1. Session validation
    2. Trust zone assignment
    3. Interface-level blocks
    4. Rate limiting
    5. Policy evaluation
    6. Confirmation handling
    7. Audit logging
    
    NO INTERFACE GETS SPECIAL TREATMENT.
    """
    
    def __init__(
        self,
        policy_engine: PolicyEngine,
        session_manager: Optional[SessionManager] = None,
        trust_mapper: Optional[TrustMapper] = None,
        rate_limiter: Optional[GatewayRateLimiter] = None,
        confirmation_manager: Optional[ConfirmationManager] = None,
        audit_logger: Optional[GatewayAuditLogger] = None,
    ):
        """
        Initialize the gateway router.
        
        Args:
            policy_engine: The policy evaluation engine
            session_manager: Session management (default: global singleton)
            trust_mapper: Trust zone mapper (default: global singleton)
            rate_limiter: Rate limiter (default: new instance)
            confirmation_manager: Confirmation handler (default: new instance)
            audit_logger: Audit logger (default: new instance)
        """
        self._policy_engine = policy_engine
        self._session_manager = session_manager or get_session_manager()
        self._trust_mapper = trust_mapper or get_trust_mapper()
        self._rate_limiter = rate_limiter or GatewayRateLimiter()
        self._confirmation_manager = confirmation_manager or ConfirmationManager()
        self._audit_logger = audit_logger or GatewayAuditLogger()
    
    # -------------------------------------------------------------------------
    # MAIN ROUTING
    # -------------------------------------------------------------------------
    
    async def route(
        self,
        request: GatewayRequest,
        access_token: Optional[str] = None,
    ) -> GatewayResponse:
        """
        Route a request through the security pipeline.
        
        Args:
            request: The gateway request
            access_token: JWT access token (if authenticated)
            
        Returns:
            GatewayResponse with decision and data
        """
        start_time = time.time()
        session: Optional[SessionData] = None
        trust_zone: TrustZone = TrustZone.GUEST
        
        try:
            # =================================================================
            # STEP 1: Session Validation
            # =================================================================
            if access_token:
                session = await self._validate_session(request, access_token)
            
            # =================================================================
            # STEP 2: Trust Zone Assignment
            # =================================================================
            trust_zone = self._assign_trust_zone(request, session)
            
            # Log incoming request
            await self._audit_logger.log_request(request, session, trust_zone)
            
            # =================================================================
            # STEP 3: Interface-Level Blocks
            # =================================================================
            blocked, block_reason = self._trust_mapper.is_action_blocked(request)
            if blocked:
                await self._audit_logger.log_blocked(
                    request.request_id,
                    block_reason or "Interface block",
                    "interface_block"
                )
                return GatewayResponse.denied(
                    request_id=request.request_id,
                    reason_code="INTERFACE_BLOCKED",
                    message=block_reason or "Action blocked for this interface",
                )
            
            # =================================================================
            # STEP 4: Rate Limiting
            # =================================================================
            rate_check = await self._check_rate_limit(request)
            if not rate_check[0]:  # not allowed
                _, remaining, reset_at = rate_check
                await self._audit_logger.log_blocked(
                    request.request_id,
                    f"Rate limit exceeded for {request.interface.value}",
                    "rate_limit"
                )
                return GatewayResponse.rate_limited(
                    request_id=request.request_id,
                    retry_after=int((reset_at - datetime.now(timezone.utc)).total_seconds()),
                    remaining=remaining,
                )
            
            # =================================================================
            # STEP 5: Confirmation Check (if this IS a confirmation)
            # =================================================================
            if request.is_confirmation and request.confirmation_token:
                return await self._handle_confirmation(
                    request, session, trust_zone, start_time
                )
            
            # =================================================================
            # STEP 6: Check if Confirmation Required
            # =================================================================
            needs_confirm, phrase = self._trust_mapper.requires_confirmation(request)
            if needs_confirm:
                return await self._request_confirmation(request, phrase)
            
            # =================================================================
            # STEP 7: Check if MFA Required
            # =================================================================
            mfa_verified = session.mfa_verified if session else False
            if self._trust_mapper.requires_mfa(request, already_verified=mfa_verified):
                return GatewayResponse.requires_mfa_response(
                    request_id=request.request_id,
                    challenge=f"MFA required. Methods: totp, face, pin. Timeout: {MFA_TIMEOUT_SECONDS}s",
                )
            
            # =================================================================
            # STEP 8: Policy Evaluation
            # =================================================================
            eval_result = await self._evaluate_policy(
                request, session, trust_zone
            )
            
            # Log decision
            await self._audit_logger.log_decision(
                request.request_id,
                eval_result.decision,
                str(eval_result.reason_code),
                eval_result.rule_id,
                eval_result.evaluation_time_ms
            )
            
            # =================================================================
            # STEP 9: Build Response
            # =================================================================
            return self._build_response(request, eval_result, start_time)
            
        except Exception as e:
            # Log error and return safe error response
            await self._audit_logger.log_blocked(
                request.request_id,
                str(e),
                "internal_error"
            )
            return GatewayResponse.error(
                request_id=request.request_id,
                status=GatewayStatus.INTERNAL_ERROR,
                error_code="INTERNAL_ERROR",
                message="An internal error occurred processing your request"
            )
    
    # -------------------------------------------------------------------------
    # SESSION VALIDATION
    # -------------------------------------------------------------------------
    
    async def _validate_session(
        self,
        request: GatewayRequest,
        access_token: str,
    ) -> Optional[SessionData]:
        """Validate session from access token."""
        # Verify token
        payload = await self._session_manager.verify_token(
            access_token,
            expected_type="access",
            check_fingerprint=request.context.device_fingerprint
        )
        
        if payload is None:
            return None
        
        # Get session
        session = await self._session_manager.validate_session(payload.session_id)
        
        return session
    
    # -------------------------------------------------------------------------
    # TRUST ZONE ASSIGNMENT
    # -------------------------------------------------------------------------
    
    def _assign_trust_zone(
        self,
        request: GatewayRequest,
        session: Optional[SessionData],
    ) -> TrustZone:
        """Assign trust zone based on interface and session."""
        is_authenticated = session is not None and session.is_valid()
        mfa_verified = session.mfa_verified if session else False
        session_elevated = session.is_elevated_valid() if session else False
        
        zone = self._trust_mapper.get_trust_zone(
            request,
            is_authenticated=is_authenticated,
            mfa_verified=mfa_verified,
            session_elevated=session_elevated,
        )
        
        return zone
    
    # -------------------------------------------------------------------------
    # RATE LIMITING
    # -------------------------------------------------------------------------
    
    async def _check_rate_limit(
        self,
        request: GatewayRequest,
    ) -> Tuple[bool, int, datetime]:
        """Check rate limit for request."""
        limit = self._trust_mapper.get_rate_limit(request.interface)
        
        return await self._rate_limiter.check(
            request.actor_id,
            request.interface,
            limit
        )
    
    # -------------------------------------------------------------------------
    # CONFIRMATION HANDLING
    # -------------------------------------------------------------------------
    
    async def _request_confirmation(
        self,
        request: GatewayRequest,
        phrase: Optional[str],
    ) -> GatewayResponse:
        """Create a confirmation request."""
        # Build prompt
        action = f"{request.tool}.{request.action}" if request.tool else "action"
        prompt = f"Are you sure you want to perform '{action}'?"
        
        if phrase:
            prompt += f" Please say: '{phrase}'"
        
        # Create pending confirmation
        pending = await self._confirmation_manager.create_confirmation(
            request=request,
            prompt=prompt,
            confirmation_phrase=phrase,
        )
        
        # Log
        await self._audit_logger.log_confirmation_required(
            request.request_id,
            pending.token
        )
        
        return GatewayResponse.requires_confirm(
            request_id=request.request_id,
            prompt=prompt,
            token=pending.token,
            timeout=CONFIRMATION_TOKEN_EXPIRY_SECONDS
        )
    
    async def _handle_confirmation(
        self,
        request: GatewayRequest,
        session: Optional[SessionData],
        trust_zone: TrustZone,
        start_time: float,
    ) -> GatewayResponse:
        """Handle a confirmation response."""
        valid, original_request, error_msg = await self._confirmation_manager.validate_confirmation(
            request.confirmation_token,
            request.text  # The confirmation text
        )
        
        if not valid:
            return GatewayResponse.denied(
                request_id=request.request_id,
                reason_code="CONFIRMATION_FAILED",
                message=error_msg or "Confirmation failed",
            )
        
        # Proceed with original request
        eval_result = await self._evaluate_policy(
            original_request,
            session,
            trust_zone
        )
        
        # Log decision
        await self._audit_logger.log_decision(
            original_request.request_id,
            eval_result.decision,
            str(eval_result.reason_code),
            eval_result.rule_id,
            eval_result.evaluation_time_ms
        )
        
        return self._build_response(original_request, eval_result, start_time)
    
    # -------------------------------------------------------------------------
    # POLICY EVALUATION
    # -------------------------------------------------------------------------
    
    async def _evaluate_policy(
        self,
        request: GatewayRequest,
        session: Optional[SessionData],
        trust_zone: TrustZone,
    ) -> EngineEvaluationResult:
        """Evaluate request against policy engine."""
        # Map interface to source type
        source_map = {
            InterfaceType.TERMINAL: SourceType.TERMINAL,
            InterfaceType.API: SourceType.API,
            InterfaceType.WEBSOCKET: SourceType.API,
            InterfaceType.MOBILE: SourceType.MOBILE,
            InterfaceType.DESKTOP: SourceType.API,
            InterfaceType.VOICE: SourceType.VOICE,
            InterfaceType.AUTOMATION: SourceType.AUTOMATION,
            InterfaceType.INTERNAL: SourceType.INTERNAL,
        }
        source = source_map.get(request.interface, SourceType.UNKNOWN)
        
        # Build evaluation request
        eval_request = EngineEvaluationRequest(
            actor_id=request.actor_id,
            role=request.role,
            trust_zone=trust_zone.value,
            source=source,
            tool=request.tool or "unknown",
            action=request.action or "execute",
            target=request.target,
            timestamp=request.timestamp,
            context={
                "ip": request.context.ip_address,
                "mfa": request.context.mfa_verified,
                "confidence": request.context.confidence,
                "session_id": request.context.session_id,
                "interface": request.interface.value,
                "device_fingerprint": request.context.device_fingerprint,
            }
        )
        
        # Evaluate
        result = await self._policy_engine.evaluate(eval_request)
        
        return result
    
    # -------------------------------------------------------------------------
    # RESPONSE BUILDING
    # -------------------------------------------------------------------------
    
    def _build_response(
        self,
        request: GatewayRequest,
        eval_result: EngineEvaluationResult,
        start_time: float,
    ) -> GatewayResponse:
        """Build gateway response from evaluation result."""
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Map decision to status
        status_map = {
            Decision.ALLOW: GatewayStatus.SUCCESS,
            Decision.DENY: GatewayStatus.DENIED,
            Decision.REQUIRE_CONFIRMATION: GatewayStatus.REQUIRES_CONFIRMATION,
            Decision.REQUIRE_MFA: GatewayStatus.REQUIRES_MFA,
            Decision.REQUIRE_ELEVATION: GatewayStatus.REQUIRES_ELEVATION,
            Decision.RATE_LIMITED: GatewayStatus.RATE_LIMITED,
        }
        status = status_map.get(eval_result.decision, GatewayStatus.DENIED)
        
        # Build reason code
        reason_code = (
            eval_result.reason_code.value
            if hasattr(eval_result.reason_code, "value")
            else str(eval_result.reason_code)
        )
        
        # Handle interactive decisions
        if eval_result.decision == Decision.REQUIRE_CONFIRMATION:
            return GatewayResponse(
                request_id=request.request_id,
                status=status,
                decision=eval_result.decision.value,
                rule_id=eval_result.rule_id,
                reason_code=reason_code,
                message=eval_result.confirmation_message or "Confirmation required",
                requires_confirmation=True,
                confirmation_prompt=eval_result.confirmation_message,
                data={
                    "evaluation_time_ms": eval_result.evaluation_time_ms,
                    "gateway_time_ms": elapsed_ms,
                }
            )
        
        if eval_result.decision == Decision.REQUIRE_MFA:
            return GatewayResponse(
                request_id=request.request_id,
                status=GatewayStatus.REQUIRES_MFA,
                decision=eval_result.decision.value,
                rule_id=eval_result.rule_id,
                reason_code=reason_code,
                message="MFA verification required",
                requires_mfa=True,
                data={
                    "evaluation_time_ms": eval_result.evaluation_time_ms,
                    "gateway_time_ms": elapsed_ms,
                    "mfa_timeout": eval_result.mfa_timeout_seconds or MFA_TIMEOUT_SECONDS,
                }
            )
        
        # Standard response
        return GatewayResponse(
            request_id=request.request_id,
            status=status,
            decision=eval_result.decision.value,
            rule_id=eval_result.rule_id,
            reason_code=reason_code,
            message=eval_result.audit_record.get("reason", ""),
            data={
                "safe_mode": eval_result.safe_mode,
                "policy_version": eval_result.policy_version,
                "evaluation_time_ms": eval_result.evaluation_time_ms,
                "gateway_time_ms": elapsed_ms,
                "rate_limit": eval_result.rate_limit,
            }
        )
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    async def get_rate_limit_status(
        self,
        actor_id: str,
        interface: InterfaceType,
    ) -> Dict[str, Any]:
        """Get current rate limit status for an actor."""
        limit = self._trust_mapper.get_rate_limit(interface)
        usage = await self._rate_limiter.get_usage(actor_id, interface)
        
        return {
            "interface": interface.value,
            "limit": limit,
            "used": usage,
            "remaining": max(0, limit - usage),
            "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
        }
    
    async def reset_rate_limit(
        self,
        actor_id: str,
        interface: Optional[InterfaceType] = None,
    ) -> None:
        """Reset rate limit for an actor (admin function)."""
        await self._rate_limiter.reset(actor_id, interface)
    
    async def get_audit_logs(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get gateway audit logs."""
        return await self._audit_logger.get_logs(since, limit)


# =============================================================================
# INTERFACE ADAPTERS
# =============================================================================

class TerminalAdapter:
    """Adapter for terminal interface."""
    
    def __init__(self, router: GatewayRouter):
        self._router = router
    
    async def execute(
        self,
        actor_id: str,
        command: str,
        role: str = "operator",
    ) -> GatewayResponse:
        """Execute a terminal command."""
        from core.gateway.base import create_terminal_request
        
        # Create request using the command
        request = create_terminal_request(
            actor_id=actor_id,
            command=command,
            role=role,
        )
        
        return await self._router.route(request)


class APIAdapter:
    """Adapter for API interface."""
    
    def __init__(self, router: GatewayRouter):
        self._router = router
    
    async def handle(
        self,
        actor_id: str,
        tool: str,
        action: str = "execute",
        params: Optional[Dict[str, Any]] = None,
        target: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> GatewayResponse:
        """Handle an API request."""
        from core.gateway.base import create_api_request
        
        request = create_api_request(
            actor_id=actor_id,
            tool=tool,
            action=action,
            params=params or {},
            target=target or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return await self._router.route(request, access_token)


class VoiceAdapter:
    """Adapter for voice interface."""
    
    def __init__(self, router: GatewayRouter):
        self._router = router
    
    async def handle(
        self,
        actor_id: str,
        text: str,
        confidence: float,
        wake_word_detected: bool = True,
        face_present: bool = False,
        access_token: Optional[str] = None,
        is_confirmation: bool = False,
        confirmation_token: Optional[str] = None,
    ) -> GatewayResponse:
        """Handle a voice command."""
        from core.gateway.base import create_voice_request
        
        request = create_voice_request(
            actor_id=actor_id,
            text=text,
            confidence=confidence,
            wake_word_detected=wake_word_detected,
            face_present=face_present,
        )
        
        # Handle confirmation flow
        if is_confirmation and confirmation_token:
            # Create confirmation request
            request = GatewayRequest(
                interface=InterfaceType.VOICE,
                actor_id=actor_id,
                text=text,
                is_confirmation=True,
                confirmation_token=confirmation_token,
                context=RequestContext(
                    confidence=confidence,
                    wake_word_detected=wake_word_detected,
                    face_present=face_present,
                )
            )
        
        return await self._router.route(request, access_token)


# =============================================================================
# SINGLETON
# =============================================================================

_gateway_router: Optional[GatewayRouter] = None


def get_gateway_router() -> GatewayRouter:
    """Get the global gateway router instance."""
    global _gateway_router
    if _gateway_router is None:
        raise RuntimeError(
            "Gateway router not initialized. Call initialize_gateway() first."
        )
    return _gateway_router


def initialize_gateway(
    policy_engine: PolicyEngine,
    session_manager: Optional[SessionManager] = None,
    trust_mapper: Optional[TrustMapper] = None,
) -> GatewayRouter:
    """Initialize the global gateway router."""
    global _gateway_router
    _gateway_router = GatewayRouter(
        policy_engine=policy_engine,
        session_manager=session_manager,
        trust_mapper=trust_mapper,
    )
    return _gateway_router


def set_gateway_router(router: GatewayRouter) -> None:
    """Set the global gateway router (for testing)."""
    global _gateway_router
    _gateway_router = router
