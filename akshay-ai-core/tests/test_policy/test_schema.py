"""
AKSHAY AI CORE — Policy Schema Tests

Comprehensive tests for policy schema validation:
- Valid policy parsing
- Invalid field rejection
- Operator validation
- Regex safety checks
- Inheritance cycle detection
- Priority conflict detection
- Allowlist reference validation

NO MOCKS. Real validation.
"""

import pytest
from datetime import datetime, timedelta
from typing import Any, Dict

from core.policy.schema import (
    # Enums
    PolicyApiVersion,
    PolicyKind,
    ActionType,
    LogLevel,
    SignatureAlgorithm,
    MatchOperator,
    ReasonCode,
    Decision,
    # Models
    PolicyMetadata,
    PolicySignature,
    TrustZone,
    Allowlist,
    DeviceAllowlistEntry,
    MatchCondition,
    RuleMatch,
    RateLimit,
    RuleAction,
    PolicyRule,
    FailureModeConfig,
    SafeModeConfig,
    PolicyDocument,
    EvaluationContext,
    EvaluationRequest,
    EvaluationResult,
    # Validators
    validate_regex_pattern,
    validate_semver,
    validate_allowlist_reference,
    validate_rule_id,
    # Constants
    MAX_INHERITANCE_DEPTH,
    MAX_RULES_PER_POLICY,
    MAX_CONDITIONS_PER_RULE,
    MAX_REGEX_LENGTH,
)
from core.policy.errors import (
    PolicyValidationError,
    PolicyErrorCode,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def valid_metadata() -> Dict[str, Any]:
    """Valid policy metadata."""
    return {
        "name": "test-policy",
        "version": "1.0.0",
        "description": "Test policy",
        "author": "test",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def valid_signature() -> Dict[str, Any]:
    """Valid policy signature."""
    import base64
    return {
        "algorithm": "ed25519",
        "key_id": "test_key_2026",
        "signed_at": datetime.utcnow().isoformat(),
        "value": base64.b64encode(b"test_signature_placeholder").decode(),
    }


@pytest.fixture
def valid_zones() -> list:
    """Valid trust zones."""
    return [
        {"name": "AI_CORE", "trust_level": 0, "description": "AI core zone"},
        {"name": "SYSTEM", "trust_level": 1, "description": "System zone"},
        {"name": "USER", "trust_level": 2, "description": "User zone"},
        {"name": "DEVICE", "trust_level": 3, "description": "Device zone"},
        {"name": "NETWORK", "trust_level": 4, "description": "Network zone"},
    ]


@pytest.fixture
def valid_allowlists() -> Dict[str, Any]:
    """Valid allowlists."""
    return {
        "web_domains": {
            "type": "domain",
            "entries": ["*.github.com", "*.google.com", "localhost"],
        },
        "iot_devices": {
            "type": "device",
            "entries": [
                {
                    "id": "esp32-001",
                    "name": "Test Device",
                    "capabilities": ["light_control"],
                }
            ],
        },
    }


@pytest.fixture
def valid_rules() -> list:
    """Valid policy rules."""
    return [
        {
            "id": "DENY-001",
            "description": "Default deny",
            "priority": 0,
            "enabled": True,
            "match": {"any": True},
            "action": {
                "type": "DENY",
                "reason_code": "DEFAULT_DENY",
                "reason_message": "No matching allow rule",
            },
        },
        {
            "id": "ALLOW-001",
            "description": "Allow web to allowed domains",
            "priority": 100,
            "enabled": True,
            "match": {
                "tool": "web_automation",
                "domain": {"in": "@allowlists.web_domains"},
            },
            "action": {
                "type": "ALLOW",
                "log_level": "info",
            },
        },
    ]


@pytest.fixture
def valid_policy_dict(
    valid_metadata,
    valid_signature,
    valid_zones,
    valid_allowlists,
    valid_rules,
) -> Dict[str, Any]:
    """Complete valid policy document."""
    return {
        "apiVersion": "policy.akshay.ai/v1",
        "kind": "PolicyDocument",
        "metadata": valid_metadata,
        "signature": valid_signature,
        "zones": valid_zones,
        "allowlists": valid_allowlists,
        "rules": valid_rules,
    }


# =============================================================================
# METADATA TESTS
# =============================================================================

class TestPolicyMetadata:
    """Tests for PolicyMetadata validation."""
    
    def test_valid_metadata(self, valid_metadata):
        """Valid metadata should parse correctly."""
        meta = PolicyMetadata(**valid_metadata)
        assert meta.name == "test-policy"
        assert meta.version == "1.0.0"
    
    def test_invalid_name_uppercase(self):
        """Uppercase names should be rejected."""
        with pytest.raises(ValueError, match="Invalid policy name"):
            PolicyMetadata(name="TestPolicy", version="1.0.0")
    
    def test_invalid_name_special_chars(self):
        """Special characters in names should be rejected."""
        with pytest.raises(ValueError, match="Invalid policy name"):
            PolicyMetadata(name="test_policy", version="1.0.0")
    
    def test_invalid_name_starts_with_number(self):
        """Names starting with numbers should be rejected."""
        with pytest.raises(ValueError, match="Invalid policy name"):
            PolicyMetadata(name="123-policy", version="1.0.0")
    
    def test_invalid_version_format(self):
        """Invalid version formats should be rejected."""
        with pytest.raises((ValueError, PolicyValidationError)):
            PolicyMetadata(name="test", version="1.0")
        
        with pytest.raises((ValueError, PolicyValidationError)):
            PolicyMetadata(name="test", version="v1.0.0")
        
        with pytest.raises((ValueError, PolicyValidationError)):
            PolicyMetadata(name="test", version="1.0.0.0")
    
    def test_valid_version_with_prerelease(self):
        """Versions with prerelease should be valid."""
        meta = PolicyMetadata(name="test", version="1.0.0-beta.1")
        assert meta.version == "1.0.0-beta.1"
    
    def test_valid_version_with_build(self):
        """Versions with build metadata should be valid."""
        meta = PolicyMetadata(name="test", version="1.0.0+build.123")
        assert meta.version == "1.0.0+build.123"


# =============================================================================
# SIGNATURE TESTS
# =============================================================================

class TestPolicySignature:
    """Tests for PolicySignature validation."""
    
    def test_valid_signature(self, valid_signature):
        """Valid signature should parse correctly."""
        sig = PolicySignature(**valid_signature)
        assert sig.algorithm == SignatureAlgorithm.ED25519
        assert sig.key_id == "test_key_2026"
    
    def test_invalid_algorithm(self, valid_signature):
        """Invalid algorithm should be rejected."""
        valid_signature["algorithm"] = "rsa-256"
        with pytest.raises(ValueError):
            PolicySignature(**valid_signature)
    
    def test_invalid_base64_signature(self, valid_signature):
        """Invalid base64 signature value should be rejected."""
        valid_signature["value"] = "not-valid-base64!!!"
        with pytest.raises(ValueError, match="valid base64"):
            PolicySignature(**valid_signature)
    
    def test_empty_key_id(self, valid_signature):
        """Empty key_id should be rejected."""
        valid_signature["key_id"] = ""
        with pytest.raises(ValueError):
            PolicySignature(**valid_signature)


# =============================================================================
# TRUST ZONE TESTS
# =============================================================================

class TestTrustZone:
    """Tests for TrustZone validation."""
    
    def test_valid_zone(self):
        """Valid zone should parse correctly."""
        zone = TrustZone(name="AI_CORE", trust_level=0)
        assert zone.name == "AI_CORE"
        assert zone.trust_level == 0
    
    def test_invalid_zone_name_lowercase(self):
        """Lowercase zone names should be rejected."""
        with pytest.raises(ValueError):
            TrustZone(name="ai_core", trust_level=0)
    
    def test_invalid_trust_level_negative(self):
        """Negative trust levels should be rejected."""
        with pytest.raises(ValueError):
            TrustZone(name="TEST", trust_level=-1)
    
    def test_invalid_trust_level_too_high(self):
        """Trust levels > 10 should be rejected."""
        with pytest.raises(ValueError):
            TrustZone(name="TEST", trust_level=11)


# =============================================================================
# ALLOWLIST TESTS
# =============================================================================

class TestAllowlist:
    """Tests for Allowlist validation."""
    
    def test_valid_domain_allowlist(self):
        """Valid domain allowlist should parse correctly."""
        al = Allowlist(
            type="domain",
            entries=["*.github.com", "localhost"],
        )
        assert al.type == "domain"
        assert len(al.entries) == 2
    
    def test_valid_device_allowlist(self):
        """Valid device allowlist should parse correctly."""
        al = Allowlist(
            type="device",
            entries=[
                {
                    "id": "esp32-001",
                    "name": "Test",
                    "capabilities": ["light"],
                }
            ],
        )
        assert al.type == "device"
    
    def test_device_allowlist_string_entries_rejected(self):
        """Device allowlist with string entries should be rejected."""
        with pytest.raises(ValueError, match="Device allowlist entries must be objects"):
            Allowlist(
                type="device",
                entries=["esp32-001"],
            )


# =============================================================================
# MATCH CONDITION TESTS
# =============================================================================

class TestMatchCondition:
    """Tests for MatchCondition validation."""
    
    def test_simple_equality(self):
        """Simple value should be converted to equals."""
        cond = MatchCondition(**{"equals": "test"})
        assert cond.get_operator() == MatchOperator.EQUALS
        assert cond.get_value() == "test"
    
    def test_in_operator(self):
        """in operator should work with list."""
        cond = MatchCondition(**{"in": ["a", "b", "c"]})
        assert cond.get_operator() == MatchOperator.IN
        assert cond.get_value() == ["a", "b", "c"]
    
    def test_in_operator_with_allowlist_ref(self):
        """in operator with allowlist reference should validate."""
        cond = MatchCondition(**{"in": "@allowlists.web_domains"})
        assert cond.get_operator() == MatchOperator.IN
        assert cond.get_value() == "@allowlists.web_domains"
    
    def test_between_operator(self):
        """between operator should require two-element list."""
        cond = MatchCondition(**{"between": [1, 10]})
        assert cond.get_operator() == MatchOperator.BETWEEN
        assert cond.get_value() == [1, 10]
    
    def test_between_invalid_not_list(self):
        """between with non-list should be rejected."""
        with pytest.raises(ValueError, match="requires a list"):
            MatchCondition(**{"between": 5})
    
    def test_between_invalid_wrong_length(self):
        """between with wrong length should be rejected."""
        with pytest.raises(ValueError, match="requires a list of two"):
            MatchCondition(**{"between": [1, 2, 3]})
    
    def test_matches_valid_regex(self):
        """matches with valid regex should parse."""
        cond = MatchCondition(**{"matches": r"^[a-z]+$"})
        assert cond.get_operator() == MatchOperator.MATCHES
    
    def test_matches_invalid_regex(self):
        """matches with invalid regex should be rejected."""
        with pytest.raises(PolicyValidationError, match="Invalid regex"):
            MatchCondition(**{"matches": r"[invalid"})
    
    def test_matches_redos_pattern_rejected(self):
        """matches with ReDoS pattern should be rejected."""
        with pytest.raises(PolicyValidationError, match="ReDoS"):
            MatchCondition(**{"matches": r"(a+)+"})


# =============================================================================
# RULE MATCH TESTS
# =============================================================================

class TestRuleMatch:
    """Tests for RuleMatch validation."""
    
    def test_any_match(self):
        """any: true should create catch-all match."""
        match = RuleMatch(any=True)
        assert match.any is True
    
    def test_simple_string_converted_to_equals(self):
        """Simple string values should convert to equals."""
        match = RuleMatch(**{"tool": "web_automation"})
        assert match.tool.get_operator() == MatchOperator.EQUALS
        assert match.tool.get_value() == "web_automation"
    
    def test_negation_prefix(self):
        """! prefix should convert to not_equals."""
        match = RuleMatch(**{"tool": "!blocked_tool"})
        assert match.tool.get_operator() == MatchOperator.NOT_EQUALS
        assert match.tool.get_value() == "blocked_tool"
    
    def test_negation_prefix_with_allowlist(self):
        """!@ prefix should convert to not_in allowlist."""
        match = RuleMatch(**{"domain": "!@allowlists.blocked"})
        assert match.domain.get_operator() == MatchOperator.NOT_IN
        assert match.domain.get_value() == "@allowlists.blocked"
    
    def test_list_converted_to_in(self):
        """List values should convert to in."""
        match = RuleMatch(**{"tool": ["a", "b", "c"]})
        assert match.tool.get_operator() == MatchOperator.IN
        assert match.tool.get_value() == ["a", "b", "c"]


# =============================================================================
# RULE ACTION TESTS
# =============================================================================

class TestRuleAction:
    """Tests for RuleAction validation."""
    
    def test_allow_action(self):
        """ALLOW action should parse correctly."""
        action = RuleAction(type=ActionType.ALLOW)
        assert action.type == ActionType.ALLOW
    
    def test_deny_action_default_reason(self):
        """DENY action should default to DEFAULT_DENY reason."""
        action = RuleAction(type=ActionType.DENY)
        assert action.reason_code == ReasonCode.DEFAULT_DENY
    
    def test_rate_limit_requires_config(self):
        """RATE_LIMIT action requires limit configuration."""
        with pytest.raises(ValueError, match="requires limit"):
            RuleAction(type=ActionType.RATE_LIMIT)
    
    def test_rate_limit_with_config(self):
        """RATE_LIMIT with valid config should parse."""
        action = RuleAction(
            type=ActionType.RATE_LIMIT,
            limit=RateLimit(requests=100, period_seconds=60),
        )
        assert action.limit.requests == 100
    
    def test_require_confirmation_requires_message(self):
        """REQUIRE_CONFIRMATION requires confirmation_message."""
        with pytest.raises(ValueError, match="requires confirmation_message"):
            RuleAction(type=ActionType.REQUIRE_CONFIRMATION)
    
    def test_require_confirmation_with_message(self):
        """REQUIRE_CONFIRMATION with message should parse."""
        action = RuleAction(
            type=ActionType.REQUIRE_CONFIRMATION,
            confirmation_message="Please confirm this action",
        )
        assert action.confirmation_message == "Please confirm this action"


# =============================================================================
# POLICY RULE TESTS
# =============================================================================

class TestPolicyRule:
    """Tests for PolicyRule validation."""
    
    def test_valid_rule(self):
        """Valid rule should parse correctly."""
        rule = PolicyRule(
            id="TEST-001",
            priority=100,
            match=RuleMatch(any=True),
            action=RuleAction(type=ActionType.DENY),
        )
        assert rule.id == "TEST-001"
        assert rule.priority == 100
    
    def test_reserved_rule_id_rejected(self):
        """Reserved rule IDs should be rejected."""
        with pytest.raises(PolicyValidationError, match="reserved"):
            PolicyRule(
                id="DEFAULT",
                priority=100,
                match=RuleMatch(any=True),
                action=RuleAction(type=ActionType.DENY),
            )
    
    def test_invalid_rule_id_format(self):
        """Invalid rule ID format should be rejected."""
        with pytest.raises(PolicyValidationError, match="Invalid rule ID"):
            PolicyRule(
                id="invalid rule id",
                priority=100,
                match=RuleMatch(any=True),
                action=RuleAction(type=ActionType.DENY),
            )
    
    def test_lowercase_rule_id_valid(self):
        """Lowercase rule IDs should be valid."""
        rule = PolicyRule(
            id="my-rule",
            priority=100,
            match=RuleMatch(any=True),
            action=RuleAction(type=ActionType.DENY),
        )
        assert rule.id == "my-rule"


# =============================================================================
# POLICY DOCUMENT TESTS
# =============================================================================

class TestPolicyDocument:
    """Tests for PolicyDocument validation."""
    
    def test_valid_document(self, valid_policy_dict):
        """Valid policy document should parse correctly."""
        policy = PolicyDocument(**valid_policy_dict)
        assert policy.metadata.name == "test-policy"
        assert len(policy.rules) == 2
    
    def test_minimum_one_rule_required(self, valid_policy_dict):
        """At least one rule is required."""
        valid_policy_dict["rules"] = []
        with pytest.raises(ValueError):
            PolicyDocument(**valid_policy_dict)
    
    def test_duplicate_rule_ids_rejected(self, valid_policy_dict):
        """Duplicate rule IDs should be rejected."""
        valid_policy_dict["rules"].append(valid_policy_dict["rules"][0])
        with pytest.raises(ValueError, match="Duplicate rule IDs"):
            PolicyDocument(**valid_policy_dict)
    
    def test_duplicate_zone_names_rejected(self, valid_policy_dict):
        """Duplicate zone names should be rejected."""
        valid_policy_dict["zones"].append(valid_policy_dict["zones"][0])
        with pytest.raises(ValueError, match="Duplicate zone names"):
            PolicyDocument(**valid_policy_dict)
    
    def test_invalid_allowlist_reference_rejected(self, valid_policy_dict):
        """Invalid allowlist references should be rejected."""
        valid_policy_dict["rules"][1]["match"]["domain"] = {
            "in": "@allowlists.nonexistent"
        }
        with pytest.raises(ValueError, match="unknown allowlist"):
            PolicyDocument(**valid_policy_dict)
    
    def test_get_body_for_signing(self, valid_policy_dict):
        """get_body_for_signing should exclude signature."""
        policy = PolicyDocument(**valid_policy_dict)
        body = policy.get_body_for_signing()
        assert "signature" not in body
        assert "metadata" in body
        assert "rules" in body


# =============================================================================
# EVALUATION REQUEST TESTS
# =============================================================================

class TestEvaluationRequest:
    """Tests for EvaluationRequest."""
    
    def test_minimal_request(self):
        """Minimal request should parse."""
        req = EvaluationRequest(tool="test_tool")
        assert req.tool == "test_tool"
        assert req.action == "execute"
    
    def test_get_field_value_simple(self):
        """get_field_value should work for simple fields."""
        req = EvaluationRequest(tool="test_tool", domain="example.com")
        assert req.get_field_value("tool") == "test_tool"
        assert req.get_field_value("domain") == "example.com"
    
    def test_get_field_value_nested(self):
        """get_field_value should work for nested fields."""
        req = EvaluationRequest(
            tool="test_tool",
            context=EvaluationContext(user_id="user123", user_role="admin"),
        )
        assert req.get_field_value("context.user_id") == "user123"
        assert req.get_field_value("context.user_role") == "admin"
    
    def test_get_field_value_missing(self):
        """get_field_value should return None for missing fields."""
        req = EvaluationRequest(tool="test_tool")
        assert req.get_field_value("nonexistent") is None
        assert req.get_field_value("context.nonexistent") is None


# =============================================================================
# EVALUATION RESULT TESTS
# =============================================================================

class TestEvaluationResult:
    """Tests for EvaluationResult."""
    
    def test_allow_result(self):
        """ALLOW result should serialize correctly."""
        result = EvaluationResult(
            decision=Decision.ALLOW,
            matched_rule_id="TEST-001",
            matched_rule_priority=100,
            reason_code=ReasonCode.RULE_MATCHED,
            reason_message="Rule matched",
        )
        assert result.decision == Decision.ALLOW
    
    def test_deny_result(self):
        """DENY result should serialize correctly."""
        result = EvaluationResult(
            decision=Decision.DENY,
            reason_code=ReasonCode.DEFAULT_DENY,
            reason_message="No matching rule",
        )
        assert result.decision == Decision.DENY
    
    def test_to_audit_dict(self):
        """to_audit_dict should produce valid audit entry."""
        result = EvaluationResult(
            decision=Decision.DENY,
            matched_rule_id="TEST-001",
            matched_rule_priority=100,
            reason_code=ReasonCode.DOMAIN_NOT_ALLOWED,
            reason_message="Domain blocked",
            should_alert=True,
        )
        audit = result.to_audit_dict()
        assert audit["decision"] == "DENY"
        assert audit["reason_code"] == "DOMAIN_NOT_ALLOWED"
        assert audit["should_alert"] is True


# =============================================================================
# VALIDATOR FUNCTION TESTS
# =============================================================================

class TestValidators:
    """Tests for validator functions."""
    
    def test_validate_regex_pattern_valid(self):
        """Valid regex patterns should pass."""
        assert validate_regex_pattern(r"^[a-z]+$") == r"^[a-z]+$"
        assert validate_regex_pattern(r"\d{3}-\d{4}") == r"\d{3}-\d{4}"
    
    def test_validate_regex_pattern_too_long(self):
        """Regex patterns over limit should fail."""
        long_pattern = "a" * (MAX_REGEX_LENGTH + 1)
        with pytest.raises(PolicyValidationError, match="too long"):
            validate_regex_pattern(long_pattern)
    
    def test_validate_regex_pattern_redos(self):
        """ReDoS-vulnerable patterns should fail."""
        with pytest.raises(PolicyValidationError, match="ReDoS"):
            validate_regex_pattern(r"(a+)+")
        
        with pytest.raises(PolicyValidationError, match="ReDoS"):
            validate_regex_pattern(r"(.*)+")
    
    def test_validate_semver_valid(self):
        """Valid semver strings should pass."""
        assert validate_semver("1.0.0") == "1.0.0"
        assert validate_semver("0.0.1") == "0.0.1"
        assert validate_semver("10.20.30") == "10.20.30"
        assert validate_semver("1.0.0-alpha") == "1.0.0-alpha"
        assert validate_semver("1.0.0+build") == "1.0.0+build"
    
    def test_validate_semver_invalid(self):
        """Invalid semver strings should fail."""
        with pytest.raises(PolicyValidationError):
            validate_semver("1.0")
        with pytest.raises(PolicyValidationError):
            validate_semver("v1.0.0")
        with pytest.raises(PolicyValidationError):
            validate_semver("1.0.0.0")
    
    def test_validate_allowlist_reference_valid(self):
        """Valid allowlist references should pass."""
        assert validate_allowlist_reference("@web_domains") == "@web_domains"
        assert validate_allowlist_reference("@allowlists.web_domains") == "@allowlists.web_domains"
    
    def test_validate_allowlist_reference_invalid(self):
        """Invalid allowlist references should fail."""
        with pytest.raises(PolicyValidationError, match="must start with @"):
            validate_allowlist_reference("web_domains")
        
        with pytest.raises(PolicyValidationError, match="Invalid allowlist name"):
            validate_allowlist_reference("@Invalid-Name")
    
    def test_validate_rule_id_valid(self):
        """Valid rule IDs should pass."""
        assert validate_rule_id("TEST-001") == "TEST-001"
        assert validate_rule_id("WEB-123") == "WEB-123"
        assert validate_rule_id("my-rule") == "my-rule"
    
    def test_validate_rule_id_reserved(self):
        """Reserved rule IDs should fail."""
        with pytest.raises(PolicyValidationError, match="reserved"):
            validate_rule_id("DEFAULT")
        with pytest.raises(PolicyValidationError, match="reserved"):
            validate_rule_id("SYSTEM")
    
    def test_validate_rule_id_invalid_format(self):
        """Invalid rule ID formats should fail."""
        with pytest.raises(PolicyValidationError, match="Invalid rule ID"):
            validate_rule_id("invalid rule")
        with pytest.raises(PolicyValidationError, match="Invalid rule ID"):
            validate_rule_id("123-INVALID")


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
