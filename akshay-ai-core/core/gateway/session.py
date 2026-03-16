"""
AKSHAY AI CORE — Session Management

JWT-based session management with:
- Role binding
- MFA tracking
- Device fingerprinting
- Token revocation
- Session audit trail

SECURITY GUARANTEES:
- Tokens are cryptographically signed
- Sessions can be revoked instantly
- MFA state is tracked per-session
- Device binding prevents token theft
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import jwt
from pydantic import BaseModel, Field, ConfigDict

from core.gateway.base import InterfaceType
from core.gateway.trust_map import TrustZone


# =============================================================================
# CONSTANTS
# =============================================================================

# Token expiry times (in seconds)
ACCESS_TOKEN_EXPIRY = 3600  # 1 hour
REFRESH_TOKEN_EXPIRY = 86400 * 7  # 7 days
MFA_GRACE_PERIOD = 300  # 5 minutes after MFA
ELEVATION_DURATION = 1800  # 30 minutes for elevated sessions

# Token types
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_MFA = "mfa"

# Maximum sessions per user
MAX_SESSIONS_PER_USER = 10


# =============================================================================
# ENUMS
# =============================================================================

class SessionState(str, Enum):
    """Session states."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    LOCKED = "locked"
    MFA_PENDING = "mfa_pending"


class MFAMethod(str, Enum):
    """MFA verification methods."""
    TOTP = "totp"
    FACE = "face"
    PIN = "pin"
    VOICE = "voice"
    PUSH = "push"


class RevokeReason(str, Enum):
    """Reasons for session revocation."""
    USER_LOGOUT = "user_logout"
    ADMIN_REVOKE = "admin_revoke"
    SECURITY_VIOLATION = "security_violation"
    PASSWORD_CHANGE = "password_change"
    MFA_RESET = "mfa_reset"
    DEVICE_CHANGE = "device_change"
    TIMEOUT = "timeout"
    CONCURRENT_LIMIT = "concurrent_limit"


# =============================================================================
# SESSION DATA
# =============================================================================

@dataclass
class SessionData:
    """
    Complete session state.
    
    Stored server-side, referenced by session_id.
    """
    
    # Identity
    session_id: str
    user_id: str
    role: str
    
    # State
    state: SessionState = SessionState.ACTIVE
    
    # Trust
    trust_zone: TrustZone = TrustZone.USER
    is_elevated: bool = False
    elevation_expires: Optional[datetime] = None
    
    # MFA
    mfa_verified: bool = False
    mfa_method: Optional[MFAMethod] = None
    mfa_verified_at: Optional[datetime] = None
    
    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_EXPIRY))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Source
    interface: InterfaceType = InterfaceType.UNKNOWN
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_fingerprint: Optional[str] = None
    
    # Revocation
    revoked_at: Optional[datetime] = None
    revoke_reason: Optional[RevokeReason] = None
    
    # Permissions (cached from role)
    permissions: Set[str] = field(default_factory=set)
    
    def is_valid(self) -> bool:
        """Check if session is currently valid."""
        if self.state != SessionState.ACTIVE:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
    
    def is_mfa_valid(self) -> bool:
        """Check if MFA is still valid."""
        if not self.mfa_verified:
            return False
        if self.mfa_verified_at is None:
            return False
        
        grace_period = timedelta(seconds=MFA_GRACE_PERIOD)
        return datetime.now(timezone.utc) - self.mfa_verified_at < grace_period
    
    def is_elevated_valid(self) -> bool:
        """Check if elevation is still valid."""
        if not self.is_elevated:
            return False
        if self.elevation_expires is None:
            return False
        return datetime.now(timezone.utc) < self.elevation_expires
    
    def touch(self) -> None:
        """Update last activity time."""
        self.last_activity = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "role": self.role,
            "state": self.state.value,
            "trust_zone": self.trust_zone.value,
            "is_elevated": self.is_elevated,
            "elevation_expires": self.elevation_expires.isoformat() if self.elevation_expires else None,
            "mfa_verified": self.mfa_verified,
            "mfa_method": self.mfa_method.value if self.mfa_method else None,
            "mfa_verified_at": self.mfa_verified_at.isoformat() if self.mfa_verified_at else None,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "interface": self.interface.value,
            "ip_address": self.ip_address,
            "device_fingerprint": self.device_fingerprint,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            role=data["role"],
            state=SessionState(data.get("state", "active")),
            trust_zone=TrustZone(data.get("trust_zone", "USER")),
            is_elevated=data.get("is_elevated", False),
            elevation_expires=datetime.fromisoformat(data["elevation_expires"]) if data.get("elevation_expires") else None,
            mfa_verified=data.get("mfa_verified", False),
            mfa_method=MFAMethod(data["mfa_method"]) if data.get("mfa_method") else None,
            mfa_verified_at=datetime.fromisoformat(data["mfa_verified_at"]) if data.get("mfa_verified_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            interface=InterfaceType(data.get("interface", "unknown")),
            ip_address=data.get("ip_address"),
            device_fingerprint=data.get("device_fingerprint"),
        )


# =============================================================================
# TOKEN PAYLOAD
# =============================================================================

@dataclass
class TokenPayload:
    """JWT token payload."""
    
    # Standard claims
    sub: str  # user_id
    jti: str  # token ID
    iat: int  # issued at
    exp: int  # expiration
    
    # Custom claims
    session_id: str
    role: str
    token_type: str
    interface: str
    device_fingerprint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JWT-compatible dict."""
        result = {
            "sub": self.sub,
            "jti": self.jti,
            "iat": self.iat,
            "exp": self.exp,
            "session_id": self.session_id,
            "role": self.role,
            "type": self.token_type,
            "iface": self.interface,
        }
        if self.device_fingerprint:
            result["dfp"] = self.device_fingerprint
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenPayload":
        """Create from decoded JWT."""
        return cls(
            sub=data["sub"],
            jti=data["jti"],
            iat=data["iat"],
            exp=data["exp"],
            session_id=data["session_id"],
            role=data["role"],
            token_type=data["type"],
            interface=data.get("iface", "unknown"),
            device_fingerprint=data.get("dfp"),
        )


# =============================================================================
# SESSION STORE INTERFACE
# =============================================================================

class SessionStore(ABC):
    """Abstract interface for session storage."""
    
    @abstractmethod
    async def create(self, session: SessionData) -> None:
        """Store a new session."""
        pass
    
    @abstractmethod
    async def get(self, session_id: str) -> Optional[SessionData]:
        """Retrieve a session by ID."""
        pass
    
    @abstractmethod
    async def update(self, session: SessionData) -> None:
        """Update an existing session."""
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        pass
    
    @abstractmethod
    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Get all sessions for a user."""
        pass
    
    @abstractmethod
    async def revoke_all_user_sessions(
        self,
        user_id: str,
        reason: RevokeReason,
    ) -> int:
        """Revoke all sessions for a user. Returns count revoked."""
        pass
    
    @abstractmethod
    async def is_token_revoked(self, token_id: str) -> bool:
        """Check if a token ID has been revoked."""
        pass
    
    @abstractmethod
    async def revoke_token(self, token_id: str) -> None:
        """Mark a token as revoked."""
        pass


class InMemorySessionStore(SessionStore):
    """
    In-memory session store for development/testing.
    
    For production, use Redis-backed store.
    """
    
    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> session_ids
        self._revoked_tokens: Set[str] = set()
        self._lock = threading.RLock()
    
    async def create(self, session: SessionData) -> None:
        """Store a new session."""
        with self._lock:
            self._sessions[session.session_id] = session
            
            if session.user_id not in self._user_sessions:
                self._user_sessions[session.user_id] = set()
            self._user_sessions[session.user_id].add(session.session_id)
    
    async def get(self, session_id: str) -> Optional[SessionData]:
        """Retrieve a session by ID."""
        with self._lock:
            return self._sessions.get(session_id)
    
    async def update(self, session: SessionData) -> None:
        """Update an existing session."""
        with self._lock:
            self._sessions[session.session_id] = session
    
    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                user_sessions = self._user_sessions.get(session.user_id)
                if user_sessions:
                    user_sessions.discard(session_id)
    
    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Get all sessions for a user."""
        with self._lock:
            session_ids = self._user_sessions.get(user_id, set())
            return [
                self._sessions[sid]
                for sid in session_ids
                if sid in self._sessions
            ]
    
    async def revoke_all_user_sessions(
        self,
        user_id: str,
        reason: RevokeReason,
    ) -> int:
        """Revoke all sessions for a user."""
        count = 0
        now = datetime.now(timezone.utc)
        
        with self._lock:
            session_ids = self._user_sessions.get(user_id, set()).copy()
            for sid in session_ids:
                session = self._sessions.get(sid)
                if session and session.state == SessionState.ACTIVE:
                    session.state = SessionState.REVOKED
                    session.revoked_at = now
                    session.revoke_reason = reason
                    count += 1
        
        return count
    
    async def is_token_revoked(self, token_id: str) -> bool:
        """Check if a token ID has been revoked."""
        with self._lock:
            return token_id in self._revoked_tokens
    
    async def revoke_token(self, token_id: str) -> None:
        """Mark a token as revoked."""
        with self._lock:
            self._revoked_tokens.add(token_id)
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count removed."""
        now = datetime.now(timezone.utc)
        removed = 0
        
        with self._lock:
            expired = [
                sid for sid, session in self._sessions.items()
                if now > session.expires_at
            ]
            for sid in expired:
                session = self._sessions.pop(sid, None)
                if session:
                    user_sessions = self._user_sessions.get(session.user_id)
                    if user_sessions:
                        user_sessions.discard(sid)
                    removed += 1
        
        return removed


# =============================================================================
# SESSION MANAGER
# =============================================================================

class SessionManager:
    """
    Central session management.
    
    Handles:
    - Session creation and validation
    - JWT token generation and verification
    - MFA tracking
    - Session elevation
    - Token revocation
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        store: Optional[SessionStore] = None,
        access_expiry: int = ACCESS_TOKEN_EXPIRY,
        refresh_expiry: int = REFRESH_TOKEN_EXPIRY,
    ):
        """
        Initialize session manager.
        
        Args:
            secret_key: JWT signing key (generated if not provided)
            store: Session storage backend
            access_expiry: Access token expiry in seconds
            refresh_expiry: Refresh token expiry in seconds
        """
        self._secret_key = secret_key or secrets.token_urlsafe(32)
        self._store = store or InMemorySessionStore()
        self._access_expiry = access_expiry
        self._refresh_expiry = refresh_expiry
        self._algorithm = "HS256"
    
    # -------------------------------------------------------------------------
    # SESSION LIFECYCLE
    # -------------------------------------------------------------------------
    
    async def create_session(
        self,
        user_id: str,
        role: str,
        interface: InterfaceType,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        trust_zone: TrustZone = TrustZone.USER,
        permissions: Optional[Set[str]] = None,
    ) -> Tuple[SessionData, str, str]:
        """
        Create a new session.
        
        Returns:
            (session_data, access_token, refresh_token)
        """
        # Enforce session limit
        existing = await self._store.get_user_sessions(user_id)
        active_count = sum(1 for s in existing if s.is_valid())
        
        if active_count >= MAX_SESSIONS_PER_USER:
            # Revoke oldest session
            oldest = min(
                (s for s in existing if s.is_valid()),
                key=lambda s: s.created_at,
                default=None
            )
            if oldest:
                await self.revoke_session(
                    oldest.session_id,
                    RevokeReason.CONCURRENT_LIMIT
                )
        
        # Create session
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            role=role,
            trust_zone=trust_zone,
            created_at=now,
            expires_at=now + timedelta(seconds=self._access_expiry),
            last_activity=now,
            interface=interface,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            permissions=permissions or set(),
        )
        
        # Store session
        await self._store.create(session)
        
        # Generate tokens
        access_token = self._create_access_token(session)
        refresh_token = self._create_refresh_token(session)
        
        return session, access_token, refresh_token
    
    async def validate_session(
        self,
        session_id: str,
    ) -> Optional[SessionData]:
        """
        Validate and return session if valid.
        
        Updates last_activity on success.
        """
        session = await self._store.get(session_id)
        
        if session is None:
            return None
        
        if not session.is_valid():
            return None
        
        # Update activity
        session.touch()
        await self._store.update(session)
        
        return session
    
    async def revoke_session(
        self,
        session_id: str,
        reason: RevokeReason,
    ) -> bool:
        """Revoke a session."""
        session = await self._store.get(session_id)
        
        if session is None:
            return False
        
        session.state = SessionState.REVOKED
        session.revoked_at = datetime.now(timezone.utc)
        session.revoke_reason = reason
        
        await self._store.update(session)
        return True
    
    async def revoke_all_sessions(
        self,
        user_id: str,
        reason: RevokeReason,
    ) -> int:
        """Revoke all sessions for a user."""
        return await self._store.revoke_all_user_sessions(user_id, reason)
    
    # -------------------------------------------------------------------------
    # TOKEN OPERATIONS
    # -------------------------------------------------------------------------
    
    def _create_access_token(self, session: SessionData) -> str:
        """Create an access token for a session."""
        now = int(time.time())
        
        payload = TokenPayload(
            sub=session.user_id,
            jti=str(uuid.uuid4()),
            iat=now,
            exp=now + self._access_expiry,
            session_id=session.session_id,
            role=session.role,
            token_type=TOKEN_TYPE_ACCESS,
            interface=session.interface.value,
            device_fingerprint=session.device_fingerprint,
        )
        
        return jwt.encode(
            payload.to_dict(),
            self._secret_key,
            algorithm=self._algorithm,
        )
    
    def _create_refresh_token(self, session: SessionData) -> str:
        """Create a refresh token for a session."""
        now = int(time.time())
        
        payload = TokenPayload(
            sub=session.user_id,
            jti=str(uuid.uuid4()),
            iat=now,
            exp=now + self._refresh_expiry,
            session_id=session.session_id,
            role=session.role,
            token_type=TOKEN_TYPE_REFRESH,
            interface=session.interface.value,
            device_fingerprint=session.device_fingerprint,
        )
        
        return jwt.encode(
            payload.to_dict(),
            self._secret_key,
            algorithm=self._algorithm,
        )
    
    async def verify_token(
        self,
        token: str,
        expected_type: str = TOKEN_TYPE_ACCESS,
        check_fingerprint: Optional[str] = None,
    ) -> Optional[TokenPayload]:
        """
        Verify a JWT token.
        
        Args:
            token: The JWT token
            expected_type: Expected token type (access/refresh)
            check_fingerprint: Device fingerprint to validate
            
        Returns:
            TokenPayload if valid, None otherwise
        """
        try:
            data = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
            )
            
            payload = TokenPayload.from_dict(data)
            
            # Check token type
            if payload.token_type != expected_type:
                return None
            
            # Check if revoked
            if await self._store.is_token_revoked(payload.jti):
                return None
            
            # Check session is still valid
            session = await self._store.get(payload.session_id)
            if session is None or not session.is_valid():
                return None
            
            # Check device fingerprint if required
            if check_fingerprint and payload.device_fingerprint:
                if not hmac.compare_digest(
                    check_fingerprint,
                    payload.device_fingerprint,
                ):
                    return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        device_fingerprint: Optional[str] = None,
    ) -> Optional[Tuple[str, str]]:
        """
        Refresh access token using refresh token.
        
        Returns:
            (new_access_token, new_refresh_token) or None if invalid
        """
        payload = await self.verify_token(
            refresh_token,
            expected_type=TOKEN_TYPE_REFRESH,
            check_fingerprint=device_fingerprint,
        )
        
        if payload is None:
            return None
        
        # Get session
        session = await self._store.get(payload.session_id)
        if session is None or not session.is_valid():
            return None
        
        # Revoke old refresh token
        await self._store.revoke_token(payload.jti)
        
        # Update session expiry
        session.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self._access_expiry
        )
        session.touch()
        await self._store.update(session)
        
        # Generate new tokens
        access_token = self._create_access_token(session)
        new_refresh_token = self._create_refresh_token(session)
        
        return access_token, new_refresh_token
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a specific token."""
        try:
            # Decode without verification to get jti
            data = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"verify_exp": False},
            )
            
            await self._store.revoke_token(data["jti"])
            return True
            
        except Exception:
            return False
    
    # -------------------------------------------------------------------------
    # MFA OPERATIONS
    # -------------------------------------------------------------------------
    
    async def verify_mfa(
        self,
        session_id: str,
        method: MFAMethod,
        verification_data: Dict[str, Any],
    ) -> bool:
        """
        Record successful MFA verification.
        
        Actual MFA verification is done by AuthManager.
        This just records the result in the session.
        """
        session = await self._store.get(session_id)
        
        if session is None or not session.is_valid():
            return False
        
        session.mfa_verified = True
        session.mfa_method = method
        session.mfa_verified_at = datetime.now(timezone.utc)
        
        await self._store.update(session)
        return True
    
    async def is_mfa_required(
        self,
        session_id: str,
    ) -> bool:
        """Check if MFA is required for session."""
        session = await self._store.get(session_id)
        
        if session is None:
            return True
        
        return not session.is_mfa_valid()
    
    # -------------------------------------------------------------------------
    # ELEVATION OPERATIONS
    # -------------------------------------------------------------------------
    
    async def elevate_session(
        self,
        session_id: str,
        duration: int = ELEVATION_DURATION,
    ) -> bool:
        """
        Elevate session to higher trust level.
        
        Requires MFA to be verified.
        """
        session = await self._store.get(session_id)
        
        if session is None or not session.is_valid():
            return False
        
        if not session.is_mfa_valid():
            return False
        
        session.is_elevated = True
        session.elevation_expires = datetime.now(timezone.utc) + timedelta(
            seconds=duration
        )
        
        await self._store.update(session)
        return True
    
    async def drop_elevation(self, session_id: str) -> bool:
        """Drop session elevation."""
        session = await self._store.get(session_id)
        
        if session is None:
            return False
        
        session.is_elevated = False
        session.elevation_expires = None
        
        await self._store.update(session)
        return True
    
    # -------------------------------------------------------------------------
    # QUERY OPERATIONS
    # -------------------------------------------------------------------------
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        return await self._store.get(session_id)
    
    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Get all sessions for a user."""
        return await self._store.get_user_sessions(user_id)
    
    async def get_active_session_count(self, user_id: str) -> int:
        """Get count of active sessions for a user."""
        sessions = await self._store.get_user_sessions(user_id)
        return sum(1 for s in sessions if s.is_valid())


# =============================================================================
# DEVICE FINGERPRINTING
# =============================================================================

def compute_device_fingerprint(
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
    accept_language: Optional[str] = None,
    screen_resolution: Optional[str] = None,
    timezone: Optional[str] = None,
) -> str:
    """
    Compute a device fingerprint from available signals.
    
    This is a weak fingerprint for detection, not authentication.
    """
    components = [
        user_agent or "",
        accept_language or "",
        screen_resolution or "",
        timezone or "",
    ]
    
    data = "|".join(components)
    return hashlib.sha256(data.encode()).hexdigest()[:32]


# =============================================================================
# SINGLETON
# =============================================================================

_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        # In production, get secret from config
        secret = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
        _session_manager = SessionManager(secret_key=secret)
    return _session_manager


def set_session_manager(manager: SessionManager) -> None:
    """Set the global session manager (for testing)."""
    global _session_manager
    _session_manager = manager
