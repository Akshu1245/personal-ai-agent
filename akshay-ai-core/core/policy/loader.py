"""
AKSHAY AI CORE — Policy Loader

Secure policy loading with inheritance resolution.

MISSION:
Load policies from config/policies/, verify signatures BEFORE processing,
resolve inheritance chains safely, and produce immutable, enforceable policy objects.

NON-NEGOTIABLE RULES:
1. Never merge before verifying signature
2. Never allow lower-trust keys to override higher-trust fields
3. Never allow child policies to weaken parent restrictions
4. Never allow inheritance loops
5. Fail closed — SAFE MODE on ambiguity

INHERITANCE RESOLUTION FLOW:
1. Load base policy
2. Verify signature + trust
3. Load child policy
4. Verify signature + trust
5. Build merge context
6. Apply merge rules
7. Validate final document
8. Freeze final object

MERGE SEMANTICS:
- Metadata: Child can override version/description, NOT zones/failure_mode/allowlists
- Allowlists: Default = intersection, child cannot expand (unless ROOT-signed)
- Rules: Combine sets, child wins conflicts if same/higher trust
- Zones: Must be identical or reject
"""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

import yaml
from pydantic import BaseModel, Field, ConfigDict

from core.policy.errors import (
    PolicyError,
    PolicyLoadError,
    PolicyValidationError,
    PolicySignatureError,
    PolicySignatureInvalidError,
    PolicySignatureMissingError,
    PolicyInheritanceError,
    PolicyInheritanceCycleError,
    PolicyKeyError,
    PolicyErrorCode,
    PolicyErrorContext,
)
from core.policy.schema import (
    PolicyDocument,
    PolicyMetadata,
    PolicySignature,
    PolicyRule,
    TrustZone,
    Allowlist,
    AllowlistEntry,
    DeviceAllowlistEntry,
    FailureModeConfig,
    SafeModeConfig,
    SignatureAlgorithm,
    ActionType,
    RuleMatch,
    RuleAction,
)
from core.policy.signer import KeyTrust, PolicyCanonicalizer
from core.policy.verifier import PolicyVerifier, VerificationStatus, VerificationResult


# =============================================================================
# CONSTANTS
# =============================================================================

# Security limits
MAX_INHERITANCE_DEPTH = 5
MAX_POLICY_SIZE_BYTES = 512 * 1024  # 512KB
MAX_RULES_PER_POLICY = 1000
MAX_ALLOWLIST_ENTRIES = 10000

# Default paths
DEFAULT_POLICIES_DIR = Path("config/policies")
DEFAULT_ACTIVE_FILE = "active.yaml"
DEFAULT_ACTIVE_POINTER = ".active_version"

# Safe mode minimal policy
SAFE_MODE_POLICY_NAME = "system-safe-mode"


# =============================================================================
# INHERITANCE GRAPH MODELS
# =============================================================================

class InheritanceNodeStatus(str, Enum):
    """Status of a node in the inheritance graph."""
    UNVISITED = "UNVISITED"
    VISITING = "VISITING"  # Currently in DFS path (for cycle detection)
    VISITED = "VISITED"
    VERIFIED = "VERIFIED"  # Signature verified
    MERGED = "MERGED"
    FAILED = "FAILED"


@dataclass
class InheritanceNode:
    """A node in the inheritance graph."""
    
    policy_name: str
    version: str
    file_path: Path
    raw_data: Dict[str, Any]
    status: InheritanceNodeStatus = InheritanceNodeStatus.UNVISITED
    
    # Signature verification
    signature_status: Optional[VerificationResult] = None
    trust_level: Optional[str] = None
    
    # Inheritance
    parent_name: Optional[str] = None
    depth: int = 0
    
    # Loaded document (after verification)
    document: Optional[PolicyDocument] = None
    
    def __hash__(self) -> int:
        return hash((self.policy_name, self.version))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InheritanceNode):
            return False
        return self.policy_name == other.policy_name and self.version == other.version


@dataclass
class InheritanceEdge:
    """An edge in the inheritance graph (child -> parent)."""
    
    child_name: str
    parent_name: str
    trust_level: str
    
    def __hash__(self) -> int:
        return hash((self.child_name, self.parent_name))


class InheritanceGraph:
    """
    Directed graph representing policy inheritance relationships.
    
    Used for:
    - Cycle detection (DFS)
    - Topological ordering (for merge order)
    - Trust validation
    """
    
    def __init__(self):
        self._nodes: Dict[str, InheritanceNode] = {}
        self._edges: Dict[str, Set[str]] = {}  # child -> parents
        self._reverse_edges: Dict[str, Set[str]] = {}  # parent -> children
        self._lock = threading.RLock()
    
    def add_node(self, node: InheritanceNode) -> None:
        """Add a node to the graph."""
        with self._lock:
            self._nodes[node.policy_name] = node
            if node.policy_name not in self._edges:
                self._edges[node.policy_name] = set()
            if node.policy_name not in self._reverse_edges:
                self._reverse_edges[node.policy_name] = set()
    
    def add_edge(self, child_name: str, parent_name: str) -> None:
        """Add an inheritance edge (child inherits from parent)."""
        with self._lock:
            if child_name not in self._edges:
                self._edges[child_name] = set()
            self._edges[child_name].add(parent_name)
            
            if parent_name not in self._reverse_edges:
                self._reverse_edges[parent_name] = set()
            self._reverse_edges[parent_name].add(child_name)
    
    def get_node(self, name: str) -> Optional[InheritanceNode]:
        """Get a node by name."""
        with self._lock:
            return self._nodes.get(name)
    
    def get_parents(self, name: str) -> Set[str]:
        """Get parent names for a node."""
        with self._lock:
            return self._edges.get(name, set()).copy()
    
    def get_children(self, name: str) -> Set[str]:
        """Get child names for a node."""
        with self._lock:
            return self._reverse_edges.get(name, set()).copy()
    
    def detect_cycle(self, start_name: str) -> Optional[List[str]]:
        """
        Detect cycles starting from a node using DFS.
        
        Returns:
            List of node names forming the cycle, or None if no cycle
        """
        with self._lock:
            visited: Set[str] = set()
            path: List[str] = []
            path_set: Set[str] = set()
            
            def dfs(name: str) -> Optional[List[str]]:
                if name in path_set:
                    # Found cycle - extract it
                    cycle_start = path.index(name)
                    return path[cycle_start:] + [name]
                
                if name in visited:
                    return None
                
                visited.add(name)
                path.append(name)
                path_set.add(name)
                
                for parent in self._edges.get(name, set()):
                    cycle = dfs(parent)
                    if cycle:
                        return cycle
                
                path.pop()
                path_set.remove(name)
                return None
            
            return dfs(start_name)
    
    def get_inheritance_chain(self, name: str) -> List[str]:
        """
        Get the inheritance chain from root to node.
        
        Returns:
            List starting from root ancestor, ending with the node
        """
        with self._lock:
            chain: List[str] = []
            visited: Set[str] = set()
            
            def build_chain(current: str) -> None:
                if current in visited:
                    return
                visited.add(current)
                
                # First visit parents (recursively)
                for parent in self._edges.get(current, set()):
                    build_chain(parent)
                
                chain.append(current)
            
            build_chain(name)
            return chain
    
    def get_depth(self, name: str) -> int:
        """Get the depth of a node in the inheritance hierarchy."""
        with self._lock:
            if name not in self._nodes:
                return 0
            
            parents = self._edges.get(name, set())
            if not parents:
                return 0
            
            return 1 + max(self.get_depth(p) for p in parents)
    
    def topological_sort(self) -> List[str]:
        """
        Get topological ordering (parents before children).
        
        Used for merge ordering.
        """
        with self._lock:
            in_degree: Dict[str, int] = {n: 0 for n in self._nodes}
            for child, parents in self._edges.items():
                for parent in parents:
                    if child in in_degree:
                        in_degree[child] += 1
            
            # Start with nodes that have no parents
            queue = [n for n, d in in_degree.items() if d == 0]
            result: List[str] = []
            
            while queue:
                node = queue.pop(0)
                result.append(node)
                
                for child in self._reverse_edges.get(node, set()):
                    if child in in_degree:
                        in_degree[child] -= 1
                        if in_degree[child] == 0:
                            queue.append(child)
            
            return result


# =============================================================================
# FINAL POLICY RESULT
# =============================================================================

class SignatureVerificationStatus(str, Enum):
    """Status of signature verification for the final policy."""
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"  # Some in chain had warnings
    FAILED = "FAILED"


@dataclass
class PolicySourceInfo:
    """Information about a policy in the inheritance chain."""
    
    name: str
    version: str
    file_path: str
    signed_by: Optional[str]
    trust_level: str
    verified_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "file_path": self.file_path,
            "signed_by": self.signed_by,
            "trust_level": self.trust_level,
            "verified_at": self.verified_at.isoformat(),
        }


@dataclass
class FinalPolicy:
    """
    The final, immutable, enforceable policy object.
    
    This is the OUTPUT of the loader - ready for the policy engine.
    """
    
    # Inheritance chain (root first)
    source_chain: List[PolicySourceInfo]
    
    # Verification status
    signature_status: SignatureVerificationStatus
    trust_level: str  # Minimum trust in chain
    
    # The merged, validated, frozen document
    document: PolicyDocument
    
    # Merge report (detailed merge operations)
    merge_report: Optional["MergeReport"] = None
    
    # Merge metadata
    merged_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = ""  # SHA-256 of final document
    
    # Warnings during loading
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Compute content hash after initialization."""
        if not self.content_hash:
            canonical = PolicyCanonicalizer.canonicalize(
                self.document.model_dump(mode="json")
            )
            self.content_hash = hashlib.sha256(canonical).hexdigest()
    
    def is_root_signed(self) -> bool:
        """Check if the effective trust level is ROOT."""
        return self.trust_level == KeyTrust.ROOT
    
    def get_effective_rules(self) -> List[PolicyRule]:
        """Get all rules from the final document."""
        return self.document.rules
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "source_chain": [s.to_dict() for s in self.source_chain],
            "signature_status": self.signature_status.value,
            "trust_level": self.trust_level,
            "merged_at": self.merged_at.isoformat(),
            "content_hash": self.content_hash,
            "warnings": self.warnings,
            "rule_count": len(self.document.rules),
            "allowlist_count": len(self.document.allowlists),
            "zone_count": len(self.document.zones),
            "merge_report": self.merge_report.to_dict() if self.merge_report else None,
        }


# =============================================================================
# MERGE REPORT
# =============================================================================

@dataclass
class MergeReport:
    """
    Detailed report of merge operations performed.
    
    Used for auditing and debugging policy inheritance.
    """
    
    # Rules
    rules_added: List[str] = field(default_factory=list)
    rules_overridden: List[Dict[str, str]] = field(default_factory=list)
    rules_kept: List[str] = field(default_factory=list)
    
    # Allowlists
    allowlists_reduced: List[Dict[str, Any]] = field(default_factory=list)
    allowlists_replaced: List[str] = field(default_factory=list)
    
    # Metadata
    metadata_overrides: List[Dict[str, Any]] = field(default_factory=list)
    
    # Trust
    trust_warnings: List[str] = field(default_factory=list)
    
    # Security violations (would cause rejection)
    security_violations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rules_added": self.rules_added,
            "rules_overridden": self.rules_overridden,
            "rules_kept": self.rules_kept,
            "allowlists_reduced": self.allowlists_reduced,
            "allowlists_replaced": self.allowlists_replaced,
            "metadata_overrides": self.metadata_overrides,
            "trust_warnings": self.trust_warnings,
            "security_violations": self.security_violations,
        }
    
    def has_violations(self) -> bool:
        return len(self.security_violations) > 0


# =============================================================================
# TRUST LEVEL UTILITIES
# =============================================================================

class TrustLevel:
    """Trust level comparison utilities."""
    
    # Trust hierarchy (higher = more trusted)
    TRUST_HIERARCHY = {
        KeyTrust.ROOT: 3,
        KeyTrust.OPERATOR: 2,
        KeyTrust.AUDIT: 1,
    }
    
    @classmethod
    def get_level(cls, trust: str) -> int:
        """Get numeric trust level."""
        return cls.TRUST_HIERARCHY.get(trust, 0)
    
    @classmethod
    def compare(cls, trust_a: str, trust_b: str) -> int:
        """
        Compare two trust levels.
        
        Returns:
            > 0 if trust_a > trust_b
            < 0 if trust_a < trust_b
            0 if equal
        """
        return cls.get_level(trust_a) - cls.get_level(trust_b)
    
    @classmethod
    def is_higher_or_equal(cls, trust: str, required: str) -> bool:
        """Check if trust is >= required level."""
        return cls.get_level(trust) >= cls.get_level(required)
    
    @classmethod
    def minimum(cls, *trusts: str) -> str:
        """Get minimum trust level from a set."""
        if not trusts:
            return KeyTrust.AUDIT
        return min(trusts, key=lambda t: cls.get_level(t))


# =============================================================================
# MERGE ENGINE
# =============================================================================

class PolicyMergeEngine:
    """
    Deterministic, trust-aware, fail-closed merge engine.
    
    MERGE ORDER: BASE → CHILD → CHILD → ... → FINAL
    
    SECURITY GUARANTEES:
    - Never allows privilege expansion
    - Never allows trust downgrades
    - Allowlists can only be reduced (intersection)
    - Zones must be identical
    - Failure mode only modifiable by ROOT
    """
    
    def __init__(self):
        self._report = MergeReport()
    
    def merge(
        self,
        policies: List[Tuple[PolicyDocument, str]],  # (document, trust_level)
    ) -> Tuple[PolicyDocument, MergeReport]:
        """
        Merge a chain of policies.
        
        Args:
            policies: List of (PolicyDocument, trust_level) tuples,
                     ordered from root to child
                     
        Returns:
            Tuple of (merged_document, merge_report)
            
        Raises:
            PolicyInheritanceError: On merge violation
        """
        if not policies:
            raise PolicyLoadError(message="No policies to merge")
        
        self._report = MergeReport()
        
        # Start with first policy as base
        base_doc, base_trust = policies[0]
        
        # Track effective values
        merged_metadata = self._copy_metadata(base_doc.metadata)
        merged_zones = list(base_doc.zones)
        merged_allowlists = self._copy_allowlists(base_doc.allowlists)
        merged_rules: Dict[str, Tuple[PolicyRule, str]] = {}  # id -> (rule, trust)
        merged_failure_mode = base_doc.failure_mode
        
        # Add base rules
        for rule in base_doc.rules:
            merged_rules[rule.id] = (rule, base_trust)
            self._report.rules_added.append(rule.id)
        
        # Track minimum trust
        min_trust = base_trust
        
        # Merge each child in order
        for child_doc, child_trust in policies[1:]:
            min_trust = TrustLevel.minimum(min_trust, child_trust)
            
            # 1. Merge metadata
            merged_metadata = self._merge_metadata(
                merged_metadata, child_doc.metadata,
                child_trust, min_trust
            )
            
            # 2. Validate zones
            self._validate_zones(merged_zones, child_doc.zones, child_doc.metadata.name)
            
            # 3. Merge allowlists
            merged_allowlists = self._merge_allowlists(
                merged_allowlists, child_doc.allowlists,
                child_trust, child_doc.metadata.name
            )
            
            # 4. Merge rules
            merged_rules = self._merge_rules(
                merged_rules, child_doc.rules,
                child_trust, child_doc.metadata.name
            )
            
            # 5. Merge failure mode
            merged_failure_mode = self._merge_failure_mode(
                merged_failure_mode, child_doc.failure_mode,
                child_trust, child_doc.metadata.name
            )
        
        # Check for security violations
        if self._report.has_violations():
            violations_str = "; ".join(self._report.security_violations)
            raise PolicyInheritanceError(
                message=f"Security violations during merge: {violations_str}",
                code=PolicyErrorCode.INHERITANCE_MERGE_CONFLICT,
            )
        
        # Build final document
        final_rules = [rule for rule, _ in merged_rules.values()]
        # Sort by priority (higher priority first)
        final_rules.sort(key=lambda r: (-r.priority, r.id))
        
        # Create the merged document
        merged_doc = PolicyDocument(
            apiVersion=base_doc.apiVersion,
            kind=base_doc.kind,
            metadata=merged_metadata,
            zones=merged_zones,
            allowlists=merged_allowlists,
            rules=final_rules,
            failure_mode=merged_failure_mode,
        )
        
        return merged_doc, self._report
    
    # =========================================================================
    # METADATA MERGE
    # =========================================================================
    
    def _copy_metadata(self, metadata: PolicyMetadata) -> PolicyMetadata:
        """Create a copy of metadata."""
        return PolicyMetadata(
            name=metadata.name,
            version=metadata.version,
            description=metadata.description,
            created_at=metadata.created_at,
            updated_at=datetime.now(timezone.utc),
            inherits=metadata.inherits,
            labels=dict(metadata.labels),
        )
    
    def _merge_metadata(
        self,
        base: PolicyMetadata,
        child: PolicyMetadata,
        child_trust: str,
        chain_min_trust: str,
    ) -> PolicyMetadata:
        """
        Merge metadata from child into base.
        
        Child CAN override: version, description, labels
        Child CANNOT override: name (preserved from child), inherits
        """
        # Child can update version and description
        overrides = []
        
        if child.version != base.version:
            overrides.append({"field": "version", "from": base.version, "to": child.version})
        
        if child.description != base.description:
            overrides.append({"field": "description", "from": base.description, "to": child.description})
        
        if overrides:
            self._report.metadata_overrides.extend(overrides)
        
        return PolicyMetadata(
            name=child.name,  # Use child's name (it's the policy being loaded)
            version=child.version,
            description=child.description,
            created_at=base.created_at,
            updated_at=datetime.now(timezone.utc),
            inherits=child.inherits,
            labels={**base.labels, **child.labels},  # Merge labels
        )
    
    # =========================================================================
    # ZONES VALIDATION
    # =========================================================================
    
    def _validate_zones(
        self,
        base_zones: List[TrustZone],
        child_zones: List[TrustZone],
        child_name: str,
    ) -> None:
        """
        Validate that zones are identical between parent and child.
        
        Zones MUST match exactly - no modifications allowed.
        """
        if not child_zones:
            return  # Child doesn't define zones, inherits parent's
        
        # Build zone maps
        base_map = {z.name: z for z in base_zones}
        child_map = {z.name: z for z in child_zones}
        
        # Check for zone mismatches
        base_names = set(base_map.keys())
        child_names = set(child_map.keys())
        
        if base_names != child_names:
            added = child_names - base_names
            removed = base_names - child_names
            self._report.security_violations.append(
                f"Zone mismatch in {child_name}: added={added}, removed={removed}"
            )
            return
        
        # Check zone properties match
        for name in base_names:
            base_zone = base_map[name]
            child_zone = child_map[name]
            
            if base_zone.trust_level != child_zone.trust_level:
                self._report.security_violations.append(
                    f"Zone trust level mismatch in {child_name}: "
                    f"{name} has {child_zone.trust_level}, expected {base_zone.trust_level}"
                )
            
            # Description can differ but we could warn about it
            # No other mutable properties to check in current schema
    
    # =========================================================================
    # ALLOWLISTS MERGE (INTERSECTION)
    # =========================================================================
    
    def _copy_allowlists(self, allowlists: Dict[str, Allowlist]) -> Dict[str, Allowlist]:
        """Create a deep copy of allowlists."""
        return {name: al for name, al in allowlists.items()}
    
    def _merge_allowlists(
        self,
        base: Dict[str, Allowlist],
        child: Dict[str, Allowlist],
        child_trust: str,
        child_name: str,
    ) -> Dict[str, Allowlist]:
        """
        Merge allowlists using INTERSECTION semantics.
        
        Rules:
        - Child cannot add new allowlists (unless ROOT)
        - Child cannot add entries to existing allowlists
        - Child can only REMOVE entries (intersection)
        - ROOT-signed child can replace entire allowlist
        """
        if not child:
            return base  # No child allowlists, keep base
        
        result = dict(base)
        
        for name, child_list in child.items():
            if name not in base:
                # Child is adding a new allowlist
                if TrustLevel.is_higher_or_equal(child_trust, KeyTrust.ROOT):
                    # ROOT can add new allowlists
                    result[name] = child_list
                    self._report.allowlists_replaced.append(name)
                else:
                    self._report.security_violations.append(
                        f"Allowlist expansion in {child_name}: "
                        f"Cannot add new allowlist '{name}' (requires ROOT trust)"
                    )
                continue
            
            # Allowlist exists in both - check for expansion
            base_list = base[name]
            
            # Get entry sets for comparison
            base_entries = self._get_allowlist_entry_set(base_list)
            child_entries = self._get_allowlist_entry_set(child_list)
            
            # Check for expansion (child has entries not in base)
            expansion = child_entries - base_entries
            if expansion:
                if TrustLevel.is_higher_or_equal(child_trust, KeyTrust.ROOT):
                    # ROOT can replace
                    result[name] = child_list
                    self._report.allowlists_replaced.append(name)
                else:
                    self._report.security_violations.append(
                        f"Allowlist expansion in {child_name}: "
                        f"'{name}' has {len(expansion)} new entries (requires ROOT trust)"
                    )
                continue
            
            # Compute intersection (child can only reduce)
            intersection = base_entries & child_entries
            reduction = base_entries - child_entries
            
            if reduction:
                # Child is reducing the allowlist - allowed
                self._report.allowlists_reduced.append({
                    "name": name,
                    "policy": child_name,
                    "removed_count": len(reduction),
                    "remaining_count": len(intersection),
                })
                
                # Create new allowlist with intersection
                result[name] = self._create_intersected_allowlist(
                    base_list, intersection
                )
            else:
                # No change
                result[name] = base_list
        
        return result
    
    def _get_allowlist_entry_set(self, allowlist: Allowlist) -> Set[str]:
        """
        Convert allowlist entries to a comparable set.
        
        For simple entries: use the value directly
        For device entries: use the device ID
        """
        entries = set()
        for entry in allowlist.entries:
            if isinstance(entry, str):
                entries.add(entry)
            elif isinstance(entry, DeviceAllowlistEntry):
                entries.add(entry.id)
            elif isinstance(entry, dict):
                # Generic dict entry - use id or str representation
                entries.add(entry.get("id", str(entry)))
        return entries
    
    def _create_intersected_allowlist(
        self,
        base: Allowlist,
        keep_entries: Set[str],
    ) -> Allowlist:
        """Create a new allowlist with only the specified entries."""
        new_entries = []
        for entry in base.entries:
            entry_key = None
            if isinstance(entry, str):
                entry_key = entry
            elif isinstance(entry, DeviceAllowlistEntry):
                entry_key = entry.id
            elif isinstance(entry, dict):
                entry_key = entry.get("id", str(entry))
            
            if entry_key in keep_entries:
                new_entries.append(entry)
        
        return Allowlist(type=base.type, entries=new_entries)
    
    # =========================================================================
    # RULES MERGE
    # =========================================================================
    
    def _merge_rules(
        self,
        base_rules: Dict[str, Tuple[PolicyRule, str]],
        child_rules: List[PolicyRule],
        child_trust: str,
        child_name: str,
    ) -> Dict[str, Tuple[PolicyRule, str]]:
        """
        Merge rules from child into base.
        
        Rules:
        - Unique by ID
        - On conflict: child wins ONLY if child_trust >= parent_trust
        - Otherwise: reject as trust downgrade
        """
        result = dict(base_rules)
        
        for rule in child_rules:
            if rule.id in result:
                existing_rule, existing_trust = result[rule.id]
                
                # Check trust level
                if TrustLevel.is_higher_or_equal(child_trust, existing_trust):
                    # Child can override
                    result[rule.id] = (rule, child_trust)
                    self._report.rules_overridden.append({
                        "id": rule.id,
                        "from_policy": "parent",
                        "to_policy": child_name,
                        "trust_change": f"{existing_trust} -> {child_trust}",
                    })
                else:
                    # Trust downgrade - reject
                    self._report.security_violations.append(
                        f"Trust downgrade in {child_name}: "
                        f"Rule '{rule.id}' cannot override (child trust {child_trust} < "
                        f"existing trust {existing_trust})"
                    )
            else:
                # New rule
                result[rule.id] = (rule, child_trust)
                self._report.rules_added.append(rule.id)
        
        return result
    
    # =========================================================================
    # FAILURE MODE MERGE
    # =========================================================================
    
    def _merge_failure_mode(
        self,
        base: FailureModeConfig,
        child: FailureModeConfig,
        child_trust: str,
        child_name: str,
    ) -> FailureModeConfig:
        """
        Merge failure mode configuration.
        
        Rules:
        - Only ROOT-signed policies can modify failure_mode
        - All others inherit parent's failure mode
        """
        # Check if child is trying to change failure mode
        base_dict = base.model_dump()
        child_dict = child.model_dump()
        
        if base_dict != child_dict:
            if TrustLevel.is_higher_or_equal(child_trust, KeyTrust.ROOT):
                # ROOT can modify
                self._report.metadata_overrides.append({
                    "field": "failure_mode",
                    "policy": child_name,
                    "note": "Modified by ROOT-signed policy",
                })
                return child
            else:
                # Non-ROOT trying to modify - violation
                self._report.security_violations.append(
                    f"Failure mode modification in {child_name}: "
                    f"Requires ROOT trust (has {child_trust})"
                )
                return base
        
        return base


# =============================================================================
# SAFE MODE POLICY
# =============================================================================

def create_safe_mode_policy() -> PolicyDocument:
    """
    Create a minimal safe mode policy.
    
    This policy:
    - Denies all actions by default
    - Allows only essential read operations
    - Used when loading fails
    """
    return PolicyDocument(
        metadata=PolicyMetadata(
            name=SAFE_MODE_POLICY_NAME,
            version="1.0.0",
            description="Safe mode fallback policy - minimal permissions",
        ),
        rules=[
            PolicyRule(
                id="SAFE-001",
                priority=0,
                description="Allow memory read in safe mode",
                match=RuleMatch(action="memory.read"),
                action=RuleAction(type=ActionType.ALLOW),
            ),
            PolicyRule(
                id="SAFE-002",
                priority=0,
                description="Allow system status check in safe mode",
                match=RuleMatch(action="system.status"),
                action=RuleAction(type=ActionType.ALLOW),
            ),
            PolicyRule(
                id="SAFE-003",
                priority=0,
                description="Allow emergency lock in safe mode",
                match=RuleMatch(action="system.emergency_lock"),
                action=RuleAction(type=ActionType.ALLOW),
            ),
            PolicyRule(
                id="SAFE-004",
                priority=0,
                description="Allow audit read in safe mode",
                match=RuleMatch(action="audit.read"),
                action=RuleAction(type=ActionType.ALLOW),
            ),
            PolicyRule(
                id="SAFE-999",
                priority=9999,
                description="Default deny all in safe mode",
                match=RuleMatch(any=True),
                action=RuleAction(
                    type=ActionType.DENY,
                    reason_message="SAFE MODE ACTIVE - Action blocked",
                ),
            ),
        ],
        failure_mode=FailureModeConfig(
            default_action=ActionType.DENY,
            safe_mode=SafeModeConfig(),
        ),
    )


# =============================================================================
# POLICY LOADER
# =============================================================================

class PolicyLoader:
    """
    Secure policy loader with inheritance resolution.
    
    RESPONSIBILITIES:
    1. Load policy YAML files
    2. Verify signatures BEFORE processing
    3. Build inheritance graph
    4. Detect cycles and depth violations
    5. Merge policies safely
    6. Validate final document
    7. Return immutable FinalPolicy
    
    SECURITY MODEL:
    - Fail closed on any error
    - Never merge unverified policies
    - Never allow trust downgrades
    - Never allow privilege escalation
    """
    
    def __init__(
        self,
        policies_dir: Optional[Path] = None,
        verifier: Optional[PolicyVerifier] = None,
        require_signatures: bool = True,
    ):
        """
        Initialize the policy loader.
        
        Args:
            policies_dir: Base directory for policies
            verifier: PolicyVerifier instance for signature verification
            require_signatures: Whether to require valid signatures
        """
        self._policies_dir = Path(policies_dir) if policies_dir else DEFAULT_POLICIES_DIR
        self._verifier = verifier or PolicyVerifier()
        self._require_signatures = require_signatures
        
        self._lock = threading.RLock()
        self._cache: Dict[str, InheritanceNode] = {}
        
        # Safe mode policy (pre-built)
        self._safe_mode_policy = create_safe_mode_policy()
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def load_policy(
        self,
        name_or_path: Union[str, Path],
        require_signature: Optional[bool] = None,
    ) -> FinalPolicy:
        """
        Load a policy by name or path.
        
        This is the main entry point for loading policies.
        
        Args:
            name_or_path: Policy name (e.g., "production") or file path
            require_signature: Override default signature requirement
            
        Returns:
            FinalPolicy ready for enforcement
            
        Raises:
            PolicyLoadError: If loading fails
            PolicySignatureError: If signature verification fails
            PolicyInheritanceError: If inheritance resolution fails
        """
        require_sig = require_signature if require_signature is not None else self._require_signatures
        
        try:
            # Step 1: Build inheritance graph
            graph = InheritanceGraph()
            root_node = self._build_inheritance_graph(name_or_path, graph, require_sig)
            
            # Step 2: Detect cycles
            cycle = graph.detect_cycle(root_node.policy_name)
            if cycle:
                raise PolicyInheritanceCycleError(cycle)
            
            # Step 3: Check depth limit
            depth = graph.get_depth(root_node.policy_name)
            if depth > MAX_INHERITANCE_DEPTH:
                raise PolicyInheritanceError(
                    message=f"Inheritance depth {depth} exceeds maximum {MAX_INHERITANCE_DEPTH}",
                    code=PolicyErrorCode.INHERITANCE_DEPTH_EXCEEDED,
                    policy_name=root_node.policy_name,
                )
            
            # Step 4: Get merge order (topological sort)
            merge_order = graph.get_inheritance_chain(root_node.policy_name)
            
            # Step 5: Merge policies
            final = self._merge_policies(graph, merge_order)
            
            return final
            
        except (PolicyLoadError, PolicySignatureError, PolicyInheritanceError):
            raise
        except Exception as e:
            raise PolicyLoadError(
                message=f"Unexpected error loading policy: {e}",
                cause=e,
            )
    
    def load_active_policy(
        self,
        require_signature: Optional[bool] = None,
    ) -> FinalPolicy:
        """
        Load the currently active policy.
        
        Args:
            require_signature: Override default signature requirement
            
        Returns:
            FinalPolicy ready for enforcement
        """
        active_pointer = self._policies_dir / DEFAULT_ACTIVE_POINTER
        active_file = self._policies_dir / DEFAULT_ACTIVE_FILE
        
        # Try pointer file first
        if active_pointer.exists():
            try:
                active_name = active_pointer.read_text().strip()
                return self.load_policy(active_name, require_signature)
            except Exception:
                pass  # Fall through to active.yaml
        
        # Try active.yaml
        if active_file.exists():
            return self.load_policy(active_file, require_signature)
        
        # No active policy found
        raise PolicyLoadError(
            message="No active policy found",
            file_path=str(self._policies_dir),
        )
    
    def get_safe_mode_policy(self) -> FinalPolicy:
        """
        Get the safe mode fallback policy.
        
        This is used when normal policy loading fails.
        
        Returns:
            FinalPolicy with minimal safe permissions
        """
        return FinalPolicy(
            source_chain=[
                PolicySourceInfo(
                    name=SAFE_MODE_POLICY_NAME,
                    version="1.0.0",
                    file_path="<builtin>",
                    signed_by=None,
                    trust_level=KeyTrust.ROOT,  # Safe mode is trusted
                    verified_at=datetime.now(timezone.utc),
                )
            ],
            signature_status=SignatureVerificationStatus.VERIFIED,
            trust_level=KeyTrust.ROOT,
            document=self._safe_mode_policy,
            warnings=["SAFE MODE ACTIVE - Using minimal fallback policy"],
        )
    
    # =========================================================================
    # INHERITANCE GRAPH BUILDING
    # =========================================================================
    
    def _build_inheritance_graph(
        self,
        name_or_path: Union[str, Path],
        graph: InheritanceGraph,
        require_signature: bool,
        depth: int = 0,
    ) -> InheritanceNode:
        """
        Recursively build the inheritance graph.
        
        This loads each policy, verifies its signature, and follows
        inheritance links to build the complete graph.
        
        Args:
            name_or_path: Policy name or file path
            graph: Graph to build into
            require_signature: Whether to require valid signatures
            depth: Current depth (for limit checking)
            
        Returns:
            The root node for this branch
        """
        # Check depth limit early
        if depth > MAX_INHERITANCE_DEPTH:
            raise PolicyInheritanceError(
                message=f"Inheritance depth {depth} exceeds maximum {MAX_INHERITANCE_DEPTH}",
                code=PolicyErrorCode.INHERITANCE_DEPTH_EXCEEDED,
            )
        
        # Resolve file path
        file_path = self._resolve_policy_path(name_or_path)
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_POLICY_SIZE_BYTES:
            raise PolicyLoadError(
                message=f"Policy file too large: {file_size} bytes (max {MAX_POLICY_SIZE_BYTES})",
                file_path=str(file_path),
            )
        
        # Load raw YAML
        raw_data = self._load_yaml(file_path)
        
        # Extract metadata
        metadata = raw_data.get("metadata", {})
        policy_name = metadata.get("name", file_path.stem)
        version = metadata.get("version", "0.0.0")
        parent_name = metadata.get("inherits")
        
        # Check if already in graph (cache hit)
        existing = graph.get_node(policy_name)
        if existing:
            return existing
        
        # Verify signature BEFORE processing
        verification = self._verify_policy(raw_data, require_signature)
        
        # Create node
        node = InheritanceNode(
            policy_name=policy_name,
            version=version,
            file_path=file_path,
            raw_data=raw_data,
            status=InheritanceNodeStatus.VERIFIED,
            signature_status=verification,
            trust_level=verification.key_trust or KeyTrust.OPERATOR,
            parent_name=parent_name,
            depth=depth,
        )
        
        # Parse document (after verification)
        try:
            node.document = PolicyDocument(**raw_data)
        except Exception as e:
            raise PolicyValidationError(
                message=f"Invalid policy document: {e}",
                code=PolicyErrorCode.VALIDATION_SCHEMA_ERROR,
                context=PolicyErrorContext(
                    policy_name=policy_name,
                    policy_version=version,
                    file_path=str(file_path),
                ),
            )
        
        # Add to graph
        graph.add_node(node)
        
        # Follow inheritance link
        if parent_name:
            graph.add_edge(policy_name, parent_name)
            
            # Recursively load parent
            self._build_inheritance_graph(
                parent_name, graph, require_signature, depth + 1
            )
        
        return node
    
    def _resolve_policy_path(self, name_or_path: Union[str, Path]) -> Path:
        """
        Resolve a policy name or path to an absolute file path.
        
        Args:
            name_or_path: Policy name (e.g., "production") or file path
            
        Returns:
            Absolute path to the policy file
            
        Raises:
            PolicyLoadError: If file not found
        """
        path = Path(name_or_path)
        
        # If it's already a valid file path
        if path.is_absolute() and path.exists():
            return path
        
        if path.exists():
            return path.absolute()
        
        # Try as policy name
        candidates = [
            self._policies_dir / f"{name_or_path}.yaml",
            self._policies_dir / f"{name_or_path}.yml",
            self._policies_dir / "versions" / f"{name_or_path}.yaml",
            self._policies_dir / "versions" / f"{name_or_path}.yml",
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return candidate.absolute()
        
        raise PolicyLoadError(
            message=f"Policy not found: {name_or_path}",
            file_path=str(name_or_path),
        )
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """
        Load and parse a YAML file.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Parsed YAML data
            
        Raises:
            PolicyLoadError: If file cannot be read or parsed
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                raise PolicyLoadError(
                    message="Policy file must contain a YAML mapping",
                    file_path=str(file_path),
                )
            
            return data
            
        except yaml.YAMLError as e:
            raise PolicyLoadError(
                message=f"YAML parse error: {e}",
                file_path=str(file_path),
                cause=e,
            )
        except PermissionError as e:
            raise PolicyLoadError(
                message=f"Permission denied reading policy file",
                file_path=str(file_path),
                cause=e,
            )
        except FileNotFoundError as e:
            raise PolicyLoadError(
                message=f"Policy file not found",
                file_path=str(file_path),
                cause=e,
            )
    
    def _verify_policy(
        self,
        policy_data: Dict[str, Any],
        require_signature: bool,
    ) -> VerificationResult:
        """
        Verify a policy's signature.
        
        Args:
            policy_data: Raw policy data
            require_signature: Whether signature is required
            
        Returns:
            VerificationResult
            
        Raises:
            PolicySignatureError: If verification fails and signature required
        """
        result = self._verifier.verify_policy(
            policy_data,
            require_signature=require_signature,
        )
        
        if require_signature and not result.valid:
            if result.status == VerificationStatus.SIGNATURE_MISSING:
                raise PolicySignatureMissingError(
                    policy_name=policy_data.get("metadata", {}).get("name"),
                )
            elif result.status == VerificationStatus.TAMPERED:
                raise PolicySignatureInvalidError(
                    policy_name=policy_data.get("metadata", {}).get("name"),
                    reason="Tampering detected",
                    tampered=True,
                )
            else:
                raise PolicySignatureInvalidError(
                    policy_name=policy_data.get("metadata", {}).get("name"),
                    reason=result.message,
                )
        
        return result
    
    # =========================================================================
    # MERGE ENGINE INTEGRATION
    # =========================================================================
    
    def _merge_policies(
        self,
        graph: InheritanceGraph,
        merge_order: List[str],
    ) -> FinalPolicy:
        """
        Merge policies in the inheritance chain using PolicyMergeEngine.
        
        MERGE RULES:
        1. Metadata: Child can override version/description only
        2. Zones: Must be identical or reject
        3. Allowlists: Intersection by default, ROOT can replace
        4. Rules: Combine, child wins conflicts if same/higher trust
        5. Failure mode: Only ROOT can modify
        
        Args:
            graph: The inheritance graph
            merge_order: Topological ordering (parents first)
            
        Returns:
            FinalPolicy with merged document and merge report
        """
        if not merge_order:
            raise PolicyLoadError(message="No policies to merge")
        
        # Collect source chain info and policies for merging
        source_chain: List[PolicySourceInfo] = []
        warnings: List[str] = []
        min_trust = KeyTrust.ROOT
        all_verified = True
        
        # Build list of (document, trust_level) for merge engine
        policies_to_merge: List[Tuple[PolicyDocument, str]] = []
        
        for name in merge_order:
            node = graph.get_node(name)
            if not node or not node.document:
                raise PolicyLoadError(
                    message=f"Policy node not found or not loaded: {name}"
                )
            
            # Get trust level
            trust_level = node.trust_level or KeyTrust.OPERATOR
            
            # Add to merge list
            policies_to_merge.append((node.document, trust_level))
            
            # Build source chain info
            source_chain.append(PolicySourceInfo(
                name=node.policy_name,
                version=node.version,
                file_path=str(node.file_path),
                signed_by=node.signature_status.key_id if node.signature_status else None,
                trust_level=trust_level,
                verified_at=node.signature_status.verified_at if node.signature_status else datetime.now(timezone.utc),
            ))
            
            # Track minimum trust
            min_trust = TrustLevel.minimum(min_trust, trust_level)
            
            # Track verification status
            if node.signature_status and not node.signature_status.valid:
                all_verified = False
            if node.signature_status and node.signature_status.warnings:
                warnings.extend(node.signature_status.warnings)
        
        # Perform the merge using PolicyMergeEngine
        engine = PolicyMergeEngine()
        merged_document, merge_report = engine.merge(policies_to_merge)
        
        # Add any trust warnings from the merge
        if merge_report.trust_warnings:
            warnings.extend(merge_report.trust_warnings)
        
        # Determine signature status
        if all_verified:
            sig_status = SignatureVerificationStatus.VERIFIED
        elif source_chain:
            sig_status = SignatureVerificationStatus.PARTIAL
        else:
            sig_status = SignatureVerificationStatus.FAILED
        
        # Create final policy with merge report
        return FinalPolicy(
            source_chain=source_chain,
            signature_status=sig_status,
            trust_level=min_trust,
            document=merged_document,
            warnings=warnings,
            merge_report=merge_report,
        )
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def clear_cache(self) -> None:
        """Clear the policy cache."""
        with self._lock:
            self._cache.clear()
    
    def list_available_policies(self) -> List[str]:
        """
        List all available policy files.
        
        Returns:
            List of policy names/paths
        """
        policies = []
        
        # Check main directory
        if self._policies_dir.exists():
            for f in self._policies_dir.glob("*.yaml"):
                policies.append(f.stem)
            for f in self._policies_dir.glob("*.yml"):
                policies.append(f.stem)
        
        # Check versions directory
        versions_dir = self._policies_dir / "versions"
        if versions_dir.exists():
            for f in versions_dir.glob("*.yaml"):
                policies.append(f.stem)
            for f in versions_dir.glob("*.yml"):
                policies.append(f.stem)
        
        return sorted(set(policies))
