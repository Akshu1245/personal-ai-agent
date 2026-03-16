"""
AKSHAY AI CORE — Policy Evaluation Engine

Pure, side-effect-free, deterministic rule evaluation.

MISSION:
Evaluate a FinalPolicy against an EvaluationRequest and return a
deterministic, auditable decision that all system components must obey.

SECURITY GUARANTEES:
- Deterministic output (same input → same output)
- No hidden state changes in match logic
- No exception leaks (all errors caught and converted to DENY)
- Constant-time comparisons for sensitive checks
- Thread-safe rate limit storage

EVALUATION FLOW:
1. Validate request schema
2. Check SAFE MODE → only allow safe actions
3. Load active FinalPolicy
4. Apply global rate limits / quotas
5. Sort rules by priority (descending)
6. For each rule:
     a. Match tool/action
     b. Evaluate conditions
     c. If match: enforce action, build audit, return
7. No match → DEFAULT DENY

NON-NEGOTIABLE:
- Never depend on LLM output
- Never skip validation
- Never return without audit record
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from core.policy.errors import (
    PolicyError,
    PolicyEvaluationError,
    PolicyErrorCode,
    PolicyErrorContext,
    PolicySafeModeError,
    PolicyValidationError,
)
from core.policy.schema import (
    ActionType,
    Decision,
    LogLevel,
    MatchCondition,
    MatchOperator,
    PolicyDocument,
    PolicyRule,
    RateLimit,
    ReasonCode,
    RuleMatch,
    EvaluationContext,
    EvaluationRequest as BaseEvaluationRequest,
    EvaluationResult,
    validate_regex_pattern,
)
from core.policy.loader import (
    FinalPolicy,
    TrustLevel,
    MergeReport,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Performance limits
MAX_RULES_EVALUATED = 1000
MAX_CONDITIONS_PER_RULE = 50
REGEX_TIMEOUT_MS = 100
MAX_EVALUATION_TIME_MS = 100

# Safe mode allowed actions
SAFE_MODE_ALLOWED = frozenset({
    "system.status",
    "policy.status",
    "memory.read",  # Only public namespace
    "emergency.lock",
    "audit.read",
})

# Default rate limit window
DEFAULT_RATE_WINDOW_SECONDS = 60


# =============================================================================
# ENUMS
# =============================================================================

class SourceType(str, Enum):
    """Source of the evaluation request."""
    TERMINAL = "terminal"
    VOICE = "voice"
    API = "api"
    MOBILE = "mobile"
    AUTOMATION = "automation"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class EvaluationPhase(str, Enum):
    """Phase of the evaluation process."""
    VALIDATION = "validation"
    SAFE_MODE_CHECK = "safe_mode_check"
    GLOBAL_RATE_LIMIT = "global_rate_limit"
    RULE_MATCHING = "rule_matching"
    CONDITION_EVALUATION = "condition_evaluation"
    ACTION_ENFORCEMENT = "action_enforcement"
    AUDIT_BUILD = "audit_build"
    COMPLETE = "complete"


# =============================================================================
# EVALUATION REQUEST (EXTENDED)
# =============================================================================

class EngineEvaluationRequest(BaseModel):
    """
    Extended evaluation request for the engine.
    
    Adds required fields for complete evaluation.
    """
    
    model_config = ConfigDict(extra="allow", frozen=True)
    
    # Actor identification
    actor_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Unique identifier for the actor",
    )
    role: str = Field(
        default="user",
        max_length=64,
        description="Actor's role in the system",
    )
    
    # Trust context
    trust_zone: str = Field(
        default="USER",
        pattern=r'^[A-Z][A-Z0-9_]*$',
        description="Current trust zone",
    )
    
    # Source
    source: SourceType = Field(
        default=SourceType.UNKNOWN,
        description="Request source interface",
    )
    
    # Action
    tool: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Tool being invoked",
    )
    action: str = Field(
        default="execute",
        max_length=256,
        description="Specific action on the tool",
    )
    
    # Target details
    target: Dict[str, Any] = Field(
        default_factory=dict,
        description="Target resource details (domain, device_id, namespace, etc.)",
    )
    
    # Timing
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Request timestamp",
    )
    
    # Additional context
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (ip, mfa, session_id, confidence, etc.)",
    )
    
    @field_validator("actor_id")
    @classmethod
    def validate_actor_id(cls, v: str) -> str:
        """Validate actor_id format."""
        # No dangerous characters
        if any(c in v for c in ['<', '>', '&', '"', "'"]):
            raise ValueError("actor_id contains invalid characters")
        return v
    
    @field_validator("tool")
    @classmethod
    def validate_tool(cls, v: str) -> str:
        """Validate tool format."""
        # Must be dot-notation like web.fetch or memory.read
        if not re.match(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$', v):
            raise ValueError(
                f"Invalid tool format: {v} (expected lowercase.dotted.notation)"
            )
        return v
    
    def get_field_value(self, field_path: str) -> Any:
        """Get a field value by dot-notation path."""
        parts = field_path.split(".")
        current: Any = self
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, "model_extra") and part in current.model_extra:
                current = current.model_extra[part]
            else:
                return None
        
        return current
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "actor_id": self.actor_id,
            "role": self.role,
            "trust_zone": self.trust_zone,
            "source": self.source.value,
            "tool": self.tool,
            "action": self.action,
            "target": self.target,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# EVALUATION RESULT (EXTENDED)
# =============================================================================

@dataclass
class EngineEvaluationResult:
    """
    Complete evaluation result from the engine.
    
    Includes full audit trail and rate limit state.
    """
    
    # Core decision
    decision: Decision
    rule_id: Optional[str]
    reason_code: Union[ReasonCode, str]
    priority: int
    
    # Rate limiting
    rate_limit: Optional[Dict[str, Any]] = None
    
    # Safe mode flag
    safe_mode: bool = False
    
    # Audit record
    audit_record: Dict[str, Any] = field(default_factory=dict)
    
    # Evaluation metadata
    evaluation_time_ms: float = 0.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_version: str = "unknown"
    
    # Detailed trace
    conditions_evaluated: List[Dict[str, Any]] = field(default_factory=list)
    rules_checked: int = 0
    
    # Requirements for interactive decisions
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None
    requires_mfa: bool = False
    mfa_timeout_seconds: Optional[int] = None
    requires_elevation: bool = False
    
    def to_evaluation_result(self) -> EvaluationResult:
        """Convert to standard EvaluationResult."""
        return EvaluationResult(
            decision=self.decision,
            matched_rule_id=self.rule_id,
            matched_rule_priority=self.priority,
            reason_code=self.reason_code,
            reason_message=self.audit_record.get("reason", ""),
            requires_confirmation=self.requires_confirmation,
            confirmation_message=self.confirmation_message,
            requires_mfa=self.requires_mfa,
            requires_elevation=self.requires_elevation,
            rate_limit_remaining=self.rate_limit.get("remaining") if self.rate_limit else None,
            rate_limit_reset_at=self.rate_limit.get("reset_at") if self.rate_limit else None,
            evaluation_time_ms=self.evaluation_time_ms,
            policy_version=self.policy_version,
            evaluated_at=self.evaluated_at,
            safe_mode_active=self.safe_mode,
        )
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Build complete audit record."""
        return {
            "timestamp": self.evaluated_at.isoformat(),
            "decision": self.decision.value,
            "rule_id": self.rule_id,
            "reason_code": (
                self.reason_code.value
                if isinstance(self.reason_code, ReasonCode)
                else self.reason_code
            ),
            "priority": self.priority,
            "safe_mode": self.safe_mode,
            "policy_version": self.policy_version,
            "evaluation_time_ms": self.evaluation_time_ms,
            "rules_checked": self.rules_checked,
            "conditions_evaluated": self.conditions_evaluated,
            "rate_limit_state": self.rate_limit,
            **self.audit_record,
        }


# =============================================================================
# MATCH RESULT
# =============================================================================

@dataclass
class MatchResult:
    """Result of matching a rule against a request."""
    
    matched: bool
    rule_id: str
    rule_priority: int
    
    # Condition details
    conditions_checked: List[Dict[str, Any]] = field(default_factory=list)
    failed_condition: Optional[Dict[str, Any]] = None
    
    # Performance
    match_time_ms: float = 0.0


# =============================================================================
# RATE LIMITER INTERFACE
# =============================================================================

class RateLimiterBackend(ABC):
    """Abstract interface for rate limiting storage."""
    
    @abstractmethod
    def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int, datetime]:
        """
        Check rate limit and increment counter.
        
        Returns:
            (allowed, remaining, reset_at)
        """
        pass
    
    @abstractmethod
    def get_current(self, key: str) -> Tuple[int, Optional[datetime]]:
        """Get current count and reset time."""
        pass
    
    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset a rate limit key."""
        pass


class InMemoryRateLimiter(RateLimiterBackend):
    """
    Thread-safe in-memory rate limiter using token bucket algorithm.
    
    Suitable for single-instance deployments.
    For distributed systems, use Redis backend.
    """
    
    def __init__(self):
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int, datetime]:
        """Check rate limit using sliding window."""
        now = datetime.now(timezone.utc)
        
        with self._lock:
            bucket = self._buckets.get(key)
            
            if bucket is None or bucket["reset_at"] <= now:
                # Create new bucket
                reset_at = now + timedelta(seconds=window_seconds)
                self._buckets[key] = {
                    "count": 1,
                    "reset_at": reset_at,
                    "limit": limit,
                    "window": window_seconds,
                }
                return (True, limit - 1, reset_at)
            
            # Check existing bucket
            if bucket["count"] >= limit:
                return (False, 0, bucket["reset_at"])
            
            # Increment
            bucket["count"] += 1
            remaining = limit - bucket["count"]
            return (True, remaining, bucket["reset_at"])
    
    def get_current(self, key: str) -> Tuple[int, Optional[datetime]]:
        """Get current count and reset time."""
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return (0, None)
            return (bucket["count"], bucket["reset_at"])
    
    def reset(self, key: str) -> None:
        """Reset a rate limit key."""
        with self._lock:
            self._buckets.pop(key, None)
    
    def cleanup_expired(self) -> int:
        """Remove expired buckets. Returns count removed."""
        now = datetime.now(timezone.utc)
        removed = 0
        
        with self._lock:
            expired = [
                k for k, v in self._buckets.items()
                if v["reset_at"] <= now
            ]
            for key in expired:
                del self._buckets[key]
                removed += 1
        
        return removed


# =============================================================================
# CONDITION EVALUATOR
# =============================================================================

class ConditionEvaluator:
    """
    Safe, deterministic condition evaluator.
    
    Supports all operators from the schema.
    No dynamic eval(), all operators explicitly implemented.
    """
    
    def __init__(self, allowlists: Dict[str, Any] = None):
        """
        Initialize with allowlists for reference resolution.
        
        Args:
            allowlists: Dictionary of allowlist name -> entries
        """
        self._allowlists = allowlists or {}
        
        # Operator dispatch table
        self._operators: Dict[MatchOperator, Callable] = {
            MatchOperator.EQUALS: self._eval_equals,
            MatchOperator.NOT_EQUALS: self._eval_not_equals,
            MatchOperator.IN: self._eval_in,
            MatchOperator.NOT_IN: self._eval_not_in,
            MatchOperator.CONTAINS: self._eval_contains,
            MatchOperator.NOT_CONTAINS: self._eval_not_contains,
            MatchOperator.STARTS_WITH: self._eval_starts_with,
            MatchOperator.ENDS_WITH: self._eval_ends_with,
            MatchOperator.MATCHES: self._eval_matches,
            MatchOperator.NOT_MATCHES: self._eval_not_matches,
            MatchOperator.GREATER_THAN: self._eval_gt,
            MatchOperator.GT: self._eval_gt,
            MatchOperator.GREATER_THAN_OR_EQUAL: self._eval_gte,
            MatchOperator.LESS_THAN: self._eval_lt,
            MatchOperator.LT: self._eval_lt,
            MatchOperator.LESS_THAN_OR_EQUAL: self._eval_lte,
            MatchOperator.BETWEEN: self._eval_between,
            MatchOperator.NOT_BETWEEN: self._eval_not_between,
            MatchOperator.TRUST_LEVEL_GT: self._eval_trust_gt,
            MatchOperator.TRUST_LEVEL_LT: self._eval_trust_lt,
            MatchOperator.TRUST_LEVEL_EQ: self._eval_trust_eq,
            MatchOperator.ANY: self._eval_any,
            MatchOperator.EXISTS: self._eval_exists,
            MatchOperator.NOT_EXISTS: self._eval_not_exists,
        }
    
    def evaluate(
        self,
        condition: MatchCondition,
        actual_value: Any,
        field_name: str = "",
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate a single condition.
        
        Returns:
            (matched, trace_info)
        """
        op = condition.get_operator()
        expected = condition.get_value()
        
        trace = {
            "field": field_name,
            "operator": op.value if op else "unknown",
            "expected": str(expected)[:100],  # Truncate for safety
            "actual": str(actual_value)[:100] if actual_value is not None else None,
        }
        
        if op is None:
            trace["result"] = False
            trace["error"] = "Unknown operator"
            return (False, trace)
        
        evaluator = self._operators.get(op)
        if evaluator is None:
            trace["result"] = False
            trace["error"] = f"Unsupported operator: {op.value}"
            return (False, trace)
        
        try:
            result = evaluator(actual_value, expected)
            trace["result"] = result
            return (result, trace)
        except Exception as e:
            trace["result"] = False
            trace["error"] = str(e)
            return (False, trace)
    
    # -------------------------------------------------------------------------
    # EQUALITY OPERATORS
    # -------------------------------------------------------------------------
    
    def _eval_equals(self, actual: Any, expected: Any) -> bool:
        """Constant-time string comparison for security."""
        if isinstance(actual, str) and isinstance(expected, str):
            return hmac.compare_digest(actual, expected)
        return actual == expected
    
    def _eval_not_equals(self, actual: Any, expected: Any) -> bool:
        return not self._eval_equals(actual, expected)
    
    # -------------------------------------------------------------------------
    # LIST MEMBERSHIP
    # -------------------------------------------------------------------------
    
    def _eval_in(self, actual: Any, expected: Any) -> bool:
        """Check if actual is in expected list or allowlist."""
        values = self._resolve_list(expected)
        if isinstance(actual, str):
            return any(hmac.compare_digest(actual, str(v)) for v in values)
        return actual in values
    
    def _eval_not_in(self, actual: Any, expected: Any) -> bool:
        return not self._eval_in(actual, expected)
    
    def _resolve_list(self, value: Any) -> List[Any]:
        """Resolve value to a list, handling allowlist references."""
        if isinstance(value, str) and value.startswith("@"):
            return self._resolve_allowlist_ref(value)
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]
    
    def _resolve_allowlist_ref(self, ref: str) -> List[Any]:
        """Resolve an allowlist reference to its entries."""
        # Extract name from @allowlists.name or @name
        parts = ref[1:].split(".")
        if len(parts) == 2 and parts[0] == "allowlists":
            name = parts[1]
        else:
            name = parts[0]
        
        allowlist = self._allowlists.get(name)
        if allowlist is None:
            return []
        
        # Extract values from allowlist
        if hasattr(allowlist, "entries"):
            entries = allowlist.entries
        elif isinstance(allowlist, dict) and "entries" in allowlist:
            entries = allowlist["entries"]
        else:
            entries = []
        
        # Flatten entries to values
        result = []
        for entry in entries:
            if isinstance(entry, str):
                result.append(entry)
            elif isinstance(entry, dict):
                result.append(entry.get("value") or entry.get("id") or entry)
            elif hasattr(entry, "value"):
                result.append(entry.value)
            elif hasattr(entry, "id"):
                result.append(entry.id)
            else:
                result.append(entry)
        
        return result
    
    # -------------------------------------------------------------------------
    # STRING OPERATORS
    # -------------------------------------------------------------------------
    
    def _eval_contains(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        return str(expected) in str(actual)
    
    def _eval_not_contains(self, actual: Any, expected: Any) -> bool:
        return not self._eval_contains(actual, expected)
    
    def _eval_starts_with(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        return str(actual).startswith(str(expected))
    
    def _eval_ends_with(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        return str(actual).endswith(str(expected))
    
    def _eval_matches(self, actual: Any, expected: Any) -> bool:
        """ReDoS-safe regex matching."""
        if actual is None:
            return False
        
        # Validate pattern safety
        try:
            validate_regex_pattern(str(expected))
        except PolicyValidationError:
            return False
        
        pattern = re.compile(str(expected))
        return bool(pattern.search(str(actual)))
    
    def _eval_not_matches(self, actual: Any, expected: Any) -> bool:
        return not self._eval_matches(actual, expected)
    
    # -------------------------------------------------------------------------
    # NUMERIC OPERATORS
    # -------------------------------------------------------------------------
    
    def _eval_gt(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False
    
    def _eval_gte(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False
    
    def _eval_lt(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False
    
    def _eval_lte(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False
    
    def _eval_between(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        if not isinstance(expected, (list, tuple)) or len(expected) != 2:
            return False
        try:
            val = float(actual)
            low, high = float(expected[0]), float(expected[1])
            return low <= val <= high
        except (ValueError, TypeError):
            return False
    
    def _eval_not_between(self, actual: Any, expected: Any) -> bool:
        return not self._eval_between(actual, expected)
    
    # -------------------------------------------------------------------------
    # TRUST LEVEL OPERATORS
    # -------------------------------------------------------------------------
    
    def _eval_trust_gt(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        return TrustLevel.compare(str(actual), str(expected)) > 0
    
    def _eval_trust_lt(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        return TrustLevel.compare(str(actual), str(expected)) < 0
    
    def _eval_trust_eq(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        return TrustLevel.compare(str(actual), str(expected)) == 0
    
    # -------------------------------------------------------------------------
    # SPECIAL OPERATORS
    # -------------------------------------------------------------------------
    
    def _eval_any(self, actual: Any, expected: Any) -> bool:
        """Always matches (for match-all rules)."""
        return True
    
    def _eval_exists(self, actual: Any, expected: Any) -> bool:
        """Check if value exists (not None/empty)."""
        if actual is None:
            return False
        if isinstance(actual, str) and actual == "":
            return False
        if isinstance(actual, (list, dict)) and len(actual) == 0:
            return False
        return True
    
    def _eval_not_exists(self, actual: Any, expected: Any) -> bool:
        return not self._eval_exists(actual, expected)


# =============================================================================
# RULE MATCHER
# =============================================================================

class RuleMatcher:
    """
    Matches rules against evaluation requests.
    
    Handles:
    - Tool/action matching
    - Condition evaluation
    - Priority ordering
    """
    
    def __init__(
        self,
        condition_evaluator: ConditionEvaluator,
    ):
        self._evaluator = condition_evaluator
    
    def match_rule(
        self,
        rule: PolicyRule,
        request: EngineEvaluationRequest,
    ) -> MatchResult:
        """
        Check if a rule matches the request.
        
        Returns:
            MatchResult with match status and condition traces
        """
        start_time = time.perf_counter()
        conditions_checked = []
        
        # Skip disabled rules
        if not rule.enabled:
            return MatchResult(
                matched=False,
                rule_id=rule.id,
                rule_priority=rule.priority,
                conditions_checked=[],
                failed_condition={"reason": "rule_disabled"},
                match_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Check match-all flag
        if rule.match.any:
            return MatchResult(
                matched=True,
                rule_id=rule.id,
                rule_priority=rule.priority,
                conditions_checked=[{"match_all": True}],
                match_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Match tool
        tool_match = self._match_field(
            rule.match.tool,
            request.tool,
            "tool",
            conditions_checked,
        )
        if tool_match is False:
            return MatchResult(
                matched=False,
                rule_id=rule.id,
                rule_priority=rule.priority,
                conditions_checked=conditions_checked,
                failed_condition=conditions_checked[-1] if conditions_checked else None,
                match_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Match action
        action_match = self._match_field(
            rule.match.action,
            request.action,
            "action",
            conditions_checked,
        )
        if action_match is False:
            return MatchResult(
                matched=False,
                rule_id=rule.id,
                rule_priority=rule.priority,
                conditions_checked=conditions_checked,
                failed_condition=conditions_checked[-1] if conditions_checked else None,
                match_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Match domain (if present in rule)
        if rule.match.domain is not None:
            domain = request.target.get("domain")
            domain_match = self._match_field(
                rule.match.domain,
                domain,
                "domain",
                conditions_checked,
            )
            if domain_match is False:
                return MatchResult(
                    matched=False,
                    rule_id=rule.id,
                    rule_priority=rule.priority,
                    conditions_checked=conditions_checked,
                    failed_condition=conditions_checked[-1],
                    match_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # Match device_id (if present in rule)
        if rule.match.device_id is not None:
            device_id = request.target.get("device_id")
            device_match = self._match_field(
                rule.match.device_id,
                device_id,
                "device_id",
                conditions_checked,
            )
            if device_match is False:
                return MatchResult(
                    matched=False,
                    rule_id=rule.id,
                    rule_priority=rule.priority,
                    conditions_checked=conditions_checked,
                    failed_condition=conditions_checked[-1],
                    match_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # Match source_zone
        if rule.match.source_zone is not None:
            zone_match = self._match_field(
                rule.match.source_zone,
                request.trust_zone,
                "source_zone",
                conditions_checked,
            )
            if zone_match is False:
                return MatchResult(
                    matched=False,
                    rule_id=rule.id,
                    rule_priority=rule.priority,
                    conditions_checked=conditions_checked,
                    failed_condition=conditions_checked[-1],
                    match_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # Match user_role
        if rule.match.user_role is not None:
            role_match = self._match_field(
                rule.match.user_role,
                request.role,
                "user_role",
                conditions_checked,
            )
            if role_match is False:
                return MatchResult(
                    matched=False,
                    rule_id=rule.id,
                    rule_priority=rule.priority,
                    conditions_checked=conditions_checked,
                    failed_condition=conditions_checked[-1],
                    match_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # Evaluate additional conditions
        for i, condition_dict in enumerate(rule.conditions):
            cond_result = self._evaluate_additional_condition(
                condition_dict,
                request,
                f"condition[{i}]",
                conditions_checked,
            )
            if cond_result is False:
                return MatchResult(
                    matched=False,
                    rule_id=rule.id,
                    rule_priority=rule.priority,
                    conditions_checked=conditions_checked,
                    failed_condition=conditions_checked[-1],
                    match_time_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # All conditions matched
        return MatchResult(
            matched=True,
            rule_id=rule.id,
            rule_priority=rule.priority,
            conditions_checked=conditions_checked,
            match_time_ms=(time.perf_counter() - start_time) * 1000,
        )
    
    def _match_field(
        self,
        condition: Optional[MatchCondition],
        actual_value: Any,
        field_name: str,
        trace: List[Dict[str, Any]],
    ) -> Optional[bool]:
        """
        Match a single field condition.
        
        Returns:
            True if matched, False if not matched, None if no condition
        """
        if condition is None:
            return None  # No condition = no constraint
        
        matched, condition_trace = self._evaluator.evaluate(
            condition, actual_value, field_name
        )
        trace.append(condition_trace)
        return matched
    
    def _evaluate_additional_condition(
        self,
        condition_dict: Dict[str, Any],
        request: EngineEvaluationRequest,
        label: str,
        trace: List[Dict[str, Any]],
    ) -> bool:
        """Evaluate an additional condition dictionary."""
        # Expected format: {"field": "...", "operator": "...", "value": "..."}
        # Or: {"field": {"operator": "value"}}
        
        field_path = condition_dict.get("field")
        if not field_path:
            trace.append({"label": label, "error": "Missing field", "result": False})
            return False
        
        # Get actual value from request
        actual_value = request.get_field_value(field_path)
        
        # Build MatchCondition
        operator = condition_dict.get("operator")
        value = condition_dict.get("value")
        
        if operator and value is not None:
            condition_data = {operator: value}
        elif isinstance(condition_dict.get(field_path), dict):
            condition_data = condition_dict[field_path]
        else:
            trace.append({
                "label": label,
                "field": field_path,
                "error": "Invalid condition format",
                "result": False,
            })
            return False
        
        try:
            condition = MatchCondition(**condition_data)
            matched, condition_trace = self._evaluator.evaluate(
                condition, actual_value, field_path
            )
            condition_trace["label"] = label
            trace.append(condition_trace)
            return matched
        except Exception as e:
            trace.append({
                "label": label,
                "field": field_path,
                "error": str(e),
                "result": False,
            })
            return False


# =============================================================================
# AUDIT BUILDER
# =============================================================================

class AuditBuilder:
    """
    Builds comprehensive audit records for every evaluation.
    
    Records are suitable for:
    - Security auditing
    - Compliance reporting
    - Debugging
    - Analytics
    """
    
    def build(
        self,
        request: EngineEvaluationRequest,
        result: EngineEvaluationResult,
        policy_name: str,
        match_details: Optional[MatchResult] = None,
    ) -> Dict[str, Any]:
        """Build complete audit record."""
        return {
            # Timing
            "timestamp": result.evaluated_at.isoformat(),
            "evaluation_time_ms": result.evaluation_time_ms,
            
            # Actor
            "actor": request.actor_id,
            "role": request.role,
            "source": request.source.value,
            
            # Action
            "tool": request.tool,
            "action": request.action,
            "target": request.target,
            
            # Context
            "trust_zone": request.trust_zone,
            "ip": request.context.get("ip"),
            "session_id": request.context.get("session_id"),
            "mfa_verified": request.context.get("mfa", False),
            
            # Decision
            "decision": result.decision.value,
            "rule_id": result.rule_id,
            "reason": result.reason_code.value if isinstance(
                result.reason_code, ReasonCode
            ) else result.reason_code,
            
            # Policy
            "policy_name": policy_name,
            "policy_version": result.policy_version,
            "safe_mode": result.safe_mode,
            
            # Details
            "conditions_evaluated": result.conditions_evaluated,
            "rules_checked": result.rules_checked,
            "rate_limit_state": result.rate_limit,
            
            # Match details
            "match_details": {
                "matched": match_details.matched if match_details else False,
                "match_time_ms": match_details.match_time_ms if match_details else 0,
            } if match_details else None,
        }


# =============================================================================
# POLICY ENGINE
# =============================================================================

class PolicyEngine:
    """
    The core policy evaluation engine.
    
    GUARANTEES:
    - Deterministic: Same input → Same output
    - Auditable: Every decision has complete trace
    - Fail-closed: Errors result in DENY
    - Thread-safe: Concurrent evaluations supported
    
    EVALUATION FLOW:
    1. Validate request
    2. Check safe mode
    3. Apply global rate limits
    4. Sort rules by priority (descending)
    5. Match rules in order
    6. Return first match or DEFAULT DENY
    """
    
    def __init__(
        self,
        rate_limiter: Optional[RateLimiterBackend] = None,
        audit_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the policy engine.
        
        Args:
            rate_limiter: Backend for rate limiting (default: in-memory)
            audit_callback: Function to call with audit records
        """
        self._rate_limiter = rate_limiter or InMemoryRateLimiter()
        self._audit_callback = audit_callback
        self._audit_builder = AuditBuilder()
        
        # Cache for sorted rules (invalidated on policy change)
        self._rules_cache: Dict[str, List[PolicyRule]] = {}
        self._cache_lock = threading.RLock()
    
    def evaluate(
        self,
        request: EngineEvaluationRequest,
        policy: FinalPolicy,
    ) -> EngineEvaluationResult:
        """
        Evaluate a request against a policy.
        
        This is the main entry point for all policy decisions.
        
        Args:
            request: The evaluation request
            policy: The final, merged policy to evaluate against
            
        Returns:
            Complete evaluation result with audit trail
        """
        start_time = time.perf_counter()
        
        try:
            # Phase 1: Validate request
            self._validate_request(request)
            
            # Phase 2: Check safe mode
            if self._is_safe_mode_active(policy):
                result = self._evaluate_safe_mode(request, policy)
                result.evaluation_time_ms = (time.perf_counter() - start_time) * 1000
                self._emit_audit(request, result, policy)
                return result
            
            # Phase 3: Global rate limits (per actor)
            rate_result = self._check_global_rate_limit(request, policy)
            if rate_result is not None:
                rate_result.evaluation_time_ms = (time.perf_counter() - start_time) * 1000
                self._emit_audit(request, rate_result, policy)
                return rate_result
            
            # Phase 4: Get sorted rules
            rules = self._get_sorted_rules(policy)
            
            # Phase 5: Create condition evaluator with allowlists
            evaluator = ConditionEvaluator(
                allowlists=policy.document.allowlists
            )
            matcher = RuleMatcher(evaluator)
            
            # Phase 6: Match rules in priority order
            rules_checked = 0
            all_conditions = []
            
            for rule in rules:
                if rules_checked >= MAX_RULES_EVALUATED:
                    break
                
                rules_checked += 1
                match_result = matcher.match_rule(rule, request)
                all_conditions.extend(match_result.conditions_checked)
                
                if match_result.matched:
                    # Build result from matched rule
                    result = self._build_result_from_rule(
                        rule, match_result, request, policy, all_conditions, rules_checked
                    )
                    result.evaluation_time_ms = (time.perf_counter() - start_time) * 1000
                    self._emit_audit(request, result, policy, match_result)
                    return result
            
            # Phase 7: No match → DEFAULT DENY
            result = self._build_default_deny(
                request, policy, all_conditions, rules_checked
            )
            result.evaluation_time_ms = (time.perf_counter() - start_time) * 1000
            self._emit_audit(request, result, policy)
            return result
            
        except PolicyValidationError as e:
            # Validation errors → DENY with context
            result = EngineEvaluationResult(
                decision=Decision.DENY,
                rule_id=None,
                reason_code=ReasonCode.CONTEXT_INVALID,
                priority=0,
                audit_record={"error": str(e), "phase": "validation"},
                policy_version=policy.document.metadata.version,
                evaluation_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self._emit_audit(request, result, policy)
            return result
            
        except Exception as e:
            # Any other error → DENY (fail closed)
            result = EngineEvaluationResult(
                decision=Decision.DENY,
                rule_id=None,
                reason_code=ReasonCode.INTERNAL_ERROR,
                priority=0,
                audit_record={"error": str(e), "phase": "unknown"},
                policy_version=policy.document.metadata.version if policy else "unknown",
                evaluation_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            if policy:
                self._emit_audit(request, result, policy)
            return result
    
    def _validate_request(self, request: EngineEvaluationRequest) -> None:
        """Validate the evaluation request."""
        # Pydantic handles most validation
        # Additional checks here
        if not request.actor_id:
            raise PolicyValidationError(
                message="actor_id is required",
                field_path="actor_id",
                code=PolicyErrorCode.EVALUATION_CONTEXT_INVALID,
            )
        
        if not request.tool:
            raise PolicyValidationError(
                message="tool is required",
                field_path="tool",
                code=PolicyErrorCode.EVALUATION_CONTEXT_INVALID,
            )
    
    def _is_safe_mode_active(self, policy: FinalPolicy) -> bool:
        """Check if safe mode is currently active."""
        # Check policy failure mode config
        failure_mode = policy.document.failure_mode
        safe_config = failure_mode.safe_mode
        
        # For now, safe mode is not auto-active
        # It would be triggered by external conditions
        return False
    
    def _evaluate_safe_mode(
        self,
        request: EngineEvaluationRequest,
        policy: FinalPolicy,
    ) -> EngineEvaluationResult:
        """Evaluate request under safe mode restrictions."""
        tool_action = f"{request.tool}"
        
        # Check if action is allowed in safe mode
        safe_config = policy.document.failure_mode.safe_mode
        allowed = safe_config.allowed_actions
        
        is_allowed = any(
            tool_action == a or tool_action.startswith(a.rstrip("*"))
            for a in allowed
        )
        
        if is_allowed:
            # Additional check: memory.read only for public namespace
            if tool_action == "memory.read":
                namespace = request.target.get("namespace", "")
                if namespace and namespace != "public":
                    is_allowed = False
        
        if is_allowed:
            return EngineEvaluationResult(
                decision=Decision.ALLOW,
                rule_id="SAFE_MODE",
                reason_code=ReasonCode.RULE_MATCHED,
                priority=10000,  # Highest priority
                safe_mode=True,
                policy_version=policy.document.metadata.version,
                audit_record={"safe_mode_allowed": True},
            )
        else:
            return EngineEvaluationResult(
                decision=Decision.DENY,
                rule_id="SAFE_MODE",
                reason_code=ReasonCode.SAFE_MODE_ACTIVE,
                priority=10000,
                safe_mode=True,
                policy_version=policy.document.metadata.version,
                audit_record={"safe_mode_blocked": tool_action},
            )
    
    def _check_global_rate_limit(
        self,
        request: EngineEvaluationRequest,
        policy: FinalPolicy,
    ) -> Optional[EngineEvaluationResult]:
        """Check global rate limits. Returns result if limited, None if OK."""
        # Global rate limit key: actor_id
        key = f"global:{request.actor_id}"
        
        # Default global limit: 1000 requests per minute
        global_limit = 1000
        global_window = 60
        
        allowed, remaining, reset_at = self._rate_limiter.check_and_increment(
            key, global_limit, global_window
        )
        
        if not allowed:
            return EngineEvaluationResult(
                decision=Decision.RATE_LIMITED,
                rule_id=None,
                reason_code=ReasonCode.RATE_LIMIT_EXCEEDED,
                priority=0,
                rate_limit={
                    "type": "global",
                    "limit": global_limit,
                    "remaining": remaining,
                    "reset_at": reset_at.isoformat(),
                    "retry_after": (reset_at - datetime.now(timezone.utc)).total_seconds(),
                },
                policy_version=policy.document.metadata.version,
            )
        
        return None
    
    def _get_sorted_rules(self, policy: FinalPolicy) -> List[PolicyRule]:
        """Get rules sorted by priority (descending), then by ID for determinism."""
        policy_hash = policy.content_hash
        
        with self._cache_lock:
            if policy_hash in self._rules_cache:
                return self._rules_cache[policy_hash]
            
            # Sort: higher priority first, then alphabetically by ID for stability
            rules = sorted(
                policy.document.rules,
                key=lambda r: (-r.priority, r.id),
            )
            
            self._rules_cache[policy_hash] = rules
            return rules
    
    def _build_result_from_rule(
        self,
        rule: PolicyRule,
        match_result: MatchResult,
        request: EngineEvaluationRequest,
        policy: FinalPolicy,
        conditions: List[Dict[str, Any]],
        rules_checked: int,
    ) -> EngineEvaluationResult:
        """Build evaluation result from a matched rule."""
        action = rule.action
        
        # Map ActionType to Decision
        decision_map = {
            ActionType.ALLOW: Decision.ALLOW,
            ActionType.DENY: Decision.DENY,
            ActionType.RATE_LIMIT: Decision.RATE_LIMITED,
            ActionType.REQUIRE_CONFIRMATION: Decision.REQUIRE_CONFIRMATION,
            ActionType.REQUIRE_MFA: Decision.REQUIRE_MFA,
            ActionType.REQUIRE_ELEVATION: Decision.REQUIRE_ELEVATION,
            ActionType.AUDIT_ONLY: Decision.ALLOW,  # Allow but audit
        }
        
        decision = decision_map.get(action.type, Decision.DENY)
        
        # Handle rate limit action
        rate_limit = None
        if action.type == ActionType.RATE_LIMIT and action.limit:
            key = f"rule:{rule.id}:{request.actor_id}"
            allowed, remaining, reset_at = self._rate_limiter.check_and_increment(
                key, action.limit.requests, action.limit.period_seconds
            )
            
            rate_limit = {
                "type": "rule",
                "rule_id": rule.id,
                "limit": action.limit.requests,
                "period_seconds": action.limit.period_seconds,
                "remaining": remaining,
                "reset_at": reset_at.isoformat(),
            }
            
            if not allowed:
                decision = Decision.RATE_LIMITED
                if action.exceed_action:
                    decision = decision_map.get(action.exceed_action, Decision.DENY)
        
        return EngineEvaluationResult(
            decision=decision,
            rule_id=rule.id,
            reason_code=action.reason_code,
            priority=rule.priority,
            rate_limit=rate_limit,
            conditions_evaluated=conditions,
            rules_checked=rules_checked,
            policy_version=policy.document.metadata.version,
            requires_confirmation=action.require_confirmation or action.type == ActionType.REQUIRE_CONFIRMATION,
            confirmation_message=action.confirmation_message,
            requires_mfa=action.type == ActionType.REQUIRE_MFA,
            mfa_timeout_seconds=action.mfa_timeout_seconds,
            requires_elevation=action.type == ActionType.REQUIRE_ELEVATION,
            audit_record={
                "reason": action.reason_message or f"Rule {rule.id} matched",
                "log_level": action.log_level.value,
                "alert": action.alert,
            },
        )
    
    def _build_default_deny(
        self,
        request: EngineEvaluationRequest,
        policy: FinalPolicy,
        conditions: List[Dict[str, Any]],
        rules_checked: int,
    ) -> EngineEvaluationResult:
        """Build default deny result when no rule matches."""
        # Use policy's failure mode default action
        default_action = policy.document.failure_mode.default_action
        
        decision_map = {
            ActionType.ALLOW: Decision.ALLOW,
            ActionType.DENY: Decision.DENY,
        }
        decision = decision_map.get(default_action, Decision.DENY)
        
        return EngineEvaluationResult(
            decision=decision,
            rule_id=None,
            reason_code=ReasonCode.DEFAULT_DENY,
            priority=0,
            conditions_evaluated=conditions,
            rules_checked=rules_checked,
            policy_version=policy.document.metadata.version,
            audit_record={
                "reason": "No matching rule found, default deny applied",
                "log_level": LogLevel.WARNING.value,
            },
        )
    
    def _emit_audit(
        self,
        request: EngineEvaluationRequest,
        result: EngineEvaluationResult,
        policy: FinalPolicy,
        match_result: Optional[MatchResult] = None,
    ) -> None:
        """Emit audit record to callback if configured."""
        if self._audit_callback:
            policy_name = policy.document.metadata.name
            audit_record = self._audit_builder.build(
                request, result, policy_name, match_result
            )
            result.audit_record.update(audit_record)
            
            try:
                self._audit_callback(audit_record)
            except Exception:
                pass  # Don't fail evaluation due to audit errors
    
    def invalidate_cache(self, policy_hash: Optional[str] = None) -> None:
        """Invalidate the rules cache."""
        with self._cache_lock:
            if policy_hash:
                self._rules_cache.pop(policy_hash, None)
            else:
                self._rules_cache.clear()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_evaluation_request(
    actor_id: str,
    tool: str,
    action: str = "execute",
    role: str = "user",
    trust_zone: str = "USER",
    source: SourceType = SourceType.UNKNOWN,
    target: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> EngineEvaluationRequest:
    """Create an evaluation request with defaults."""
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


def quick_evaluate(
    policy: FinalPolicy,
    actor_id: str,
    tool: str,
    action: str = "execute",
    **kwargs,
) -> Decision:
    """
    Quick evaluation for simple use cases.
    
    Returns just the decision without full audit trail.
    """
    engine = PolicyEngine()
    request = create_evaluation_request(
        actor_id=actor_id,
        tool=tool,
        action=action,
        **kwargs,
    )
    result = engine.evaluate(request, policy)
    return result.decision
