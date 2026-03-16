"""
AKSHAY AI CORE — Policy Schema

Pydantic models for policy documents with strict validation.
This module defines the formal schema for:
- Policy documents
- Rules and conditions
- Match operators
- Actions and reason codes
- Trust zones
- Allowlists
- Evaluation requests/responses

SECURITY NOTES:
- No dynamic eval() - all operators are explicitly implemented
- Regex patterns are validated to prevent ReDoS
- All fields have explicit types and constraints
- Inheritance depth is limited to prevent stack overflow
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Union
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)

from core.policy.errors import (
    PolicyValidationError,
    PolicyErrorCode,
    PolicyErrorContext,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Maximum inheritance depth to prevent infinite loops
MAX_INHERITANCE_DEPTH = 10

# Maximum number of rules per policy
MAX_RULES_PER_POLICY = 1000

# Maximum number of conditions per rule
MAX_CONDITIONS_PER_RULE = 50

# Maximum regex pattern length to prevent ReDoS
MAX_REGEX_LENGTH = 500

# Regex timeout hint (not enforced in Python, but documented)
REGEX_TIMEOUT_MS = 100

# Reserved rule IDs
RESERVED_RULE_IDS = {"DEFAULT", "SYSTEM", "SAFE_MODE"}

# Safe regex pattern - no catastrophic backtracking
SAFE_REGEX_PATTERN = re.compile(
    r'^[^()*+?]*'  # Disallow nested quantifiers at start
    r'(?:'
    r'[^()*+?]+'  # Normal characters
    r'|'
    r'\[[^\]]+\]'  # Character classes
    r'|'
    r'\([^)]+\)'  # Non-nested groups
    r'|'
    r'[*+?]'  # Single quantifiers
    r')*$'
)


# =============================================================================
# ENUMS
# =============================================================================

class PolicyApiVersion(str, Enum):
    """Supported policy API versions."""
    V1 = "policy.akshay.ai/v1"


class PolicyKind(str, Enum):
    """Policy document kinds."""
    POLICY_DOCUMENT = "PolicyDocument"
    ALLOWLIST = "Allowlist"
    KEY_CONFIG = "KeyConfig"


class ActionType(str, Enum):
    """Policy action types."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    RATE_LIMIT = "RATE_LIMIT"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_MFA = "REQUIRE_MFA"
    REQUIRE_ELEVATION = "REQUIRE_ELEVATION"
    AUDIT_ONLY = "AUDIT_ONLY"


class LogLevel(str, Enum):
    """Log levels for policy actions."""
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SignatureAlgorithm(str, Enum):
    """Supported signature algorithms."""
    ED25519 = "ed25519"
    HMAC_SHA256 = "hmac-sha256"


class MatchOperator(str, Enum):
    """Match operators for rule conditions."""
    # Equality
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    
    # List membership
    IN = "in"
    NOT_IN = "not_in"
    
    # String operations
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex
    NOT_MATCHES = "not_matches"
    
    # Numeric comparisons
    GREATER_THAN = "greater_than"
    GT = "gt"  # Alias
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "less_than"
    LT = "lt"  # Alias
    LESS_THAN_OR_EQUAL = "lte"
    BETWEEN = "between"
    NOT_BETWEEN = "not_between"
    
    # Trust zone comparisons
    TRUST_LEVEL_GT = "trust_level_gt"
    TRUST_LEVEL_LT = "trust_level_lt"
    TRUST_LEVEL_EQ = "trust_level_eq"
    
    # Special
    ANY = "any"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class ReasonCode(str, Enum):
    """Standardized reason codes for policy decisions."""
    # Deny reasons
    DEFAULT_DENY = "DEFAULT_DENY"
    DOMAIN_NOT_ALLOWED = "DOMAIN_NOT_ALLOWED"
    DEVICE_NOT_REGISTERED = "DEVICE_NOT_REGISTERED"
    PLUGIN_NOT_TRUSTED = "PLUGIN_NOT_TRUSTED"
    CROSS_ZONE_DENIED = "CROSS_ZONE_DENIED"
    OUTSIDE_BUSINESS_HOURS = "OUTSIDE_BUSINESS_HOURS"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    LEGAL_NOT_ACKNOWLEDGED = "LEGAL_NOT_ACKNOWLEDGED"
    ROLE_NOT_PERMITTED = "ROLE_NOT_PERMITTED"
    MFA_REQUIRED = "MFA_REQUIRED"
    ELEVATION_REQUIRED = "ELEVATION_REQUIRED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_REJECTED = "CONFIRMATION_REJECTED"
    POLICY_SIGNATURE_INVALID = "POLICY_SIGNATURE_INVALID"
    POLICY_EXPIRED = "POLICY_EXPIRED"
    SAFE_MODE_ACTIVE = "SAFE_MODE_ACTIVE"
    RULE_DISABLED = "RULE_DISABLED"
    CONTEXT_INVALID = "CONTEXT_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # Allow reasons
    RULE_MATCHED = "RULE_MATCHED"
    ALLOWLIST_MATCHED = "ALLOWLIST_MATCHED"
    ELEVATED_SESSION = "ELEVATED_SESSION"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"
    
    # Custom (user-defined)
    CUSTOM = "CUSTOM"


class Decision(str, Enum):
    """Policy decision outcomes."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_MFA = "REQUIRE_MFA"
    REQUIRE_ELEVATION = "REQUIRE_ELEVATION"
    RATE_LIMITED = "RATE_LIMITED"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def validate_regex_pattern(pattern: str) -> str:
    """
    Validate a regex pattern for safety.
    
    Checks:
    - Length limit
    - Valid syntax
    - No obvious ReDoS patterns
    
    Returns:
        The pattern if valid
        
    Raises:
        PolicyValidationError if invalid
    """
    if len(pattern) > MAX_REGEX_LENGTH:
        raise PolicyValidationError(
            message=f"Regex pattern too long: {len(pattern)} > {MAX_REGEX_LENGTH}",
            field_path="pattern",
            code=PolicyErrorCode.VALIDATION_REGEX_INVALID,
        )
    
    # Check for obvious ReDoS patterns
    redos_patterns = [
        r'\(\.\*\)\+',  # (.*)+
        r'\(\.\+\)\+',  # (.+)+
        r'\(\[.*\]\+\)\+',  # ([...]+)+
        r'\(\w\+\)\+',  # (\w+)+
        r'\(\d\+\)\+',  # (\d+)+
    ]
    
    for redos in redos_patterns:
        if re.search(redos, pattern):
            raise PolicyValidationError(
                message=f"Regex pattern contains potential ReDoS vulnerability",
                field_path="pattern",
                actual_value=pattern,
                code=PolicyErrorCode.VALIDATION_REGEX_INVALID,
            )
    
    # Validate syntax
    try:
        re.compile(pattern)
    except re.error as e:
        raise PolicyValidationError(
            message=f"Invalid regex pattern: {e}",
            field_path="pattern",
            actual_value=pattern,
            code=PolicyErrorCode.VALIDATION_REGEX_INVALID,
        )
    
    return pattern


def validate_semver(version: str) -> str:
    """
    Validate semantic version string.
    
    Format: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
    """
    semver_pattern = r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'
    
    if not re.match(semver_pattern, version):
        raise PolicyValidationError(
            message=f"Invalid semantic version: {version}",
            field_path="version",
            actual_value=version,
            code=PolicyErrorCode.VALIDATION_VERSION_INVALID,
        )
    
    return version


def validate_allowlist_reference(ref: str) -> str:
    """
    Validate allowlist reference format.
    
    Format: @allowlists.<name> or @<name>
    """
    if not ref.startswith("@"):
        raise PolicyValidationError(
            message=f"Allowlist reference must start with @: {ref}",
            field_path="allowlist_ref",
            actual_value=ref,
            code=PolicyErrorCode.VALIDATION_FIELD_INVALID,
        )
    
    # Extract name
    parts = ref[1:].split(".")
    if len(parts) == 1:
        name = parts[0]
    elif len(parts) == 2 and parts[0] == "allowlists":
        name = parts[1]
    else:
        raise PolicyValidationError(
            message=f"Invalid allowlist reference format: {ref}",
            field_path="allowlist_ref",
            actual_value=ref,
            code=PolicyErrorCode.VALIDATION_FIELD_INVALID,
        )
    
    # Validate name
    if not re.match(r'^[a-z][a-z0-9_]*$', name):
        raise PolicyValidationError(
            message=f"Invalid allowlist name: {name} (must be lowercase alphanumeric with underscores)",
            field_path="allowlist_ref",
            actual_value=ref,
            code=PolicyErrorCode.VALIDATION_FIELD_INVALID,
        )
    
    return ref


def validate_rule_id(rule_id: str) -> str:
    """
    Validate rule ID format.
    
    Format: PREFIX-NNN or alphanumeric with hyphens/underscores
    """
    if rule_id in RESERVED_RULE_IDS:
        raise PolicyValidationError(
            message=f"Rule ID is reserved: {rule_id}",
            field_path="rule_id",
            actual_value=rule_id,
            code=PolicyErrorCode.VALIDATION_FIELD_INVALID,
        )
    
    if not re.match(r'^[A-Z][A-Z0-9_-]*[0-9]+$|^[a-z][a-z0-9_-]*$', rule_id):
        raise PolicyValidationError(
            message=f"Invalid rule ID format: {rule_id}",
            field_path="rule_id",
            actual_value=rule_id,
            expected_value="PREFIX-NNN or lowercase-with-hyphens",
            code=PolicyErrorCode.VALIDATION_FIELD_INVALID,
        )
    
    return rule_id


# =============================================================================
# SCHEMA MODELS
# =============================================================================

class PolicyMetadata(BaseModel):
    """Policy document metadata."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique policy identifier",
    )
    version: str = Field(
        ...,
        description="Semantic version (MAJOR.MINOR.PATCH)",
    )
    description: str = Field(
        default="",
        max_length=1024,
        description="Human-readable description",
    )
    author: str = Field(
        default="system",
        max_length=64,
        description="Policy author",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last modification timestamp",
    )
    inherits: Optional[str] = Field(
        default=None,
        description="Parent policy name to inherit from",
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Key-value labels for organization",
    )
    
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        return validate_semver(v)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$', v):
            raise ValueError(
                f"Invalid policy name: {v} (must be lowercase with hyphens, "
                "start with letter, end with letter or number)"
            )
        return v


class PolicySignature(BaseModel):
    """Cryptographic signature for policy verification."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    algorithm: SignatureAlgorithm = Field(
        ...,
        description="Signing algorithm used",
    )
    key_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Identifier of the signing key",
    )
    signed_at: datetime = Field(
        ...,
        description="Timestamp when policy was signed",
    )
    value: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded signature value",
    )
    
    @field_validator("value")
    @classmethod
    def validate_signature_value(cls, v: str) -> str:
        # Validate base64 format
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError("Signature value must be valid base64")
        return v


class TrustZone(BaseModel):
    """Trust zone definition."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    name: str = Field(
        ...,
        pattern=r'^[A-Z][A-Z0-9_]*$',
        description="Zone identifier (uppercase)",
    )
    trust_level: int = Field(
        ...,
        ge=0,
        le=10,
        description="Trust level (0=highest, 10=lowest)",
    )
    description: str = Field(
        default="",
        max_length=256,
        description="Zone description",
    )


class AllowlistEntry(BaseModel):
    """Simple allowlist entry (string value)."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    value: str = Field(..., min_length=1)
    description: Optional[str] = None


class DeviceAllowlistEntry(BaseModel):
    """Device allowlist entry with capabilities."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Device identifier",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable device name",
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Allowed capabilities for this device",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional device metadata",
    )


class Allowlist(BaseModel):
    """Allowlist definition."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    type: Literal["domain", "device", "plugin", "user", "ip", "custom"] = Field(
        ...,
        description="Type of allowlist entries",
    )
    entries: List[Union[str, DeviceAllowlistEntry, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Allowlist entries",
    )
    
    @model_validator(mode="after")
    def validate_entries(self) -> "Allowlist":
        """Validate entries match the allowlist type."""
        if self.type == "device":
            for entry in self.entries:
                if isinstance(entry, str):
                    raise ValueError(
                        "Device allowlist entries must be objects with id, name, capabilities"
                    )
        return self


class MatchCondition(BaseModel):
    """Single match condition with operator and value."""
    
    model_config = ConfigDict(extra="allow", frozen=True)
    
    # The actual operator and value are stored as extra fields
    # This allows flexible YAML like: `equals: "value"` or `in: ["a", "b"]`
    
    @model_validator(mode="before")
    @classmethod
    def extract_operator(cls, data: Any) -> Dict[str, Any]:
        """Extract operator and value from input."""
        if not isinstance(data, dict):
            # Simple equality check
            return {"equals": data}
        
        # Validate only one operator
        operators = [k for k in data.keys() if k in [op.value for op in MatchOperator]]
        if len(operators) > 1:
            raise ValueError(f"Multiple operators in condition: {operators}")
        
        return data
    
    def get_operator(self) -> Optional[MatchOperator]:
        """Get the operator from this condition."""
        for key in self.model_extra:
            try:
                return MatchOperator(key)
            except ValueError:
                continue
        return None
    
    def get_value(self) -> Any:
        """Get the value for the operator."""
        op = self.get_operator()
        if op:
            return self.model_extra.get(op.value)
        return None
    
    @model_validator(mode="after")
    def validate_operator_value(self) -> "MatchCondition":
        """Validate operator value types and regex patterns."""
        op = self.get_operator()
        value = self.get_value()
        
        if op is None:
            return self
        
        # Validate regex patterns
        if op in (MatchOperator.MATCHES, MatchOperator.NOT_MATCHES):
            if isinstance(value, str):
                validate_regex_pattern(value)
        
        # Validate range operators
        if op in (MatchOperator.BETWEEN, MatchOperator.NOT_BETWEEN):
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError(f"{op.value} requires a list of two values")
            if not all(isinstance(v, (int, float)) for v in value):
                raise ValueError(f"{op.value} requires numeric values")
        
        # Validate list operators
        if op in (MatchOperator.IN, MatchOperator.NOT_IN):
            if isinstance(value, str) and value.startswith("@"):
                validate_allowlist_reference(value)
            elif not isinstance(value, (list, tuple)):
                raise ValueError(f"{op.value} requires a list or allowlist reference")
        
        return self


class RuleMatch(BaseModel):
    """Rule match criteria."""
    
    model_config = ConfigDict(extra="allow", frozen=True)
    
    # Special match-all flag
    any: bool = Field(default=False, description="Match any request")
    
    # Common match fields (all optional)
    tool: Optional[MatchCondition] = None
    action: Optional[MatchCondition] = None
    domain: Optional[MatchCondition] = None
    device_id: Optional[MatchCondition] = None
    plugin: Optional[MatchCondition] = None
    user_role: Optional[MatchCondition] = None
    source_zone: Optional[MatchCondition] = None
    target_zone: Optional[MatchCondition] = None
    environment: Optional[MatchCondition] = None
    
    @model_validator(mode="before")
    @classmethod
    def convert_simple_values(cls, data: Any) -> Dict[str, Any]:
        """Convert simple string values to MatchCondition format."""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if key == "any":
                result[key] = value
            elif isinstance(value, dict):
                result[key] = value
            elif isinstance(value, str):
                # Check for negation prefix
                if value.startswith("!"):
                    if value[1:].startswith("@"):
                        result[key] = {"not_in": value[1:]}
                    else:
                        result[key] = {"not_equals": value[1:]}
                elif value.startswith("@"):
                    result[key] = {"in": value}
                else:
                    result[key] = {"equals": value}
            elif isinstance(value, list):
                result[key] = {"in": value}
            else:
                result[key] = {"equals": value}
        
        return result


class RateLimit(BaseModel):
    """Rate limit configuration."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    requests: int = Field(
        ...,
        gt=0,
        le=100000,
        description="Maximum requests allowed",
    )
    period_seconds: int = Field(
        ...,
        gt=0,
        le=86400,  # Max 24 hours
        description="Time period in seconds",
    )


class RuleAction(BaseModel):
    """Rule action configuration."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    type: ActionType = Field(
        ...,
        description="Action type to take",
    )
    reason_code: Union[ReasonCode, str] = Field(
        default=ReasonCode.RULE_MATCHED,
        description="Machine-readable reason code",
    )
    reason_message: str = Field(
        default="",
        max_length=512,
        description="Human-readable reason message",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log level for this action",
    )
    alert: bool = Field(
        default=False,
        description="Whether to send alert",
    )
    require_confirmation: bool = Field(
        default=False,
        description="Whether user confirmation is required",
    )
    confirmation_message: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Message to show for confirmation",
    )
    mfa_timeout_seconds: Optional[int] = Field(
        default=None,
        ge=30,
        le=3600,
        description="MFA verification timeout",
    )
    audit_detailed: bool = Field(
        default=False,
        description="Whether to log detailed audit info",
    )
    limit: Optional[RateLimit] = Field(
        default=None,
        description="Rate limit configuration",
    )
    exceed_action: Optional[ActionType] = Field(
        default=None,
        description="Action when rate limit exceeded",
    )
    
    @model_validator(mode="after")
    def validate_action_consistency(self) -> "RuleAction":
        """Validate action configuration is consistent."""
        if self.type == ActionType.DENY and self.reason_code == ReasonCode.RULE_MATCHED:
            # Default reason for deny
            object.__setattr__(self, "reason_code", ReasonCode.DEFAULT_DENY)
        
        if self.type == ActionType.RATE_LIMIT and self.limit is None:
            raise ValueError("RATE_LIMIT action requires limit configuration")
        
        if self.type == ActionType.REQUIRE_CONFIRMATION and not self.confirmation_message:
            raise ValueError("REQUIRE_CONFIRMATION action requires confirmation_message")
        
        if self.type == ActionType.REQUIRE_MFA and self.mfa_timeout_seconds is None:
            # Default timeout
            object.__setattr__(self, "mfa_timeout_seconds", 300)
        
        return self


class PolicyRule(BaseModel):
    """Policy rule definition."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    id: str = Field(
        ...,
        description="Unique rule identifier",
    )
    description: str = Field(
        default="",
        max_length=512,
        description="Rule description",
    )
    priority: int = Field(
        ...,
        ge=0,
        le=10000,
        description="Rule priority (higher = evaluated first)",
    )
    enabled: bool = Field(
        default=True,
        description="Whether rule is active",
    )
    match: RuleMatch = Field(
        ...,
        description="Match criteria",
    )
    conditions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Additional conditions",
    )
    action: RuleAction = Field(
        ...,
        description="Action to take when matched",
    )
    
    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return validate_rule_id(v)
    
    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(v) > MAX_CONDITIONS_PER_RULE:
            raise ValueError(
                f"Too many conditions: {len(v)} > {MAX_CONDITIONS_PER_RULE}"
            )
        return v


class SafeModeConfig(BaseModel):
    """Safe mode configuration."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    allowed_actions: List[str] = Field(
        default_factory=lambda: [
            "memory.read",
            "system.status",
            "system.emergency_lock",
            "audit.read",
        ],
        description="Actions allowed in safe mode",
    )
    blocked_actions: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Actions blocked in safe mode",
    )


class FailureModeConfig(BaseModel):
    """Failure mode configuration."""
    
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    default_action: ActionType = Field(
        default=ActionType.DENY,
        description="Default action on policy failure",
    )
    safe_mode: SafeModeConfig = Field(
        default_factory=SafeModeConfig,
        description="Safe mode configuration",
    )


class PolicyDocument(BaseModel):
    """Complete policy document."""
    
    model_config = ConfigDict(extra="forbid")
    
    apiVersion: PolicyApiVersion = Field(
        default=PolicyApiVersion.V1,
        description="Policy API version",
    )
    kind: PolicyKind = Field(
        default=PolicyKind.POLICY_DOCUMENT,
        description="Document kind",
    )
    metadata: PolicyMetadata = Field(
        ...,
        description="Policy metadata",
    )
    signature: Optional[PolicySignature] = Field(
        default=None,
        description="Cryptographic signature",
    )
    zones: List[TrustZone] = Field(
        default_factory=list,
        description="Trust zone definitions",
    )
    allowlists: Dict[str, Allowlist] = Field(
        default_factory=dict,
        description="Allowlist definitions",
    )
    rules: List[PolicyRule] = Field(
        default_factory=list,
        min_length=1,
        description="Policy rules",
    )
    failure_mode: FailureModeConfig = Field(
        default_factory=FailureModeConfig,
        description="Failure mode configuration",
    )
    
    @field_validator("rules")
    @classmethod
    def validate_rules(cls, v: List[PolicyRule]) -> List[PolicyRule]:
        if len(v) > MAX_RULES_PER_POLICY:
            raise ValueError(
                f"Too many rules: {len(v)} > {MAX_RULES_PER_POLICY}"
            )
        
        # Check for duplicate IDs
        rule_ids = [r.id for r in v]
        duplicates = [rid for rid in rule_ids if rule_ids.count(rid) > 1]
        if duplicates:
            raise ValueError(f"Duplicate rule IDs: {set(duplicates)}")
        
        return v
    
    @model_validator(mode="after")
    def validate_document(self) -> "PolicyDocument":
        """Validate complete document consistency."""
        # Check zone uniqueness
        zone_names = [z.name for z in self.zones]
        if len(zone_names) != len(set(zone_names)):
            raise ValueError("Duplicate zone names")
        
        # Check allowlist references in rules
        allowlist_names = set(self.allowlists.keys())
        for rule in self.rules:
            self._validate_rule_allowlist_refs(rule, allowlist_names)
        
        # Check for priority conflicts (same priority rules)
        priority_map: Dict[int, List[str]] = {}
        for rule in self.rules:
            if rule.enabled:
                if rule.priority not in priority_map:
                    priority_map[rule.priority] = []
                priority_map[rule.priority].append(rule.id)
        
        # Warn about priority conflicts (but don't fail - deterministic order by ID)
        for priority, rule_ids in priority_map.items():
            if len(rule_ids) > 1:
                # Sort by ID for deterministic ordering
                pass  # We'll handle this in the engine
        
        return self
    
    def _validate_rule_allowlist_refs(
        self,
        rule: PolicyRule,
        allowlist_names: Set[str],
    ) -> None:
        """Validate allowlist references in a rule."""
        # Check match conditions
        for field_name in rule.match.model_fields:
            condition = getattr(rule.match, field_name, None)
            if isinstance(condition, MatchCondition):
                value = condition.get_value()
                if isinstance(value, str) and value.startswith("@"):
                    self._check_allowlist_ref(value, allowlist_names, rule.id)
        
        # Check extra match fields
        for key, condition in rule.match.model_extra.items():
            if isinstance(condition, dict):
                for op_value in condition.values():
                    if isinstance(op_value, str) and op_value.startswith("@"):
                        self._check_allowlist_ref(op_value, allowlist_names, rule.id)
    
    def _check_allowlist_ref(
        self,
        ref: str,
        allowlist_names: Set[str],
        rule_id: str,
    ) -> None:
        """Check if an allowlist reference is valid."""
        # Extract name from @allowlists.name or @name
        parts = ref[1:].split(".")
        if len(parts) == 2 and parts[0] == "allowlists":
            name = parts[1]
        else:
            name = parts[0]
        
        if name not in allowlist_names:
            raise ValueError(
                f"Rule {rule_id} references unknown allowlist: {ref}"
            )
    
    def get_body_for_signing(self) -> Dict[str, Any]:
        """Get the policy body for signing (excludes signature)."""
        data = self.model_dump(mode="json")
        data.pop("signature", None)
        return data


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class EvaluationContext(BaseModel):
    """Context for policy evaluation."""
    
    model_config = ConfigDict(extra="allow", frozen=True)
    
    # User context
    user_id: str = Field(default="anonymous")
    user_role: str = Field(default="user")
    session_id: Optional[str] = None
    session_elevated: bool = False
    mfa_verified: bool = False
    
    # Trust context
    source_zone: str = Field(default="USER")
    target_zone: Optional[str] = None
    
    # Time context
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Environment
    environment: str = Field(default="production")
    
    # Legal acknowledgments
    legal_acknowledged: bool = False


class EvaluationRequest(BaseModel):
    """Request for policy evaluation."""
    
    model_config = ConfigDict(extra="allow", frozen=True)
    
    # Action being evaluated
    tool: str = Field(
        ...,
        description="Tool being invoked",
    )
    action: str = Field(
        default="execute",
        description="Specific action",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters",
    )
    
    # Context
    context: EvaluationContext = Field(
        default_factory=EvaluationContext,
        description="Evaluation context",
    )
    
    # Optional fields for specific tools
    domain: Optional[str] = None
    device_id: Optional[str] = None
    plugin: Optional[str] = None
    
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


class EvaluationResult(BaseModel):
    """Result of policy evaluation."""
    
    model_config = ConfigDict(extra="forbid")
    
    # Decision
    decision: Decision = Field(
        ...,
        description="Policy decision",
    )
    
    # Matched rule info
    matched_rule_id: Optional[str] = Field(
        default=None,
        description="ID of the rule that matched",
    )
    matched_rule_priority: int = Field(
        default=0,
        description="Priority of matched rule",
    )
    
    # Reason
    reason_code: Union[ReasonCode, str] = Field(
        ...,
        description="Machine-readable reason code",
    )
    reason_message: str = Field(
        default="",
        description="Human-readable reason",
    )
    
    # Requirements
    requires_confirmation: bool = Field(default=False)
    confirmation_message: Optional[str] = None
    requires_mfa: bool = Field(default=False)
    requires_elevation: bool = Field(default=False)
    
    # Rate limit info
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset_at: Optional[datetime] = None
    
    # Audit
    should_log: bool = Field(default=True)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    should_alert: bool = Field(default=False)
    
    # Metadata
    evaluation_time_ms: float = Field(default=0.0)
    policy_version: str = Field(default="unknown")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    safe_mode_active: bool = Field(default=False)
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "decision": self.decision.value,
            "matched_rule_id": self.matched_rule_id,
            "matched_rule_priority": self.matched_rule_priority,
            "reason_code": (
                self.reason_code.value
                if isinstance(self.reason_code, ReasonCode)
                else self.reason_code
            ),
            "reason_message": self.reason_message,
            "requires_confirmation": self.requires_confirmation,
            "requires_mfa": self.requires_mfa,
            "requires_elevation": self.requires_elevation,
            "log_level": self.log_level.value,
            "should_alert": self.should_alert,
            "evaluation_time_ms": self.evaluation_time_ms,
            "policy_version": self.policy_version,
            "evaluated_at": self.evaluated_at.isoformat(),
            "safe_mode_active": self.safe_mode_active,
        }
