"""
AKSHAY AI CORE — Policy Engine Errors

Typed exceptions for all policy engine failure modes.
Every exception includes:
- Machine-readable error code
- Human-readable message
- Contextual details for debugging
- Audit-friendly serialization

NO SILENT FAILURES. Every error is explicit and traceable.
"""

from typing import Any, Dict, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class PolicyErrorCode(str, Enum):
    """Machine-readable error codes for policy failures."""
    
    # Load errors (1xx)
    LOAD_FILE_NOT_FOUND = "POLICY_101"
    LOAD_PARSE_ERROR = "POLICY_102"
    LOAD_ENCODING_ERROR = "POLICY_103"
    LOAD_PERMISSION_DENIED = "POLICY_104"
    
    # Validation errors (2xx)
    VALIDATION_SCHEMA_ERROR = "POLICY_201"
    VALIDATION_FIELD_MISSING = "POLICY_202"
    VALIDATION_FIELD_INVALID = "POLICY_203"
    VALIDATION_VERSION_INVALID = "POLICY_204"
    VALIDATION_OPERATOR_INVALID = "POLICY_205"
    VALIDATION_ACTION_INVALID = "POLICY_206"
    VALIDATION_PRIORITY_INVALID = "POLICY_207"
    VALIDATION_ZONE_INVALID = "POLICY_208"
    VALIDATION_REGEX_INVALID = "POLICY_209"
    
    # Signature errors (3xx)
    SIGNATURE_MISSING = "POLICY_301"
    SIGNATURE_INVALID = "POLICY_302"
    SIGNATURE_ALGORITHM_UNSUPPORTED = "POLICY_303"
    SIGNATURE_VERIFICATION_FAILED = "POLICY_304"
    SIGNATURE_TAMPERING_DETECTED = "POLICY_305"
    
    # Key errors (4xx)
    KEY_NOT_FOUND = "POLICY_401"
    KEY_EXPIRED = "POLICY_402"
    KEY_INVALID_FORMAT = "POLICY_403"
    KEY_PERMISSION_DENIED = "POLICY_404"
    KEY_ALGORITHM_MISMATCH = "POLICY_405"
    
    # Inheritance errors (5xx)
    INHERITANCE_CYCLE_DETECTED = "POLICY_501"
    INHERITANCE_PARENT_NOT_FOUND = "POLICY_502"
    INHERITANCE_DEPTH_EXCEEDED = "POLICY_503"
    INHERITANCE_MERGE_CONFLICT = "POLICY_504"
    
    # Rule errors (6xx)
    RULE_PRIORITY_CONFLICT = "POLICY_601"
    RULE_ID_DUPLICATE = "POLICY_602"
    RULE_MATCH_INVALID = "POLICY_603"
    RULE_ACTION_INVALID = "POLICY_604"
    RULE_CONDITION_INVALID = "POLICY_605"
    
    # Allowlist errors (7xx)
    ALLOWLIST_NOT_FOUND = "POLICY_701"
    ALLOWLIST_ENTRY_INVALID = "POLICY_702"
    ALLOWLIST_REFERENCE_INVALID = "POLICY_703"
    ALLOWLIST_CIRCULAR_REFERENCE = "POLICY_704"
    
    # Evaluation errors (8xx)
    EVALUATION_TIMEOUT = "POLICY_801"
    EVALUATION_CONTEXT_INVALID = "POLICY_802"
    EVALUATION_OPERATOR_ERROR = "POLICY_803"
    EVALUATION_INTERNAL_ERROR = "POLICY_804"
    
    # Safe mode errors (9xx)
    SAFE_MODE_ACTIVE = "POLICY_901"
    SAFE_MODE_TRIGGER_FAILED = "POLICY_902"
    SAFE_MODE_EXIT_DENIED = "POLICY_903"
    
    # Store errors (10xx)
    STORE_CORRUPTED = "POLICY_1001"
    STORE_VERSION_NOT_FOUND = "POLICY_1002"
    STORE_WRITE_FAILED = "POLICY_1003"
    STORE_LOCK_FAILED = "POLICY_1004"
    
    # Rollback errors (11xx)
    ROLLBACK_VERSION_NOT_FOUND = "POLICY_1101"
    ROLLBACK_NO_PREVIOUS_VERSION = "POLICY_1102"
    ROLLBACK_VERIFICATION_FAILED = "POLICY_1103"


@dataclass
class PolicyErrorContext:
    """Contextual information for policy errors."""
    
    policy_name: Optional[str] = None
    policy_version: Optional[str] = None
    rule_id: Optional[str] = None
    field_path: Optional[str] = None
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    additional: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "timestamp": self.timestamp.isoformat(),
        }
        if self.policy_name:
            result["policy_name"] = self.policy_name
        if self.policy_version:
            result["policy_version"] = self.policy_version
        if self.rule_id:
            result["rule_id"] = self.rule_id
        if self.field_path:
            result["field_path"] = self.field_path
        if self.expected_value is not None:
            result["expected_value"] = str(self.expected_value)
        if self.actual_value is not None:
            result["actual_value"] = str(self.actual_value)
        if self.file_path:
            result["file_path"] = self.file_path
        if self.line_number:
            result["line_number"] = self.line_number
        if self.additional:
            result["additional"] = self.additional
        return result


class PolicyError(Exception):
    """Base exception for all policy engine errors."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode,
        context: Optional[PolicyErrorContext] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or PolicyErrorContext()
        self.cause = cause
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        result = {
            "error_type": self.__class__.__name__,
            "code": self.code.value,
            "code_name": self.code.name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context.to_dict(),
        }
        if self.cause:
            result["cause"] = {
                "type": type(self.cause).__name__,
                "message": str(self.cause),
            }
        return result
    
    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code.value}, message={self.message!r})"


# =============================================================================
# LOAD ERRORS
# =============================================================================

class PolicyLoadError(PolicyError):
    """Error loading policy file."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        context = PolicyErrorContext(file_path=file_path)
        super().__init__(
            message=message,
            code=PolicyErrorCode.LOAD_FILE_NOT_FOUND,
            context=context,
            cause=cause,
        )


# =============================================================================
# VALIDATION ERRORS
# =============================================================================

class PolicyValidationError(PolicyError):
    """Error validating policy schema or content."""
    
    def __init__(
        self,
        message: str,
        field_path: Optional[str] = None,
        expected_value: Optional[Any] = None,
        actual_value: Optional[Any] = None,
        code: PolicyErrorCode = PolicyErrorCode.VALIDATION_SCHEMA_ERROR,
        context: Optional[PolicyErrorContext] = None,
    ):
        ctx = context or PolicyErrorContext(
            field_path=field_path,
            expected_value=expected_value,
            actual_value=actual_value,
        )
        super().__init__(message=message, code=code, context=ctx)


# =============================================================================
# SIGNATURE ERRORS
# =============================================================================

class PolicySignatureError(PolicyError):
    """Base error for signature-related failures."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode,
        context: Optional[PolicyErrorContext] = None,
    ):
        super().__init__(message=message, code=code, context=context)


class PolicySignatureMissingError(PolicySignatureError):
    """Policy is missing required signature."""
    
    def __init__(
        self,
        policy_name: Optional[str] = None,
        message: str = "Policy signature is missing",
    ):
        context = PolicyErrorContext(policy_name=policy_name)
        super().__init__(
            message=message,
            code=PolicyErrorCode.SIGNATURE_MISSING,
            context=context,
        )


class PolicySignatureInvalidError(PolicySignatureError):
    """Policy signature is invalid or verification failed."""
    
    def __init__(
        self,
        policy_name: Optional[str] = None,
        reason: str = "Signature verification failed",
        tampered: bool = False,
    ):
        code = (
            PolicyErrorCode.SIGNATURE_TAMPERING_DETECTED
            if tampered
            else PolicyErrorCode.SIGNATURE_INVALID
        )
        context = PolicyErrorContext(
            policy_name=policy_name,
            additional={"tampered": tampered, "reason": reason},
        )
        super().__init__(
            message=f"Policy signature invalid: {reason}",
            code=code,
            context=context,
        )


# =============================================================================
# KEY ERRORS
# =============================================================================

class PolicyKeyError(PolicyError):
    """Base error for key-related failures."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode,
        key_id: Optional[str] = None,
    ):
        context = PolicyErrorContext(additional={"key_id": key_id} if key_id else {})
        super().__init__(message=message, code=code, context=context)


class PolicyKeyNotFoundError(PolicyKeyError):
    """Signing key not found in key store."""
    
    def __init__(self, key_id: str):
        super().__init__(
            message=f"Signing key not found: {key_id}",
            code=PolicyErrorCode.KEY_NOT_FOUND,
            key_id=key_id,
        )


class PolicyKeyExpiredError(PolicyKeyError):
    """Signing key has expired."""
    
    def __init__(self, key_id: str, expired_at: datetime):
        super().__init__(
            message=f"Signing key expired: {key_id} (expired at {expired_at.isoformat()})",
            code=PolicyErrorCode.KEY_EXPIRED,
            key_id=key_id,
        )
        self.context.additional["expired_at"] = expired_at.isoformat()


# =============================================================================
# INHERITANCE ERRORS
# =============================================================================

class PolicyInheritanceError(PolicyError):
    """Base error for inheritance-related failures."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode,
        policy_name: Optional[str] = None,
        parent_name: Optional[str] = None,
    ):
        context = PolicyErrorContext(
            policy_name=policy_name,
            additional={"parent_name": parent_name} if parent_name else {},
        )
        super().__init__(message=message, code=code, context=context)


class PolicyInheritanceCycleError(PolicyInheritanceError):
    """Circular inheritance detected in policy chain."""
    
    def __init__(self, cycle_path: List[str]):
        cycle_str = " -> ".join(cycle_path)
        super().__init__(
            message=f"Inheritance cycle detected: {cycle_str}",
            code=PolicyErrorCode.INHERITANCE_CYCLE_DETECTED,
            policy_name=cycle_path[0] if cycle_path else None,
        )
        self.context.additional["cycle_path"] = cycle_path


# =============================================================================
# RULE ERRORS
# =============================================================================

class PolicyRuleError(PolicyError):
    """Base error for rule-related failures."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode,
        rule_id: Optional[str] = None,
        policy_name: Optional[str] = None,
    ):
        context = PolicyErrorContext(
            rule_id=rule_id,
            policy_name=policy_name,
        )
        super().__init__(message=message, code=code, context=context)


class PolicyRulePriorityConflictError(PolicyRuleError):
    """Multiple rules have the same priority and match criteria."""
    
    def __init__(
        self,
        rule_ids: List[str],
        priority: int,
        policy_name: Optional[str] = None,
    ):
        super().__init__(
            message=f"Priority conflict: rules {rule_ids} share priority {priority}",
            code=PolicyErrorCode.RULE_PRIORITY_CONFLICT,
            rule_id=rule_ids[0] if rule_ids else None,
            policy_name=policy_name,
        )
        self.context.additional["conflicting_rules"] = rule_ids
        self.context.additional["priority"] = priority


# =============================================================================
# ALLOWLIST ERRORS
# =============================================================================

class PolicyAllowlistError(PolicyError):
    """Base error for allowlist-related failures."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode,
        allowlist_name: Optional[str] = None,
    ):
        context = PolicyErrorContext(
            additional={"allowlist_name": allowlist_name} if allowlist_name else {}
        )
        super().__init__(message=message, code=code, context=context)


class PolicyAllowlistNotFoundError(PolicyAllowlistError):
    """Referenced allowlist does not exist."""
    
    def __init__(self, allowlist_ref: str, policy_name: Optional[str] = None):
        super().__init__(
            message=f"Allowlist not found: {allowlist_ref}",
            code=PolicyErrorCode.ALLOWLIST_NOT_FOUND,
            allowlist_name=allowlist_ref,
        )
        self.context.policy_name = policy_name


# =============================================================================
# EVALUATION ERRORS
# =============================================================================

class PolicyEvaluationError(PolicyError):
    """Error during policy evaluation."""
    
    def __init__(
        self,
        message: str,
        rule_id: Optional[str] = None,
        code: PolicyErrorCode = PolicyErrorCode.EVALUATION_INTERNAL_ERROR,
        cause: Optional[Exception] = None,
    ):
        context = PolicyErrorContext(rule_id=rule_id)
        super().__init__(message=message, code=code, context=context, cause=cause)


# =============================================================================
# SAFE MODE ERRORS
# =============================================================================

class PolicySafeModeError(PolicyError):
    """Error related to safe mode operations."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode = PolicyErrorCode.SAFE_MODE_ACTIVE,
        action_attempted: Optional[str] = None,
    ):
        context = PolicyErrorContext(
            additional={"action_attempted": action_attempted} if action_attempted else {}
        )
        super().__init__(message=message, code=code, context=context)


# =============================================================================
# STORE ERRORS
# =============================================================================

class PolicyStoreError(PolicyError):
    """Error with policy store operations."""
    
    def __init__(
        self,
        message: str,
        code: PolicyErrorCode = PolicyErrorCode.STORE_CORRUPTED,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message=message, code=code, cause=cause)


class PolicyVersionError(PolicyStoreError):
    """Error with policy versioning."""
    
    def __init__(self, version: str, message: Optional[str] = None):
        super().__init__(
            message=message or f"Policy version error: {version}",
            code=PolicyErrorCode.STORE_VERSION_NOT_FOUND,
        )
        self.context.policy_version = version


class PolicyRollbackError(PolicyStoreError):
    """Error during policy rollback."""
    
    def __init__(
        self,
        target_version: str,
        reason: str,
        code: PolicyErrorCode = PolicyErrorCode.ROLLBACK_VERSION_NOT_FOUND,
    ):
        super().__init__(
            message=f"Rollback to {target_version} failed: {reason}",
            code=code,
        )
        self.context.policy_version = target_version
        self.context.additional["reason"] = reason
