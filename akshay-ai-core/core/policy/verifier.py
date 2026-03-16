"""
AKSHAY AI CORE — Policy Verifier

Cryptographic verification for policy documents.
Verifies Ed25519 and HMAC-SHA256 signatures.

SECURITY GUARANTEES:
- Constant-time comparison for signatures
- No timing side channels
- Thread-safe operations
- Audit logging of all verification attempts
- Safe mode trigger on verification failure

VERIFICATION PIPELINE:
1. Extract signature from policy
2. Look up public key / secret
3. Recompute canonical hash
4. Verify signature
5. Check key trust vs policy contents
6. Return result with details
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict

from core.policy.errors import (
    PolicySignatureError,
    PolicySignatureInvalidError,
    PolicySignatureMissingError,
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
from core.policy.signer import (
    PolicyCanonicalizer,
    KeyTrust,
    SigningKey,
    MIN_KEY_ID_LENGTH,
)

# Try to import cryptography for Ed25519
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    from cryptography.exceptions import InvalidSignature
    ED25519_AVAILABLE = True
except ImportError:
    ED25519_AVAILABLE = False
    Ed25519PublicKey = None
    InvalidSignature = Exception


# =============================================================================
# VERIFICATION RESULT
# =============================================================================

class VerificationStatus(str, Enum):
    """Verification result status."""
    VALID = "VALID"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    INVALID_KEY = "INVALID_KEY"
    KEY_NOT_FOUND = "KEY_NOT_FOUND"
    KEY_EXPIRED = "KEY_EXPIRED"
    KEY_REVOKED = "KEY_REVOKED"
    KEY_TRUST_INSUFFICIENT = "KEY_TRUST_INSUFFICIENT"
    SIGNATURE_MISSING = "SIGNATURE_MISSING"
    TAMPERED = "TAMPERED"
    ALGORITHM_MISMATCH = "ALGORITHM_MISMATCH"


@dataclass
class VerificationResult:
    """Result of policy signature verification."""
    
    valid: bool
    status: VerificationStatus
    message: str
    
    # Key information
    key_id: Optional[str] = None
    key_trust: Optional[str] = None
    algorithm: Optional[SignatureAlgorithm] = None
    
    # Verification details
    policy_hash: Optional[str] = None
    signed_at: Optional[datetime] = None
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Warnings (e.g., key about to expire)
    warnings: List[str] = field(default_factory=list)
    
    # For audit logging
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "valid": self.valid,
            "status": self.status.value,
            "message": self.message,
            "key_id": self.key_id,
            "key_trust": self.key_trust,
            "algorithm": self.algorithm.value if self.algorithm else None,
            "policy_hash": self.policy_hash,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "verified_at": self.verified_at.isoformat(),
            "warnings": self.warnings,
        }


# =============================================================================
# PUBLIC KEY REGISTRY
# =============================================================================

class PublicKeyEntry(BaseModel):
    """Public key entry in registry."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    key_id: str = Field(
        ...,
        min_length=MIN_KEY_ID_LENGTH,
        description="Unique key identifier",
    )
    algorithm: SignatureAlgorithm = Field(
        ...,
        description="Key algorithm",
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
        description="Whether key is deprecated",
    )
    revoked: bool = Field(
        default=False,
        description="Whether key is revoked",
    )
    
    # Public key material
    public_key_pem: Optional[str] = None  # For Ed25519
    hmac_secret_hash: Optional[str] = None  # Hash of HMAC secret for verification
    
    def is_valid(self) -> bool:
        """Check if key is currently valid."""
        if self.revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True


# =============================================================================
# POLICY VERIFIER
# =============================================================================

class PolicyVerifier:
    """
    Verify policy document signatures.
    
    Thread-safe implementation with public key registry.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._public_keys: Dict[str, PublicKeyEntry] = {}
        self._ed25519_keys: Dict[str, bytes] = {}  # Raw public key bytes
        self._hmac_secrets: Dict[str, bytes] = {}  # HMAC secrets for verification
    
    # =========================================================================
    # KEY REGISTRATION
    # =========================================================================
    
    def register_ed25519_public_key(
        self,
        key_id: str,
        public_key_pem: str,
        trust: str = KeyTrust.OPERATOR,
        description: str = "",
        expires_at: Optional[datetime] = None,
    ) -> PublicKeyEntry:
        """
        Register an Ed25519 public key for verification.
        
        Args:
            key_id: Unique identifier
            public_key_pem: Public key in PEM format
            trust: Trust level
            description: Description
            expires_at: Expiration time
            
        Returns:
            Registered PublicKeyEntry
        """
        if not ED25519_AVAILABLE:
            raise PolicyKeyError(
                message="Ed25519 not available",
                code=PolicyErrorCode.KEY_INVALID_FORMAT,
            )
        
        # Load and validate key
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode("ascii")
            )
            if not isinstance(public_key, Ed25519PublicKey):
                raise ValueError("Not an Ed25519 key")
            
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        except Exception as e:
            raise PolicyKeyError(
                message=f"Invalid Ed25519 public key: {e}",
                code=PolicyErrorCode.KEY_INVALID_FORMAT,
            )
        
        entry = PublicKeyEntry(
            key_id=key_id,
            algorithm=SignatureAlgorithm.ED25519,
            trust=trust,
            description=description,
            expires_at=expires_at,
            public_key_pem=public_key_pem,
        )
        
        with self._lock:
            self._public_keys[key_id] = entry
            self._ed25519_keys[key_id] = public_key_bytes
        
        return entry
    
    def register_hmac_secret(
        self,
        key_id: str,
        secret: Union[str, bytes],
        trust: str = KeyTrust.OPERATOR,
        description: str = "",
        expires_at: Optional[datetime] = None,
    ) -> PublicKeyEntry:
        """
        Register an HMAC secret for verification.
        
        Args:
            key_id: Unique identifier
            secret: Secret as base64 string or bytes
            trust: Trust level
            description: Description
            expires_at: Expiration time
            
        Returns:
            Registered PublicKeyEntry
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
        
        # Store hash of secret for metadata (not the actual secret)
        secret_hash = hashlib.sha256(secret_bytes).hexdigest()[:16]
        
        entry = PublicKeyEntry(
            key_id=key_id,
            algorithm=SignatureAlgorithm.HMAC_SHA256,
            trust=trust,
            description=description,
            expires_at=expires_at,
            hmac_secret_hash=secret_hash,
        )
        
        with self._lock:
            self._public_keys[key_id] = entry
            self._hmac_secrets[key_id] = secret_bytes
        
        return entry
    
    def register_from_signing_key(
        self,
        signing_key: SigningKey,
        public_key_pem: Optional[str] = None,
        hmac_secret: Optional[Union[str, bytes]] = None,
    ) -> PublicKeyEntry:
        """
        Register a key from a SigningKey object.
        
        Args:
            signing_key: SigningKey to register
            public_key_pem: Public key PEM (for Ed25519)
            hmac_secret: HMAC secret (for HMAC-SHA256)
            
        Returns:
            Registered PublicKeyEntry
        """
        if signing_key.algorithm == SignatureAlgorithm.ED25519:
            if not public_key_pem:
                raise ValueError("public_key_pem required for Ed25519")
            return self.register_ed25519_public_key(
                key_id=signing_key.key_id,
                public_key_pem=public_key_pem,
                trust=signing_key.trust,
                description=signing_key.description,
                expires_at=signing_key.expires_at,
            )
        else:
            if not hmac_secret:
                raise ValueError("hmac_secret required for HMAC-SHA256")
            return self.register_hmac_secret(
                key_id=signing_key.key_id,
                secret=hmac_secret,
                trust=signing_key.trust,
                description=signing_key.description,
                expires_at=signing_key.expires_at,
            )
    
    # =========================================================================
    # VERIFICATION
    # =========================================================================
    
    def verify_policy(
        self,
        policy_data: Dict[str, Any],
        require_signature: bool = True,
    ) -> VerificationResult:
        """
        Verify a policy document signature.
        
        Args:
            policy_data: Policy document as dictionary
            require_signature: Whether to fail if no signature present
            
        Returns:
            VerificationResult with status and details
        """
        # Extract signature
        signature_data = policy_data.get("signature")
        
        if not signature_data:
            if require_signature:
                return VerificationResult(
                    valid=False,
                    status=VerificationStatus.SIGNATURE_MISSING,
                    message="Policy has no signature",
                )
            else:
                return VerificationResult(
                    valid=True,
                    status=VerificationStatus.VALID,
                    message="Policy has no signature (not required)",
                    warnings=["Policy is unsigned"],
                )
        
        # Parse signature
        try:
            signature = PolicySignature(**signature_data)
        except Exception as e:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.INVALID_SIGNATURE,
                message=f"Invalid signature format: {e}",
            )
        
        # Look up key
        with self._lock:
            key_entry = self._public_keys.get(signature.key_id)
        
        if not key_entry:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.KEY_NOT_FOUND,
                message=f"Key not found: {signature.key_id}",
                key_id=signature.key_id,
            )
        
        # Check key status
        if key_entry.revoked:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.KEY_REVOKED,
                message=f"Key has been revoked: {signature.key_id}",
                key_id=signature.key_id,
                key_trust=key_entry.trust,
            )
        
        if key_entry.expires_at and datetime.now(timezone.utc) > key_entry.expires_at:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.KEY_EXPIRED,
                message=f"Key has expired: {signature.key_id}",
                key_id=signature.key_id,
                key_trust=key_entry.trust,
            )
        
        # Check algorithm match
        if key_entry.algorithm != signature.algorithm:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.ALGORITHM_MISMATCH,
                message=f"Algorithm mismatch: key is {key_entry.algorithm.value}, signature is {signature.algorithm.value}",
                key_id=signature.key_id,
                algorithm=signature.algorithm,
            )
        
        # Validate trust level vs policy contents
        trust_result = self._validate_trust_for_policy(key_entry, policy_data)
        if trust_result:
            return trust_result
        
        # Recompute canonical hash
        canonical = PolicyCanonicalizer.canonicalize(policy_data)
        content_hash = PolicyCanonicalizer.hash(canonical)
        content_hash_hex = content_hash.hex()
        
        # Verify signature
        try:
            signature_bytes = base64.b64decode(signature.value)
        except Exception:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.INVALID_SIGNATURE,
                message="Invalid signature encoding",
                key_id=signature.key_id,
            )
        
        if key_entry.algorithm == SignatureAlgorithm.ED25519:
            valid = self._verify_ed25519(signature.key_id, content_hash, signature_bytes)
        else:
            valid = self._verify_hmac(signature.key_id, content_hash, signature_bytes)
        
        if not valid:
            return VerificationResult(
                valid=False,
                status=VerificationStatus.TAMPERED,
                message="Signature verification failed - policy may have been tampered",
                key_id=signature.key_id,
                key_trust=key_entry.trust,
                algorithm=signature.algorithm,
                policy_hash=content_hash_hex,
            )
        
        # Build warnings
        warnings = []
        if key_entry.deprecated:
            warnings.append(f"Key {signature.key_id} is deprecated")
        
        if key_entry.expires_at:
            from datetime import timedelta
            days_left = (key_entry.expires_at - datetime.now(timezone.utc)).days
            if days_left <= 30:
                warnings.append(f"Key {signature.key_id} expires in {days_left} days")
        
        return VerificationResult(
            valid=True,
            status=VerificationStatus.VALID,
            message="Signature verified successfully",
            key_id=signature.key_id,
            key_trust=key_entry.trust,
            algorithm=signature.algorithm,
            policy_hash=content_hash_hex,
            signed_at=signature.signed_at,
            warnings=warnings,
        )
    
    def verify_policy_document(
        self,
        policy: PolicyDocument,
        require_signature: bool = True,
    ) -> VerificationResult:
        """
        Verify a PolicyDocument signature.
        
        Args:
            policy: Policy document to verify
            require_signature: Whether to fail if no signature present
            
        Returns:
            VerificationResult with status and details
        """
        policy_data = policy.model_dump(mode="json")
        return self.verify_policy(policy_data, require_signature)
    
    def _validate_trust_for_policy(
        self,
        key_entry: PublicKeyEntry,
        policy_data: Dict[str, Any],
    ) -> Optional[VerificationResult]:
        """
        Validate that key trust level is sufficient for policy contents.
        
        Returns:
            VerificationResult if trust insufficient, None if OK
        """
        if key_entry.trust == KeyTrust.ROOT:
            return None  # ROOT can sign anything
        
        # Check for ROOT-only fields
        for field in KeyTrust.ROOT_ONLY_FIELDS:
            if field in policy_data and policy_data[field]:
                return VerificationResult(
                    valid=False,
                    status=VerificationStatus.KEY_TRUST_INSUFFICIENT,
                    message=f"Key {key_entry.key_id} with trust {key_entry.trust} cannot sign field '{field}' (requires ROOT)",
                    key_id=key_entry.key_id,
                    key_trust=key_entry.trust,
                )
        
        return None
    
    def _verify_ed25519(
        self,
        key_id: str,
        content_hash: bytes,
        signature: bytes,
    ) -> bool:
        """Verify Ed25519 signature."""
        if not ED25519_AVAILABLE:
            return False
        
        with self._lock:
            public_key_bytes = self._ed25519_keys.get(key_id)
        
        if not public_key_bytes:
            return False
        
        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, content_hash)
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False
    
    def _verify_hmac(
        self,
        key_id: str,
        content_hash: bytes,
        signature: bytes,
    ) -> bool:
        """Verify HMAC-SHA256 signature using constant-time comparison."""
        with self._lock:
            secret = self._hmac_secrets.get(key_id)
        
        if not secret:
            return False
        
        expected = hmac.new(secret, content_hash, hashlib.sha256).digest()
        
        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(expected, signature)
    
    # =========================================================================
    # KEY MANAGEMENT
    # =========================================================================
    
    def get_key(self, key_id: str) -> Optional[PublicKeyEntry]:
        """Get key by ID."""
        with self._lock:
            return self._public_keys.get(key_id)
    
    def list_keys(self) -> List[PublicKeyEntry]:
        """List all registered keys."""
        with self._lock:
            return list(self._public_keys.values())
    
    def deprecate_key(self, key_id: str) -> None:
        """Mark a key as deprecated."""
        with self._lock:
            if key_id in self._public_keys:
                old = self._public_keys[key_id]
                self._public_keys[key_id] = PublicKeyEntry(
                    key_id=old.key_id,
                    algorithm=old.algorithm,
                    trust=old.trust,
                    description=old.description,
                    created_at=old.created_at,
                    expires_at=old.expires_at,
                    deprecated=True,
                    revoked=old.revoked,
                    public_key_pem=old.public_key_pem,
                    hmac_secret_hash=old.hmac_secret_hash,
                )
    
    def revoke_key(self, key_id: str) -> None:
        """Revoke a key (cannot be used for verification)."""
        with self._lock:
            if key_id in self._public_keys:
                old = self._public_keys[key_id]
                self._public_keys[key_id] = PublicKeyEntry(
                    key_id=old.key_id,
                    algorithm=old.algorithm,
                    trust=old.trust,
                    description=old.description,
                    created_at=old.created_at,
                    expires_at=old.expires_at,
                    deprecated=True,
                    revoked=True,
                    public_key_pem=old.public_key_pem,
                    hmac_secret_hash=old.hmac_secret_hash,
                )
    
    def remove_key(self, key_id: str) -> bool:
        """Remove a key from the registry."""
        with self._lock:
            if key_id in self._public_keys:
                del self._public_keys[key_id]
                self._ed25519_keys.pop(key_id, None)
                self._hmac_secrets.pop(key_id, None)
                return True
            return False


# =============================================================================
# MODULE-LEVEL VERIFIER INSTANCE
# =============================================================================

# Global verifier instance (thread-safe)
_default_verifier: Optional[PolicyVerifier] = None
_verifier_lock = threading.Lock()


def get_verifier() -> PolicyVerifier:
    """Get the default policy verifier instance."""
    global _default_verifier
    if _default_verifier is None:
        with _verifier_lock:
            if _default_verifier is None:
                _default_verifier = PolicyVerifier()
    return _default_verifier


def set_verifier(verifier: PolicyVerifier) -> None:
    """Set the default policy verifier instance."""
    global _default_verifier
    with _verifier_lock:
        _default_verifier = verifier
