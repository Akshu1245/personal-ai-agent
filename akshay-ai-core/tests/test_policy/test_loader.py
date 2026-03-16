"""
AKSHAY AI CORE — Policy Loader Tests

Tests for:
- Inheritance graph building
- Cycle detection
- Depth limit enforcement
- Signature verification before merge
- Trust level tracking
- Safe mode fallback
"""

import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml

from core.policy.loader import (
    PolicyLoader,
    InheritanceGraph,
    InheritanceNode,
    InheritanceNodeStatus,
    FinalPolicy,
    PolicySourceInfo,
    SignatureVerificationStatus,
    MAX_INHERITANCE_DEPTH,
    MAX_POLICY_SIZE_BYTES,
    SAFE_MODE_POLICY_NAME,
    create_safe_mode_policy,
)
from core.policy.schema import (
    PolicyDocument,
    PolicyMetadata,
    PolicyRule,
    RuleMatch,
    RuleAction,
    ActionType,
)
from core.policy.signer import PolicySigner, KeyTrust
from core.policy.verifier import PolicyVerifier, VerificationStatus
from core.policy.errors import (
    PolicyLoadError,
    PolicyInheritanceCycleError,
    PolicyInheritanceError,
    PolicySignatureMissingError,
    PolicySignatureInvalidError,
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
    """Create a PolicySigner with test keys."""
    signer = PolicySigner()
    signer.generate_hmac_key(key_id="test_root_key", trust=KeyTrust.ROOT)
    signer.generate_hmac_key(key_id="test_operator_key", trust=KeyTrust.OPERATOR)
    return signer


@pytest.fixture
def verifier(signer):
    """Create a PolicyVerifier with test keys registered."""
    verifier = PolicyVerifier()
    
    # Register the keys from signer
    for key_id in ["test_root_key", "test_operator_key"]:
        key = signer.get_key(key_id)
        if key:
            secret = signer._hmac_secrets.get(key_id)
            if secret:
                import base64
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
        require_signatures=False,  # For easier testing
    )


@pytest.fixture
def loader_with_signatures(temp_policies_dir, verifier):
    """Create a PolicyLoader that requires signatures."""
    return PolicyLoader(
        policies_dir=temp_policies_dir,
        verifier=verifier,
        require_signatures=True,
    )


def create_policy_yaml(
    name: str,
    version: str = "1.0.0",
    inherits: str = None,
    rules: list = None,
) -> Dict[str, Any]:
    """Create a minimal policy YAML structure."""
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
                "id": f"{name.upper()}-001",
                "priority": 100,
                "match": {"any": True},
                "action": {"type": "DENY"},
            }
        ],
    }
    if inherits:
        policy["metadata"]["inherits"] = inherits
    return policy


def write_policy_file(
    policies_dir: Path,
    name: str,
    policy_data: Dict[str, Any],
) -> Path:
    """Write a policy to the test directory."""
    file_path = policies_dir / f"{name}.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(policy_data, f)
    return file_path


# =============================================================================
# INHERITANCE GRAPH TESTS
# =============================================================================

class TestInheritanceGraph:
    """Tests for the InheritanceGraph class."""
    
    def test_add_node(self):
        """Nodes can be added to the graph."""
        graph = InheritanceGraph()
        node = InheritanceNode(
            policy_name="test",
            version="1.0.0",
            file_path=Path("test.yaml"),
            raw_data={},
        )
        graph.add_node(node)
        
        assert graph.get_node("test") == node
    
    def test_add_edge(self):
        """Edges can be added between nodes."""
        graph = InheritanceGraph()
        
        # Add nodes
        parent = InheritanceNode("parent", "1.0.0", Path("parent.yaml"), {})
        child = InheritanceNode("child", "1.0.0", Path("child.yaml"), {})
        
        graph.add_node(parent)
        graph.add_node(child)
        graph.add_edge("child", "parent")
        
        assert "parent" in graph.get_parents("child")
        assert "child" in graph.get_children("parent")
    
    def test_detect_cycle_none(self):
        """No cycle detected in acyclic graph."""
        graph = InheritanceGraph()
        
        # Create linear chain: A -> B -> C
        for name in ["a", "b", "c"]:
            graph.add_node(InheritanceNode(name, "1.0.0", Path(f"{name}.yaml"), {}))
        
        graph.add_edge("a", "b")  # a inherits from b
        graph.add_edge("b", "c")  # b inherits from c
        
        assert graph.detect_cycle("a") is None
    
    def test_detect_cycle_simple(self):
        """Simple cycle is detected."""
        graph = InheritanceGraph()
        
        # Create cycle: A -> B -> A
        for name in ["a", "b"]:
            graph.add_node(InheritanceNode(name, "1.0.0", Path(f"{name}.yaml"), {}))
        
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        
        cycle = graph.detect_cycle("a")
        assert cycle is not None
        assert "a" in cycle
        assert "b" in cycle
    
    def test_detect_cycle_complex(self):
        """Complex cycle is detected."""
        graph = InheritanceGraph()
        
        # Create: A -> B -> C -> D -> B (cycle through B-C-D)
        for name in ["a", "b", "c", "d"]:
            graph.add_node(InheritanceNode(name, "1.0.0", Path(f"{name}.yaml"), {}))
        
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "d")
        graph.add_edge("d", "b")  # Creates cycle
        
        cycle = graph.detect_cycle("a")
        assert cycle is not None
        assert len(cycle) >= 3  # At least B-C-D-B
    
    def test_get_inheritance_chain(self):
        """Inheritance chain is correctly computed."""
        graph = InheritanceGraph()
        
        # Create: child -> parent -> grandparent
        for name in ["child", "parent", "grandparent"]:
            graph.add_node(InheritanceNode(name, "1.0.0", Path(f"{name}.yaml"), {}))
        
        graph.add_edge("child", "parent")
        graph.add_edge("parent", "grandparent")
        
        chain = graph.get_inheritance_chain("child")
        
        # Should be: grandparent, parent, child (root first)
        assert chain == ["grandparent", "parent", "child"]
    
    def test_get_depth(self):
        """Depth is correctly computed."""
        graph = InheritanceGraph()
        
        # Create 4-level chain
        for name in ["a", "b", "c", "d"]:
            graph.add_node(InheritanceNode(name, "1.0.0", Path(f"{name}.yaml"), {}))
        
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "d")
        
        assert graph.get_depth("d") == 0  # Root
        assert graph.get_depth("c") == 1
        assert graph.get_depth("b") == 2
        assert graph.get_depth("a") == 3
    
    def test_topological_sort(self):
        """Topological sort orders parents before children."""
        graph = InheritanceGraph()
        
        # Create: child -> parent -> root
        for name in ["root", "parent", "child"]:
            graph.add_node(InheritanceNode(name, "1.0.0", Path(f"{name}.yaml"), {}))
        
        graph.add_edge("child", "parent")
        graph.add_edge("parent", "root")
        
        order = graph.topological_sort()
        
        # Root should come before parent, parent before child
        assert order.index("root") < order.index("parent")
        assert order.index("parent") < order.index("child")


# =============================================================================
# POLICY LOADER TESTS
# =============================================================================

class TestPolicyLoader:
    """Tests for the PolicyLoader class."""
    
    def test_load_simple_policy(self, loader, temp_policies_dir):
        """Simple policy without inheritance loads correctly."""
        policy_data = create_policy_yaml("simple")
        write_policy_file(temp_policies_dir, "simple", policy_data)
        
        result = loader.load_policy("simple")
        
        assert isinstance(result, FinalPolicy)
        assert result.document.metadata.name == "simple"
        assert len(result.source_chain) == 1
    
    def test_load_policy_by_path(self, loader, temp_policies_dir):
        """Policy can be loaded by file path."""
        policy_data = create_policy_yaml("bypath")
        file_path = write_policy_file(temp_policies_dir, "bypath", policy_data)
        
        result = loader.load_policy(file_path)
        
        assert result.document.metadata.name == "bypath"
    
    def test_load_policy_with_inheritance(self, loader, temp_policies_dir):
        """Policy with single-level inheritance loads correctly."""
        # Create parent
        parent_data = create_policy_yaml("parent")
        write_policy_file(temp_policies_dir, "parent", parent_data)
        
        # Create child that inherits from parent
        child_data = create_policy_yaml("child", inherits="parent")
        write_policy_file(temp_policies_dir, "child", child_data)
        
        result = loader.load_policy("child")
        
        assert len(result.source_chain) == 2
        assert result.source_chain[0].name == "parent"
        assert result.source_chain[1].name == "child"
    
    def test_load_policy_multi_level_inheritance(self, loader, temp_policies_dir):
        """Multi-level inheritance chain loads correctly."""
        # Create grandparent -> parent -> child
        write_policy_file(temp_policies_dir, "grandparent", 
                         create_policy_yaml("grandparent"))
        write_policy_file(temp_policies_dir, "parent",
                         create_policy_yaml("parent", inherits="grandparent"))
        write_policy_file(temp_policies_dir, "child",
                         create_policy_yaml("child", inherits="parent"))
        
        result = loader.load_policy("child")
        
        assert len(result.source_chain) == 3
        names = [s.name for s in result.source_chain]
        assert names == ["grandparent", "parent", "child"]
    
    def test_load_policy_not_found(self, loader):
        """Missing policy raises error."""
        with pytest.raises(PolicyLoadError) as exc_info:
            loader.load_policy("nonexistent")
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_inheritance_cycle_detected(self, loader, temp_policies_dir):
        """Circular inheritance is detected and rejected."""
        # Create cycle: a -> b -> c -> a
        write_policy_file(temp_policies_dir, "a",
                         create_policy_yaml("a", inherits="b"))
        write_policy_file(temp_policies_dir, "b",
                         create_policy_yaml("b", inherits="c"))
        write_policy_file(temp_policies_dir, "c",
                         create_policy_yaml("c", inherits="a"))
        
        with pytest.raises(PolicyInheritanceCycleError) as exc_info:
            loader.load_policy("a")
        
        assert "cycle" in str(exc_info.value).lower()
    
    def test_inheritance_self_cycle(self, loader, temp_policies_dir):
        """Self-referential inheritance is detected."""
        write_policy_file(temp_policies_dir, "selfish",
                         create_policy_yaml("selfish", inherits="selfish"))
        
        with pytest.raises(PolicyInheritanceCycleError):
            loader.load_policy("selfish")
    
    def test_inheritance_depth_limit(self, loader, temp_policies_dir):
        """Inheritance depth limit is enforced."""
        # Create chain deeper than MAX_INHERITANCE_DEPTH
        depth = MAX_INHERITANCE_DEPTH + 2
        
        for i in range(depth):
            name = f"level{i}"
            inherits = f"level{i+1}" if i < depth - 1 else None
            write_policy_file(temp_policies_dir, name,
                             create_policy_yaml(name, inherits=inherits))
        
        with pytest.raises(PolicyInheritanceError) as exc_info:
            loader.load_policy("level0")
        
        assert exc_info.value.code == PolicyErrorCode.INHERITANCE_DEPTH_EXCEEDED
    
    def test_policy_size_limit(self, loader, temp_policies_dir):
        """Large policy files are rejected."""
        # Create a policy that exceeds size limit
        large_rules = []
        for i in range(5000):  # Many rules to exceed size
            large_rules.append({
                "id": f"LARGE-{i:05d}",
                "priority": i,
                "description": "x" * 100,  # Pad with description
                "match": {"action": f"action.{i}", "domain": f"domain{i}.example.com"},
                "action": {"type": "DENY", "reason": "x" * 100},
            })
        
        policy_data = create_policy_yaml("large", rules=large_rules)
        file_path = write_policy_file(temp_policies_dir, "large", policy_data)
        
        # Check if file is actually large enough
        file_size = file_path.stat().st_size
        if file_size > MAX_POLICY_SIZE_BYTES:
            with pytest.raises(PolicyLoadError) as exc_info:
                loader.load_policy("large")
            assert "too large" in str(exc_info.value).lower()
        else:
            pytest.skip(f"File size {file_size} did not exceed limit")


# =============================================================================
# SIGNATURE VERIFICATION TESTS
# =============================================================================

class TestSignatureVerification:
    """Tests for signature verification during loading."""
    
    def test_unsigned_policy_rejected_when_required(
        self, loader_with_signatures, temp_policies_dir
    ):
        """Unsigned policy rejected when signatures required."""
        policy_data = create_policy_yaml("unsigned")
        write_policy_file(temp_policies_dir, "unsigned", policy_data)
        
        with pytest.raises(PolicySignatureMissingError):
            loader_with_signatures.load_policy("unsigned")
    
    def test_signed_policy_accepted(
        self, signer, verifier, temp_policies_dir
    ):
        """Properly signed policy is accepted."""
        loader = PolicyLoader(
            policies_dir=temp_policies_dir,
            verifier=verifier,
            require_signatures=True,
        )
        
        # Create and sign a policy
        policy_data = create_policy_yaml("signed")
        
        # Sign with ROOT key (since policy has failure_mode by default)
        signature, _ = signer.sign_policy(policy_data, "test_root_key")
        policy_data["signature"] = signature.model_dump(mode="json")
        
        write_policy_file(temp_policies_dir, "signed", policy_data)
        
        result = loader.load_policy("signed")
        
        assert result.signature_status == SignatureVerificationStatus.VERIFIED
        assert result.trust_level == KeyTrust.ROOT


# =============================================================================
# TRUST LEVEL TESTS
# =============================================================================

class TestTrustLevels:
    """Tests for trust level tracking."""
    
    def test_minimum_trust_in_chain(self, signer, verifier, temp_policies_dir):
        """Minimum trust level in chain is tracked."""
        loader = PolicyLoader(
            policies_dir=temp_policies_dir,
            verifier=verifier,
            require_signatures=False,
        )
        
        # Create parent with ROOT trust (by signing with ROOT key)
        parent_data = create_policy_yaml("parent")
        sig1, _ = signer.sign_policy(parent_data, "test_root_key")
        parent_data["signature"] = sig1.model_dump(mode="json")
        write_policy_file(temp_policies_dir, "parent", parent_data)
        
        # Create child (don't inherit failure_mode, use minimal)
        child_data = {
            "apiVersion": "policy.akshay.ai/v1",
            "kind": "PolicyDocument",
            "metadata": {
                "name": "child",
                "version": "1.0.0",
                "inherits": "parent",
            },
            "rules": [
                {
                    "id": "CHILD-001",
                    "priority": 100,
                    "match": {"any": True},
                    "action": {"type": "DENY"},
                }
            ],
        }
        sig2, _ = signer.sign_policy(child_data, "test_operator_key")
        child_data["signature"] = sig2.model_dump(mode="json")
        write_policy_file(temp_policies_dir, "child", child_data)
        
        result = loader.load_policy("child")
        
        # Should be OPERATOR (the lower of ROOT and OPERATOR)
        assert result.trust_level == KeyTrust.OPERATOR


# =============================================================================
# SAFE MODE TESTS
# =============================================================================

class TestSafeMode:
    """Tests for safe mode fallback."""
    
    def test_safe_mode_policy_created(self):
        """Safe mode policy is properly created."""
        policy = create_safe_mode_policy()
        
        assert policy.metadata.name == SAFE_MODE_POLICY_NAME
        assert len(policy.rules) >= 2  # At least allow and deny rules
        assert policy.failure_mode.default_action == ActionType.DENY
    
    def test_get_safe_mode_policy(self, loader):
        """Loader can return safe mode policy."""
        safe = loader.get_safe_mode_policy()
        
        assert isinstance(safe, FinalPolicy)
        assert safe.document.metadata.name == SAFE_MODE_POLICY_NAME
        assert safe.trust_level == KeyTrust.ROOT
        assert "SAFE MODE" in safe.warnings[0]
    
    def test_safe_mode_policy_immutable(self):
        """Safe mode policy rules are reasonable."""
        policy = create_safe_mode_policy()
        
        # Should have allow rules for safe actions
        allow_rules = [r for r in policy.rules if r.action.type == ActionType.ALLOW]
        deny_rules = [r for r in policy.rules if r.action.type == ActionType.DENY]
        
        assert len(allow_rules) >= 4  # memory.read, system.status, etc.
        assert len(deny_rules) >= 1  # Default deny


# =============================================================================
# ACTIVE POLICY TESTS
# =============================================================================

class TestActivePolicy:
    """Tests for active policy loading."""
    
    def test_load_active_from_pointer(self, loader, temp_policies_dir):
        """Active policy loaded from .active_version pointer."""
        # Create policy
        write_policy_file(temp_policies_dir, "production",
                         create_policy_yaml("production"))
        
        # Create pointer
        pointer_file = temp_policies_dir / ".active_version"
        pointer_file.write_text("production")
        
        result = loader.load_active_policy()
        
        assert result.document.metadata.name == "production"
    
    def test_load_active_from_file(self, loader, temp_policies_dir):
        """Active policy loaded from active.yaml file."""
        # Create active.yaml directly
        write_policy_file(temp_policies_dir, "active",
                         create_policy_yaml("active"))
        
        result = loader.load_active_policy()
        
        assert result.document.metadata.name == "active"
    
    def test_no_active_policy_error(self, loader):
        """Error when no active policy found."""
        with pytest.raises(PolicyLoadError) as exc_info:
            loader.load_active_policy()
        
        assert "active" in str(exc_info.value).lower()


# =============================================================================
# CACHE TESTS
# =============================================================================

class TestCache:
    """Tests for policy caching."""
    
    def test_list_available_policies(self, loader, temp_policies_dir):
        """Available policies are listed correctly."""
        # Create several policies
        for name in ["alpha", "beta", "gamma"]:
            write_policy_file(temp_policies_dir, name,
                             create_policy_yaml(name))
        
        available = loader.list_available_policies()
        
        assert "alpha" in available
        assert "beta" in available
        assert "gamma" in available
    
    def test_clear_cache(self, loader, temp_policies_dir):
        """Cache can be cleared."""
        write_policy_file(temp_policies_dir, "cached",
                         create_policy_yaml("cached"))
        
        loader.load_policy("cached")
        loader.clear_cache()
        
        # Should still be able to load
        result = loader.load_policy("cached")
        assert result.document.metadata.name == "cached"


# =============================================================================
# FINAL POLICY TESTS
# =============================================================================

class TestFinalPolicy:
    """Tests for FinalPolicy output."""
    
    def test_content_hash_computed(self, loader, temp_policies_dir):
        """Content hash is computed on FinalPolicy creation."""
        write_policy_file(temp_policies_dir, "hashed",
                         create_policy_yaml("hashed"))
        
        result = loader.load_policy("hashed")
        
        assert result.content_hash
        assert len(result.content_hash) == 64  # SHA-256 hex
    
    def test_audit_dict_complete(self, loader, temp_policies_dir):
        """Audit dict contains all required fields."""
        write_policy_file(temp_policies_dir, "audited",
                         create_policy_yaml("audited"))
        
        result = loader.load_policy("audited")
        audit = result.to_audit_dict()
        
        assert "source_chain" in audit
        assert "signature_status" in audit
        assert "trust_level" in audit
        assert "content_hash" in audit
        assert "rule_count" in audit
