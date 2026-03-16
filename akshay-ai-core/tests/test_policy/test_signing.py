"""
AKSHAY AI CORE — Signing & Verification Tests

Comprehensive tests for:
- Policy canonicalization
- Key generation (Ed25519, HMAC)
- Signing operations
- Signature verification
- Tamper detection
- Key trust validation
- Key lifecycle (expiry, deprecation, revocation)
- Thread safety

NO MOCKS. Real cryptographic operations.
"""

import base64
import hashlib
import json
import pytest
import secrets
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from core.policy.schema import (
    SignatureAlgorithm,
    PolicyDocument,
    PolicyMetadata,
    PolicySignature,
    PolicyRule,
    RuleMatch,
    RuleAction,
    ActionType,
    TrustZone,
    Allowlist,
)
from core.policy.signer import (
    PolicySigner,
    PolicyCanonicalizer,
    KeyTrust,
    SigningKey,
    KeyPair,
    HMACKey,
    ED25519_AVAILABLE,
)
from core.policy.verifier import (
    PolicyVerifier,
    VerificationResult,
    VerificationStatus,
    PublicKeyEntry,
)
from core.policy.errors import (
    PolicyKeyNotFoundError,
    PolicyKeyExpiredError,
    PolicyKeyError,
    PolicySignatureError,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def signer() -> PolicySigner:
    """Fresh policy signer instance."""
    return PolicySigner()


@pytest.fixture
def verifier() -> PolicyVerifier:
    """Fresh policy verifier instance."""
    return PolicyVerifier()


@pytest.fixture
def minimal_policy_data() -> Dict[str, Any]:
    """Minimal valid policy data."""
    return {
        "apiVersion": "policy.akshay.ai/v1",
        "kind": "PolicyDocument",
        "metadata": {
            "name": "test-policy",
            "version": "1.0.0",
            "description": "Test policy",
            "author": "test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "zones": [],
        "allowlists": {},
        "rules": [
            {
                "id": "DENY-001",
                "priority": 0,
                "match": {"any": True},
                "action": {"type": "DENY"},
            }
        ],
    }


@pytest.fixture
def full_policy_data() -> Dict[str, Any]:
    """Full policy data with all fields."""
    return {
        "apiVersion": "policy.akshay.ai/v1",
        "kind": "PolicyDocument",
        "metadata": {
            "name": "full-policy",
            "version": "1.0.0",
            "description": "Full test policy",
            "author": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "inherits": "base-policy",
        },
        "zones": [
            {"name": "AI_CORE", "trust_level": 0},
            {"name": "USER", "trust_level": 2},
        ],
        "allowlists": {
            "web_domains": {
                "type": "domain",
                "entries": ["github.com", "google.com"],
            }
        },
        "rules": [
            {
                "id": "DENY-001",
                "priority": 0,
                "match": {"any": True},
                "action": {"type": "DENY"},
            },
            {
                "id": "ALLOW-001",
                "priority": 100,
                "match": {"tool": "web"},
                "action": {"type": "ALLOW"},
            },
        ],
        "failure_mode": {
            "default_action": "DENY",
            "safe_mode": {
                "allowed_actions": ["system.status"],
                "blocked_actions": ["*"],
            },
        },
    }


# =============================================================================
# CANONICALIZATION TESTS
# =============================================================================

class TestPolicyCanonicalizer:
    """Tests for deterministic canonicalization."""
    
    def test_canonicalize_deterministic(self, minimal_policy_data):
        """Same input should always produce same output."""
        result1 = PolicyCanonicalizer.canonicalize(minimal_policy_data)
        result2 = PolicyCanonicalizer.canonicalize(minimal_policy_data)
        assert result1 == result2
    
    def test_canonicalize_removes_signature(self, minimal_policy_data):
        """Signature block should be removed before canonicalization."""
        minimal_policy_data["signature"] = {
            "algorithm": "ed25519",
            "key_id": "test",
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "value": "fake_signature",
        }
        
        result = PolicyCanonicalizer.canonicalize(minimal_policy_data)
        assert b"signature" not in result
        assert b"fake_signature" not in result
    
    def test_canonicalize_sorts_keys(self):
        """Dictionary keys should be sorted."""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}
        
        result1 = PolicyCanonicalizer.canonicalize(data1)
        result2 = PolicyCanonicalizer.canonicalize(data2)
        
        assert result1 == result2
        # Verify order in output
        decoded = result1.decode("utf-8")
        assert decoded.index('"a"') < decoded.index('"m"') < decoded.index('"z"')
    
    def test_canonicalize_nested_sorts(self):
        """Nested dictionaries should also be sorted."""
        data = {
            "outer": {
                "z_inner": 1,
                "a_inner": 2,
            }
        }
        
        result = PolicyCanonicalizer.canonicalize(data)
        decoded = result.decode("utf-8")
        assert decoded.index('"a_inner"') < decoded.index('"z_inner"')
    
    def test_canonicalize_compact_json(self, minimal_policy_data):
        """Output should be compact JSON (no extra whitespace)."""
        result = PolicyCanonicalizer.canonicalize(minimal_policy_data)
        decoded = result.decode("utf-8")
        
        # No pretty-printing whitespace
        assert "\n" not in decoded
        assert ": " not in decoded  # Compact uses ":" not ": "
    
    def test_hash_consistency(self, minimal_policy_data):
        """Hash should be consistent for same input."""
        canonical = PolicyCanonicalizer.canonicalize(minimal_policy_data)
        
        hash1 = PolicyCanonicalizer.hash(canonical)
        hash2 = PolicyCanonicalizer.hash(canonical)
        
        assert hash1 == hash2
        assert len(hash1) == 32  # SHA-256 = 32 bytes
    
    def test_hash_hex_format(self, minimal_policy_data):
        """Hash hex should be 64 characters."""
        canonical = PolicyCanonicalizer.canonicalize(minimal_policy_data)
        hash_hex = PolicyCanonicalizer.hash_hex(canonical)
        
        assert len(hash_hex) == 64
        assert all(c in "0123456789abcdef" for c in hash_hex)


# =============================================================================
# KEY GENERATION TESTS
# =============================================================================

class TestKeyGeneration:
    """Tests for key generation."""
    
    def test_generate_hmac_key(self, signer):
        """HMAC key generation should work."""
        key = signer.generate_hmac_key(
            key_id="test_hmac_key",
            trust=KeyTrust.OPERATOR,
            description="Test HMAC key",
        )
        
        assert key.key_id == "test_hmac_key"
        assert key.algorithm == SignatureAlgorithm.HMAC_SHA256
        assert len(base64.b64decode(key.secret_base64)) == 32
    
    def test_hmac_key_registered(self, signer):
        """Generated HMAC key should be registered in signer."""
        key = signer.generate_hmac_key(key_id="registered_key")
        
        signing_key = signer.get_key("registered_key")
        assert signing_key is not None
        assert signing_key.algorithm == SignatureAlgorithm.HMAC_SHA256
    
    @pytest.mark.skipif(not ED25519_AVAILABLE, reason="cryptography not installed")
    def test_generate_ed25519_keypair(self, signer):
        """Ed25519 key generation should work."""
        keypair = signer.generate_ed25519_keypair(
            key_id="test_ed25519_key",
            trust=KeyTrust.ROOT,
            description="Test Ed25519 key",
        )
        
        assert keypair.key_id == "test_ed25519_key"
        assert keypair.algorithm == SignatureAlgorithm.ED25519
        assert "BEGIN PUBLIC KEY" in keypair.public_key_pem
        assert "BEGIN PRIVATE KEY" in keypair.private_key_pem
    
    @pytest.mark.skipif(not ED25519_AVAILABLE, reason="cryptography not installed")
    def test_ed25519_key_registered(self, signer):
        """Generated Ed25519 key should be registered in signer."""
        keypair = signer.generate_ed25519_keypair(key_id="registered_ed25519")
        
        signing_key = signer.get_key("registered_ed25519")
        assert signing_key is not None
        assert signing_key.algorithm == SignatureAlgorithm.ED25519
    
    def test_key_expiry(self, signer):
        """Key expiry should be set correctly."""
        key = signer.generate_hmac_key(
            key_id="expiring_key",
            expires_in_days=30,
        )
        
        signing_key = signer.get_key("expiring_key")
        assert signing_key.expires_at is not None
        
        days_left = signing_key.days_until_expiry()
        assert 29 <= days_left <= 30


# =============================================================================
# SIGNING TESTS
# =============================================================================

class TestSigning:
    """Tests for policy signing."""
    
    def test_sign_with_hmac(self, signer, minimal_policy_data):
        """Signing with HMAC should produce valid signature."""
        signer.generate_hmac_key(key_id="hmac_sign_key", trust=KeyTrust.OPERATOR)
        
        signature, content_hash = signer.sign_policy(
            minimal_policy_data,
            key_id="hmac_sign_key",
        )
        
        assert signature.algorithm == SignatureAlgorithm.HMAC_SHA256
        assert signature.key_id == "hmac_sign_key"
        assert len(base64.b64decode(signature.value)) == 32  # HMAC-SHA256
        assert len(content_hash) == 64  # Hex SHA-256
    
    @pytest.mark.skipif(not ED25519_AVAILABLE, reason="cryptography not installed")
    def test_sign_with_ed25519(self, signer, minimal_policy_data):
        """Signing with Ed25519 should produce valid signature."""
        signer.generate_ed25519_keypair(key_id="ed25519_sign_key", trust=KeyTrust.ROOT)
        
        signature, content_hash = signer.sign_policy(
            minimal_policy_data,
            key_id="ed25519_sign_key",
        )
        
        assert signature.algorithm == SignatureAlgorithm.ED25519
        assert signature.key_id == "ed25519_sign_key"
        assert len(base64.b64decode(signature.value)) == 64  # Ed25519 signature
    
    def test_sign_unknown_key_fails(self, signer, minimal_policy_data):
        """Signing with unknown key should fail."""
        with pytest.raises(PolicyKeyNotFoundError):
            signer.sign_policy(minimal_policy_data, key_id="nonexistent_key")
    
    def test_sign_expired_key_fails(self, signer, minimal_policy_data):
        """Signing with expired key should fail."""
        # Create key that's already expired
        signer.generate_hmac_key(
            key_id="expired_key",
            expires_in_days=-1,  # Already expired
        )
        
        with pytest.raises(PolicyKeyExpiredError):
            signer.sign_policy(minimal_policy_data, key_id="expired_key")
    
    def test_sign_revoked_key_fails(self, signer, minimal_policy_data):
        """Signing with revoked key should fail."""
        signer.generate_hmac_key(key_id="revoked_key")
        signer.revoke_key("revoked_key")
        
        with pytest.raises(PolicyKeyError):
            signer.sign_policy(minimal_policy_data, key_id="revoked_key")
    
    def test_sign_audit_key_fails(self, signer, minimal_policy_data):
        """AUDIT keys cannot sign."""
        signer.generate_hmac_key(key_id="audit_key", trust=KeyTrust.AUDIT)
        
        with pytest.raises(PolicyKeyError, match="cannot sign"):
            signer.sign_policy(minimal_policy_data, key_id="audit_key")


# =============================================================================
# KEY TRUST TESTS
# =============================================================================

class TestKeyTrust:
    """Tests for key trust level enforcement."""
    
    def test_root_can_sign_all_fields(self, signer, full_policy_data):
        """ROOT keys can sign policies with all fields."""
        signer.generate_hmac_key(key_id="root_key", trust=KeyTrust.ROOT)
        
        # Should succeed - ROOT can sign everything
        signature, _ = signer.sign_policy(full_policy_data, key_id="root_key")
        assert signature is not None
    
    def test_operator_cannot_sign_root_fields(self, signer, full_policy_data):
        """OPERATOR keys cannot sign ROOT-only fields."""
        signer.generate_hmac_key(key_id="operator_key", trust=KeyTrust.OPERATOR)
        
        # full_policy_data has zones, allowlists, failure_mode - all ROOT-only
        with pytest.raises(PolicyKeyError, match="requires ROOT"):
            signer.sign_policy(full_policy_data, key_id="operator_key")
    
    def test_operator_can_sign_rules_only(self, signer, minimal_policy_data):
        """OPERATOR keys can sign policies with only rules."""
        signer.generate_hmac_key(key_id="operator_key", trust=KeyTrust.OPERATOR)
        
        # minimal_policy_data has no ROOT-only fields
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="operator_key")
        assert signature is not None


# =============================================================================
# VERIFICATION TESTS
# =============================================================================

class TestVerification:
    """Tests for signature verification."""
    
    def test_verify_valid_hmac_signature(self, signer, verifier, minimal_policy_data):
        """Valid HMAC signature should verify."""
        # Generate and sign
        hmac_key = signer.generate_hmac_key(key_id="verify_hmac", trust=KeyTrust.OPERATOR)
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="verify_hmac")
        
        # Register key in verifier
        verifier.register_hmac_secret(
            key_id="verify_hmac",
            secret=hmac_key.secret_base64,
            trust=KeyTrust.OPERATOR,
        )
        
        # Add signature to policy
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        # Verify
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is True
        assert result.status == VerificationStatus.VALID
        assert result.key_id == "verify_hmac"
    
    @pytest.mark.skipif(not ED25519_AVAILABLE, reason="cryptography not installed")
    def test_verify_valid_ed25519_signature(self, signer, verifier, minimal_policy_data):
        """Valid Ed25519 signature should verify."""
        # Generate and sign
        keypair = signer.generate_ed25519_keypair(key_id="verify_ed25519", trust=KeyTrust.ROOT)
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="verify_ed25519")
        
        # Register public key in verifier
        verifier.register_ed25519_public_key(
            key_id="verify_ed25519",
            public_key_pem=keypair.public_key_pem,
            trust=KeyTrust.ROOT,
        )
        
        # Add signature to policy
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        # Verify
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is True
        assert result.status == VerificationStatus.VALID
    
    def test_verify_missing_signature(self, verifier, minimal_policy_data):
        """Missing signature should fail verification."""
        result = verifier.verify_policy(minimal_policy_data, require_signature=True)
        
        assert result.valid is False
        assert result.status == VerificationStatus.SIGNATURE_MISSING
    
    def test_verify_unknown_key(self, signer, verifier, minimal_policy_data):
        """Signature with unknown key should fail."""
        hmac_key = signer.generate_hmac_key(key_id="unknown_key")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="unknown_key")
        
        # Don't register key in verifier
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.KEY_NOT_FOUND
    
    def test_verify_expired_key(self, signer, verifier, minimal_policy_data):
        """Signature with expired key should fail."""
        hmac_key = signer.generate_hmac_key(key_id="expiring_verify")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="expiring_verify")
        
        # Register key as already expired
        verifier.register_hmac_secret(
            key_id="expiring_verify",
            secret=hmac_key.secret_base64,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.KEY_EXPIRED
    
    def test_verify_revoked_key(self, signer, verifier, minimal_policy_data):
        """Signature with revoked key should fail."""
        hmac_key = signer.generate_hmac_key(key_id="revoke_verify")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="revoke_verify")
        
        verifier.register_hmac_secret(
            key_id="revoke_verify",
            secret=hmac_key.secret_base64,
        )
        verifier.revoke_key("revoke_verify")
        
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.KEY_REVOKED


# =============================================================================
# TAMPER DETECTION TESTS
# =============================================================================

class TestTamperDetection:
    """Tests for detecting policy tampering."""
    
    def test_detect_modified_rule(self, signer, verifier, minimal_policy_data):
        """Modifying a rule should be detected."""
        hmac_key = signer.generate_hmac_key(key_id="tamper_test")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="tamper_test")
        
        verifier.register_hmac_secret(
            key_id="tamper_test",
            secret=hmac_key.secret_base64,
        )
        
        # Sign and embed
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        # Tamper with rule
        minimal_policy_data["rules"][0]["action"]["type"] = "ALLOW"
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.TAMPERED
    
    def test_detect_added_rule(self, signer, verifier, minimal_policy_data):
        """Adding a rule should be detected."""
        hmac_key = signer.generate_hmac_key(key_id="tamper_add")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="tamper_add")
        
        verifier.register_hmac_secret(
            key_id="tamper_add",
            secret=hmac_key.secret_base64,
        )
        
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        # Add new rule
        minimal_policy_data["rules"].append({
            "id": "EVIL-001",
            "priority": 1000,
            "match": {"any": True},
            "action": {"type": "ALLOW"},
        })
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.TAMPERED
    
    def test_detect_removed_rule(self, signer, verifier, full_policy_data):
        """Removing a rule should be detected."""
        hmac_key = signer.generate_hmac_key(key_id="tamper_remove", trust=KeyTrust.ROOT)
        signature, _ = signer.sign_policy(full_policy_data, key_id="tamper_remove")
        
        verifier.register_hmac_secret(
            key_id="tamper_remove",
            secret=hmac_key.secret_base64,
            trust=KeyTrust.ROOT,
        )
        
        full_policy_data["signature"] = signature.model_dump(mode="json")
        
        # Remove a rule
        full_policy_data["rules"].pop()
        
        result = verifier.verify_policy(full_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.TAMPERED
    
    def test_detect_modified_metadata(self, signer, verifier, minimal_policy_data):
        """Modifying metadata should be detected."""
        hmac_key = signer.generate_hmac_key(key_id="tamper_meta")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="tamper_meta")
        
        verifier.register_hmac_secret(
            key_id="tamper_meta",
            secret=hmac_key.secret_base64,
        )
        
        minimal_policy_data["signature"] = signature.model_dump(mode="json")
        
        # Tamper with metadata
        minimal_policy_data["metadata"]["version"] = "9.9.9"
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.TAMPERED
    
    def test_detect_corrupted_signature(self, signer, verifier, minimal_policy_data):
        """Corrupted signature should be detected."""
        hmac_key = signer.generate_hmac_key(key_id="corrupt_sig")
        signature, _ = signer.sign_policy(minimal_policy_data, key_id="corrupt_sig")
        
        verifier.register_hmac_secret(
            key_id="corrupt_sig",
            secret=hmac_key.secret_base64,
        )
        
        # Corrupt the signature
        sig_data = signature.model_dump(mode="json")
        sig_bytes = base64.b64decode(sig_data["value"])
        corrupted = bytes([b ^ 0xFF for b in sig_bytes])  # Flip all bits
        sig_data["value"] = base64.b64encode(corrupted).decode()
        
        minimal_policy_data["signature"] = sig_data
        
        result = verifier.verify_policy(minimal_policy_data)
        
        assert result.valid is False
        assert result.status == VerificationStatus.TAMPERED


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================

class TestThreadSafety:
    """Tests for thread-safe operations."""
    
    def test_concurrent_signing(self, signer, minimal_policy_data):
        """Multiple threads can sign concurrently."""
        signer.generate_hmac_key(key_id="concurrent_key")
        
        results = []
        errors = []
        
        def sign_policy():
            try:
                sig, _ = signer.sign_policy(minimal_policy_data, key_id="concurrent_key")
                results.append(sig)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=sign_policy) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 10
        
        # All signatures should be identical (same input)
        sig_values = [r.value for r in results]
        assert len(set(sig_values)) == 1
    
    def test_concurrent_key_operations(self, signer):
        """Multiple threads can manage keys concurrently."""
        errors = []
        
        def key_operations(thread_id: int):
            try:
                key_id = f"thread_key_{thread_id}"
                signer.generate_hmac_key(key_id=key_id)
                signer.get_key(key_id)
                signer.deprecate_key(key_id)
                signer.list_keys()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=key_operations, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


# =============================================================================
# POLICY DOCUMENT TESTS
# =============================================================================

class TestPolicyDocumentSigning:
    """Tests for signing PolicyDocument objects."""
    
    def test_sign_policy_document(self, signer):
        """PolicyDocument can be signed and returns new document."""
        policy = PolicyDocument(
            metadata=PolicyMetadata(name="doc-test", version="1.0.0"),
            rules=[
                PolicyRule(
                    id="TEST-001",
                    priority=0,
                    match=RuleMatch(any=True),
                    action=RuleAction(type=ActionType.DENY),
                )
            ],
        )
        
        # Use ROOT trust because PolicyDocument has default failure_mode field
        signer.generate_hmac_key(key_id="doc_key_test", trust=KeyTrust.ROOT)
        signed_policy = signer.sign_policy_document(policy, key_id="doc_key_test")
        
        assert signed_policy.signature is not None
        assert signed_policy.signature.key_id == "doc_key_test"
        
        # Original should be unchanged
        assert policy.signature is None
    
    def test_verify_policy_document(self, signer, verifier):
        """Signed PolicyDocument can be verified."""
        policy = PolicyDocument(
            metadata=PolicyMetadata(name="verify-doc", version="1.0.0"),
            rules=[
                PolicyRule(
                    id="TEST-001",
                    priority=0,
                    match=RuleMatch(any=True),
                    action=RuleAction(type=ActionType.DENY),
                )
            ],
        )
        
        # Use ROOT trust since PolicyDocument has default failure_mode
        hmac_key = signer.generate_hmac_key(key_id="verify_doc_key", trust=KeyTrust.ROOT)
        signed_policy = signer.sign_policy_document(policy, key_id="verify_doc_key")
        
        verifier.register_hmac_secret(
            key_id="verify_doc_key",
            secret=hmac_key.secret_base64,
            trust=KeyTrust.ROOT,
        )
        
        result = verifier.verify_policy_document(signed_policy)
        
        assert result.valid is True, f"Verification failed: {result.status} - {result.message}"
        assert result.status == VerificationStatus.VALID


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
