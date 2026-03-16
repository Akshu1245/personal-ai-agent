"""
AKSHAY AI CORE — Gateway Module

The unified entry point for ALL system interfaces.

ARCHITECTURE:
- Terminal, API, Voice, UI → GatewayRouter → PolicyEngine → Response
- Same security pipeline for everyone
- No interface gets special treatment

COMPONENTS:
- base: Request/Response models (GatewayRequest, GatewayResponse)
- trust_map: Interface → TrustZone mapping with constraints
- session: JWT sessions, MFA, device binding, revocation
- router: Unified routing to policy engine
- errors: Gateway-specific exception hierarchy

USAGE:

    from core.gateway import (
        GatewayRouter,
        GatewayRequest,
        GatewayResponse,
        InterfaceType,
        TrustZone,
        initialize_gateway,
    )
    
    # Initialize once at startup
    router = initialize_gateway(policy_engine)
    
    # Route requests
    response = await router.route(request, access_token)

SECURITY GUARANTEES:
- All requests go through the same policy evaluation
- All requests are rate-limited per interface
- All requests are audit-logged
- Voice requests have extra confirmation requirements
- Sessions are cryptographically signed with JWT
- MFA state is tracked per-session
- Device binding prevents token theft
"""

# =============================================================================
# BASE MODELS
# =============================================================================

from core.gateway.base import (
    # Enums
    InterfaceType,
    GatewayStatus,
    RequestPriority,
    ConfidenceLevel,
    # Models
    RequestContext,
    GatewayRequest,
    GatewayResponse,
    StreamChunk,
    ConfirmationRequest,
    # Helpers
    create_gateway_request,
    create_terminal_request,
    create_api_request,
    create_voice_request,
)

# =============================================================================
# TRUST MAPPING
# =============================================================================

from core.gateway.trust_map import (
    # Enums
    TrustZone,
    # Constants
    TRUST_LEVELS,
    INTERFACE_CONSTRAINTS,
    VOICE_CONSTRAINTS,
    # Classes
    InterfaceConstraints,
    VoiceConstraints,
    TrustMapper,
    # Functions
    get_trust_mapper,
    map_interface_to_zone,
    get_voice_confirmation_phrase,
)

# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

from core.gateway.session import (
    # Constants
    ACCESS_TOKEN_EXPIRY,
    REFRESH_TOKEN_EXPIRY,
    MFA_GRACE_PERIOD,
    ELEVATION_DURATION,
    MAX_SESSIONS_PER_USER,
    # Enums
    SessionState,
    MFAMethod,
    RevokeReason,
    # Classes
    SessionData,
    TokenPayload,
    SessionStore,
    InMemorySessionStore,
    SessionManager,
    # Functions
    compute_device_fingerprint,
    get_session_manager,
    set_session_manager,
)

# =============================================================================
# ROUTER
# =============================================================================

from core.gateway.router import (
    # Constants
    CONFIRMATION_TOKEN_EXPIRY_SECONDS,
    MFA_TIMEOUT_SECONDS,
    RATE_LIMIT_WINDOW_SECONDS,
    # Classes
    GatewayRateLimiter,
    PendingConfirmation,
    ConfirmationManager,
    GatewayAuditLogger,
    GatewayRouter,
    # Adapters
    TerminalAdapter,
    APIAdapter,
    VoiceAdapter,
    # Functions
    get_gateway_router,
    initialize_gateway,
    set_gateway_router,
)

# =============================================================================
# ERRORS
# =============================================================================

from core.gateway.errors import (
    # Base
    GatewayErrorCode,
    GatewayErrorContext,
    GatewayError,
    # Authentication
    AuthenticationError,
    InvalidTokenError,
    ExpiredTokenError,
    RevokedTokenError,
    SessionExpiredError,
    UnauthorizedError,
    # Authorization
    AuthorizationError,
    ForbiddenError,
    TrustViolationError,
    InsufficientPermissionsError,
    # Rate limiting
    RateLimitError,
    RateLimitedError,
    QuotaExceededError,
    # Interface blocks
    InterfaceBlockError,
    ActionBlockedError,
    VoiceBlockedError,
    # Confirmation
    ConfirmationError,
    ConfirmationRequiredError,
    ConfirmationFailedError,
    ConfirmationExpiredError,
    # MFA
    MFAError,
    MFARequiredError,
    MFAFailedError,
    MFATimeoutError,
    # Request
    RequestError,
    InvalidRequestError,
    MalformedRequestError,
    MissingFieldError,
    InvalidFieldError,
    # Policy
    PolicyDeniedError,
    SafeModeBlockError,
    # System
    InternalError,
    ServiceUnavailableError,
)

# =============================================================================
# MODULE INFO
# =============================================================================

__all__ = [
    # Base
    "InterfaceType",
    "GatewayStatus",
    "RequestPriority",
    "ConfidenceLevel",
    "RequestContext",
    "GatewayRequest",
    "GatewayResponse",
    "StreamChunk",
    "ConfirmationRequest",
    "create_gateway_request",
    "create_terminal_request",
    "create_api_request",
    "create_voice_request",
    # Trust
    "TrustZone",
    "TRUST_LEVELS",
    "INTERFACE_CONSTRAINTS",
    "VOICE_CONSTRAINTS",
    "InterfaceConstraints",
    "VoiceConstraints",
    "TrustMapper",
    "get_trust_mapper",
    "map_interface_to_zone",
    "get_voice_confirmation_phrase",
    # Session
    "ACCESS_TOKEN_EXPIRY",
    "REFRESH_TOKEN_EXPIRY",
    "MFA_GRACE_PERIOD",
    "ELEVATION_DURATION",
    "MAX_SESSIONS_PER_USER",
    "SessionState",
    "MFAMethod",
    "RevokeReason",
    "SessionData",
    "TokenPayload",
    "SessionStore",
    "InMemorySessionStore",
    "SessionManager",
    "compute_device_fingerprint",
    "get_session_manager",
    "set_session_manager",
    # Router
    "CONFIRMATION_TOKEN_EXPIRY_SECONDS",
    "MFA_TIMEOUT_SECONDS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "GatewayRateLimiter",
    "PendingConfirmation",
    "ConfirmationManager",
    "GatewayAuditLogger",
    "GatewayRouter",
    "TerminalAdapter",
    "APIAdapter",
    "VoiceAdapter",
    "get_gateway_router",
    "initialize_gateway",
    "set_gateway_router",
    # Errors
    "GatewayErrorCode",
    "GatewayErrorContext",
    "GatewayError",
    "AuthenticationError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "RevokedTokenError",
    "SessionExpiredError",
    "UnauthorizedError",
    "AuthorizationError",
    "ForbiddenError",
    "TrustViolationError",
    "InsufficientPermissionsError",
    "RateLimitError",
    "RateLimitedError",
    "QuotaExceededError",
    "InterfaceBlockError",
    "ActionBlockedError",
    "VoiceBlockedError",
    "ConfirmationError",
    "ConfirmationRequiredError",
    "ConfirmationFailedError",
    "ConfirmationExpiredError",
    "MFAError",
    "MFARequiredError",
    "MFAFailedError",
    "MFATimeoutError",
    "RequestError",
    "InvalidRequestError",
    "MalformedRequestError",
    "MissingFieldError",
    "InvalidFieldError",
    "PolicyDeniedError",
    "SafeModeBlockError",
    "InternalError",
    "ServiceUnavailableError",
]

__version__ = "1.0.0"
__author__ = "AKSHAY AI CORE"
