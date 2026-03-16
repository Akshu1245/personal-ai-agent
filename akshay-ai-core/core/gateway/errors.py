"""
AKSHAY AI CORE — Gateway Errors

Exception hierarchy for gateway-level errors.

DESIGN:
- All gateway errors derive from GatewayError
- Each error carries structured context
- Errors map cleanly to GatewayResponse status codes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


# =============================================================================
# ERROR CODES
# =============================================================================

class GatewayErrorCode(str, Enum):
    """Gateway error codes."""
    
    # Authentication errors
    INVALID_TOKEN = "INVALID_TOKEN"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    REVOKED_TOKEN = "REVOKED_TOKEN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    UNAUTHORIZED = "UNAUTHORIZED"
    
    # Authorization errors
    FORBIDDEN = "FORBIDDEN"
    TRUST_VIOLATION = "TRUST_VIOLATION"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    
    # Rate limiting
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # Interface blocks
    INTERFACE_BLOCKED = "INTERFACE_BLOCKED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    VOICE_BLOCKED = "VOICE_BLOCKED"
    
    # Confirmation
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_FAILED = "CONFIRMATION_FAILED"
    CONFIRMATION_EXPIRED = "CONFIRMATION_EXPIRED"
    
    # MFA
    MFA_REQUIRED = "MFA_REQUIRED"
    MFA_FAILED = "MFA_FAILED"
    MFA_TIMEOUT = "MFA_TIMEOUT"
    
    # Request errors
    INVALID_REQUEST = "INVALID_REQUEST"
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FIELD = "INVALID_FIELD"
    
    # Policy errors
    POLICY_DENIED = "POLICY_DENIED"
    POLICY_ERROR = "POLICY_ERROR"
    SAFE_MODE_BLOCK = "SAFE_MODE_BLOCK"
    
    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


# =============================================================================
# ERROR CONTEXT
# =============================================================================

@dataclass(frozen=True)
class GatewayErrorContext:
    """Structured context for gateway errors."""
    
    # Request context
    request_id: Optional[str] = None
    interface: Optional[str] = None
    actor_id: Optional[str] = None
    
    # Action context
    tool: Optional[str] = None
    action: Optional[str] = None
    
    # Error details
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    
    # Rate limit context
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset_at: Optional[datetime] = None
    
    # Additional data
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.request_id:
            result["request_id"] = self.request_id
        if self.interface:
            result["interface"] = self.interface
        if self.actor_id:
            result["actor_id"] = self.actor_id
        if self.tool:
            result["tool"] = self.tool
        if self.action:
            result["action"] = self.action
        if self.field_name:
            result["field"] = self.field_name
        if self.limit is not None:
            result["rate_limit"] = {
                "limit": self.limit,
                "remaining": self.remaining,
                "reset_at": self.reset_at.isoformat() if self.reset_at else None,
            }
        if self.extra:
            result.update(self.extra)
        return result


# =============================================================================
# BASE EXCEPTION
# =============================================================================

class GatewayError(Exception):
    """Base exception for all gateway errors."""
    
    def __init__(
        self,
        message: str,
        code: GatewayErrorCode,
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or GatewayErrorContext()
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for response."""
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context.to_dict(),
        }


# =============================================================================
# AUTHENTICATION ERRORS
# =============================================================================

class AuthenticationError(GatewayError):
    """Authentication-related errors."""
    pass


class InvalidTokenError(AuthenticationError):
    """Token is invalid or malformed."""
    
    def __init__(
        self,
        message: str = "Invalid or malformed token",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.INVALID_TOKEN, context)


class ExpiredTokenError(AuthenticationError):
    """Token has expired."""
    
    def __init__(
        self,
        message: str = "Token has expired",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.EXPIRED_TOKEN, context)


class RevokedTokenError(AuthenticationError):
    """Token has been revoked."""
    
    def __init__(
        self,
        message: str = "Token has been revoked",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.REVOKED_TOKEN, context)


class SessionExpiredError(AuthenticationError):
    """Session has expired."""
    
    def __init__(
        self,
        message: str = "Session has expired",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.SESSION_EXPIRED, context)


class UnauthorizedError(AuthenticationError):
    """User is not authenticated."""
    
    def __init__(
        self,
        message: str = "Authentication required",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.UNAUTHORIZED, context)


# =============================================================================
# AUTHORIZATION ERRORS
# =============================================================================

class AuthorizationError(GatewayError):
    """Authorization-related errors."""
    pass


class ForbiddenError(AuthorizationError):
    """User is not allowed to perform this action."""
    
    def __init__(
        self,
        message: str = "Action forbidden",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.FORBIDDEN, context)


class TrustViolationError(AuthorizationError):
    """Trust zone violation."""
    
    def __init__(
        self,
        message: str = "Trust zone requirements not met",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.TRUST_VIOLATION, context)


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.INSUFFICIENT_PERMISSIONS, context)


# =============================================================================
# RATE LIMITING ERRORS
# =============================================================================

class RateLimitError(GatewayError):
    """Rate limiting errors."""
    pass


class RateLimitedError(RateLimitError):
    """Request rate limit exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.RATE_LIMITED, context)


class QuotaExceededError(RateLimitError):
    """Usage quota exceeded."""
    
    def __init__(
        self,
        message: str = "Quota exceeded",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.QUOTA_EXCEEDED, context)


# =============================================================================
# INTERFACE BLOCK ERRORS
# =============================================================================

class InterfaceBlockError(GatewayError):
    """Interface-level block errors."""
    pass


class ActionBlockedError(InterfaceBlockError):
    """Action is blocked for this interface."""
    
    def __init__(
        self,
        message: str = "Action blocked for this interface",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.ACTION_BLOCKED, context)


class VoiceBlockedError(InterfaceBlockError):
    """Action is blocked for voice interface."""
    
    def __init__(
        self,
        message: str = "Action cannot be performed via voice",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.VOICE_BLOCKED, context)


# =============================================================================
# CONFIRMATION ERRORS
# =============================================================================

class ConfirmationError(GatewayError):
    """Confirmation flow errors."""
    pass


class ConfirmationRequiredError(ConfirmationError):
    """Action requires confirmation."""
    
    def __init__(
        self,
        message: str = "Confirmation required",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.CONFIRMATION_REQUIRED, context)


class ConfirmationFailedError(ConfirmationError):
    """Confirmation validation failed."""
    
    def __init__(
        self,
        message: str = "Confirmation failed",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.CONFIRMATION_FAILED, context)


class ConfirmationExpiredError(ConfirmationError):
    """Confirmation token expired."""
    
    def __init__(
        self,
        message: str = "Confirmation token expired",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.CONFIRMATION_EXPIRED, context)


# =============================================================================
# MFA ERRORS
# =============================================================================

class MFAError(GatewayError):
    """MFA-related errors."""
    pass


class MFARequiredError(MFAError):
    """MFA verification required."""
    
    def __init__(
        self,
        message: str = "MFA verification required",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.MFA_REQUIRED, context)


class MFAFailedError(MFAError):
    """MFA verification failed."""
    
    def __init__(
        self,
        message: str = "MFA verification failed",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.MFA_FAILED, context)


class MFATimeoutError(MFAError):
    """MFA verification timed out."""
    
    def __init__(
        self,
        message: str = "MFA verification timed out",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.MFA_TIMEOUT, context)


# =============================================================================
# REQUEST ERRORS
# =============================================================================

class RequestError(GatewayError):
    """Request validation errors."""
    pass


class InvalidRequestError(RequestError):
    """Request is invalid."""
    
    def __init__(
        self,
        message: str = "Invalid request",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.INVALID_REQUEST, context)


class MalformedRequestError(RequestError):
    """Request is malformed."""
    
    def __init__(
        self,
        message: str = "Malformed request",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.MALFORMED_REQUEST, context)


class MissingFieldError(RequestError):
    """Required field is missing."""
    
    def __init__(
        self,
        field_name: str,
        message: Optional[str] = None,
        context: Optional[GatewayErrorContext] = None,
    ):
        msg = message or f"Required field '{field_name}' is missing"
        ctx = context or GatewayErrorContext(field_name=field_name)
        super().__init__(msg, GatewayErrorCode.MISSING_FIELD, ctx)


class InvalidFieldError(RequestError):
    """Field value is invalid."""
    
    def __init__(
        self,
        field_name: str,
        message: Optional[str] = None,
        context: Optional[GatewayErrorContext] = None,
    ):
        msg = message or f"Field '{field_name}' has invalid value"
        ctx = context or GatewayErrorContext(field_name=field_name)
        super().__init__(msg, GatewayErrorCode.INVALID_FIELD, ctx)


# =============================================================================
# POLICY ERRORS
# =============================================================================

class PolicyDeniedError(GatewayError):
    """Policy denied the request."""
    
    def __init__(
        self,
        message: str = "Request denied by policy",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.POLICY_DENIED, context)


class SafeModeBlockError(GatewayError):
    """Request blocked due to safe mode."""
    
    def __init__(
        self,
        message: str = "Request blocked: system is in safe mode",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.SAFE_MODE_BLOCK, context)


# =============================================================================
# SYSTEM ERRORS
# =============================================================================

class InternalError(GatewayError):
    """Internal server error."""
    
    def __init__(
        self,
        message: str = "Internal error occurred",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.INTERNAL_ERROR, context)


class ServiceUnavailableError(GatewayError):
    """Service is unavailable."""
    
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.SERVICE_UNAVAILABLE, context)


class TimeoutError(GatewayError):
    """Request timed out."""
    
    def __init__(
        self,
        message: str = "Request timed out",
        context: Optional[GatewayErrorContext] = None,
    ):
        super().__init__(message, GatewayErrorCode.TIMEOUT, context)
