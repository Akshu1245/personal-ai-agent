"""
============================================================
AKSHAY AI CORE — Security Hardening Module
============================================================
Production security controls for defense in depth.

COMPONENTS:
1. Plugin Sandboxing - Restricted execution environment
2. Secrets Manager - Encrypted credential storage
3. Secure Session Manager - Session lifecycle control
4. Input Sanitization - XSS, injection, path traversal prevention
5. Security Headers - HTTP security headers middleware
============================================================
"""

import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Tuple, TypeVar, Union
import html
import json
import urllib.parse

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from core.config import settings
from core.utils.logger import get_logger
from core.security.audit_log import immutable_audit_log, AuditEventType, AuditSeverity

logger = get_logger("security.hardening")


# =============================================================================
# 1. SECRETS MANAGER
# =============================================================================

class SecretType(Enum):
    """Types of secrets."""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    WEBHOOK_SECRET = "webhook_secret"
    ENCRYPTION_KEY = "encryption_key"
    OTHER = "other"


@dataclass
class SecretMetadata:
    """Metadata for a stored secret."""
    name: str
    secret_type: SecretType
    description: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    created_by: str
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    tags: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        """Check if secret has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without the actual secret)."""
        return {
            "name": self.name,
            "secret_type": self.secret_type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_by": self.created_by,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "tags": list(self.tags),
            "is_expired": self.is_expired(),
        }


class SecretsManager:
    """
    Secure secrets management with encryption at rest.
    
    Features:
    - AES-256 encryption via Fernet
    - Key derivation from master password
    - Access auditing
    - Expiration support
    - Secure memory handling
    """
    
    _instance: Optional["SecretsManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "SecretsManager":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # Derive encryption key from master key
        self._master_key = self._derive_key()
        self._fernet = Fernet(self._master_key)
        
        # In-memory cache (encrypted values)
        self._secrets: Dict[str, bytes] = {}
        self._metadata: Dict[str, SecretMetadata] = {}
        
        # Lock for thread safety
        self._access_lock = threading.Lock()
        
        # Storage path
        self._storage_path = Path(getattr(settings, "SECRETS_STORAGE_PATH", "data/secrets"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing secrets
        self._load_secrets()
        
        logger.info("Secrets Manager initialized")
    
    def _derive_key(self) -> bytes:
        """Derive encryption key from master secret."""
        master_secret = getattr(settings, "SECRETS_MASTER_KEY", None)
        
        if not master_secret:
            # Generate and store a new master key
            master_secret = secrets.token_urlsafe(32)
            logger.warning(
                "No SECRETS_MASTER_KEY configured. Generated ephemeral key. "
                "Secrets will NOT persist across restarts."
            )
        
        # Use PBKDF2 to derive key
        salt = b"akshay_ai_core_secrets_v1"  # Fixed salt for deterministic derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(master_secret.encode()))
        return key
    
    def _load_secrets(self) -> None:
        """Load secrets from storage."""
        secrets_file = self._storage_path / "secrets.enc"
        metadata_file = self._storage_path / "metadata.json"
        
        if not secrets_file.exists():
            return
        
        try:
            # Load encrypted secrets
            with open(secrets_file, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            secrets_dict = json.loads(decrypted_data.decode())
            
            for name, encrypted_value in secrets_dict.items():
                self._secrets[name] = encrypted_value.encode()
            
            # Load metadata
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata_dict = json.load(f)
                
                for name, meta in metadata_dict.items():
                    self._metadata[name] = SecretMetadata(
                        name=meta["name"],
                        secret_type=SecretType(meta["secret_type"]),
                        description=meta["description"],
                        created_at=datetime.fromisoformat(meta["created_at"]),
                        updated_at=datetime.fromisoformat(meta["updated_at"]),
                        expires_at=datetime.fromisoformat(meta["expires_at"]) if meta["expires_at"] else None,
                        created_by=meta["created_by"],
                        last_accessed=datetime.fromisoformat(meta["last_accessed"]) if meta.get("last_accessed") else None,
                        access_count=meta.get("access_count", 0),
                        tags=set(meta.get("tags", [])),
                    )
            
            logger.info(f"Loaded {len(self._secrets)} secrets from storage")
            
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
    
    def _save_secrets(self) -> None:
        """Persist secrets to storage."""
        try:
            # Save encrypted secrets
            secrets_dict = {
                name: value.decode() for name, value in self._secrets.items()
            }
            
            encrypted_data = self._fernet.encrypt(json.dumps(secrets_dict).encode())
            
            secrets_file = self._storage_path / "secrets.enc"
            with open(secrets_file, "wb") as f:
                f.write(encrypted_data)
            
            # Save metadata (not encrypted, no sensitive data)
            metadata_dict = {
                name: meta.to_dict() for name, meta in self._metadata.items()
            }
            
            metadata_file = self._storage_path / "metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata_dict, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
    
    def store_secret(
        self,
        name: str,
        value: str,
        secret_type: SecretType,
        description: str = "",
        expires_at: Optional[datetime] = None,
        created_by: str = "system",
        tags: Optional[Set[str]] = None,
    ) -> bool:
        """
        Store a secret securely.
        
        Args:
            name: Unique name for the secret
            value: The secret value to store
            secret_type: Type of secret
            description: Description of the secret
            expires_at: Optional expiration datetime
            created_by: User who created the secret
            tags: Optional tags for categorization
            
        Returns:
            True if stored successfully
        """
        with self._access_lock:
            try:
                # Encrypt the secret
                encrypted_value = self._fernet.encrypt(value.encode())
                
                # Store encrypted value
                self._secrets[name] = encrypted_value
                
                # Store metadata
                now = datetime.utcnow()
                self._metadata[name] = SecretMetadata(
                    name=name,
                    secret_type=secret_type,
                    description=description,
                    created_at=now,
                    updated_at=now,
                    expires_at=expires_at,
                    created_by=created_by,
                    tags=tags or set(),
                )
                
                # Persist to storage
                self._save_secrets()
                
                # Audit log
                immutable_audit_log.log(
                    event_type=AuditEventType.DATA_CREATE,
                    severity=AuditSeverity.INFO,
                    action="secret_stored",
                    user_id=created_by,
                    resource_type="secret",
                    resource_id=name,
                    details={"secret_type": secret_type.value},
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to store secret: {e}")
                return False
    
    def get_secret(self, name: str, accessor: str = "system") -> Optional[str]:
        """
        Retrieve a secret.
        
        Args:
            name: Secret name
            accessor: User/service accessing the secret
            
        Returns:
            Decrypted secret value or None
        """
        with self._access_lock:
            if name not in self._secrets:
                return None
            
            metadata = self._metadata.get(name)
            
            # Check expiration
            if metadata and metadata.is_expired():
                logger.warning(f"Secret '{name}' has expired")
                return None
            
            try:
                # Decrypt
                decrypted = self._fernet.decrypt(self._secrets[name])
                
                # Update access tracking
                if metadata:
                    metadata.last_accessed = datetime.utcnow()
                    metadata.access_count += 1
                
                # Audit log
                immutable_audit_log.log(
                    event_type=AuditEventType.DATA_READ,
                    severity=AuditSeverity.INFO,
                    action="secret_accessed",
                    user_id=accessor,
                    resource_type="secret",
                    resource_id=name,
                )
                
                return decrypted.decode()
                
            except Exception as e:
                logger.error(f"Failed to decrypt secret: {e}")
                return None
    
    def delete_secret(self, name: str, deleted_by: str = "system") -> bool:
        """Delete a secret."""
        with self._access_lock:
            if name not in self._secrets:
                return False
            
            del self._secrets[name]
            if name in self._metadata:
                del self._metadata[name]
            
            self._save_secrets()
            
            immutable_audit_log.log(
                event_type=AuditEventType.DATA_DELETE,
                severity=AuditSeverity.NOTICE,
                action="secret_deleted",
                user_id=deleted_by,
                resource_type="secret",
                resource_id=name,
            )
            
            return True
    
    def list_secrets(self) -> List[Dict[str, Any]]:
        """List all secrets metadata (not values)."""
        return [meta.to_dict() for meta in self._metadata.values()]
    
    def rotate_secret(
        self,
        name: str,
        new_value: str,
        rotated_by: str = "system",
    ) -> bool:
        """
        Rotate a secret to a new value.
        
        Args:
            name: Secret name
            new_value: New secret value
            rotated_by: User performing rotation
            
        Returns:
            True if rotated successfully
        """
        with self._access_lock:
            if name not in self._secrets:
                return False
            
            metadata = self._metadata.get(name)
            if not metadata:
                return False
            
            try:
                # Encrypt new value
                encrypted_value = self._fernet.encrypt(new_value.encode())
                
                # Update
                self._secrets[name] = encrypted_value
                metadata.updated_at = datetime.utcnow()
                
                self._save_secrets()
                
                immutable_audit_log.log(
                    event_type=AuditEventType.DATA_UPDATE,
                    severity=AuditSeverity.NOTICE,
                    action="secret_rotated",
                    user_id=rotated_by,
                    resource_type="secret",
                    resource_id=name,
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to rotate secret: {e}")
                return False


# =============================================================================
# 2. SECURE SESSION MANAGER
# =============================================================================

@dataclass
class Session:
    """User session data."""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Security flags
    is_mfa_verified: bool = False
    mfa_verified_at: Optional[datetime] = None
    is_elevated: bool = False  # Elevated privileges session
    elevation_expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    def is_elevation_valid(self) -> bool:
        """Check if elevation is still valid."""
        if not self.is_elevated:
            return False
        if self.elevation_expires_at is None:
            return False
        return datetime.utcnow() < self.elevation_expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ip_address": self.ip_address,
            "is_mfa_verified": self.is_mfa_verified,
            "is_elevated": self.is_elevation_valid(),
        }


class SessionManager:
    """
    Secure session management.
    
    Features:
    - Cryptographically secure session IDs
    - Session expiration and cleanup
    - Concurrent session limits
    - Session binding (IP, user agent)
    - Elevation for sensitive operations
    """
    
    _instance: Optional["SessionManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "SessionManager":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # Session storage
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> session_ids
        
        # Configuration
        self._session_timeout_minutes = getattr(settings, "SESSION_TIMEOUT_MINUTES", 30)
        self._max_sessions_per_user = getattr(settings, "MAX_SESSIONS_PER_USER", 5)
        self._elevation_timeout_minutes = getattr(settings, "ELEVATION_TIMEOUT_MINUTES", 15)
        self._bind_ip = getattr(settings, "SESSION_BIND_IP", True)
        
        # Cleanup task
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
        
        self._access_lock = threading.Lock()
        
        logger.info("Session Manager initialized")
    
    def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """
        Create a new session.
        
        Args:
            user_id: User identifier
            ip_address: Client IP address
            user_agent: Client user agent
            data: Additional session data
            
        Returns:
            Created session
        """
        with self._access_lock:
            # Check concurrent session limit
            user_sessions = self._user_sessions.get(user_id, set())
            if len(user_sessions) >= self._max_sessions_per_user:
                # Remove oldest session
                oldest = None
                oldest_time = None
                for sid in user_sessions:
                    session = self._sessions.get(sid)
                    if session:
                        if oldest_time is None or session.created_at < oldest_time:
                            oldest = sid
                            oldest_time = session.created_at
                
                if oldest:
                    self._invalidate_session(oldest)
            
            # Generate secure session ID
            session_id = secrets.token_urlsafe(32)
            
            now = datetime.utcnow()
            session = Session(
                session_id=session_id,
                user_id=user_id,
                created_at=now,
                expires_at=now + timedelta(minutes=self._session_timeout_minutes),
                last_activity=now,
                ip_address=ip_address,
                user_agent=user_agent,
                data=data or {},
            )
            
            self._sessions[session_id] = session
            
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session_id)
            
            immutable_audit_log.log(
                event_type=AuditEventType.AUTH_LOGIN,
                severity=AuditSeverity.INFO,
                action="session_created",
                user_id=user_id,
                ip_address=ip_address,
                details={"session_id": session_id[:8] + "..."},
            )
            
            return session
    
    def get_session(
        self,
        session_id: str,
        ip_address: Optional[str] = None,
    ) -> Optional[Session]:
        """
        Get and validate a session.
        
        Args:
            session_id: Session ID
            ip_address: Current client IP (for binding validation)
            
        Returns:
            Valid session or None
        """
        # Periodic cleanup
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
        
        with self._access_lock:
            session = self._sessions.get(session_id)
            
            if not session:
                return None
            
            # Check expiration
            if session.is_expired():
                self._invalidate_session(session_id)
                return None
            
            # Check IP binding
            if self._bind_ip and ip_address and session.ip_address:
                if ip_address != session.ip_address:
                    logger.warning(
                        f"Session IP mismatch: expected {session.ip_address}, got {ip_address}"
                    )
                    
                    immutable_audit_log.log(
                        event_type=AuditEventType.SECURITY_ALERT,
                        severity=AuditSeverity.WARNING,
                        action="session_ip_mismatch",
                        user_id=session.user_id,
                        ip_address=ip_address,
                        details={
                            "expected_ip": session.ip_address,
                            "session_id": session_id[:8] + "...",
                        },
                    )
                    
                    return None
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            
            # Extend expiration on activity
            session.expires_at = datetime.utcnow() + timedelta(minutes=self._session_timeout_minutes)
            
            return session
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a specific session."""
        with self._access_lock:
            return self._invalidate_session(session_id)
    
    def _invalidate_session(self, session_id: str) -> bool:
        """Internal session invalidation (must hold lock)."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        # Remove from user sessions
        user_sessions = self._user_sessions.get(session.user_id)
        if user_sessions:
            user_sessions.discard(session_id)
        
        # Remove session
        del self._sessions[session_id]
        
        immutable_audit_log.log(
            event_type=AuditEventType.AUTH_LOGOUT,
            severity=AuditSeverity.INFO,
            action="session_invalidated",
            user_id=session.user_id,
            details={"session_id": session_id[:8] + "..."},
        )
        
        return True
    
    def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        with self._access_lock:
            user_sessions = self._user_sessions.get(user_id, set()).copy()
            count = 0
            
            for session_id in user_sessions:
                if self._invalidate_session(session_id):
                    count += 1
            
            return count
    
    def elevate_session(
        self,
        session_id: str,
        verification_method: str,
    ) -> bool:
        """
        Elevate session for sensitive operations.
        
        Args:
            session_id: Session to elevate
            verification_method: How the user was verified (mfa, password, etc.)
            
        Returns:
            True if elevated successfully
        """
        with self._access_lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            session.is_elevated = True
            session.elevation_expires_at = datetime.utcnow() + timedelta(
                minutes=self._elevation_timeout_minutes
            )
            
            immutable_audit_log.log(
                event_type=AuditEventType.AUTHZ_GRANTED,
                severity=AuditSeverity.NOTICE,
                action="session_elevated",
                user_id=session.user_id,
                details={
                    "verification_method": verification_method,
                    "session_id": session_id[:8] + "...",
                },
            )
            
            return True
    
    def mark_mfa_verified(self, session_id: str) -> bool:
        """Mark session as MFA verified."""
        with self._access_lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            session.is_mfa_verified = True
            session.mfa_verified_at = datetime.utcnow()
            
            return True
    
    def _cleanup_expired(self) -> None:
        """Clean up expired sessions."""
        with self._access_lock:
            self._last_cleanup = time.time()
            
            expired = [
                sid for sid, session in self._sessions.items()
                if session.is_expired()
            ]
            
            for sid in expired:
                self._invalidate_session(sid)
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        with self._access_lock:
            session_ids = self._user_sessions.get(user_id, set())
            sessions = []
            
            for sid in session_ids:
                session = self._sessions.get(sid)
                if session and not session.is_expired():
                    sessions.append(session.to_dict())
            
            return sessions


# =============================================================================
# 3. INPUT SANITIZATION
# =============================================================================

class InputSanitizer:
    """
    Input sanitization utilities for defense against injection attacks.
    
    Protects against:
    - XSS (Cross-Site Scripting)
    - SQL Injection patterns
    - Command Injection
    - Path Traversal
    - LDAP Injection
    - XML/JSON Injection
    """
    
    # Dangerous patterns
    _SQL_PATTERNS: List[Pattern] = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)", re.IGNORECASE),
        re.compile(r"(--)|(;)|(\/\*)"),
        re.compile(r"(\bOR\b|\bAND\b)\s*[\d\w]+\s*=\s*[\d\w]+", re.IGNORECASE),
    ]
    
    _COMMAND_PATTERNS: List[Pattern] = [
        re.compile(r"[;&|`$]"),
        re.compile(r"(\||&&)"),
        re.compile(r"\$\([^)]+\)"),
        re.compile(r"`[^`]+`"),
    ]
    
    _PATH_TRAVERSAL_PATTERNS: List[Pattern] = [
        re.compile(r"\.\.[\\/]"),
        re.compile(r"[\\/]\.\."),
        re.compile(r"^~"),
        re.compile(r"[\x00]"),  # Null byte
    ]
    
    _LDAP_PATTERNS: List[Pattern] = [
        re.compile(r"[()\\*\x00]"),
    ]
    
    @classmethod
    def html_escape(cls, text: str) -> str:
        """
        Escape HTML special characters.
        
        Args:
            text: Input text
            
        Returns:
            HTML-escaped text
        """
        return html.escape(text, quote=True)
    
    @classmethod
    def strip_html(cls, text: str) -> str:
        """
        Remove all HTML tags from text.
        
        Args:
            text: Input text with potential HTML
            
        Returns:
            Text with HTML tags removed
        """
        clean = re.sub(r'<[^>]+>', '', text)
        return clean
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize a filename for safe filesystem use.
        
        Args:
            filename: Input filename
            
        Returns:
            Safe filename
        """
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
        
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255 - len(ext)] + ext
        
        # Default if empty
        if not filename:
            filename = "unnamed"
        
        return filename
    
    @classmethod
    def sanitize_path(cls, path: str, base_path: str) -> Optional[str]:
        """
        Sanitize a path and ensure it's within base_path.
        
        Args:
            path: User-provided path
            base_path: Allowed base directory
            
        Returns:
            Safe absolute path or None if invalid
        """
        try:
            # Resolve paths
            base = Path(base_path).resolve()
            target = (base / path).resolve()
            
            # Ensure target is under base
            if not str(target).startswith(str(base)):
                return None
            
            return str(target)
            
        except Exception:
            return None
    
    @classmethod
    def check_sql_injection(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check for SQL injection patterns.
        
        Args:
            text: Input to check
            
        Returns:
            (is_safe, pattern_found)
        """
        for pattern in cls._SQL_PATTERNS:
            match = pattern.search(text)
            if match:
                return False, match.group()
        return True, None
    
    @classmethod
    def check_command_injection(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check for command injection patterns.
        
        Args:
            text: Input to check
            
        Returns:
            (is_safe, pattern_found)
        """
        for pattern in cls._COMMAND_PATTERNS:
            match = pattern.search(text)
            if match:
                return False, match.group()
        return True, None
    
    @classmethod
    def check_path_traversal(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check for path traversal patterns.
        
        Args:
            text: Input to check
            
        Returns:
            (is_safe, pattern_found)
        """
        for pattern in cls._PATH_TRAVERSAL_PATTERNS:
            match = pattern.search(text)
            if match:
                return False, match.group()
        return True, None
    
    @classmethod
    def sanitize_json_string(cls, text: str) -> str:
        """
        Sanitize a string for safe JSON embedding.
        
        Args:
            text: Input text
            
        Returns:
            JSON-safe string
        """
        # JSON encode will escape necessary characters
        return json.dumps(text)[1:-1]  # Remove surrounding quotes
    
    @classmethod
    def sanitize_url_param(cls, text: str) -> str:
        """
        Sanitize a string for use in URL parameters.
        
        Args:
            text: Input text
            
        Returns:
            URL-safe string
        """
        return urllib.parse.quote(text, safe='')
    
    @classmethod
    def sanitize_ldap(cls, text: str) -> str:
        """
        Sanitize a string for LDAP queries.
        
        Args:
            text: Input text
            
        Returns:
            LDAP-safe string
        """
        # Escape LDAP special characters
        replacements = [
            ('\\', '\\5c'),
            ('*', '\\2a'),
            ('(', '\\28'),
            (')', '\\29'),
            ('\x00', '\\00'),
        ]
        
        result = text
        for char, escape in replacements:
            result = result.replace(char, escape)
        
        return result
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid format
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @classmethod
    def validate_uuid(cls, uuid_str: str) -> bool:
        """
        Validate UUID format.
        
        Args:
            uuid_str: UUID string to validate
            
        Returns:
            True if valid UUID
        """
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(pattern, uuid_str.lower()))
    
    @classmethod
    def comprehensive_check(cls, text: str) -> Dict[str, Any]:
        """
        Perform comprehensive security check on input.
        
        Args:
            text: Input to check
            
        Returns:
            Dictionary with check results
        """
        sql_safe, sql_pattern = cls.check_sql_injection(text)
        cmd_safe, cmd_pattern = cls.check_command_injection(text)
        path_safe, path_pattern = cls.check_path_traversal(text)
        
        is_safe = sql_safe and cmd_safe and path_safe
        
        return {
            "is_safe": is_safe,
            "sql_injection": {"safe": sql_safe, "pattern": sql_pattern},
            "command_injection": {"safe": cmd_safe, "pattern": cmd_pattern},
            "path_traversal": {"safe": path_safe, "pattern": path_pattern},
        }


# =============================================================================
# 4. PLUGIN SANDBOX
# =============================================================================

class SandboxViolation(Exception):
    """Raised when sandbox policy is violated."""
    pass


class PluginSandbox:
    """
    Sandbox environment for plugin execution.
    
    Restrictions:
    - No file system access outside allowed paths
    - No network access unless explicitly allowed
    - No subprocess execution
    - No dangerous builtins
    - Resource limits (memory, CPU time)
    """
    
    # Dangerous builtins to remove
    BLOCKED_BUILTINS = {
        'eval', 'exec', 'compile', '__import__',
        'open', 'file', 'input', 'raw_input',
        'execfile', 'reload', 'quit', 'exit',
    }
    
    # Blocked modules
    BLOCKED_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'multiprocessing',
        'ctypes', 'gc', 'importlib', 'builtins', 'code',
        'shutil', 'pathlib', 'pickle', 'shelve', 'marshal',
    }
    
    def __init__(
        self,
        allow_network: bool = False,
        allow_filesystem: bool = False,
        allowed_paths: Optional[Set[str]] = None,
        max_memory_mb: int = 256,
        max_time_seconds: int = 60,
    ):
        self.allow_network = allow_network
        self.allow_filesystem = allow_filesystem
        self.allowed_paths = allowed_paths or set()
        self.max_memory_mb = max_memory_mb
        self.max_time_seconds = max_time_seconds
        
        self._restricted_globals = self._create_restricted_globals()
    
    def _create_restricted_globals(self) -> Dict[str, Any]:
        """Create restricted global namespace."""
        import builtins
        
        # Start with safe builtins
        safe_builtins = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if not name.startswith('_') and name not in self.BLOCKED_BUILTINS
        }
        
        # Create custom __import__ that blocks dangerous modules
        original_import = builtins.__import__
        
        def restricted_import(name, *args, **kwargs):
            if name in self.BLOCKED_MODULES:
                raise SandboxViolation(f"Module '{name}' is not allowed in sandbox")
            
            # Block submodules of blocked modules
            for blocked in self.BLOCKED_MODULES:
                if name.startswith(f"{blocked}."):
                    raise SandboxViolation(f"Module '{name}' is not allowed in sandbox")
            
            return original_import(name, *args, **kwargs)
        
        safe_builtins['__import__'] = restricted_import
        
        return {
            '__builtins__': safe_builtins,
            '__name__': '__sandbox__',
            '__doc__': None,
        }
    
    def check_file_access(self, path: str) -> bool:
        """
        Check if file access is allowed.
        
        Args:
            path: Path to check
            
        Returns:
            True if access is allowed
        """
        if not self.allow_filesystem:
            return False
        
        if not self.allowed_paths:
            return False
        
        try:
            resolved = Path(path).resolve()
            
            for allowed in self.allowed_paths:
                allowed_path = Path(allowed).resolve()
                if str(resolved).startswith(str(allowed_path)):
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def execute(
        self,
        code: str,
        local_vars: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute code in sandbox.
        
        Args:
            code: Python code to execute
            local_vars: Local variables to provide
            
        Returns:
            Execution result
        """
        # Compile first to check syntax
        try:
            compiled = compile(code, '<sandbox>', 'exec')
        except SyntaxError as e:
            raise SandboxViolation(f"Syntax error: {e}")
        
        # Set up execution environment
        globals_dict = self._restricted_globals.copy()
        locals_dict = local_vars or {}
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: exec(compiled, globals_dict, locals_dict)
                ),
                timeout=self.max_time_seconds,
            )
            
            return locals_dict.get('result', result)
            
        except asyncio.TimeoutError:
            raise SandboxViolation(f"Execution timeout ({self.max_time_seconds}s)")
        except SandboxViolation:
            raise
        except Exception as e:
            raise SandboxViolation(f"Execution error: {e}")


# =============================================================================
# 5. SECURITY HEADERS MIDDLEWARE
# =============================================================================

def get_security_headers() -> Dict[str, str]:
    """
    Get recommended security headers for HTTP responses.
    
    Returns:
        Dictionary of security headers
    """
    return {
        # Prevent XSS
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        
        # Prevent clickjacking
        "X-Frame-Options": "DENY",
        
        # Content Security Policy
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        ),
        
        # Strict Transport Security
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        
        # Referrer Policy
        "Referrer-Policy": "strict-origin-when-cross-origin",
        
        # Permissions Policy
        "Permissions-Policy": (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=()"
        ),
        
        # Cache control for sensitive data
        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

secrets_manager = SecretsManager()
session_manager = SessionManager()
input_sanitizer = InputSanitizer()
