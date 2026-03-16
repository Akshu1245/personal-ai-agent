"""
AKSHAY AI CORE — Policy Merge Engine Tests

Tests for the trust-aware, fail-closed merge engine that:
- Enforces INTERSECTION semantics for allowlists (NEVER UNION)
- Detects and rejects trust downgrade attacks
- Validates zone identity across inheritance chain
- Protects failure_mode from non-ROOT modification
- Resolves rule conflicts based on trust hierarchy

Security guarantees tested:
- Never allows privilege expansion
- Never allows trust downgrades
- Allowlists can only shrink (intersection)
- Zones must be identical
- Failure mode only modifiable by ROOT
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import pytest
import yaml

from core.policy.loader import (
    PolicyLoader,
    PolicyMergeEngine,
    MergeReport,
    TrustLevel,
    FinalPolicy,
    create_safe_mode_policy,
)
from core.policy.schema import (
    PolicyDocument,
    PolicyMetadata,
    PolicyRule,
    RuleMatch,
    RuleAction,
    ActionType,
    TrustZone,
    Allowlist,
    DeviceAllowlistEntry,
    FailureModeConfig,
    SafeModeConfig,
)
from core.policy.signer import PolicySigner, KeyTrust
from core.policy.verifier import PolicyVerifier
from core.policy.errors import (
    PolicyInheritanceError,
    PolicyLoadError,
    PolicyErrorCode,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_policies_dir():
    """Create a temporary directory for policy files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        policies_dir = Path(tmpdir) / "policies"
        policies_dir.mkdir()
        (policies_dir / "versions").mkdir()
        yield policies_dir


@pytest.fixture
def signer():
    """Create a PolicySigner with test keys at all trust levels."""
    signer = PolicySigner()
    signer.generate_hmac_key(key_id="root_key", trust=KeyTrust.ROOT)
    signer.generate_hmac_key(key_id="operator_key", trust=KeyTrust.OPERATOR)
    signer.generate_hmac_key(key_id="audit_key", trust=KeyTrust.AUDIT)
    return signer


@pytest.fixture
def verifier(signer):
    """Create a PolicyVerifier with test keys registered."""
    import base64
    verifier = PolicyVerifier()
    
    for key_id in ["root_key", "operator_key", "audit_key"]:
        key = signer.get_key(key_id)
        if key:
            secret = signer._hmac_secrets.get(key_id)
            if secret:
                verifier.register_hmac_secret(
                    key_id=key_id,
                    secret=base64.b64encode(secret).decode(),
                    trust=key.trust,
                )
    return verifier


@pytest.fixture
def loader(temp_policies_dir, verifier):
    """Create a PolicyLoader with test configuration."""
    return PolicyLoader(
        policies_dir=temp_policies_dir,
        verifier=verifier,
    )


def create_test_rule(
    id: str,
    action_type: ActionType = ActionType.ALLOW,
    priority: int = 50,
    match_action: str = "test",
) -> PolicyRule:
    """Helper to create a policy rule with required fields."""
    return PolicyRule(
        id=id,
        priority=priority,
        match=RuleMatch(action=match_action),
        action=RuleAction(type=action_type),
    )


def create_base_policy(
    name: str = "base-policy",
    version: str = "1.0.0",
    rules: List[Dict[str, Any]] = None,
    zones: List[Dict[str, Any]] = None,
    allowlists: Dict[str, Dict[str, Any]] = None,
    failure_mode: Dict[str, Any] = None,
    inherits: str = None,
) -> Dict[str, Any]:
    """Create a base policy document for testing."""
    policy = {
        "apiVersion": "policy.akshay.ai/v1",
        "kind": "PolicyDocument",
        "metadata": {
            "name": name,
            "version": version,
            "description": f"Test policy: {name}",
        },
        "rules": rules or [
            {
                "id": "default-deny",
                "description": "Default deny all",
                "match": {"action": "*"},
                "action": {"type": "DENY"},
                "priority": 0,
            }
        ],
    }
    
    if zones:
        policy["zones"] = zones
    
    if allowlists:
        policy["allowlists"] = allowlists
    
    if failure_mode:
        policy["failure_mode"] = failure_mode
    
    if inherits:
        policy["metadata"]["inherits"] = inherits
    
    return policy


# =============================================================================
# TRUST LEVEL UTILITY TESTS
# =============================================================================

class TestTrustLevel:
    """Tests for trust level comparison utilities."""
    
    def test_get_level_root(self):
        """ROOT has highest level (3)."""
        assert TrustLevel.get_level(KeyTrust.ROOT) == 3
    
    def test_get_level_operator(self):
        """OPERATOR has medium level (2)."""
        assert TrustLevel.get_level(KeyTrust.OPERATOR) == 2
    
    def test_get_level_audit(self):
        """AUDIT has lowest level (1)."""
        assert TrustLevel.get_level(KeyTrust.AUDIT) == 1
    
    def test_root_higher_than_operator(self):
        """ROOT is higher than OPERATOR."""
        result = TrustLevel.compare(KeyTrust.ROOT, KeyTrust.OPERATOR)
        assert result > 0
    
    def test_operator_higher_than_audit(self):
        """OPERATOR is higher than AUDIT."""
        result = TrustLevel.compare(KeyTrust.OPERATOR, KeyTrust.AUDIT)
        assert result > 0
    
    def test_root_higher_or_equal_to_root(self):
        """ROOT is >= ROOT."""
        assert TrustLevel.is_higher_or_equal(KeyTrust.ROOT, KeyTrust.ROOT)
    
    def test_operator_not_higher_than_root(self):
        """OPERATOR is not >= ROOT."""
        assert not TrustLevel.is_higher_or_equal(KeyTrust.OPERATOR, KeyTrust.ROOT)
    
    def test_minimum_root_operator(self):
        """Minimum of ROOT and OPERATOR is OPERATOR."""
        result = TrustLevel.minimum(KeyTrust.ROOT, KeyTrust.OPERATOR)
        assert result == KeyTrust.OPERATOR
    
    def test_minimum_audit_root(self):
        """Minimum of AUDIT and ROOT is AUDIT."""
        result = TrustLevel.minimum(KeyTrust.AUDIT, KeyTrust.ROOT)
        assert result == KeyTrust.AUDIT


# =============================================================================
# MERGE REPORT TESTS
# =============================================================================

class TestMergeReport:
    """Tests for merge report tracking."""
    
    def test_report_initialized_empty(self):
        """New report has empty collections."""
        report = MergeReport()
        assert report.rules_added == []
        assert report.rules_overridden == []
        assert report.allowlists_reduced == []
        assert report.allowlists_replaced == []
        assert report.metadata_overrides == []
        assert report.trust_warnings == []
        assert report.security_violations == []
    
    def test_has_violations_empty(self):
        """Empty report has no violations."""
        report = MergeReport()
        assert not report.has_violations()
    
    def test_has_violations_with_violation(self):
        """Report with violations is detected."""
        report = MergeReport()
        report.security_violations.append("Test violation")
        assert report.has_violations()


# =============================================================================
# ALLOWLIST MERGE TESTS (INTERSECTION SEMANTICS)
# =============================================================================

class TestAllowlistMerge:
    """Tests for allowlist intersection merge semantics."""
    
    def test_allowlist_intersection_reduces(self):
        """Child policy can only REDUCE allowlist entries."""
        engine = PolicyMergeEngine()
        
        # Base policy with 3 allowed domains
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            allowlists={
                "domains": Allowlist(
                    type="domain",
                    entries=["example.com", "trusted.com", "allowed.com"]
                )
            },
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # Child policy with only 2 of those domains
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0"),
            allowlists={
                "domains": Allowlist(
                    type="domain",
                    entries=["example.com", "trusted.com"]  # Removed "allowed.com"
                )
            },
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.OPERATOR),
        ])
        
        # Intersection should have only 2 entries
        assert "domains" in result.allowlists
        assert len(result.allowlists["domains"].entries) == 2
        assert "example.com" in result.allowlists["domains"].entries
        assert "trusted.com" in result.allowlists["domains"].entries
        assert "allowed.com" not in result.allowlists["domains"].entries
        
        # Report should track the reduction
        assert len(report.allowlists_reduced) == 1
        assert report.allowlists_reduced[0]["name"] == "domains"
        assert report.allowlists_reduced[0]["removed_count"] == 1
    
    def test_allowlist_expansion_rejected_operator(self):
        """OPERATOR-signed child cannot expand allowlist."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            allowlists={
                "domains": Allowlist(
                    type="domain",
                    entries=["example.com"]
                )
            },
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # Child tries to ADD entries (expansion attack)
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0"),
            allowlists={
                "domains": Allowlist(
                    type="domain",
                    entries=["example.com", "malicious.com"]  # Added entry!
                )
            },
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        # Should raise due to security violation
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "expansion" in str(exc_info.value).lower()
    
    def test_allowlist_expansion_allowed_root(self):
        """ROOT-signed child CAN expand/replace allowlist."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            allowlists={
                "domains": Allowlist(
                    type="domain",
                    entries=["example.com"]
                )
            },
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # ROOT child can add entries
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0"),
            allowlists={
                "domains": Allowlist(
                    type="domain",
                    entries=["example.com", "new-trusted.com"]
                )
            },
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.ROOT),  # ROOT can expand
        ])
        
        # ROOT replacement is tracked
        assert "domains" in report.allowlists_replaced
        # Result should have the expanded allowlist
        assert len(result.allowlists["domains"].entries) == 2
    
    def test_new_allowlist_rejected_operator(self):
        """OPERATOR cannot add a NEW allowlist that doesn't exist in base."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # Child tries to add a completely new allowlist
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0"),
            allowlists={
                "new-allowlist": Allowlist(
                    type="domain",
                    entries=["sneaky.com"]
                )
            },
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "expansion" in str(exc_info.value).lower() or "new allowlist" in str(exc_info.value).lower()


# =============================================================================
# TRUST DOWNGRADE DETECTION TESTS
# =============================================================================

class TestTrustDowngrade:
    """Tests for trust downgrade attack detection."""
    
    def test_operator_cannot_override_root_rule(self):
        """OPERATOR cannot override a rule defined by ROOT."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[PolicyRule(
                id="critical-rule",
                description="ROOT-defined critical rule",
                priority=100,
                match=RuleMatch(action="dangerous_action"),
                action=RuleAction(type=ActionType.DENY),
            )],
        )
        
        # OPERATOR tries to override the ROOT rule
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            rules=[PolicyRule(
                id="critical-rule",  # Same ID = override attempt
                description="Trying to allow dangerous action",
                priority=100,
                match=RuleMatch(action="dangerous_action"),
                action=RuleAction(type=ActionType.ALLOW),  # Changed DENY to ALLOW!
            )],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "trust downgrade" in str(exc_info.value).lower()
    
    def test_audit_cannot_override_operator_rule(self):
        """AUDIT cannot override a rule defined by OPERATOR."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[PolicyRule(
                id="operator-rule",
                priority=50,
                match=RuleMatch(action="some_action"),
                action=RuleAction(type=ActionType.DENY),
            )],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            rules=[PolicyRule(
                id="operator-rule",
                priority=50,
                match=RuleMatch(action="some_action"),
                action=RuleAction(type=ActionType.ALLOW),
            )],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.OPERATOR),
                (child, KeyTrust.AUDIT),
            ])
        
        assert "trust downgrade" in str(exc_info.value).lower()
    
    def test_root_can_override_operator_rule(self):
        """ROOT can override a rule defined by OPERATOR."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[PolicyRule(
                id="operator-rule",
                priority=50,
                match=RuleMatch(action="some_action"),
                action=RuleAction(type=ActionType.DENY),
            )],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            rules=[PolicyRule(
                id="operator-rule",
                priority=50,
                match=RuleMatch(action="some_action"),
                action=RuleAction(type=ActionType.ALLOW),
            )],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.OPERATOR),
            (child, KeyTrust.ROOT),
        ])
        
        # The override should succeed
        assert len(report.rules_overridden) == 1
        # Final rule should be ALLOW
        final_rule = next(r for r in result.rules if r.id == "operator-rule")
        assert final_rule.action.type == ActionType.ALLOW
    
    def test_same_trust_can_override(self):
        """Same trust level can override previous rule."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[PolicyRule(
                id="shared-rule",
                priority=50,
                match=RuleMatch(action="action"),
                action=RuleAction(type=ActionType.DENY),
            )],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            rules=[PolicyRule(
                id="shared-rule",
                priority=50,
                match=RuleMatch(action="action"),
                action=RuleAction(type=ActionType.ALLOW),
            )],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.OPERATOR),
            (child, KeyTrust.OPERATOR),
        ])
        
        # Same trust level override is allowed
        assert len(report.rules_overridden) == 1
        final_rule = next(r for r in result.rules if r.id == "shared-rule")
        assert final_rule.action.type == ActionType.ALLOW


# =============================================================================
# ZONE VALIDATION TESTS
# =============================================================================

class TestZoneValidation:
    """Tests for zone identity validation."""
    
    def test_zone_modification_rejected(self):
        """Child cannot modify zone definitions."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
                TrustZone(name="USER", trust_level=2),
            ],
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # Child tries to change zone trust level
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            zones=[
                TrustZone(name="CORE", trust_level=1),  # Changed from 3 to 1!
                TrustZone(name="USER", trust_level=2),
            ],
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "zone" in str(exc_info.value).lower()
    
    def test_zone_addition_rejected(self):
        """Child cannot add new zones."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
            ],
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # Child tries to add a new zone
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
                TrustZone(name="NEW_ZONE", trust_level=1),  # New zone!
            ],
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "zone" in str(exc_info.value).lower()
    
    def test_zone_removal_rejected(self):
        """Child cannot remove zones."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
                TrustZone(name="USER", trust_level=2),
            ],
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # Child removes a zone
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
                # USER zone removed!
            ],
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "zone" in str(exc_info.value).lower()
    
    def test_identical_zones_accepted(self):
        """Identical zones between parent and child are accepted."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
            ],
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            zones=[
                TrustZone(name="CORE", trust_level=3),
            ],
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        # Should not raise
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.OPERATOR),
        ])
        
        assert len(result.zones) == 1
        assert result.zones[0].name == "CORE"


# =============================================================================
# FAILURE MODE PROTECTION TESTS
# =============================================================================

class TestFailureModeProtection:
    """Tests for failure_mode protection (ROOT only)."""
    
    def test_operator_cannot_modify_failure_mode(self):
        """OPERATOR cannot modify failure_mode configuration."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            failure_mode=FailureModeConfig(
                default_action=ActionType.DENY,
            ),
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        # OPERATOR tries to change failure mode
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            failure_mode=FailureModeConfig(
                default_action=ActionType.ALLOW,  # Changed from deny to allow!
            ),
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            engine.merge([
                (base, KeyTrust.ROOT),
                (child, KeyTrust.OPERATOR),
            ])
        
        assert "failure" in str(exc_info.value).lower() or "root" in str(exc_info.value).lower()
    
    def test_root_can_modify_failure_mode(self):
        """ROOT can modify failure_mode configuration."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            failure_mode=FailureModeConfig(
                default_action=ActionType.DENY,
            ),
            rules=[create_test_rule(id="rule1", priority=50)],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            failure_mode=FailureModeConfig(
                default_action=ActionType.ALLOW,
            ),
            rules=[create_test_rule(id="rule2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.ROOT),  # ROOT can modify
        ])
        
        # Failure mode should be updated
        assert result.failure_mode.default_action == ActionType.ALLOW


# =============================================================================
# RULE MERGE TESTS
# =============================================================================

class TestRuleMerge:
    """Tests for rule merging and conflict resolution."""
    
    def test_rules_combined_from_all_policies(self):
        """Rules from all policies in chain are combined."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[
                create_test_rule(id="base-rule-1", match_action="a", priority=50),
                create_test_rule(id="base-rule-2", action_type=ActionType.DENY, match_action="b", priority=40),
            ],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            rules=[
                create_test_rule(id="child-rule-1", match_action="c", priority=60),
                create_test_rule(id="child-rule-2", action_type=ActionType.DENY, match_action="d", priority=70),
            ],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.ROOT),
        ])
        
        # All 4 rules should be present
        rule_ids = {r.id for r in result.rules}
        assert rule_ids == {"base-rule-1", "base-rule-2", "child-rule-1", "child-rule-2"}
        
        # Report should track all added rules
        assert len(report.rules_added) == 4
    
    def test_rules_sorted_by_priority(self):
        """Merged rules are sorted by priority (highest first)."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[
                create_test_rule(id="low", match_action="a", priority=10),
                create_test_rule(id="high", action_type=ActionType.DENY, match_action="b", priority=100),
            ],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            rules=[
                create_test_rule(id="medium", match_action="c", priority=50),
            ],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.ROOT),
        ])
        
        # Rules should be sorted by priority (descending)
        priorities = [r.priority for r in result.rules]
        assert priorities == sorted(priorities, reverse=True)


# =============================================================================
# METADATA MERGE TESTS
# =============================================================================

class TestMetadataMerge:
    """Tests for metadata merging."""
    
    def test_child_name_used(self):
        """Final policy uses child's name."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            rules=[create_test_rule(id="r", priority=50)],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="2.0.0", inherits="base"),
            rules=[create_test_rule(id="r2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.OPERATOR),
        ])
        
        assert result.metadata.name == "child"
        assert result.metadata.version == "2.0.0"
    
    def test_labels_merged(self):
        """Labels from parent and child are merged."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(
                name="base",
                version="1.0.0",
                labels={"env": "production", "team": "security"},
            ),
            rules=[create_test_rule(id="r", priority=50)],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(
                name="child",
                version="2.0.0",
                inherits="base",
                labels={"team": "platform", "feature": "new"},  # Overrides team, adds feature
            ),
            rules=[create_test_rule(id="r2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.OPERATOR),
        ])
        
        # Labels should be merged with child overriding
        assert result.metadata.labels["env"] == "production"  # From base
        assert result.metadata.labels["team"] == "platform"  # From child (override)
        assert result.metadata.labels["feature"] == "new"  # From child (new)


# =============================================================================
# INTEGRATION TESTS (FULL LOADER)
# =============================================================================

class TestMergeIntegration:
    """Integration tests using PolicyLoader."""
    
    def test_merge_with_inheritance_chain(self, temp_policies_dir, signer, verifier, loader):
        """Test complete merge through inheritance chain."""
        # Create base policy
        base_policy = create_base_policy(
            name="base",
            version="1.0.0",
            allowlists={
                "domains": {
                    "type": "domain",
                    "entries": ["a.com", "b.com", "c.com"]
                }
            },
            rules=[
                {"id": "base-rule", "match": {"action": "read"}, "action": {"type": "ALLOW"}, "priority": 50},
            ],
        )
        
        # Sign base with ROOT
        signature, _ = signer.sign_policy(base_policy, key_id="root_key")
        base_policy["signature"] = signature.model_dump(mode="json")
        
        base_path = temp_policies_dir / "base.yaml"
        with open(base_path, "w") as f:
            yaml.dump(base_policy, f)
        
        # Create child policy - only rules, no allowlists (OPERATOR can sign rules)
        child_policy = create_base_policy(
            name="child",
            version="1.0.0",
            inherits="base",
            rules=[
                {"id": "child-rule", "match": {"action": "write"}, "action": {"type": "DENY"}, "priority": 60},
            ],
        )
        
        # Sign child with OPERATOR (no allowlists, so this is allowed)
        signature, _ = signer.sign_policy(child_policy, key_id="operator_key")
        child_policy["signature"] = signature.model_dump(mode="json")
        
        child_path = temp_policies_dir / "child.yaml"
        with open(child_path, "w") as f:
            yaml.dump(child_policy, f)
        
        # Load the child (should merge with base)
        final = loader.load_policy("child", require_signature=True)
        
        # Verify merge results
        assert final.document.metadata.name == "child"
        
        # Both rules should be present
        rule_ids = {r.id for r in final.document.rules}
        assert "base-rule" in rule_ids
        assert "child-rule" in rule_ids
        
        # Allowlist should be inherited from base (3 entries)
        assert len(final.document.allowlists["domains"].entries) == 3
        
        # Trust level should be minimum (OPERATOR)
        assert final.trust_level == KeyTrust.OPERATOR
        
        # Merge report should be present
        assert final.merge_report is not None


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_policies_list_raises(self):
        """Empty policies list raises error."""
        engine = PolicyMergeEngine()
        
        with pytest.raises(PolicyLoadError):
            engine.merge([])
    
    def test_single_policy_no_merge(self):
        """Single policy returns as-is without merge."""
        engine = PolicyMergeEngine()
        
        policy = PolicyDocument(
            metadata=PolicyMetadata(name="single", version="1.0.0"),
            rules=[create_test_rule(id="r", priority=50)],
        )
        
        result, report = engine.merge([(policy, KeyTrust.ROOT)])
        
        assert result.metadata.name == "single"
        assert len(result.rules) == 1
        assert len(report.rules_added) == 1  # Base rules counted as "added"
    
    def test_child_no_zones_inherits_parent(self):
        """Child without zones inherits parent zones."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            zones=[TrustZone(name="CORE", trust_level=3)],
            rules=[create_test_rule(id="r", priority=50)],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            # No zones defined
            rules=[create_test_rule(id="r2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.OPERATOR),
        ])
        
        # Child inherits parent's zones
        assert len(result.zones) == 1
        assert result.zones[0].name == "CORE"
    
    def test_child_no_allowlists_inherits_parent(self):
        """Child without allowlists inherits parent allowlists."""
        engine = PolicyMergeEngine()
        
        base = PolicyDocument(
            metadata=PolicyMetadata(name="base", version="1.0.0"),
            allowlists={
                "domains": Allowlist(type="domain", entries=["example.com"])
            },
            rules=[create_test_rule(id="r", priority=50)],
        )
        
        child = PolicyDocument(
            metadata=PolicyMetadata(name="child", version="1.0.0", inherits="base"),
            # No allowlists defined
            rules=[create_test_rule(id="r2", priority=60)],
        )
        
        result, report = engine.merge([
            (base, KeyTrust.ROOT),
            (child, KeyTrust.OPERATOR),
        ])
        
        # Child inherits parent's allowlists
        assert "domains" in result.allowlists
        assert len(result.allowlists["domains"].entries) == 1
