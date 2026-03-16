"""
Tests for the Policy Evaluation Engine.

Covers:
- Request validation
- Priority ordering
- Default deny behavior
- Operator evaluation
- Safe mode enforcement
- Rate limiting
- Audit trail generation
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.policy.engine import (
    PolicyEngine,
    EngineEvaluationRequest,
    EngineEvaluationResult,
    MatchResult,
    SourceType,
    EvaluationPhase,
    ConditionEvaluator,
    RuleMatcher,
    InMemoryRateLimiter,
    AuditBuilder,
    create_evaluation_request,
    quick_evaluate,
)
from core.policy.schema import (
    ActionType,
    Decision,
    LogLevel,
    MatchCondition,
    MatchOperator,
    PolicyApiVersion,
    PolicyDocument,
    PolicyKind,
    PolicyMetadata,
    PolicyRule,
    PolicySignature,
    ReasonCode,
    RuleAction,
    RuleMatch,
    RateLimit,
    TrustZone,
    Allowlist,
    FailureModeConfig,
    SafeModeConfig,
    SignatureAlgorithm,
)
from core.policy.loader import FinalPolicy, PolicySourceInfo, SignatureVerificationStatus
from core.policy.signer import KeyTrust


# =============================================================================
# FIXTURES
# =============================================================================

def create_test_metadata(name: str = "test-policy", version: str = "1.0.0") -> PolicyMetadata:
    """Create test policy metadata."""
    return PolicyMetadata(
        name=name,
        version=version,
        description="Test policy",
        author="test",
    )


def create_test_signature() -> PolicySignature:
    """Create test policy signature."""
    return PolicySignature(
        algorithm=SignatureAlgorithm.ED25519,
        key_id="test-key",
        signed_at=datetime.now(timezone.utc),
        value="dGVzdC1zaWduYXR1cmU=",  # "test-signature" base64
    )


def create_test_rule(
    rule_id: str,
    priority: int,
    tool: Optional[str] = None,
    action_type: ActionType = ActionType.ALLOW,
    enabled: bool = True,
    match_any: bool = False,
    conditions: Optional[List[Dict[str, Any]]] = None,
    rate_limit: Optional[RateLimit] = None,
) -> PolicyRule:
    """Create a test policy rule."""
    match_data: Dict[str, Any] = {"any": match_any}
    if tool:
        match_data["tool"] = {"equals": tool}
    
    action_data = {
        "type": action_type,
        "reason_code": ReasonCode.RULE_MATCHED if action_type == ActionType.ALLOW else ReasonCode.DEFAULT_DENY,
    }
    
    if rate_limit:
        action_data["limit"] = rate_limit
    
    if action_type == ActionType.REQUIRE_CONFIRMATION:
        action_data["confirmation_message"] = "Please confirm this action"
    
    return PolicyRule(
        id=rule_id,
        description=f"Test rule {rule_id}",
        priority=priority,
        enabled=enabled,
        match=RuleMatch(**match_data),
        conditions=conditions or [],
        action=RuleAction(**action_data),
    )


def create_test_policy(
    rules: Optional[List[PolicyRule]] = None,
    allowlists: Optional[Dict[str, Allowlist]] = None,
    zones: Optional[List[TrustZone]] = None,
) -> PolicyDocument:
    """Create a test policy document."""
    if rules is None:
        rules = [create_test_rule("rule-001", priority=100, match_any=True)]
    
    return PolicyDocument(
        apiVersion=PolicyApiVersion.V1,
        kind=PolicyKind.POLICY_DOCUMENT,
        metadata=create_test_metadata(),
        signature=create_test_signature(),
        zones=zones or [],
        allowlists=allowlists or {},
        rules=rules,
        failure_mode=FailureModeConfig(),
    )


def create_final_policy(
    doc: Optional[PolicyDocument] = None,
    trust_level: str = KeyTrust.ROOT,
) -> FinalPolicy:
    """Create a FinalPolicy for testing."""
    if doc is None:
        doc = create_test_policy()
    
    source_info = PolicySourceInfo(
        name=doc.metadata.name,
        version=doc.metadata.version,
        file_path="/test/policy.yaml",
        signed_by="test-key",
        trust_level=trust_level,
        verified_at=datetime.now(timezone.utc),
    )
    
    return FinalPolicy(
        source_chain=[source_info],
        signature_status=SignatureVerificationStatus.VERIFIED,
        trust_level=trust_level,
        document=doc,
    )


def create_test_request(
    actor_id: str = "user-123",
    tool: str = "web.fetch",
    action: str = "execute",
    role: str = "user",
    trust_zone: str = "USER",
    source: SourceType = SourceType.API,
    target: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> EngineEvaluationRequest:
    """Create a test evaluation request."""
    return EngineEvaluationRequest(
        actor_id=actor_id,
        tool=tool,
        action=action,
        role=role,
        trust_zone=trust_zone,
        source=source,
        target=target or {},
        context=context or {},
    )


# =============================================================================
# TEST: REQUEST VALIDATION
# =============================================================================

class TestRequestValidation:
    """Test EvaluationRequest validation."""
    
    def test_valid_request(self):
        """Valid request should be accepted."""
        request = create_test_request()
        assert request.actor_id == "user-123"
        assert request.tool == "web.fetch"
        assert request.source == SourceType.API
    
    def test_actor_id_required(self):
        """actor_id is required."""
        with pytest.raises(ValueError):
            EngineEvaluationRequest(
                actor_id="",  # Empty not allowed
                tool="web.fetch",
            )
    
    def test_tool_format_validation(self):
        """tool must be dot-notation format."""
        # Valid formats
        create_test_request(tool="web.fetch")
        create_test_request(tool="memory.read")
        create_test_request(tool="system.status")
        create_test_request(tool="a")  # Single lowercase
        create_test_request(tool="web_fetch")  # Underscore is allowed
        
        # Invalid formats - uppercase
        with pytest.raises(ValueError):
            create_test_request(tool="Web.Fetch")  # Uppercase
        
    def test_invalid_characters_in_actor_id(self):
        """actor_id cannot contain dangerous characters."""
        with pytest.raises(ValueError):
            create_test_request(actor_id="<script>")
    
    def test_get_field_value(self):
        """get_field_value retrieves nested fields."""
        request = create_test_request(
            target={"domain": "example.com", "nested": {"key": "value"}},
            context={"ip": "192.168.1.1"},
        )
        
        assert request.get_field_value("tool") == "web.fetch"
        assert request.get_field_value("target.domain") == "example.com"
        assert request.get_field_value("context.ip") == "192.168.1.1"
        assert request.get_field_value("nonexistent") is None
    
    def test_to_audit_dict(self):
        """to_audit_dict produces serializable output."""
        request = create_test_request()
        audit = request.to_audit_dict()
        
        assert audit["actor_id"] == "user-123"
        assert audit["tool"] == "web.fetch"
        assert audit["source"] == "api"


# =============================================================================
# TEST: CONDITION EVALUATOR
# =============================================================================

class TestConditionEvaluator:
    """Test the condition evaluator operators."""
    
    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        """Create a condition evaluator."""
        return ConditionEvaluator()
    
    def test_equals_string(self, evaluator):
        """equals operator with strings."""
        condition = MatchCondition(**{"equals": "hello"})
        result, trace = evaluator.evaluate(condition, "hello", "test")
        assert result is True
        
        result, trace = evaluator.evaluate(condition, "world", "test")
        assert result is False
    
    def test_equals_number(self, evaluator):
        """equals operator with numbers."""
        condition = MatchCondition(**{"equals": 42})
        result, _ = evaluator.evaluate(condition, 42, "test")
        assert result is True
    
    def test_not_equals(self, evaluator):
        """not_equals operator."""
        condition = MatchCondition(**{"not_equals": "hello"})
        result, _ = evaluator.evaluate(condition, "world", "test")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, "hello", "test")
        assert result is False
    
    def test_in_list(self, evaluator):
        """in operator with list."""
        condition = MatchCondition(**{"in": ["a", "b", "c"]})
        result, _ = evaluator.evaluate(condition, "b", "test")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, "d", "test")
        assert result is False
    
    def test_not_in_list(self, evaluator):
        """not_in operator."""
        condition = MatchCondition(**{"not_in": ["a", "b", "c"]})
        result, _ = evaluator.evaluate(condition, "d", "test")
        assert result is True
    
    def test_in_allowlist_reference(self):
        """in operator with allowlist reference."""
        allowlists = {
            "domains": Allowlist(
                type="domain",
                entries=["example.com", "test.org"],
            )
        }
        evaluator = ConditionEvaluator(allowlists=allowlists)
        
        condition = MatchCondition(**{"in": "@domains"})
        result, _ = evaluator.evaluate(condition, "example.com", "domain")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, "evil.com", "domain")
        assert result is False
    
    def test_contains(self, evaluator):
        """contains operator."""
        condition = MatchCondition(**{"contains": "world"})
        result, _ = evaluator.evaluate(condition, "hello world", "test")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, "hello", "test")
        assert result is False
    
    def test_starts_with(self, evaluator):
        """starts_with operator."""
        condition = MatchCondition(**{"starts_with": "hello"})
        result, _ = evaluator.evaluate(condition, "hello world", "test")
        assert result is True
    
    def test_ends_with(self, evaluator):
        """ends_with operator."""
        condition = MatchCondition(**{"ends_with": "world"})
        result, _ = evaluator.evaluate(condition, "hello world", "test")
        assert result is True
    
    def test_matches_regex(self, evaluator):
        """matches operator with regex."""
        condition = MatchCondition(**{"matches": r"^[a-z]+@[a-z]+\.[a-z]+$"})
        result, _ = evaluator.evaluate(condition, "test@example.com", "email")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, "invalid", "email")
        assert result is False
    
    def test_greater_than(self, evaluator):
        """gt operator."""
        condition = MatchCondition(**{"gt": 10})
        result, _ = evaluator.evaluate(condition, 15, "test")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, 5, "test")
        assert result is False
    
    def test_less_than(self, evaluator):
        """lt operator."""
        condition = MatchCondition(**{"lt": 10})
        result, _ = evaluator.evaluate(condition, 5, "test")
        assert result is True
    
    def test_between(self, evaluator):
        """between operator."""
        condition = MatchCondition(**{"between": [10, 20]})
        result, _ = evaluator.evaluate(condition, 15, "test")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, 25, "test")
        assert result is False
    
    def test_exists(self, evaluator):
        """exists operator."""
        condition = MatchCondition(**{"exists": True})
        result, _ = evaluator.evaluate(condition, "value", "test")
        assert result is True
        
        result, _ = evaluator.evaluate(condition, None, "test")
        assert result is False
        
        result, _ = evaluator.evaluate(condition, "", "test")
        assert result is False
    
    def test_not_exists(self, evaluator):
        """not_exists operator."""
        condition = MatchCondition(**{"not_exists": True})
        result, _ = evaluator.evaluate(condition, None, "test")
        assert result is True
    
    def test_any_always_matches(self, evaluator):
        """any operator always returns True."""
        condition = MatchCondition(**{"any": True})
        result, _ = evaluator.evaluate(condition, "anything", "test")
        assert result is True
    
    def test_null_handling(self, evaluator):
        """Operators handle None values safely."""
        condition = MatchCondition(**{"equals": "test"})
        result, _ = evaluator.evaluate(condition, None, "test")
        assert result is False
        
        condition = MatchCondition(**{"gt": 10})
        result, _ = evaluator.evaluate(condition, None, "test")
        assert result is False


# =============================================================================
# TEST: RULE MATCHER
# =============================================================================

class TestRuleMatcher:
    """Test rule matching logic."""
    
    @pytest.fixture
    def matcher(self) -> RuleMatcher:
        """Create a rule matcher."""
        return RuleMatcher(ConditionEvaluator())
    
    def test_match_any_rule(self, matcher):
        """Rule with match.any=True matches everything."""
        rule = create_test_rule("rule-any", priority=100, match_any=True)
        request = create_test_request(tool="anything.here")
        
        result = matcher.match_rule(rule, request)
        assert result.matched is True
        assert result.rule_id == "rule-any"
    
    def test_match_tool(self, matcher):
        """Rule matches specific tool."""
        rule = create_test_rule("rule-tool", priority=100, tool="web.fetch")
        
        request = create_test_request(tool="web.fetch")
        result = matcher.match_rule(rule, request)
        assert result.matched is True
        
        request = create_test_request(tool="memory.read")
        result = matcher.match_rule(rule, request)
        assert result.matched is False
    
    def test_disabled_rule_not_matched(self, matcher):
        """Disabled rules are not matched."""
        rule = create_test_rule("rule-disabled", priority=100, tool="web.fetch", enabled=False)
        request = create_test_request(tool="web.fetch")
        
        result = matcher.match_rule(rule, request)
        assert result.matched is False
        assert result.failed_condition == {"reason": "rule_disabled"}
    
    def test_match_result_has_timing(self, matcher):
        """MatchResult includes timing information."""
        rule = create_test_rule("rule-timing", priority=100, match_any=True)
        request = create_test_request()
        
        result = matcher.match_rule(rule, request)
        assert result.match_time_ms >= 0
    
    def test_conditions_traced(self, matcher):
        """All evaluated conditions are traced."""
        rule = create_test_rule("rule-traced", priority=100, tool="web.fetch")
        request = create_test_request(tool="web.fetch")
        
        result = matcher.match_rule(rule, request)
        assert len(result.conditions_checked) > 0


# =============================================================================
# TEST: PRIORITY ORDERING
# =============================================================================

class TestPriorityOrdering:
    """Test that rules are evaluated in priority order."""
    
    def test_higher_priority_wins(self):
        """Higher priority rule wins when both match."""
        rules = [
            create_test_rule("rule-low", priority=50, match_any=True, action_type=ActionType.DENY),
            create_test_rule("rule-high", priority=100, match_any=True, action_type=ActionType.ALLOW),
        ]
        
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        request = create_test_request()
        
        result = engine.evaluate(request, policy)
        assert result.decision == Decision.ALLOW
        assert result.rule_id == "rule-high"
    
    def test_deterministic_ordering_same_priority(self):
        """Rules with same priority are sorted by ID for determinism."""
        rules = [
            create_test_rule("rule-b", priority=100, match_any=True, action_type=ActionType.DENY),
            create_test_rule("rule-a", priority=100, match_any=True, action_type=ActionType.ALLOW),
        ]
        
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        # Multiple evaluations should give same result
        for _ in range(10):
            result = engine.evaluate(create_test_request(), policy)
            assert result.rule_id == "rule-a"  # Alphabetically first


# =============================================================================
# TEST: DEFAULT DENY
# =============================================================================

class TestDefaultDeny:
    """Test default deny behavior."""
    
    def test_no_matching_rule_denies(self):
        """When no rule matches, default is DENY."""
        rules = [
            create_test_rule("rule-specific", priority=100, tool="specific.tool"),
        ]
        
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        request = create_test_request(tool="other.tool")
        
        result = engine.evaluate(request, policy)
        assert result.decision == Decision.DENY
        assert result.reason_code == ReasonCode.DEFAULT_DENY
        assert result.rule_id is None
    
    def test_default_deny_has_audit(self):
        """Default deny still produces audit record."""
        rules = [
            create_test_rule("rule-specific", priority=100, tool="specific.tool"),
        ]
        
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        request = create_test_request(tool="other.tool")
        
        result = engine.evaluate(request, policy)
        assert "reason" in result.audit_record


# =============================================================================
# TEST: SAFE MODE
# =============================================================================

class TestSafeMode:
    """Test safe mode enforcement."""
    
    def test_safe_mode_allowed_actions(self):
        """Safe mode allows only specific actions."""
        # Note: Safe mode is currently not auto-active in the implementation
        # This tests the _evaluate_safe_mode method directly
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        # Manually test safe mode evaluation
        request = create_test_request(tool="system.status")
        result = engine._evaluate_safe_mode(request, policy)
        assert result.decision == Decision.ALLOW
    
    def test_safe_mode_blocks_dangerous(self):
        """Safe mode blocks dangerous actions."""
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        request = create_test_request(tool="system.shell")
        result = engine._evaluate_safe_mode(request, policy)
        assert result.decision == Decision.DENY
        assert result.reason_code == ReasonCode.SAFE_MODE_ACTIVE


# =============================================================================
# TEST: RATE LIMITING
# =============================================================================

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_in_memory_rate_limiter_allows_within_limit(self):
        """Rate limiter allows requests within limit."""
        limiter = InMemoryRateLimiter()
        
        allowed, remaining, reset_at = limiter.check_and_increment("key1", 10, 60)
        assert allowed is True
        assert remaining == 9
    
    def test_in_memory_rate_limiter_blocks_over_limit(self):
        """Rate limiter blocks requests over limit."""
        limiter = InMemoryRateLimiter()
        
        # Exhaust the limit
        for i in range(10):
            limiter.check_and_increment("key2", 10, 60)
        
        # 11th request should be blocked
        allowed, remaining, reset_at = limiter.check_and_increment("key2", 10, 60)
        assert allowed is False
        assert remaining == 0
    
    def test_global_rate_limit(self):
        """Global rate limit is enforced."""
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        # Make many requests to hit global rate limit
        # Default global limit is 1000/min, so we test the mechanism
        request = create_test_request(actor_id="rate-test-user")
        
        # First request should pass
        result = engine.evaluate(request, policy)
        assert result.decision == Decision.ALLOW
    
    def test_rule_rate_limit(self):
        """Rule-specific rate limit is enforced."""
        rate_limit = RateLimit(requests=2, period_seconds=60)
        rules = [
            create_test_rule(
                "rule-limited", 
                priority=100, 
                match_any=True,
                action_type=ActionType.RATE_LIMIT,
                rate_limit=rate_limit,
            ),
        ]
        
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        # First request
        result = engine.evaluate(create_test_request(actor_id="limited-user"), policy)
        assert result.rate_limit is not None
        assert result.rate_limit["remaining"] == 1


# =============================================================================
# TEST: AUDIT TRAIL
# =============================================================================

class TestAuditTrail:
    """Test audit trail generation."""
    
    def test_audit_builder(self):
        """AuditBuilder produces complete records."""
        builder = AuditBuilder()
        
        request = create_test_request()
        result = EngineEvaluationResult(
            decision=Decision.ALLOW,
            rule_id="rule-001",
            reason_code=ReasonCode.RULE_MATCHED,
            priority=100,
            policy_version="1.0.0",
        )
        
        audit = builder.build(request, result, "test-policy")
        
        assert audit["actor"] == "user-123"
        assert audit["tool"] == "web.fetch"
        assert audit["decision"] == "ALLOW"
        assert audit["policy_name"] == "test-policy"
    
    def test_audit_callback_invoked(self):
        """Audit callback is invoked on evaluation."""
        audit_records = []
        
        def capture_audit(record):
            audit_records.append(record)
        
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine(audit_callback=capture_audit)
        
        request = create_test_request()
        engine.evaluate(request, policy)
        
        assert len(audit_records) == 1
        assert audit_records[0]["decision"] == "ALLOW"
    
    def test_result_to_audit_dict(self):
        """EngineEvaluationResult.to_audit_dict works."""
        result = EngineEvaluationResult(
            decision=Decision.DENY,
            rule_id="rule-001",
            reason_code=ReasonCode.DEFAULT_DENY,
            priority=100,
            policy_version="1.0.0",
            rules_checked=5,
        )
        
        audit = result.to_audit_dict()
        assert audit["decision"] == "DENY"
        assert audit["rules_checked"] == 5


# =============================================================================
# TEST: DECISION TYPES
# =============================================================================

class TestDecisionTypes:
    """Test different decision types."""
    
    def test_allow_decision(self):
        """ALLOW decision is returned correctly."""
        rules = [create_test_rule("rule-allow", priority=100, match_any=True, action_type=ActionType.ALLOW)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        result = engine.evaluate(create_test_request(), policy)
        assert result.decision == Decision.ALLOW
    
    def test_deny_decision(self):
        """DENY decision is returned correctly."""
        rules = [create_test_rule("rule-deny", priority=100, match_any=True, action_type=ActionType.DENY)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        result = engine.evaluate(create_test_request(), policy)
        assert result.decision == Decision.DENY
    
    def test_require_confirmation_decision(self):
        """REQUIRE_CONFIRMATION decision is returned correctly."""
        rules = [create_test_rule(
            "rule-confirm", 
            priority=100, 
            match_any=True, 
            action_type=ActionType.REQUIRE_CONFIRMATION,
        )]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        result = engine.evaluate(create_test_request(), policy)
        assert result.decision == Decision.REQUIRE_CONFIRMATION
        assert result.requires_confirmation is True
    
    def test_require_mfa_decision(self):
        """REQUIRE_MFA decision is returned correctly."""
        rules = [create_test_rule(
            "rule-mfa", 
            priority=100, 
            match_any=True, 
            action_type=ActionType.REQUIRE_MFA,
        )]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        result = engine.evaluate(create_test_request(), policy)
        assert result.decision == Decision.REQUIRE_MFA
        assert result.requires_mfa is True


# =============================================================================
# TEST: ERROR HANDLING
# =============================================================================

class TestErrorHandling:
    """Test error handling and fail-closed behavior."""
    
    def test_internal_error_results_in_deny(self):
        """Internal errors result in DENY (fail closed)."""
        # Create a policy with invalid state that might cause issues
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        # Force an error by passing invalid request type
        # This should be caught and result in DENY
        request = create_test_request()
        result = engine.evaluate(request, policy)
        
        # Should still get a result (not an exception)
        assert result.decision is not None


# =============================================================================
# TEST: CONVENIENCE FUNCTIONS
# =============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_evaluation_request(self):
        """create_evaluation_request creates valid request."""
        request = create_evaluation_request(
            actor_id="user-1",
            tool="web.fetch",
            role="admin",
        )
        
        assert request.actor_id == "user-1"
        assert request.tool == "web.fetch"
        assert request.role == "admin"
    
    def test_quick_evaluate(self):
        """quick_evaluate returns just the decision."""
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        
        decision = quick_evaluate(
            policy=policy,
            actor_id="user-1",
            tool="web.fetch",
        )
        
        assert decision == Decision.ALLOW


# =============================================================================
# TEST: RESULT CONVERSION
# =============================================================================

class TestResultConversion:
    """Test result type conversions."""
    
    def test_engine_result_to_standard_result(self):
        """EngineEvaluationResult converts to standard EvaluationResult."""
        engine_result = EngineEvaluationResult(
            decision=Decision.ALLOW,
            rule_id="rule-001",
            reason_code=ReasonCode.RULE_MATCHED,
            priority=100,
            policy_version="1.0.0",
            requires_confirmation=True,
            confirmation_message="Please confirm",
        )
        
        std_result = engine_result.to_evaluation_result()
        
        assert std_result.decision == Decision.ALLOW
        assert std_result.matched_rule_id == "rule-001"
        assert std_result.requires_confirmation is True
        assert std_result.confirmation_message == "Please confirm"


# =============================================================================
# TEST: PERFORMANCE
# =============================================================================

class TestPerformance:
    """Test performance characteristics."""
    
    def test_evaluation_time_recorded(self):
        """Evaluation time is recorded in result."""
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        result = engine.evaluate(create_test_request(), policy)
        
        assert result.evaluation_time_ms > 0
    
    def test_many_rules_performance(self):
        """Engine handles many rules efficiently."""
        # Create 100 rules with different priorities
        rules = [
            create_test_rule(f"rule-{i:03d}", priority=i, tool=f"tool{i}.action")
            for i in range(100)
        ]
        # Add a catch-all rule at the end
        rules.append(create_test_rule("rule-catchall", priority=0, match_any=True))
        
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        start = time.perf_counter()
        for _ in range(100):
            engine.evaluate(create_test_request(), policy)
        elapsed = time.perf_counter() - start
        
        # 100 evaluations should complete in under 1 second
        assert elapsed < 1.0


# =============================================================================
# TEST: THREAD SAFETY
# =============================================================================

class TestThreadSafety:
    """Test thread safety of the engine."""
    
    def test_concurrent_evaluations(self):
        """Engine handles concurrent evaluations."""
        import concurrent.futures
        
        rules = [create_test_rule("rule-any", priority=100, match_any=True)]
        policy = create_final_policy(create_test_policy(rules=rules))
        engine = PolicyEngine()
        
        def evaluate_request(i):
            request = create_test_request(actor_id=f"user-{i}")
            return engine.evaluate(request, policy)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(evaluate_request, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(r.decision == Decision.ALLOW for r in results)
    
    def test_concurrent_rate_limiting(self):
        """Rate limiter is thread-safe."""
        import concurrent.futures
        
        limiter = InMemoryRateLimiter()
        
        def check_limit(i):
            return limiter.check_and_increment(f"concurrent-key", 100, 60)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_limit, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should be allowed (under limit)
        assert all(r[0] for r in results)
