"""
AKSHAY AI CORE — Trust Zone Mapping

Maps interfaces to trust zones with security constraints.

TRUST MODEL:
- Each interface has a default trust zone
- Trust can be elevated with MFA
- Trust can be downgraded based on confidence/context
- Voice ALWAYS has reduced trust for destructive actions

TRUST ZONES (highest to lowest):
- SYSTEM: Terminal, Internal automation
- OPERATOR: Elevated sessions, Admin API
- USER: Standard API, UI, Mobile
- GUEST: Unauthenticated, Low-confidence voice

NO INTERFACE CAN BYPASS TRUST ZONE ASSIGNMENT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set

from core.gateway.base import (
    InterfaceType,
    ConfidenceLevel,
    RequestContext,
    GatewayRequest,
)


# =============================================================================
# TRUST ZONES
# =============================================================================

class TrustZone(str, Enum):
    """
    Trust zones define the security context for operations.
    
    Higher trust = more permissions, lower scrutiny.
    Lower trust = fewer permissions, more scrutiny.
    """
    
    # Highest trust - local terminal, internal system calls
    SYSTEM = "SYSTEM"
    
    # Elevated trust - admin with MFA, operator console
    OPERATOR = "OPERATOR"
    
    # Standard trust - authenticated users via API/UI
    USER = "USER"
    
    # Lowest trust - guests, unverified, low-confidence voice
    GUEST = "GUEST"


# Trust level hierarchy (higher number = more trust)
TRUST_LEVELS: Dict[TrustZone, int] = {
    TrustZone.SYSTEM: 100,
    TrustZone.OPERATOR: 75,
    TrustZone.USER: 50,
    TrustZone.GUEST: 25,
}


# =============================================================================
# INTERFACE CONSTRAINTS
# =============================================================================

@dataclass(frozen=True)
class InterfaceConstraints:
    """
    Security constraints for an interface type.
    
    Defines what an interface can and cannot do.
    """
    
    # Default trust zone
    default_zone: TrustZone
    
    # Maximum trust zone (even with MFA)
    max_zone: TrustZone
    
    # Rate limiting tier
    rate_limit_tier: str  # "strict", "medium", "relaxed"
    
    # Requests per minute (base limit)
    requests_per_minute: int
    
    # Whether MFA can elevate trust
    can_elevate: bool
    
    # Whether confirmation is always required for destructive actions
    always_confirm_destructive: bool
    
    # Allowed actions (empty = all allowed, subject to policy)
    allowed_actions: FrozenSet[str] = field(default_factory=frozenset)
    
    # Blocked actions (always blocked regardless of policy)
    blocked_actions: FrozenSet[str] = field(default_factory=frozenset)
    
    # Requires face presence for certain actions
    requires_face_for_sensitive: bool = False


# =============================================================================
# INTERFACE → CONSTRAINTS MAPPING
# =============================================================================

INTERFACE_CONSTRAINTS: Dict[InterfaceType, InterfaceConstraints] = {
    # Terminal: Highest trust, relaxed limits
    InterfaceType.TERMINAL: InterfaceConstraints(
        default_zone=TrustZone.SYSTEM,
        max_zone=TrustZone.SYSTEM,
        rate_limit_tier="relaxed",
        requests_per_minute=1000,
        can_elevate=False,  # Already at max
        always_confirm_destructive=False,
    ),
    
    # API: Standard trust, medium limits
    InterfaceType.API: InterfaceConstraints(
        default_zone=TrustZone.USER,
        max_zone=TrustZone.OPERATOR,
        rate_limit_tier="medium",
        requests_per_minute=200,
        can_elevate=True,
        always_confirm_destructive=False,
    ),
    
    # WebSocket: Same as API
    InterfaceType.WEBSOCKET: InterfaceConstraints(
        default_zone=TrustZone.USER,
        max_zone=TrustZone.OPERATOR,
        rate_limit_tier="medium",
        requests_per_minute=300,  # Slightly higher for real-time
        can_elevate=True,
        always_confirm_destructive=False,
    ),
    
    # Mobile: Standard trust, medium limits
    InterfaceType.MOBILE: InterfaceConstraints(
        default_zone=TrustZone.USER,
        max_zone=TrustZone.USER,  # Cannot elevate to OPERATOR
        rate_limit_tier="medium",
        requests_per_minute=150,
        can_elevate=False,
        always_confirm_destructive=True,  # Always confirm on mobile
    ),
    
    # Desktop: Standard trust, can elevate
    InterfaceType.DESKTOP: InterfaceConstraints(
        default_zone=TrustZone.USER,
        max_zone=TrustZone.OPERATOR,
        rate_limit_tier="medium",
        requests_per_minute=200,
        can_elevate=True,
        always_confirm_destructive=False,
    ),
    
    # Voice: Lower trust, strict limits, ALWAYS requires confirmation
    InterfaceType.VOICE: InterfaceConstraints(
        default_zone=TrustZone.USER,
        max_zone=TrustZone.USER,  # Voice cannot elevate
        rate_limit_tier="strict",
        requests_per_minute=30,  # Very limited
        can_elevate=False,
        always_confirm_destructive=True,  # ALWAYS
        requires_face_for_sensitive=True,
        # Blocked actions for voice
        blocked_actions=frozenset({
            "system.shutdown",
            "system.reboot",
            "policy.delete",
            "user.delete",
            "data.wipe",
        }),
    ),
    
    # Automation: High trust, relaxed limits
    InterfaceType.AUTOMATION: InterfaceConstraints(
        default_zone=TrustZone.SYSTEM,
        max_zone=TrustZone.SYSTEM,
        rate_limit_tier="relaxed",
        requests_per_minute=500,
        can_elevate=False,
        always_confirm_destructive=False,  # Automations pre-approved
    ),
    
    # Internal: Highest trust, no limits
    InterfaceType.INTERNAL: InterfaceConstraints(
        default_zone=TrustZone.SYSTEM,
        max_zone=TrustZone.SYSTEM,
        rate_limit_tier="relaxed",
        requests_per_minute=10000,
        can_elevate=False,
        always_confirm_destructive=False,
    ),
    
    # Unknown: Lowest trust, strict limits
    InterfaceType.UNKNOWN: InterfaceConstraints(
        default_zone=TrustZone.GUEST,
        max_zone=TrustZone.GUEST,
        rate_limit_tier="strict",
        requests_per_minute=10,
        can_elevate=False,
        always_confirm_destructive=True,
    ),
}


# =============================================================================
# VOICE-SPECIFIC CONSTRAINTS
# =============================================================================

@dataclass(frozen=True)
class VoiceConstraints:
    """
    Additional constraints specific to voice interface.
    
    Voice is treated with extra caution due to:
    - Ambient noise/errors in STT
    - Possibility of replay attacks
    - Social engineering risks
    """
    
    # Minimum confidence for execution
    min_confidence: float = 0.7
    
    # Minimum confidence for destructive actions
    min_confidence_destructive: float = 0.9
    
    # Wake word required
    require_wake_word: bool = True
    
    # Face presence required for sensitive actions
    require_face_for_sensitive: bool = True
    
    # Actions requiring verbal confirmation phrase
    require_confirmation_phrase: FrozenSet[str] = field(
        default_factory=lambda: frozenset({
            "iot.device_control",
            "file.delete",
            "memory.delete",
            "policy.update",
            "automation.create",
            "system.config",
        })
    )
    
    # Actions always blocked via voice
    always_blocked: FrozenSet[str] = field(
        default_factory=lambda: frozenset({
            "system.shutdown",
            "system.reboot",
            "policy.delete",
            "user.delete",
            "data.wipe",
            "vault.decrypt",
        })
    )
    
    # Confirmation phrases for specific actions
    confirmation_phrases: Dict[str, str] = field(
        default_factory=lambda: {
            "iot.device_control": "Yes, do it",
            "file.delete": "Delete confirmed",
            "memory.delete": "Forget this",
            "default": "Yes, confirm",
        }
    )
    
    # Public network restrictions
    block_on_public_network: FrozenSet[str] = field(
        default_factory=lambda: frozenset({
            "iot.device_control",
            "file.write",
            "memory.write",
            "vault.access",
            "policy.inspect",
        })
    )


# Global voice constraints instance
VOICE_CONSTRAINTS = VoiceConstraints()


# =============================================================================
# TRUST MAPPER
# =============================================================================

class TrustMapper:
    """
    Maps gateway requests to trust zones.
    
    Considers:
    - Interface type
    - Authentication state
    - MFA status
    - Confidence level (for voice)
    - Environmental factors
    """
    
    def __init__(self):
        self._constraints = INTERFACE_CONSTRAINTS
        self._voice_constraints = VOICE_CONSTRAINTS
    
    def get_trust_zone(
        self,
        request: GatewayRequest,
        is_authenticated: bool = True,
        mfa_verified: bool = False,
        session_elevated: bool = False,
    ) -> TrustZone:
        """
        Determine the trust zone for a request.
        
        Args:
            request: The gateway request
            is_authenticated: Whether user is authenticated
            mfa_verified: Whether MFA was verified
            session_elevated: Whether session has been elevated
            
        Returns:
            Appropriate trust zone
        """
        constraints = self._constraints.get(
            request.interface,
            INTERFACE_CONSTRAINTS[InterfaceType.UNKNOWN]
        )
        
        # Start with default zone
        zone = constraints.default_zone
        
        # Downgrade for unauthenticated
        if not is_authenticated:
            return TrustZone.GUEST
        
        # Handle voice-specific downgrades
        if request.interface == InterfaceType.VOICE:
            zone = self._apply_voice_downgrades(request, zone)
        
        # Potential elevation with MFA
        if mfa_verified and constraints.can_elevate and session_elevated:
            if TRUST_LEVELS[constraints.max_zone] > TRUST_LEVELS[zone]:
                zone = constraints.max_zone
        
        return zone
    
    def _apply_voice_downgrades(
        self,
        request: GatewayRequest,
        zone: TrustZone,
    ) -> TrustZone:
        """Apply voice-specific trust downgrades."""
        ctx = request.context
        
        # Downgrade for low confidence
        if ctx.confidence < self._voice_constraints.min_confidence:
            return TrustZone.GUEST
        
        # Downgrade for missing wake word
        if self._voice_constraints.require_wake_word and not ctx.wake_word_detected:
            return TrustZone.GUEST
        
        # Downgrade for public network
        if ctx.is_public_network:
            return TrustZone.GUEST
        
        return zone
    
    def get_constraints(self, interface: InterfaceType) -> InterfaceConstraints:
        """Get constraints for an interface type."""
        return self._constraints.get(
            interface,
            INTERFACE_CONSTRAINTS[InterfaceType.UNKNOWN]
        )
    
    def is_action_blocked(
        self,
        request: GatewayRequest,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an action is blocked for the interface.
        
        Returns:
            (is_blocked, reason)
        """
        constraints = self.get_constraints(request.interface)
        
        # Get tool.action string
        action = f"{request.tool}.{request.action}" if request.tool else None
        
        if not action:
            return (False, None)
        
        # Check interface blocked actions
        if action in constraints.blocked_actions:
            return (True, f"Action '{action}' is blocked for {request.interface.value}")
        
        # Voice-specific blocks
        if request.interface == InterfaceType.VOICE:
            return self._check_voice_blocks(request, action)
        
        return (False, None)
    
    def _check_voice_blocks(
        self,
        request: GatewayRequest,
        action: str,
    ) -> tuple[bool, Optional[str]]:
        """Check voice-specific action blocks."""
        vc = self._voice_constraints
        ctx = request.context
        
        # Always blocked via voice
        if action in vc.always_blocked:
            return (True, f"Action '{action}' cannot be performed via voice")
        
        # Check confidence for destructive actions
        if self.is_destructive_action(action):
            if ctx.confidence < vc.min_confidence_destructive:
                return (True, f"Confidence too low ({ctx.confidence}) for destructive action")
        
        # Public network restrictions
        if ctx.is_public_network and action in vc.block_on_public_network:
            return (True, f"Action '{action}' blocked on public network")
        
        # Sensitive actions require face
        if vc.require_face_for_sensitive and self.is_sensitive_action(action):
            if not ctx.face_present:
                return (True, f"Face presence required for '{action}'")
        
        return (False, None)
    
    def requires_confirmation(
        self,
        request: GatewayRequest,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an action requires confirmation.
        
        Returns:
            (requires_confirmation, confirmation_phrase)
        """
        constraints = self.get_constraints(request.interface)
        action = f"{request.tool}.{request.action}" if request.tool else None
        
        if not action:
            return (False, None)
        
        # Interface requires confirmation for all destructive
        if constraints.always_confirm_destructive:
            if self.is_destructive_action(action):
                phrase = None
                if request.interface == InterfaceType.VOICE:
                    phrase = self._get_confirmation_phrase(action)
                return (True, phrase)
        
        # Voice-specific confirmation requirements
        if request.interface == InterfaceType.VOICE:
            vc = self._voice_constraints
            if action in vc.require_confirmation_phrase:
                phrase = self._get_confirmation_phrase(action)
                return (True, phrase)
        
        return (False, None)
    
    def _get_confirmation_phrase(self, action: str) -> str:
        """Get the confirmation phrase for an action."""
        phrases = self._voice_constraints.confirmation_phrases
        return phrases.get(action, phrases.get("default", "Yes, confirm"))
    
    def requires_mfa(
        self,
        request: GatewayRequest,
        already_verified: bool = False,
    ) -> bool:
        """Check if MFA is required for an action."""
        if already_verified:
            return False
        
        action = f"{request.tool}.{request.action}" if request.tool else None
        if not action:
            return False
        
        # Voice ALWAYS requires MFA for sensitive actions
        if request.interface == InterfaceType.VOICE:
            if self.is_sensitive_action(action):
                return True
        
        # MFA-required actions
        mfa_required = {
            "iot.device_control",
            "file.vault",
            "policy.update",
            "policy.delete",
            "user.delete",
            "system.config",
            "vault.decrypt",
            "data.export",
        }
        
        return action in mfa_required
    
    @staticmethod
    def is_destructive_action(action: str) -> bool:
        """Check if an action is destructive."""
        destructive_patterns = {
            "delete", "remove", "wipe", "destroy", "reset",
            "shutdown", "reboot", "disable", "revoke",
        }
        return any(p in action.lower() for p in destructive_patterns)
    
    @staticmethod
    def is_sensitive_action(action: str) -> bool:
        """Check if an action is sensitive."""
        sensitive_patterns = {
            "iot", "device", "file", "memory", "policy",
            "vault", "secret", "key", "config", "user",
            "permission", "auth", "credential",
        }
        return any(p in action.lower() for p in sensitive_patterns)
    
    def get_rate_limit(self, interface: InterfaceType) -> int:
        """Get requests per minute for interface."""
        constraints = self.get_constraints(interface)
        return constraints.requests_per_minute
    
    def compare_trust(self, zone_a: TrustZone, zone_b: TrustZone) -> int:
        """
        Compare two trust zones.
        
        Returns:
            > 0 if zone_a is more trusted
            < 0 if zone_b is more trusted
            0 if equal
        """
        return TRUST_LEVELS[zone_a] - TRUST_LEVELS[zone_b]
    
    def is_trusted_enough(
        self,
        zone: TrustZone,
        required: TrustZone,
    ) -> bool:
        """Check if zone meets required trust level."""
        return TRUST_LEVELS[zone] >= TRUST_LEVELS[required]


# =============================================================================
# SINGLETON
# =============================================================================

# Global trust mapper instance
_trust_mapper: Optional[TrustMapper] = None


def get_trust_mapper() -> TrustMapper:
    """Get the global trust mapper instance."""
    global _trust_mapper
    if _trust_mapper is None:
        _trust_mapper = TrustMapper()
    return _trust_mapper


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def map_interface_to_zone(
    interface: InterfaceType,
    is_authenticated: bool = True,
    mfa_verified: bool = False,
) -> TrustZone:
    """Quick mapping of interface to trust zone."""
    constraints = INTERFACE_CONSTRAINTS.get(
        interface,
        INTERFACE_CONSTRAINTS[InterfaceType.UNKNOWN]
    )
    
    if not is_authenticated:
        return TrustZone.GUEST
    
    if mfa_verified and constraints.can_elevate:
        return constraints.max_zone
    
    return constraints.default_zone


def get_voice_confirmation_phrase(action: str) -> str:
    """Get voice confirmation phrase for an action."""
    return get_trust_mapper()._get_confirmation_phrase(action)
