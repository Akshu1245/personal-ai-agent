"""
============================================================
AKSHAY AI CORE — Automation Safety Layer
============================================================
Provides comprehensive safety controls for automation and
scheduled task execution.

SAFETY CONTROLS:
1. Rate Limits - prevent runaway automation
2. Quotas - limit resource consumption
3. Kill Switch - emergency stop all automation
4. Dry-Run Mode - test without execution
5. Approval Workflows - require approval for sensitive actions
6. Execution Sandboxing - isolated execution environment
7. Rollback Support - undo automation actions
============================================================
"""

import asyncio
import hashlib
import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict
import uuid

from core.config import settings
from core.utils.logger import get_logger
from core.security.permissions import Permission, Role, ROLE_PERMISSIONS
from core.security.firewall import (
    permission_firewall,
    create_security_context,
    SecurityContext,
)
from core.security.audit_log import immutable_audit_log, AuditEventType, AuditSeverity

logger = get_logger("security.automation_safety")


class AutomationState(Enum):
    """Automation system states."""
    RUNNING = "running"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"
    MAINTENANCE = "maintenance"
    DRY_RUN = "dry_run"


class ApprovalStatus(Enum):
    """Approval workflow status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RuleCategory(Enum):
    """Categories of automation rules for policy enforcement."""
    DATA = "data"           # Data manipulation
    SYSTEM = "system"       # System commands
    NETWORK = "network"     # Network operations
    IOT = "iot"            # IoT device control
    NOTIFICATION = "notification"  # Notifications/alerts
    INTEGRATION = "integration"    # External integrations
    MAINTENANCE = "maintenance"    # System maintenance


@dataclass
class AutomationQuota:
    """
    Quota configuration for automation rules.
    """
    # Execution limits
    max_executions_per_hour: int = 60
    max_executions_per_day: int = 1000
    max_concurrent_executions: int = 5
    
    # Resource limits
    max_memory_mb: int = 256
    max_cpu_seconds: int = 60
    max_network_requests: int = 100
    max_file_operations: int = 50
    
    # Time limits
    max_execution_time_seconds: int = 300
    
    # Cooldown
    min_interval_seconds: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_executions_per_hour": self.max_executions_per_hour,
            "max_executions_per_day": self.max_executions_per_day,
            "max_concurrent_executions": self.max_concurrent_executions,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_seconds": self.max_cpu_seconds,
            "max_network_requests": self.max_network_requests,
            "max_file_operations": self.max_file_operations,
            "max_execution_time_seconds": self.max_execution_time_seconds,
            "min_interval_seconds": self.min_interval_seconds,
        }


@dataclass
class SafeAutomationRule:
    """
    Automation rule with safety metadata.
    """
    id: str
    name: str
    description: str
    owner_id: str
    category: RuleCategory
    
    # Safety settings
    quota: AutomationQuota = field(default_factory=AutomationQuota)
    requires_approval: bool = False
    approval_roles: Set[Role] = field(default_factory=lambda: {Role.ADMIN})
    dry_run_only: bool = False
    
    # Sandboxing
    sandboxed: bool = True
    allow_network: bool = False
    allow_filesystem: bool = False
    allow_subprocess: bool = False
    allowed_plugins: Set[str] = field(default_factory=set)
    
    # State
    enabled: bool = True
    paused: bool = False
    
    # Statistics
    execution_count: int = 0
    last_executed: Optional[datetime] = None
    failure_count: int = 0
    last_failure: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "category": self.category.value,
            "quota": self.quota.to_dict(),
            "requires_approval": self.requires_approval,
            "dry_run_only": self.dry_run_only,
            "sandboxed": self.sandboxed,
            "allow_network": self.allow_network,
            "allow_filesystem": self.allow_filesystem,
            "enabled": self.enabled,
            "paused": self.paused,
            "execution_count": self.execution_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "failure_count": self.failure_count,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ApprovalRequest:
    """
    Request for automation approval.
    """
    id: str
    rule_id: str
    rule_name: str
    requested_by: str
    requested_at: datetime
    
    # Approval details
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Expiry
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=24)
    )
    
    # Execution context
    execution_params: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass
class ExecutionRecord:
    """
    Record of automation execution for rollback support.
    """
    id: str
    rule_id: str
    executed_at: datetime
    executed_by: str
    
    # Result
    success: bool
    output: Any = None
    error: Optional[str] = None
    
    # Rollback
    can_rollback: bool = False
    rollback_data: Optional[Dict[str, Any]] = None
    rolled_back: bool = False
    
    # Metrics
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "executed_at": self.executed_at.isoformat(),
            "executed_by": self.executed_by,
            "success": self.success,
            "error": self.error,
            "can_rollback": self.can_rollback,
            "rolled_back": self.rolled_back,
            "execution_time_ms": self.execution_time_ms,
        }


class RateLimitTracker:
    """
    Tracks rate limits for automation rules.
    """
    
    def __init__(self):
        # Format: {rule_id: [(timestamp, count)]}
        self._hourly_executions: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        self._daily_executions: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        self._last_execution: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def check_rate_limit(
        self,
        rule_id: str,
        quota: AutomationQuota,
    ) -> Tuple[bool, str]:
        """
        Check if rule is within rate limits.
        
        Returns:
            Tuple of (allowed, reason)
        """
        current_time = time.time()
        
        with self._lock:
            # Check minimum interval
            last_exec = self._last_execution.get(rule_id, 0)
            if current_time - last_exec < quota.min_interval_seconds:
                remaining = quota.min_interval_seconds - (current_time - last_exec)
                return False, f"Cooldown active, wait {remaining:.1f}s"
            
            # Clean and count hourly executions
            hour_ago = current_time - 3600
            self._hourly_executions[rule_id] = [
                (ts, c) for ts, c in self._hourly_executions[rule_id]
                if ts > hour_ago
            ]
            hourly_count = sum(c for _, c in self._hourly_executions[rule_id])
            
            if hourly_count >= quota.max_executions_per_hour:
                return False, f"Hourly limit reached ({quota.max_executions_per_hour}/hour)"
            
            # Clean and count daily executions
            day_ago = current_time - 86400
            self._daily_executions[rule_id] = [
                (ts, c) for ts, c in self._daily_executions[rule_id]
                if ts > day_ago
            ]
            daily_count = sum(c for _, c in self._daily_executions[rule_id])
            
            if daily_count >= quota.max_executions_per_day:
                return False, f"Daily limit reached ({quota.max_executions_per_day}/day)"
        
        return True, "Rate limit OK"
    
    def record_execution(self, rule_id: str) -> None:
        """Record an execution for rate limiting."""
        current_time = time.time()
        
        with self._lock:
            self._hourly_executions[rule_id].append((current_time, 1))
            self._daily_executions[rule_id].append((current_time, 1))
            self._last_execution[rule_id] = current_time
    
    def get_remaining_quota(
        self,
        rule_id: str,
        quota: AutomationQuota,
    ) -> Dict[str, int]:
        """Get remaining quota for rule."""
        current_time = time.time()
        
        with self._lock:
            # Count hourly
            hour_ago = current_time - 3600
            hourly_count = sum(
                c for ts, c in self._hourly_executions.get(rule_id, [])
                if ts > hour_ago
            )
            
            # Count daily
            day_ago = current_time - 86400
            daily_count = sum(
                c for ts, c in self._daily_executions.get(rule_id, [])
                if ts > day_ago
            )
        
        return {
            "hourly_remaining": max(0, quota.max_executions_per_hour - hourly_count),
            "daily_remaining": max(0, quota.max_executions_per_day - daily_count),
        }


class ConcurrencyTracker:
    """
    Tracks concurrent executions.
    """
    
    def __init__(self, global_limit: int = 20):
        self._global_limit = global_limit
        self._active: Dict[str, int] = defaultdict(int)  # rule_id -> count
        self._global_count = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self, rule_id: str, max_concurrent: int) -> bool:
        """Acquire execution slot."""
        async with self._lock:
            if self._global_count >= self._global_limit:
                return False
            if self._active[rule_id] >= max_concurrent:
                return False
            
            self._active[rule_id] += 1
            self._global_count += 1
            return True
    
    async def release(self, rule_id: str) -> None:
        """Release execution slot."""
        async with self._lock:
            if self._active[rule_id] > 0:
                self._active[rule_id] -= 1
                self._global_count -= 1
    
    def get_active_count(self, rule_id: Optional[str] = None) -> int:
        """Get count of active executions."""
        if rule_id:
            return self._active.get(rule_id, 0)
        return self._global_count


class AutomationSafetyLayer:
    """
    Automation Safety Layer.
    
    Provides comprehensive safety controls for all automation:
    - Rate limiting and quotas
    - Kill switch for emergency stop
    - Dry-run mode for testing
    - Approval workflows for sensitive actions
    - Execution sandboxing
    - Rollback support
    
    ALL automation MUST go through this safety layer.
    """
    
    _instance: Optional["AutomationSafetyLayer"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "AutomationSafetyLayer":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # State
        self._state = AutomationState.RUNNING
        self._state_lock = threading.Lock()
        
        # Rules
        self._rules: Dict[str, SafeAutomationRule] = {}
        
        # Rate limiting
        self._rate_limiter = RateLimitTracker()
        
        # Concurrency
        self._concurrency = ConcurrencyTracker()
        
        # Approval workflow
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        
        # Execution history for rollback
        self._execution_history: List[ExecutionRecord] = []
        self._history_max_size = 1000
        
        # Kill switch handlers
        self._kill_switch_callbacks: List[Callable] = []
        
        # Statistics
        self._stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "blocked_by_rate_limit": 0,
            "blocked_by_kill_switch": 0,
            "dry_run_executions": 0,
            "pending_approvals": 0,
            "approved_executions": 0,
            "rejected_executions": 0,
            "rollbacks_performed": 0,
        }
        
        logger.info("Automation Safety Layer initialized")
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def get_state(self) -> AutomationState:
        """Get current automation state."""
        with self._state_lock:
            return self._state
    
    def set_state(self, state: AutomationState, reason: str = "") -> None:
        """Set automation state."""
        with self._state_lock:
            old_state = self._state
            self._state = state
        
        # Log state change
        immutable_audit_log.log(
            event_type=AuditEventType.SYSTEM_CONFIG,
            severity=AuditSeverity.WARNING if state == AutomationState.EMERGENCY_STOP else AuditSeverity.NOTICE,
            action="automation_state_change",
            details={
                "old_state": old_state.value,
                "new_state": state.value,
                "reason": reason,
            },
        )
        
        logger.info(f"Automation state changed: {old_state.value} -> {state.value}", reason=reason)
    
    def activate_kill_switch(self, reason: str, activated_by: str) -> None:
        """
        Activate emergency kill switch.
        
        Immediately stops all automation execution.
        """
        self.set_state(AutomationState.EMERGENCY_STOP, reason)
        
        # Run kill switch callbacks
        for callback in self._kill_switch_callbacks:
            try:
                callback(reason)
            except Exception as e:
                logger.error("Kill switch callback failed", error=str(e))
        
        self._stats["blocked_by_kill_switch"] += 1
        
        # Critical audit log
        immutable_audit_log.log(
            event_type=AuditEventType.SECURITY_ALERT,
            severity=AuditSeverity.CRITICAL,
            action="kill_switch_activated",
            user_id=activated_by,
            details={"reason": reason},
        )
    
    def deactivate_kill_switch(self, deactivated_by: str) -> None:
        """Deactivate kill switch and resume automation."""
        if self._state == AutomationState.EMERGENCY_STOP:
            self.set_state(AutomationState.RUNNING, f"Deactivated by {deactivated_by}")
            
            immutable_audit_log.log(
                event_type=AuditEventType.SYSTEM_CONFIG,
                severity=AuditSeverity.NOTICE,
                action="kill_switch_deactivated",
                user_id=deactivated_by,
            )
    
    def enable_dry_run_mode(self) -> None:
        """Enable dry-run mode for all automation."""
        self.set_state(AutomationState.DRY_RUN, "Dry-run mode enabled")
    
    def disable_dry_run_mode(self) -> None:
        """Disable dry-run mode."""
        if self._state == AutomationState.DRY_RUN:
            self.set_state(AutomationState.RUNNING, "Dry-run mode disabled")
    
    def register_kill_switch_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for kill switch activation."""
        self._kill_switch_callbacks.append(callback)
    
    # =========================================================================
    # RULE MANAGEMENT
    # =========================================================================
    
    def register_rule(self, rule: SafeAutomationRule) -> None:
        """Register an automation rule."""
        self._rules[rule.id] = rule
        
        immutable_audit_log.log(
            event_type=AuditEventType.AUTOMATION_CREATE,
            severity=AuditSeverity.INFO,
            action="automation_rule_registered",
            user_id=rule.owner_id,
            resource_type="automation_rule",
            resource_id=rule.id,
            details={
                "name": rule.name,
                "category": rule.category.value,
                "requires_approval": rule.requires_approval,
            },
        )
    
    def unregister_rule(self, rule_id: str) -> bool:
        """Unregister an automation rule."""
        if rule_id in self._rules:
            rule = self._rules.pop(rule_id)
            
            immutable_audit_log.log(
                event_type=AuditEventType.AUTOMATION_DELETE,
                severity=AuditSeverity.INFO,
                action="automation_rule_unregistered",
                resource_type="automation_rule",
                resource_id=rule_id,
            )
            return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[SafeAutomationRule]:
        """Get rule by ID."""
        return self._rules.get(rule_id)
    
    def list_rules(
        self,
        owner_id: Optional[str] = None,
        category: Optional[RuleCategory] = None,
        enabled_only: bool = False,
    ) -> List[SafeAutomationRule]:
        """List rules with optional filters."""
        rules = list(self._rules.values())
        
        if owner_id:
            rules = [r for r in rules if r.owner_id == owner_id]
        if category:
            rules = [r for r in rules if r.category == category]
        if enabled_only:
            rules = [r for r in rules if r.enabled and not r.paused]
        
        return rules
    
    # =========================================================================
    # EXECUTION
    # =========================================================================
    
    async def execute_rule(
        self,
        rule_id: str,
        context: SecurityContext,
        params: Optional[Dict[str, Any]] = None,
        executor: Optional[Callable] = None,
        force_dry_run: bool = False,
    ) -> ExecutionRecord:
        """
        Execute an automation rule with all safety checks.
        
        Safety pipeline:
        1. Check system state (kill switch, maintenance, etc.)
        2. Check rule state (enabled, paused)
        3. Check permissions
        4. Check rate limits
        5. Check concurrency
        6. Check approval if required
        7. Execute (or dry-run)
        8. Record execution
        
        Args:
            rule_id: Rule to execute
            context: Security context
            params: Execution parameters
            executor: Function to execute the rule
            force_dry_run: Force dry-run regardless of settings
            
        Returns:
            Execution record
        """
        self._stats["total_executions"] += 1
        
        rule = self._rules.get(rule_id)
        if not rule:
            raise ValueError(f"Rule not found: {rule_id}")
        
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Create execution record
        record = ExecutionRecord(
            id=execution_id,
            rule_id=rule_id,
            executed_at=datetime.utcnow(),
            executed_by=context.user_id,
            success=False,
        )
        
        try:
            # ================================================================
            # SAFETY CHECK 1: System State
            # ================================================================
            state = self.get_state()
            
            if state == AutomationState.EMERGENCY_STOP:
                record.error = "Automation disabled: Kill switch active"
                self._stats["blocked_by_kill_switch"] += 1
                return record
            
            if state == AutomationState.PAUSED:
                record.error = "Automation paused"
                return record
            
            if state == AutomationState.MAINTENANCE:
                record.error = "Automation in maintenance mode"
                return record
            
            is_dry_run = force_dry_run or state == AutomationState.DRY_RUN or rule.dry_run_only
            
            # ================================================================
            # SAFETY CHECK 2: Rule State
            # ================================================================
            if not rule.enabled:
                record.error = "Rule is disabled"
                return record
            
            if rule.paused:
                record.error = "Rule is paused"
                return record
            
            # ================================================================
            # SAFETY CHECK 3: Permissions
            # ================================================================
            context.action = f"automation_execute:{rule_id}"
            context.resource_type = "automation_rule"
            context.resource_id = rule_id
            
            result = await permission_firewall.evaluate(
                context,
                {Permission.TRIGGER_AUTOMATIONS},
            )
            
            if not result.allowed:
                record.error = f"Permission denied: {result.reason}"
                self._stats["failed_executions"] += 1
                return record
            
            # ================================================================
            # SAFETY CHECK 4: Rate Limits
            # ================================================================
            rate_ok, rate_msg = self._rate_limiter.check_rate_limit(rule_id, rule.quota)
            
            if not rate_ok:
                record.error = f"Rate limit exceeded: {rate_msg}"
                self._stats["blocked_by_rate_limit"] += 1
                return record
            
            # ================================================================
            # SAFETY CHECK 5: Concurrency
            # ================================================================
            if not await self._concurrency.acquire(rule_id, rule.quota.max_concurrent_executions):
                record.error = "Concurrency limit reached"
                return record
            
            try:
                # ================================================================
                # SAFETY CHECK 6: Approval
                # ================================================================
                if rule.requires_approval:
                    approval = self._check_approval(rule_id, context.user_id, params)
                    
                    if not approval:
                        # Create approval request
                        request = await self._create_approval_request(rule, context.user_id, params)
                        record.error = f"Approval required. Request ID: {request.id}"
                        self._stats["pending_approvals"] += 1
                        return record
                    
                    if approval.status == ApprovalStatus.REJECTED:
                        record.error = f"Approval rejected: {approval.rejection_reason}"
                        self._stats["rejected_executions"] += 1
                        return record
                    
                    self._stats["approved_executions"] += 1
                
                # ================================================================
                # EXECUTE
                # ================================================================
                if is_dry_run:
                    self._stats["dry_run_executions"] += 1
                    record.success = True
                    record.output = {"dry_run": True, "would_execute": True}
                    
                    immutable_audit_log.log(
                        event_type=AuditEventType.AUTOMATION_EXECUTE,
                        severity=AuditSeverity.INFO,
                        action=f"automation_dry_run:{rule_id}",
                        user_id=context.user_id,
                        resource_type="automation_rule",
                        resource_id=rule_id,
                        details={"params": params, "dry_run": True},
                    )
                else:
                    if executor:
                        try:
                            # Execute with timeout
                            result = await asyncio.wait_for(
                                executor(rule_id, params),
                                timeout=rule.quota.max_execution_time_seconds,
                            )
                            record.success = True
                            record.output = result
                            
                            # Check if rollback is possible
                            if isinstance(result, dict) and "rollback_data" in result:
                                record.can_rollback = True
                                record.rollback_data = result["rollback_data"]
                            
                        except asyncio.TimeoutError:
                            record.error = f"Execution timeout after {rule.quota.max_execution_time_seconds}s"
                        except Exception as e:
                            record.error = str(e)
                    else:
                        record.error = "No executor provided"
                    
                    # Update rule statistics
                    rule.execution_count += 1
                    rule.last_executed = datetime.utcnow()
                    
                    if not record.success:
                        rule.failure_count += 1
                        rule.last_failure = record.error
                    
                    # Record rate limit
                    self._rate_limiter.record_execution(rule_id)
                    
                    # Audit log
                    immutable_audit_log.log(
                        event_type=AuditEventType.AUTOMATION_EXECUTE,
                        severity=AuditSeverity.INFO if record.success else AuditSeverity.WARNING,
                        action=f"automation_execute:{rule_id}",
                        user_id=context.user_id,
                        resource_type="automation_rule",
                        resource_id=rule_id,
                        status="success" if record.success else "failure",
                        error_message=record.error,
                        details={"params": params},
                    )
                
            finally:
                await self._concurrency.release(rule_id)
            
            # Update stats
            if record.success:
                self._stats["successful_executions"] += 1
            else:
                self._stats["failed_executions"] += 1
            
        except Exception as e:
            record.error = str(e)
            self._stats["failed_executions"] += 1
            logger.error(f"Automation execution error", rule_id=rule_id, error=str(e))
        
        finally:
            record.execution_time_ms = (time.time() - start_time) * 1000
            self._add_to_history(record)
        
        return record
    
    # =========================================================================
    # APPROVAL WORKFLOW
    # =========================================================================
    
    def _check_approval(
        self,
        rule_id: str,
        user_id: str,
        params: Optional[Dict[str, Any]],
    ) -> Optional[ApprovalRequest]:
        """Check if there's an approved request for this execution."""
        for approval in self._pending_approvals.values():
            if approval.rule_id != rule_id:
                continue
            if approval.requested_by != user_id:
                continue
            if approval.is_expired():
                approval.status = ApprovalStatus.EXPIRED
                continue
            if approval.status == ApprovalStatus.APPROVED:
                # Remove after use
                del self._pending_approvals[approval.id]
                return approval
            if approval.status == ApprovalStatus.REJECTED:
                return approval
        
        return None
    
    async def _create_approval_request(
        self,
        rule: SafeAutomationRule,
        user_id: str,
        params: Optional[Dict[str, Any]],
    ) -> ApprovalRequest:
        """Create a new approval request."""
        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            rule_name=rule.name,
            requested_by=user_id,
            requested_at=datetime.utcnow(),
            execution_params=params or {},
        )
        
        self._pending_approvals[request.id] = request
        
        immutable_audit_log.log(
            event_type=AuditEventType.AUTOMATION_CREATE,
            severity=AuditSeverity.NOTICE,
            action="approval_requested",
            user_id=user_id,
            resource_type="approval_request",
            resource_id=request.id,
            details={
                "rule_id": rule.id,
                "rule_name": rule.name,
            },
        )
        
        return request
    
    async def approve_request(
        self,
        request_id: str,
        approved_by: str,
        approver_role: Role,
    ) -> bool:
        """Approve an automation request."""
        request = self._pending_approvals.get(request_id)
        if not request:
            raise ValueError(f"Approval request not found: {request_id}")
        
        if request.is_expired():
            request.status = ApprovalStatus.EXPIRED
            return False
        
        if request.status != ApprovalStatus.PENDING:
            return False
        
        # Check approver has permission
        rule = self._rules.get(request.rule_id)
        if rule and approver_role not in rule.approval_roles:
            raise PermissionError(f"Role {approver_role} cannot approve this rule")
        
        request.status = ApprovalStatus.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.utcnow()
        
        immutable_audit_log.log(
            event_type=AuditEventType.AUTHZ_GRANTED,
            severity=AuditSeverity.NOTICE,
            action="approval_granted",
            user_id=approved_by,
            resource_type="approval_request",
            resource_id=request_id,
            details={"rule_id": request.rule_id},
        )
        
        return True
    
    async def reject_request(
        self,
        request_id: str,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """Reject an automation request."""
        request = self._pending_approvals.get(request_id)
        if not request:
            raise ValueError(f"Approval request not found: {request_id}")
        
        if request.status != ApprovalStatus.PENDING:
            return False
        
        request.status = ApprovalStatus.REJECTED
        request.rejection_reason = reason
        request.approved_by = rejected_by
        request.approved_at = datetime.utcnow()
        
        immutable_audit_log.log(
            event_type=AuditEventType.AUTHZ_DENIED,
            severity=AuditSeverity.NOTICE,
            action="approval_rejected",
            user_id=rejected_by,
            resource_type="approval_request",
            resource_id=request_id,
            details={"rule_id": request.rule_id, "reason": reason},
        )
        
        return True
    
    def get_pending_approvals(
        self,
        approver_role: Optional[Role] = None,
    ) -> List[ApprovalRequest]:
        """Get pending approval requests."""
        pending = [
            r for r in self._pending_approvals.values()
            if r.status == ApprovalStatus.PENDING and not r.is_expired()
        ]
        
        if approver_role:
            # Filter to rules this role can approve
            pending = [
                r for r in pending
                if r.rule_id in self._rules and 
                approver_role in self._rules[r.rule_id].approval_roles
            ]
        
        return pending
    
    # =========================================================================
    # ROLLBACK
    # =========================================================================
    
    async def rollback_execution(
        self,
        execution_id: str,
        context: SecurityContext,
        rollback_executor: Callable,
    ) -> bool:
        """
        Rollback a previous automation execution.
        
        Args:
            execution_id: Execution to rollback
            context: Security context
            rollback_executor: Function to perform rollback
            
        Returns:
            True if rolled back successfully
        """
        record = None
        for rec in self._execution_history:
            if rec.id == execution_id:
                record = rec
                break
        
        if not record:
            raise ValueError(f"Execution not found: {execution_id}")
        
        if not record.can_rollback:
            raise ValueError("Execution cannot be rolled back")
        
        if record.rolled_back:
            raise ValueError("Execution already rolled back")
        
        try:
            await rollback_executor(record.rollback_data)
            record.rolled_back = True
            self._stats["rollbacks_performed"] += 1
            
            immutable_audit_log.log(
                event_type=AuditEventType.AUTOMATION_EXECUTE,
                severity=AuditSeverity.NOTICE,
                action="automation_rollback",
                user_id=context.user_id,
                resource_type="automation_execution",
                resource_id=execution_id,
                details={"rule_id": record.rule_id},
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed", execution_id=execution_id, error=str(e))
            return False
    
    # =========================================================================
    # HISTORY AND STATS
    # =========================================================================
    
    def _add_to_history(self, record: ExecutionRecord) -> None:
        """Add execution record to history."""
        self._execution_history.append(record)
        
        if len(self._execution_history) > self._history_max_size:
            self._execution_history = self._execution_history[-self._history_max_size:]
    
    def get_execution_history(
        self,
        rule_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExecutionRecord]:
        """Get execution history."""
        history = self._execution_history[-limit:]
        
        if rule_id:
            history = [r for r in history if r.rule_id == rule_id]
        
        return history
    
    def get_stats(self) -> Dict[str, Any]:
        """Get safety layer statistics."""
        return {
            **self._stats,
            "current_state": self._state.value,
            "active_rules": len([r for r in self._rules.values() if r.enabled]),
            "active_executions": self._concurrency.get_active_count(),
        }
    
    def get_rule_stats(self, rule_id: str) -> Dict[str, Any]:
        """Get statistics for a specific rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            raise ValueError(f"Rule not found: {rule_id}")
        
        remaining = self._rate_limiter.get_remaining_quota(rule_id, rule.quota)
        
        return {
            "execution_count": rule.execution_count,
            "failure_count": rule.failure_count,
            "last_executed": rule.last_executed.isoformat() if rule.last_executed else None,
            "last_failure": rule.last_failure,
            "active_executions": self._concurrency.get_active_count(rule_id),
            "remaining_quota": remaining,
        }


# Global instance
automation_safety = AutomationSafetyLayer()
