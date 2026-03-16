"""
AKSHAY AI CORE — Policy Engine

The authoritative decision layer for the AI platform.
No component may bypass this engine.

Exports:
    - PolicyEngine: Main evaluation engine
    - PolicyLoader: Load and parse policies
    - PolicyStore: Versioned policy storage
    - PolicySigner: Sign policies
    - PolicyVerifier: Verify signatures
    - PolicySimulator: Dry-run simulation
    - SafeModeController: Safe mode management
    - All schema models and exceptions
"""

from core.policy.errors import (
    PolicyError,
    PolicyLoadError,
    PolicyValidationError,
    PolicySignatureError,
    PolicySignatureInvalidError,
    PolicySignatureMissingError,
    PolicyKeyError,
    PolicyKeyNotFoundError,
    PolicyKeyExpiredError,
    PolicyInheritanceError,
    PolicyInheritanceCycleError,
    PolicyRuleError,
    PolicyRulePriorityConflictError,
    PolicyAllowlistError,
    PolicyAllowlistNotFoundError,
    PolicyEvaluationError,
    PolicySafeModeError,
    PolicyStoreError,
    PolicyVersionError,
    PolicyRollbackError,
)

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
    AllowlistEntry,
    DeviceAllowlistEntry,
    Allowlist,
    MatchCondition,
    RuleMatch,
    RateLimit,
    RuleAction,
    PolicyRule,
    FailureModeConfig,
    SafeModeConfig,
    PolicyDocument,
    # Request/Response
    EvaluationContext,
    EvaluationRequest,
    EvaluationResult,
)

from core.policy.signer import (
    PolicyCanonicalizer,
    KeyTrust,
    SigningKey,
    KeyPair,
    HMACKey,
    PolicySigner,
)

from core.policy.verifier import (
    VerificationStatus,
    VerificationResult,
    PublicKeyEntry,
    PolicyVerifier,
)

from core.policy.store import (
    PolicyVersionInfo,
    PolicyChangeRecord,
    KeyChangeRecord,
    StoredPublicKey,
    PolicyStore,
)

from core.policy.loader import (
    InheritanceGraph,
    InheritanceNode,
    InheritanceNodeStatus,
    FinalPolicy,
    PolicySourceInfo,
    SignatureVerificationStatus,
    PolicyLoader,
    create_safe_mode_policy,
    MAX_INHERITANCE_DEPTH,
    MAX_POLICY_SIZE_BYTES,
    # Merge engine
    MergeReport,
    TrustLevel,
    PolicyMergeEngine,
)

from core.policy.engine import (
    # Enums
    SourceType,
    EvaluationPhase,
    # Request/Response
    EngineEvaluationRequest,
    EngineEvaluationResult,
    MatchResult,
    # Components
    RateLimiterBackend,
    InMemoryRateLimiter,
    ConditionEvaluator,
    RuleMatcher,
    AuditBuilder,
    PolicyEngine,
    # Convenience functions
    create_evaluation_request,
    quick_evaluate,
)

__all__ = [
    # Errors
    "PolicyError",
    "PolicyLoadError",
    "PolicyValidationError",
    "PolicySignatureError",
    "PolicySignatureInvalidError",
    "PolicySignatureMissingError",
    "PolicyKeyError",
    "PolicyKeyNotFoundError",
    "PolicyKeyExpiredError",
    "PolicyInheritanceError",
    "PolicyInheritanceCycleError",
    "PolicyRuleError",
    "PolicyRulePriorityConflictError",
    "PolicyAllowlistError",
    "PolicyAllowlistNotFoundError",
    "PolicyEvaluationError",
    "PolicySafeModeError",
    "PolicyStoreError",
    "PolicyVersionError",
    "PolicyRollbackError",
    # Enums
    "PolicyApiVersion",
    "PolicyKind",
    "ActionType",
    "LogLevel",
    "SignatureAlgorithm",
    "MatchOperator",
    "ReasonCode",
    "Decision",
    # Models
    "PolicyMetadata",
    "PolicySignature",
    "TrustZone",
    "AllowlistEntry",
    "DeviceAllowlistEntry",
    "Allowlist",
    "MatchCondition",
    "RuleMatch",
    "RateLimit",
    "RuleAction",
    "PolicyRule",
    "FailureModeConfig",
    "SafeModeConfig",
    "PolicyDocument",
    # Request/Response
    "EvaluationContext",
    "EvaluationRequest",
    "EvaluationResult",
    # Signing
    "PolicyCanonicalizer",
    "KeyTrust",
    "SigningKey",
    "KeyPair",
    "HMACKey",
    "PolicySigner",
    # Verification
    "VerificationStatus",
    "VerificationResult",
    "PublicKeyEntry",
    "PolicyVerifier",
    # Storage
    "PolicyVersionInfo",
    "PolicyChangeRecord",
    "KeyChangeRecord",
    "StoredPublicKey",
    "PolicyStore",
    # Loader
    "InheritanceGraph",
    "InheritanceNode",
    "InheritanceNodeStatus",
    "FinalPolicy",
    "PolicySourceInfo",
    "SignatureVerificationStatus",
    "PolicyLoader",
    "create_safe_mode_policy",
    "MAX_INHERITANCE_DEPTH",
    "MAX_POLICY_SIZE_BYTES",
    # Merge engine
    "MergeReport",
    "TrustLevel",
    "PolicyMergeEngine",
    # Engine
    "SourceType",
    "EvaluationPhase",
    "EngineEvaluationRequest",
    "EngineEvaluationResult",
    "MatchResult",
    "RateLimiterBackend",
    "InMemoryRateLimiter",
    "ConditionEvaluator",
    "RuleMatcher",
    "AuditBuilder",
    "PolicyEngine",
    "create_evaluation_request",
    "quick_evaluate",
]

__version__ = "1.0.0"
