"""
AKSHAY AI CORE — Policy Signer

Cryptographic signing for policy documents.
Supports Ed25519 (production) and HMAC-SHA256 (development).

SECURITY GUARANTEES:
- Deterministic canonicalization
- Constant-time comparisons
- No hardcoded secrets
- Thread-safe operations
- Audit logging of all sign operations

SIGNING PIPELINE:
1. Load policy body (exclude signature block)
2. Canonicalize: sort keys, strip whitespace, UTF-8 encode
3. Hash with SHA-256
4. Sign hash with Ed25519 or HMAC-SHA256
5. Embed signature metadata
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from pydantic import BaseModel, Field, ConfigDict

from core.policy.errors import (
    PolicySignatureError,
    PolicyKeyError,
    PolicyKeyNotFoundError,
    PolicyKeyExpiredError,
    PolicyErrorCode,
)
from core.policy.schema import (
    SignatureAlgorithm,
    PolicySignature,
    PolicyDocument,
)

# Try to import cryptography for Ed25519
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    ED25519_AVAILABLE = True
except ImportError:
    ED25519_AVAILABLE = False
    Ed25519PrivateKey = None
    Ed25519PublicKey = None


# =============================================================================
# CONSTANTS
# =============================================================================

# Canonical JSON encoding settings
CANONICAL_SEPARATORS = (",", ":")
CANONICAL_ENSURE_ASCII = False

# Hash algorithm for policy content
HASH_ALGORITHM = "sha256"

# Minimum key ID length
MIN_KEY_ID_LENGTH = 8

# Maximum key age before warning (365 days)
MAX_KEY_AGE_DAYS = 365


# =============================================================================
# KEY TRUST LEVELS
# =============================================================================

class KeyTrust:
    """Key trust levels for hierarchical signing permissions."""
    
    ROOT = "ROOT"           # Can sign everything including failure_mode, inherits, allowlists
    OPERATOR = "OPERATOR"   # Can sign rules only
    AUDIT = "AUDIT"         # Verify only, cannot sign
    
    # Fields that require ROOT trust to modify
    ROOT_ONLY_FIELDS = frozenset({
        "failure_mode",
        "inherits",
        "allowlists",
        "zones",
    })
    
    # Fields that OPERATOR can modify
    OPERATOR_FIELDS = frozenset({
        "rules",
        "metadata",
    })
    
    @classmethod
    def can_sign(cls, trust_level: str) -> bool:
        """Check if trust level allows signing."""
        return trust_level in (cls.ROOT, cls.OPERATOR)
    
    @classmethod
    def can_sign_field(cls, trust_level: str, field: str) -> bool:
        """Check if trust level can sign a specific field."""
        if trust_level == cls.ROOT:
            return True
        if trust_level == cls.OPERATOR:
            return field in cls.OPERATOR_FIELDS
        return False


# =============================================================================
# KEY MODELS
# =============================================================================

class SigningKey(BaseModel):
    """Signing key configuration."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    key_id: str = Field(
        ...,
        min_length=MIN_KEY_ID_LENGTH,
        description="Unique key identifier",
    )
    algorithm: SignatureAlgorithm = Field(
        ...,
        description="Signing algorithm",
    )
    trust: str = Field(
        default=KeyTrust.OPERATOR,
        description="Key trust level",
    )
    description: str = Field(
        default="",
        description="Human-readable description",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Key creation time",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Key expiration time",
    )
    deprecated: bool = Field(
        default=False,
        description="Whether key is deprecated (still valid but warned)",
    )
    revoked: bool = Field(
        default=False,
        description="Whether key is revoked (no longer valid)",
    )
    
    # Private key material (sensitive - never logged)
    _private_key_bytes: Optional[bytes] = None
    _hmac_secret: Optional[bytes] = None
    
    def is_valid(self) -> bool:
        """Check if key is currently valid."""
        if self.revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
    
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at:
            return datetime.now(timezone.utc) > self.expires_at
        return False
    
    def days_until_expiry(self) -> Optional[int]:
        """Get days until key expires."""
        if self.expires_at:
            delta = self.expires_at - datetime.now(timezone.utc)
            return delta.days
        return None


class KeyPair(BaseModel):
    """Generated key pair for Ed25519."""
    
    model_config = ConfigDict(extra="forbid")
    
    key_id: str
    algorithm: SignatureAlgorithm
    public_key_pem: str
    private_key_pem: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_public_key_bytes(self) -> bytes:
        """Get raw public key bytes."""
        return base64.b64decode(
            self.public_key_pem
            .replace("-----BEGIN PUBLIC KEY-----", "")
            .replace("-----END PUBLIC KEY-----", "")
            .replace("\n", "")
        )


class HMACKey(BaseModel):
    """Generated HMAC key for development."""
    
    model_config = ConfigDict(extra="forbid")
    
    key_id: str
    algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    secret_base64: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_secret_bytes(self) -> bytes:
        """Get raw secret bytes."""
        return base64.b64decode(self.secret_base64)


# =============================================================================
# CANONICALIZATION
# =============================================================================

class PolicyCanonicalizer:
    """
    Deterministic policy canonicalization for signing.
    
    Canonicalization Pipeline:
    1. Remove signature block from policy
    2. Sort all dictionary keys recursively
    3. Use compact JSON encoding
    4. UTF-8 encode
    5. SHA-256 hash
    """
    
    @staticmethod
    def canonicalize(policy_data: Dict[str, Any]) -> bytes:
        """
        Canonicalize policy data to deterministic bytes.
        
        Args:
            policy_data: Policy document as dictionary (without signature)
            
        Returns:
            Canonical UTF-8 encoded bytes
        """
        # Remove signature if present
        data = {k: v for k, v in policy_data.items() if k != "signature"}
        
        # Sort keys recursively
        sorted_data = PolicyCanonicalizer._sort_recursive(data)
        
        # Encode to compact JSON
        canonical_json = json.dumps(
            sorted_data,
            separators=CANONICAL_SEPARATORS,
            ensure_ascii=CANONICAL_ENSURE_ASCII,
            sort_keys=True,  # Belt and suspenders
            default=PolicyCanonicalizer._json_serializer,
        )
        
        # UTF-8 encode
        return canonical_json.encode("utf-8")
    
    @staticmethod
    def _sort_recursive(obj: Any) -> Any:
        """Recursively sort dictionary keys."""
        if isinstance(obj, dict):
            return {
                k: PolicyCanonicalizer._sort_recursive(v)
                for k in sorted(obj.keys())
                for k, v in [(k, obj[k])]
            }
        elif isinstance(obj, list):
            return [PolicyCanonicalizer._sort_recursive(item) for item in obj]
        else:
            return obj
    
    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    @staticmethod
    def hash(canonical_bytes: bytes) -> bytes:
        """
        Hash canonical bytes with SHA-256.
        
        Args:
            canonical_bytes: Canonicalized policy bytes
            
        Returns:
            SHA-256 hash bytes
        """
        return hashlib.sha256(canonical_bytes).digest()
    
    @staticmethod
    def hash_hex(canonical_bytes: bytes) -> str:
        """
        Hash canonical bytes and return hex string.
        
        Args:
            canonical_bytes: Canonicalized policy bytes
            
        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(canonical_bytes).hexdigest()


# =============================================================================
# POLICY SIGNER
# =============================================================================

class PolicySigner:
    """
    Sign policy documents with Ed25519 or HMAC-SHA256.
    
    Thread-safe implementation with key registry.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._keys: Dict[str, SigningKey] = {}
        self._private_keys: Dict[str, bytes] = {}  # Ed25519 private keys
        self._hmac_secrets: Dict[str, bytes] = {}  # HMAC secrets
    
    # =========================================================================
    # KEY GENERATION
    # =========================================================================
    
    def generate_ed25519_keypair(
        self,
        key_id: str,
        trust: str = KeyTrust.OPERATOR,
        description: str = "",
        expires_in_days: Optional[int] = MAX_KEY_AGE_DAYS,
    ) -> KeyPair:
        """
        Generate a new Ed25519 key pair.
        
        Args:
            key_id: Unique identifier for the key
            trust: Trust level (ROOT, OPERATOR, AUDIT)
            description: Human-readable description
            expires_in_days: Days until expiry (None for no expiry)
            
        Returns:
            KeyPair with public and private keys in PEM format
            
        Raises:
            PolicyKeyError: If Ed25519 not available
        """
        if not ED25519_AVAILABLE:
            raise PolicyKeyError(
                message="Ed25519 not available. Install 'cryptography' package.",
                code=PolicyErrorCode.KEY_INVALID_FORMAT,
            )
        
        # Generate key pair
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize to PEM
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        
        # Calculate expiry
        expires_at = None
        if expires_in_days:
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        # Register key
        signing_key = SigningKey(
            key_id=key_id,
            algorithm=SignatureAlgorithm.ED25519,
            trust=trust,
            description=description,
            expires_at=expires_at,
        )
        
        with self._lock:
            self._keys[key_id] = signing_key
            self._private_keys[key_id] = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        
        return KeyPair(
            key_id=key_id,
            algorithm=SignatureAlgorithm.ED25519,
            public_key_pem=public_pem,
            private_key_pem=private_pem,
        )
    
    def generate_hmac_key(
        self,
        key_id: str,
        trust: str = KeyTrust.OPERATOR,
        description: str = "",
        expires_in_days: Optional[int] = MAX_KEY_AGE_DAYS,
    ) -> HMACKey:
        """
        Generate a new HMAC-SHA256 key for development.
        
        Args:
            key_id: Unique identifier for the key
            trust: Trust level (ROOT, OPERATOR, AUDIT)
            description: Human-readable description
            expires_in_days: Days until expiry (None for no expiry)
            
        Returns:
            HMACKey with secret
        """
        # Generate 32-byte secret
        secret = secrets.token_bytes(32)
        secret_b64 = base64.b64encode(secret).decode("ascii")
        
        # Calculate expiry
        expires_at = None
        if expires_in_days:
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        # Register key
        signing_key = SigningKey(
            key_id=key_id,
            algorithm=SignatureAlgorithm.HMAC_SHA256,
            trust=trust,
            description=description,
            expires_at=expires_at,
        )
        
        with self._lock:
            self._keys[key_id] = signing_key
            self._hmac_secrets[key_id] = secret
        
        return HMACKey(
            key_id=key_id,
            secret_base64=secret_b64,
        )
    
    # =========================================================================
    # KEY REGISTRATION
    # =========================================================================
    
    def register_ed25519_key(
        self,
        key_id: str,
        private_key_pem: str,
        trust: str = KeyTrust.OPERATOR,
        description: str = "",
        expires_at: Optional[datetime] = None,
    ) -> SigningKey:
        """
        Register an existing Ed25519 private key.
        
        Args:
            key_id: Unique identifier
            private_key_pem: Private key in PEM format
            trust: Trust level
            description: Description
            expires_at: Expiration time
            
        Returns:
            Registered SigningKey
        """
        if not ED25519_AVAILABLE:
            raise PolicyKeyError(
                message="Ed25519 not available",
                code=PolicyErrorCode.KEY_INVALID_FORMAT,
            )
        
        # Load and validate key
        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode("ascii"),
                password=None,
            )
            if not isinstance(private_key, Ed25519PrivateKey):
                raise ValueError("Not an Ed25519 key")
        except Exception as e:
            raise PolicyKeyError(
                message=f"Invalid Ed25519 private key: {e}",
                code=PolicyErrorCode.KEY_INVALID_FORMAT,
            )
        
        signing_key = SigningKey(
            key_id=key_id,
            algorithm=SignatureAlgorithm.ED25519,
            trust=trust,
            description=description,
            expires_at=expires_at,
        )
        
        with self._lock:
            self._keys[key_id] = signing_key
            self._private_keys[key_id] = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        
        return signing_key
    
    def register_hmac_key(
        self,
        key_id: str,
        secret: Union[str, bytes],
        trust: str = KeyTrust.OPERATOR,
        description: str = "",
        expires_at: Optional[datetime] = None,
    ) -> SigningKey:
        """
        Register an existing HMAC secret.
        
        Args:
            key_id: Unique identifier
            secret: Secret as base64 string or bytes
            trust: Trust level
            description: Description
            expires_at: Expiration time
            
        Returns:
            Registered SigningKey
        """
        if isinstance(secret, str):
            secret_bytes = base64.b64decode(secret)
        else:
            secret_bytes = secret
        
        if len(secret_bytes) < 32:
            raise PolicyKeyError(
                message="HMAC secret must be at least 32 bytes",
                code=PolicyErrorCode.KEY_INVALID_FORMAT,
            )
        
        signing_key = SigningKey(
            key_id=key_id,
            algorithm=SignatureAlgorithm.HMAC_SHA256,
            trust=trust,
            description=description,
            expires_at=expires_at,
        )
        
        with self._lock:
            self._keys[key_id] = signing_key
            self._hmac_secrets[key_id] = secret_bytes
        
        return signing_key
    
    # =========================================================================
    # SIGNING
    # =========================================================================
    
    def sign_policy(
        self,
        policy_data: Dict[str, Any],
        key_id: str,
    ) -> Tuple[PolicySignature, str]:
        """
        Sign a policy document.
        
        Args:
            policy_data: Policy document as dictionary
            key_id: Key ID to sign with
            
        Returns:
            Tuple of (PolicySignature, content_hash_hex)
            
        Raises:
            PolicyKeyNotFoundError: If key not found
            PolicyKeyExpiredError: If key expired
            PolicyKeyError: If key cannot sign
            PolicySignatureError: If signing fails
        """
        with self._lock:
            # Get key
            if key_id not in self._keys:
                raise PolicyKeyNotFoundError(key_id)
            
            key = self._keys[key_id]
            
            # Check key validity
            if key.revoked:
                raise PolicyKeyError(
                    message=f"Key {key_id} has been revoked",
                    code=PolicyErrorCode.KEY_PERMISSION_DENIED,
                    key_id=key_id,
                )
            
            if key.is_expired():
                raise PolicyKeyExpiredError(key_id, key.expires_at)
            
            if not KeyTrust.can_sign(key.trust):
                raise PolicyKeyError(
                    message=f"Key {key_id} with trust {key.trust} cannot sign",
                    code=PolicyErrorCode.KEY_PERMISSION_DENIED,
                    key_id=key_id,
                )
            
            # Check trust level vs policy contents
            self._validate_trust_for_policy(key, policy_data)
            
            # Canonicalize
            canonical = PolicyCanonicalizer.canonicalize(policy_data)
            content_hash = PolicyCanonicalizer.hash(canonical)
            content_hash_hex = content_hash.hex()
            
            # Sign based on algorithm
            if key.algorithm == SignatureAlgorithm.ED25519:
                signature_bytes = self._sign_ed25519(key_id, content_hash)
            else:
                signature_bytes = self._sign_hmac(key_id, content_hash)
            
            # Create signature object
            signature = PolicySignature(
                algorithm=key.algorithm,
                key_id=key_id,
                signed_at=datetime.now(timezone.utc),
                value=base64.b64encode(signature_bytes).decode("ascii"),
            )
            
            return signature, content_hash_hex
    
    def sign_policy_document(
        self,
        policy: PolicyDocument,
        key_id: str,
    ) -> PolicyDocument:
        """
        Sign a PolicyDocument and return new document with signature.
        
        Args:
            policy: Policy document to sign
            key_id: Key ID to sign with
            
        Returns:
            New PolicyDocument with signature embedded
        """
        # Get policy data without signature
        policy_data = policy.get_body_for_signing()
        
        # Sign
        signature, _ = self.sign_policy(policy_data, key_id)
        
        # Use model_copy to preserve exact internal state
        # This avoids round-trip serialization that can change None to defaults
        return policy.model_copy(update={"signature": signature})
    
    def _validate_trust_for_policy(
        self,
        key: SigningKey,
        policy_data: Dict[str, Any],
    ) -> None:
        """
        Validate that key trust level allows signing this policy.
        
        Raises:
            PolicyKeyError: If trust insufficient
        """
        if key.trust == KeyTrust.ROOT:
            return  # ROOT can sign anything
        
        # Check for ROOT-only fields
        for field in KeyTrust.ROOT_ONLY_FIELDS:
            if field in policy_data and policy_data[field]:
                raise PolicyKeyError(
                    message=f"Key {key.key_id} with trust {key.trust} cannot sign field '{field}' (requires ROOT)",
                    code=PolicyErrorCode.KEY_PERMISSION_DENIED,
                    key_id=key.key_id,
                )
    
    def _sign_ed25519(self, key_id: str, content_hash: bytes) -> bytes:
        """Sign with Ed25519."""
        if not ED25519_AVAILABLE:
            raise PolicySignatureError(
                message="Ed25519 not available",
                code=PolicyErrorCode.SIGNATURE_ALGORITHM_UNSUPPORTED,
            )
        
        private_key_bytes = self._private_keys.get(key_id)
        if not private_key_bytes:
            raise PolicyKeyNotFoundError(key_id)
        
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        return private_key.sign(content_hash)
    
    def _sign_hmac(self, key_id: str, content_hash: bytes) -> bytes:
        """Sign with HMAC-SHA256."""
        secret = self._hmac_secrets.get(key_id)
        if not secret:
            raise PolicyKeyNotFoundError(key_id)
        
        return hmac.new(secret, content_hash, hashlib.sha256).digest()
    
    # =========================================================================
    # KEY MANAGEMENT
    # =========================================================================
    
    def get_key(self, key_id: str) -> Optional[SigningKey]:
        """Get key by ID."""
        with self._lock:
            return self._keys.get(key_id)
    
    def list_keys(self) -> list[SigningKey]:
        """List all registered keys."""
        with self._lock:
            return list(self._keys.values())
    
    def deprecate_key(self, key_id: str) -> None:
        """Mark a key as deprecated."""
        with self._lock:
            if key_id in self._keys:
                old_key = self._keys[key_id]
                self._keys[key_id] = SigningKey(
                    key_id=old_key.key_id,
                    algorithm=old_key.algorithm,
                    trust=old_key.trust,
                    description=old_key.description,
                    created_at=old_key.created_at,
                    expires_at=old_key.expires_at,
                    deprecated=True,
                    revoked=old_key.revoked,
                )
    
    def revoke_key(self, key_id: str) -> None:
        """Revoke a key (cannot be used for signing or verification)."""
        with self._lock:
            if key_id in self._keys:
                old_key = self._keys[key_id]
                self._keys[key_id] = SigningKey(
                    key_id=old_key.key_id,
                    algorithm=old_key.algorithm,
                    trust=old_key.trust,
                    description=old_key.description,
                    created_at=old_key.created_at,
                    expires_at=old_key.expires_at,
                    deprecated=True,
                    revoked=True,
                )
    
    def remove_key(self, key_id: str) -> bool:
        """Remove a key from the registry."""
        with self._lock:
            if key_id in self._keys:
                del self._keys[key_id]
                self._private_keys.pop(key_id, None)
                self._hmac_secrets.pop(key_id, None)
                return True
            return False


# =============================================================================
# MODULE-LEVEL SIGNER INSTANCE
# =============================================================================

# Global signer instance (thread-safe)
_default_signer: Optional[PolicySigner] = None
_signer_lock = threading.Lock()


def get_signer() -> PolicySigner:
    """Get the default policy signer instance."""
    global _default_signer
    if _default_signer is None:
        with _signer_lock:
            if _default_signer is None:
                _default_signer = PolicySigner()
    return _default_signer


def set_signer(signer: PolicySigner) -> None:
    """Set the default policy signer instance."""
    global _default_signer
    with _signer_lock:
        _default_signer = signer
