"""
AKSHAY AI CORE — Gateway Base Models

Unified request/response models for all interfaces.

PRINCIPLE: Every interface (Terminal, API, Voice, UI) converts
its input into a GatewayRequest. This ensures:
- Same policy evaluation path
- Same audit logging
- Same rate limiting
- Same permission checks

NO INTERFACE GETS SPECIAL TREATMENT.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# =============================================================================
# ENUMS
# =============================================================================

class InterfaceType(str, Enum):
    """Source interface types."""
    TERMINAL = "terminal"
    API = "api"
    WEBSOCKET = "websocket"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    VOICE = "voice"
    AUTOMATION = "automation"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class GatewayStatus(str, Enum):
    """Gateway response status codes."""
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    REQUIRES_MFA = "REQUIRES_MFA"
    REQUIRES_ELEVATION = "REQUIRES_ELEVATION"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SAFE_MODE = "SAFE_MODE"


class RequestPriority(str, Enum):
    """Request priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class ConfidenceLevel(str, Enum):
    """Confidence levels for input processing (especially voice)."""
    HIGH = "high"      # > 0.9 confidence
    MEDIUM = "medium"  # 0.7 - 0.9
    LOW = "low"        # 0.5 - 0.7
    VERY_LOW = "very_low"  # < 0.5


# =============================================================================
# REQUEST CONTEXT
# =============================================================================

class RequestContext(BaseModel):
    """
    Context information for a gateway request.
    
    Includes environmental factors, device info, and trust indicators.
    """
    
    model_config = ConfigDict(extra="allow", frozen=True)
    
    # Network context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_fingerprint: Optional[str] = None
    
    # Authentication context
    session_id: Optional[str] = None
    mfa_verified: bool = False
    mfa_timestamp: Optional[datetime] = None
    auth_timestamp: Optional[datetime] = None
    
    # Input context (especially for voice)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    raw_input: Optional[str] = None
    processed_input: Optional[str] = None
    
    # Environmental context
    location: Optional[str] = None
    is_public_network: bool = False
    
    # Voice-specific
    wake_word_detected: bool = False
    voice_verified: bool = False
    face_present: bool = False
    
    # Correlation
    correlation_id: Optional[str] = None
    parent_request_id: Optional[str] = None
    
    @field_validator("confidence_level", mode="before")
    @classmethod
    def compute_confidence_level(cls, v, info):
        """Compute confidence level from confidence score."""
        if v is not None:
            return v
        
        confidence = info.data.get("confidence", 1.0)
        if confidence > 0.9:
            return ConfidenceLevel.HIGH
        elif confidence > 0.7:
            return ConfidenceLevel.MEDIUM
        elif confidence > 0.5:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


# =============================================================================
# GATEWAY REQUEST
# =============================================================================

class GatewayRequest(BaseModel):
    """
    Unified request model for all gateway interfaces.
    
    Every interface MUST convert its input into this format.
    This ensures:
    - Consistent policy evaluation
    - Uniform audit logging
    - Standard rate limiting
    - Same permission checks across all interfaces
    """
    
    model_config = ConfigDict(extra="forbid")
    
    # Request identification
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Request timestamp",
    )
    
    # Source interface
    interface: InterfaceType = Field(
        ...,
        description="Source interface type",
    )
    
    # Actor identification
    actor_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Unique identifier for the actor (user/system)",
    )
    role: str = Field(
        default="user",
        max_length=64,
        description="Actor's role",
    )
    
    # Trust zone (determined by trust_map)
    trust_zone: str = Field(
        default="USER",
        pattern=r'^[A-Z][A-Z0-9_]*$',
        description="Trust zone for this request",
    )
    
    # Input (mutually exclusive: text OR tool+action)
    text: Optional[str] = Field(
        default=None,
        max_length=10000,
        description="Natural language input (for chat/voice)",
    )
    tool: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Tool to invoke (for direct commands)",
    )
    action: Optional[str] = Field(
        default="execute",
        max_length=256,
        description="Specific action on the tool",
    )
    
    # Target resource
    target: Dict[str, Any] = Field(
        default_factory=dict,
        description="Target resource details (domain, device_id, namespace, etc.)",
    )
    
    # Parameters
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for the action",
    )
    
    # Context
    context: RequestContext = Field(
        default_factory=RequestContext,
        description="Request context (network, auth, environment)",
    )
    
    # Priority
    priority: RequestPriority = Field(
        default=RequestPriority.NORMAL,
        description="Request priority",
    )
    
    # Flags
    requires_response: bool = Field(
        default=True,
        description="Whether the request requires a response",
    )
    is_confirmation: bool = Field(
        default=False,
        description="Whether this is a confirmation of a previous request",
    )
    confirmation_token: Optional[str] = Field(
        default=None,
        description="Token for confirmation flow",
    )
    
    @model_validator(mode="after")
    def validate_input(self) -> "GatewayRequest":
        """Validate that either text or tool is provided."""
        if self.text is None and self.tool is None:
            raise ValueError("Either 'text' or 'tool' must be provided")
        return self
    
    def get_fingerprint(self) -> str:
        """Generate request fingerprint for deduplication."""
        content = f"{self.actor_id}:{self.tool}:{self.action}:{self.text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "interface": self.interface.value,
            "actor_id": self.actor_id,
            "role": self.role,
            "trust_zone": self.trust_zone,
            "tool": self.tool,
            "action": self.action,
            "text": self.text[:100] if self.text else None,  # Truncate
            "priority": self.priority.value,
            "context": {
                "ip": self.context.ip_address,
                "mfa": self.context.mfa_verified,
                "confidence": self.context.confidence,
            },
        }


# =============================================================================
# GATEWAY RESPONSE
# =============================================================================

class GatewayResponse(BaseModel):
    """
    Unified response model for all gateway interfaces.
    
    Every interface receives responses in this format.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    # Response identification
    request_id: str = Field(
        ...,
        description="Original request ID",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response timestamp",
    )
    
    # Status
    status: GatewayStatus = Field(
        ...,
        description="Response status",
    )
    
    # Policy decision info
    decision: Optional[str] = Field(
        default=None,
        description="Policy decision (ALLOW/DENY/etc.)",
    )
    rule_id: Optional[str] = Field(
        default=None,
        description="Matched rule ID",
    )
    reason_code: Optional[str] = Field(
        default=None,
        description="Machine-readable reason code",
    )
    
    # Human-readable message
    message: str = Field(
        default="",
        max_length=2048,
        description="Human-readable response message",
    )
    
    # Response data
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Response payload",
    )
    
    # For interactive flows
    requires_confirmation: bool = Field(
        default=False,
        description="Whether confirmation is required",
    )
    confirmation_prompt: Optional[str] = Field(
        default=None,
        description="Prompt for confirmation",
    )
    confirmation_token: Optional[str] = Field(
        default=None,
        description="Token for confirmation flow",
    )
    confirmation_timeout_seconds: int = Field(
        default=60,
        description="Timeout for confirmation",
    )
    
    requires_mfa: bool = Field(
        default=False,
        description="Whether MFA is required",
    )
    mfa_challenge: Optional[str] = Field(
        default=None,
        description="MFA challenge details",
    )
    
    # Rate limiting info
    rate_limit_remaining: Optional[int] = Field(
        default=None,
        description="Remaining requests in window",
    )
    rate_limit_reset: Optional[datetime] = Field(
        default=None,
        description="When rate limit resets",
    )
    retry_after_seconds: Optional[int] = Field(
        default=None,
        description="Seconds to wait before retry",
    )
    
    # Error details
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code",
    )
    error_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error context",
    )
    
    # Metadata
    processing_time_ms: float = Field(
        default=0.0,
        description="Processing time in milliseconds",
    )
    safe_mode_active: bool = Field(
        default=False,
        description="Whether safe mode is active",
    )
    
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.status == GatewayStatus.SUCCESS
    
    def is_denied(self) -> bool:
        """Check if response indicates denial."""
        return self.status in {
            GatewayStatus.DENIED,
            GatewayStatus.FORBIDDEN,
            GatewayStatus.UNAUTHORIZED,
        }
    
    def needs_interaction(self) -> bool:
        """Check if response requires user interaction."""
        return self.requires_confirmation or self.requires_mfa
    
    @classmethod
    def success(
        cls,
        request_id: str,
        message: str = "Success",
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> "GatewayResponse":
        """Create a success response."""
        return cls(
            request_id=request_id,
            status=GatewayStatus.SUCCESS,
            decision="ALLOW",
            message=message,
            data=data,
            **kwargs,
        )
    
    @classmethod
    def denied(
        cls,
        request_id: str,
        reason_code: str,
        message: str,
        rule_id: Optional[str] = None,
        **kwargs,
    ) -> "GatewayResponse":
        """Create a denied response."""
        return cls(
            request_id=request_id,
            status=GatewayStatus.DENIED,
            decision="DENY",
            reason_code=reason_code,
            message=message,
            rule_id=rule_id,
            **kwargs,
        )
    
    @classmethod
    def rate_limited(
        cls,
        request_id: str,
        retry_after: int,
        remaining: int = 0,
        **kwargs,
    ) -> "GatewayResponse":
        """Create a rate-limited response."""
        return cls(
            request_id=request_id,
            status=GatewayStatus.RATE_LIMITED,
            decision="RATE_LIMITED",
            reason_code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            rate_limit_remaining=remaining,
            retry_after_seconds=retry_after,
            **kwargs,
        )
    
    @classmethod
    def requires_confirm(
        cls,
        request_id: str,
        prompt: str,
        token: str,
        timeout: int = 60,
        **kwargs,
    ) -> "GatewayResponse":
        """Create a confirmation-required response."""
        return cls(
            request_id=request_id,
            status=GatewayStatus.REQUIRES_CONFIRMATION,
            decision="REQUIRE_CONFIRMATION",
            message=prompt,
            requires_confirmation=True,
            confirmation_prompt=prompt,
            confirmation_token=token,
            confirmation_timeout_seconds=timeout,
            **kwargs,
        )
    
    @classmethod
    def requires_mfa_response(
        cls,
        request_id: str,
        challenge: str,
        **kwargs,
    ) -> "GatewayResponse":
        """Create an MFA-required response."""
        return cls(
            request_id=request_id,
            status=GatewayStatus.REQUIRES_MFA,
            decision="REQUIRE_MFA",
            message="Multi-factor authentication required",
            requires_mfa=True,
            mfa_challenge=challenge,
            **kwargs,
        )
    
    @classmethod
    def error(
        cls,
        request_id: str,
        status: GatewayStatus,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> "GatewayResponse":
        """Create an error response."""
        return cls(
            request_id=request_id,
            status=status,
            error_code=error_code,
            message=message,
            error_details=details,
            **kwargs,
        )


# =============================================================================
# STREAMING RESPONSE
# =============================================================================

@dataclass
class StreamChunk:
    """A chunk in a streaming response."""
    
    request_id: str
    sequence: int
    content: str
    is_final: bool = False
    chunk_type: str = "text"  # text, audio, status
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CONFIRMATION FLOW
# =============================================================================

@dataclass
class ConfirmationRequest:
    """
    Pending confirmation request.
    
    Stores state for confirmation workflows.
    """
    
    token: str
    original_request: GatewayRequest
    prompt: str
    created_at: datetime
    expires_at: datetime
    confirmation_type: str = "destructive"  # destructive, sensitive, expensive
    
    # Voice-specific
    confirmation_phrase: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if confirmation has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "token": self.token,
            "prompt": self.prompt,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "confirmation_type": self.confirmation_type,
            "confirmation_phrase": self.confirmation_phrase,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_gateway_request(
    interface: InterfaceType,
    actor_id: str,
    tool: Optional[str] = None,
    action: str = "execute",
    text: Optional[str] = None,
    role: str = "user",
    trust_zone: str = "USER",
    target: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    context: Optional[RequestContext] = None,
    **kwargs,
) -> GatewayRequest:
    """Create a gateway request with defaults."""
    return GatewayRequest(
        interface=interface,
        actor_id=actor_id,
        role=role,
        trust_zone=trust_zone,
        tool=tool,
        action=action,
        text=text,
        target=target or {},
        params=params or {},
        context=context or RequestContext(),
        **kwargs,
    )


def create_terminal_request(
    actor_id: str,
    command: str,
    role: str = "user",
    **kwargs,
) -> GatewayRequest:
    """Create a request from terminal input."""
    # Parse command to extract tool/action or treat as text
    parts = command.strip().split(maxsplit=2)
    
    if len(parts) >= 2 and "." in parts[0]:
        # Looks like tool.action format
        tool_action = parts[0].split(".", 1)
        return create_gateway_request(
            interface=InterfaceType.TERMINAL,
            actor_id=actor_id,
            tool=tool_action[0] if len(tool_action) > 0 else parts[0],
            action=tool_action[1] if len(tool_action) > 1 else "execute",
            params={"args": parts[1:]} if len(parts) > 1 else {},
            role=role,
            trust_zone="SYSTEM",  # Terminal gets SYSTEM zone
            **kwargs,
        )
    else:
        # Treat as natural language
        return create_gateway_request(
            interface=InterfaceType.TERMINAL,
            actor_id=actor_id,
            text=command,
            role=role,
            trust_zone="SYSTEM",
            **kwargs,
        )


def create_api_request(
    actor_id: str,
    tool: str,
    action: str = "execute",
    params: Optional[Dict[str, Any]] = None,
    target: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs,
) -> GatewayRequest:
    """Create a request from API input."""
    return create_gateway_request(
        interface=InterfaceType.API,
        actor_id=actor_id,
        tool=tool,
        action=action,
        params=params or {},
        target=target or {},
        trust_zone="USER",
        context=RequestContext(
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        ),
        **kwargs,
    )


def create_voice_request(
    actor_id: str,
    text: str,
    confidence: float = 1.0,
    wake_word_detected: bool = True,
    face_present: bool = False,
    **kwargs,
) -> GatewayRequest:
    """Create a request from voice input."""
    # Determine confidence level
    if confidence > 0.9:
        conf_level = ConfidenceLevel.HIGH
    elif confidence > 0.7:
        conf_level = ConfidenceLevel.MEDIUM
    elif confidence > 0.5:
        conf_level = ConfidenceLevel.LOW
    else:
        conf_level = ConfidenceLevel.VERY_LOW
    
    return create_gateway_request(
        interface=InterfaceType.VOICE,
        actor_id=actor_id,
        text=text,
        role="user",
        trust_zone="USER",  # Voice always USER zone
        context=RequestContext(
            confidence=confidence,
            confidence_level=conf_level,
            raw_input=text,
            wake_word_detected=wake_word_detected,
            face_present=face_present,
        ),
        **kwargs,
    )
