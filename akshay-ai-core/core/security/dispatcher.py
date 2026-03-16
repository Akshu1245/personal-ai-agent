"""
============================================================
AKSHAY AI CORE — Tool Dispatcher
============================================================
Mandatory execution pipeline that ALL tool and plugin
calls MUST route through.

Pipeline: Intent → Permission → Sandbox → RateLimit → 
         Execute → Validate → Log → Response

NO TOOL CAN BYPASS THIS DISPATCHER.
============================================================
"""

import asyncio
import hashlib
import inspect
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
import threading
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
import copy

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.permissions import Permission, Role
from core.security.firewall import (
    PermissionFirewall,
    SecurityContext,
    SecurityDecision,
    SecurityDecisionResult,
    permission_firewall,
    create_security_context,
)

logger = get_logger("security.dispatcher")

T = TypeVar("T")


class ToolCategory(Enum):
    """Categories of tools for classification and policy enforcement."""
    QUERY = "query"
    MEMORY = "memory"
    PLUGIN = "plugin"
    AUTOMATION = "automation"
    SYSTEM = "system"
    FILE = "file"
    NETWORK = "network"
    DATA = "data"
    IOT = "iot"
    USER = "user"
    ADMIN = "admin"


class ExecutionStage(Enum):
    """Stages in the execution pipeline."""
    RECEIVED = auto()
    VALIDATED = auto()
    PERMISSION_CHECKED = auto()
    RATE_LIMITED = auto()
    SANDBOXED = auto()
    EXECUTING = auto()
    OUTPUT_VALIDATED = auto()
    LOGGED = auto()
    COMPLETED = auto()
    FAILED = auto()
    ABORTED = auto()


class ExecutionPriority(Enum):
    """Execution priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class ToolDefinition:
    """
    Complete definition of a tool.
    
    Includes metadata, permissions, validation rules,
    and execution constraints.
    """
    name: str
    category: ToolCategory
    description: str
    handler: Callable[..., Coroutine[Any, Any, Any]]
    
    # Permission requirements
    required_permissions: Set[Permission] = field(default_factory=set)
    required_role: Optional[Role] = None
    
    # Execution constraints
    timeout_seconds: int = 30
    max_concurrent: int = 5
    rate_limit_per_minute: int = 30
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    
    # Sandbox settings
    sandbox_enabled: bool = True
    allow_network: bool = False
    allow_filesystem: bool = False
    allow_subprocess: bool = False
    max_memory_mb: int = 256
    
    # Validation
    input_validator: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None
    output_validator: Optional[Callable[[Any], Tuple[bool, str]]] = None
    
    # Flags
    requires_confirmation: bool = False
    is_destructive: bool = False
    is_sensitive: bool = False
    audit_inputs: bool = True
    audit_outputs: bool = True
    
    def __post_init__(self):
        """Generate tool ID."""
        self.tool_id = hashlib.sha256(
            f"{self.category.value}:{self.name}".encode()
        ).hexdigest()[:16]


@dataclass
class ExecutionRequest:
    """
    Request to execute a tool.
    
    Contains all information needed to execute a tool
    through the dispatcher pipeline.
    """
    request_id: str
    tool_name: str
    context: SecurityContext
    parameters: Dict[str, Any]
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    
    # Options
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    allow_retry: bool = True
    max_retries: int = 3
    confirmation_token: Optional[str] = None
    
    # Callbacks
    on_progress: Optional[Callable[[str, float], None]] = None
    on_complete: Optional[Callable[[Any], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None
    
    @classmethod
    def create(
        cls,
        tool_name: str,
        context: SecurityContext,
        parameters: Dict[str, Any],
        **kwargs,
    ) -> "ExecutionRequest":
        """Factory method to create execution request."""
        return cls(
            request_id=str(uuid.uuid4()),
            tool_name=tool_name,
            context=context,
            parameters=parameters,
            **kwargs,
        )


@dataclass
class ExecutionResult:
    """
    Complete result of a tool execution.
    
    Includes the result data, execution metadata,
    and detailed stage information.
    """
    request_id: str
    tool_name: str
    success: bool
    
    # Result data
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: datetime = field(default_factory=datetime.utcnow)
    execution_time_ms: float = 0.0
    
    # Stage tracking
    stages_completed: List[ExecutionStage] = field(default_factory=list)
    current_stage: ExecutionStage = ExecutionStage.RECEIVED
    stage_times: Dict[str, float] = field(default_factory=dict)
    
    # Security
    security_decision: Optional[SecurityDecisionResult] = None
    sandbox_violations: List[str] = field(default_factory=list)
    
    # Validation
    input_validation_passed: bool = False
    output_validation_passed: bool = False
    validation_errors: List[str] = field(default_factory=list)
    
    # Retry info
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data if self.success else None,
            "error": self.error,
            "error_type": self.error_type,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat(),
            "execution_time_ms": self.execution_time_ms,
            "stages_completed": [s.name for s in self.stages_completed],
            "current_stage": self.current_stage.name,
            "input_validation_passed": self.input_validation_passed,
            "output_validation_passed": self.output_validation_passed,
            "retry_count": self.retry_count,
        }


class ExecutionSandbox:
    """
    Sandbox environment for tool execution.
    
    Provides isolation and resource limiting for
    tool execution to prevent abuse.
    """
    
    def __init__(self, tool_def: ToolDefinition):
        self.tool_def = tool_def
        self.violations: List[str] = []
        self._start_time: Optional[float] = None
        self._resource_usage: Dict[str, float] = {}
    
    async def __aenter__(self) -> "ExecutionSandbox":
        """Enter sandbox environment."""
        self._start_time = time.time()
        self.violations = []
        
        logger.debug(
            "Entering sandbox",
            tool=self.tool_def.name,
            allow_network=self.tool_def.allow_network,
            allow_filesystem=self.tool_def.allow_filesystem,
            timeout=self.tool_def.timeout_seconds,
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit sandbox, check for violations."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        
        # Check timeout violation
        if elapsed > self.tool_def.timeout_seconds:
            self.violations.append(
                f"Timeout exceeded: {elapsed:.2f}s > {self.tool_def.timeout_seconds}s"
            )
        
        if self.violations:
            logger.warning(
                "Sandbox violations detected",
                tool=self.tool_def.name,
                violations=self.violations,
            )
        
        return False  # Don't suppress exceptions
    
    def check_network_access(self, host: str, port: int) -> bool:
        """Check if network access is allowed."""
        if not self.tool_def.allow_network:
            self.violations.append(f"Network access denied: {host}:{port}")
            return False
        return True
    
    def check_filesystem_access(self, path: str, write: bool = False) -> bool:
        """Check if filesystem access is allowed."""
        if not self.tool_def.allow_filesystem:
            op = "write" if write else "read"
            self.violations.append(f"Filesystem {op} denied: {path}")
            return False
        return True
    
    def check_subprocess(self, command: str) -> bool:
        """Check if subprocess execution is allowed."""
        if not self.tool_def.allow_subprocess:
            self.violations.append(f"Subprocess denied: {command}")
            return False
        return True


class ConcurrencyManager:
    """
    Manages concurrent execution of tools.
    
    Enforces per-tool and global concurrency limits.
    """
    
    def __init__(self, max_global: int = 50):
        self.max_global = max_global
        self._tool_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._global_semaphore = asyncio.Semaphore(max_global)
        self._active_executions: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
    
    async def acquire(self, tool_def: ToolDefinition) -> bool:
        """Acquire execution slot for tool."""
        tool_name = tool_def.name
        
        async with self._lock:
            # Get or create tool semaphore
            if tool_name not in self._tool_semaphores:
                self._tool_semaphores[tool_name] = asyncio.Semaphore(
                    tool_def.max_concurrent
                )
        
        # Try to acquire global slot
        if not self._global_semaphore.locked():
            await self._global_semaphore.acquire()
        else:
            # Check if we can wait
            try:
                await asyncio.wait_for(
                    self._global_semaphore.acquire(),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Global concurrency limit reached")
                return False
        
        # Try to acquire tool slot
        tool_sem = self._tool_semaphores[tool_name]
        try:
            await asyncio.wait_for(tool_sem.acquire(), timeout=5.0)
            self._active_executions[tool_name] += 1
            return True
        except asyncio.TimeoutError:
            self._global_semaphore.release()
            logger.warning(
                "Tool concurrency limit reached",
                tool=tool_name,
                active=self._active_executions[tool_name],
            )
            return False
    
    async def release(self, tool_def: ToolDefinition) -> None:
        """Release execution slot for tool."""
        tool_name = tool_def.name
        
        if tool_name in self._tool_semaphores:
            self._tool_semaphores[tool_name].release()
            self._active_executions[tool_name] -= 1
        
        self._global_semaphore.release()
    
    def get_active_count(self, tool_name: Optional[str] = None) -> int:
        """Get count of active executions."""
        if tool_name:
            return self._active_executions.get(tool_name, 0)
        return sum(self._active_executions.values())


class ToolDispatcher:
    """
    Central Tool Dispatcher.
    
    ALL tool and plugin calls MUST route through this dispatcher.
    Implements the mandatory execution pipeline:
    
    1. RECEIVE - Accept execution request
    2. VALIDATE - Validate input parameters
    3. PERMISSION - Check permissions via firewall
    4. RATE_LIMIT - Enforce rate limits
    5. SANDBOX - Set up execution sandbox
    6. EXECUTE - Run the tool
    7. VALIDATE_OUTPUT - Validate result
    8. LOG - Audit log the execution
    9. RESPOND - Return result
    
    NO TOOL CAN BYPASS THIS PIPELINE.
    """
    
    _instance: Optional["ToolDispatcher"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "ToolDispatcher":
        """Singleton pattern for global dispatcher."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # Core components
        self.firewall = permission_firewall
        self.concurrency = ConcurrencyManager()
        
        # Tool registry
        self._tools: Dict[str, ToolDefinition] = {}
        self._tool_categories: Dict[ToolCategory, List[str]] = defaultdict(list)
        
        # Execution tracking
        self._pending_requests: Dict[str, ExecutionRequest] = {}
        self._execution_history: List[ExecutionResult] = []
        self._history_max_size = 1000
        
        # Rate limiting per user per tool
        self._rate_limits: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Confirmation tokens for destructive actions
        self._confirmation_tokens: Dict[str, Tuple[str, datetime]] = {}
        
        # Hooks for pipeline stages
        self._pre_execute_hooks: List[Callable] = []
        self._post_execute_hooks: List[Callable] = []
        
        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "permission_denied": 0,
            "rate_limited": 0,
            "validation_failed": 0,
            "sandbox_violations": 0,
            "timeouts": 0,
        }
        
        logger.info("Tool Dispatcher initialized")
    
    def register_tool(self, tool_def: ToolDefinition) -> None:
        """
        Register a tool with the dispatcher.
        
        All tools MUST be registered before they can be executed.
        """
        if tool_def.name in self._tools:
            logger.warning(f"Tool '{tool_def.name}' already registered, updating")
        
        self._tools[tool_def.name] = tool_def
        self._tool_categories[tool_def.category].append(tool_def.name)
        
        logger.info(
            "Tool registered",
            name=tool_def.name,
            category=tool_def.category.value,
            permissions=[p.value for p in tool_def.required_permissions],
        )
    
    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool from the dispatcher."""
        if tool_name not in self._tools:
            return False
        
        tool_def = self._tools.pop(tool_name)
        self._tool_categories[tool_def.category].remove(tool_name)
        
        logger.info("Tool unregistered", name=tool_name)
        return True
    
    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._tools.get(tool_name)
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        context: Optional[SecurityContext] = None,
    ) -> List[ToolDefinition]:
        """
        List available tools.
        
        If context provided, filters to only tools user has permission to execute.
        """
        if category:
            tool_names = self._tool_categories.get(category, [])
            tools = [self._tools[name] for name in tool_names]
        else:
            tools = list(self._tools.values())
        
        if context:
            # Filter to permitted tools
            permitted = []
            for tool in tools:
                if tool.required_permissions.issubset(context.permissions):
                    if tool.required_role is None or context.role == tool.required_role:
                        permitted.append(tool)
            return permitted
        
        return tools
    
    async def dispatch(
        self,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        """
        Execute a tool through the mandatory pipeline.
        
        This is the ONLY way to execute tools in the system.
        
        Pipeline stages:
        1. RECEIVE & VALIDATE
        2. PERMISSION CHECK
        3. RATE LIMIT CHECK
        4. CONCURRENCY CHECK
        5. SANDBOX SETUP
        6. EXECUTE
        7. OUTPUT VALIDATION
        8. AUDIT LOG
        9. RETURN RESULT
        """
        self._stats["total_requests"] += 1
        start_time = time.time()
        
        # Create result template
        result = ExecutionResult(
            request_id=request.request_id,
            tool_name=request.tool_name,
            success=False,
            started_at=datetime.utcnow(),
        )
        
        try:
            # ==========================================
            # STAGE 1: RECEIVE & VALIDATE
            # ==========================================
            result.current_stage = ExecutionStage.RECEIVED
            result.stages_completed.append(ExecutionStage.RECEIVED)
            
            # Get tool definition
            tool_def = self._tools.get(request.tool_name)
            if not tool_def:
                result.error = f"Unknown tool: {request.tool_name}"
                result.error_type = "ToolNotFoundError"
                result.current_stage = ExecutionStage.FAILED
                await self._log_execution(request, result)
                return result
            
            # Validate input
            if tool_def.input_validator:
                valid, reason = tool_def.input_validator(request.parameters)
                if not valid:
                    result.error = f"Input validation failed: {reason}"
                    result.error_type = "ValidationError"
                    result.current_stage = ExecutionStage.FAILED
                    self._stats["validation_failed"] += 1
                    await self._log_execution(request, result)
                    return result
            
            result.input_validation_passed = True
            result.stages_completed.append(ExecutionStage.VALIDATED)
            result.stage_times["validation"] = time.time() - start_time
            
            # ==========================================
            # STAGE 2: PERMISSION CHECK
            # ==========================================
            result.current_stage = ExecutionStage.PERMISSION_CHECKED
            
            # Update context with tool action
            request.context.action = f"tool_execute:{request.tool_name}"
            request.context.parameters = request.parameters
            
            # Check through firewall
            security_result = await self.firewall.evaluate(
                request.context,
                tool_def.required_permissions,
            )
            result.security_decision = security_result
            
            if not security_result.allowed:
                result.error = f"Permission denied: {security_result.reason}"
                result.error_type = "PermissionError"
                result.current_stage = ExecutionStage.FAILED
                self._stats["permission_denied"] += 1
                await self._log_execution(request, result)
                return result
            
            result.stages_completed.append(ExecutionStage.PERMISSION_CHECKED)
            result.stage_times["permission"] = time.time() - start_time
            
            # ==========================================
            # STAGE 3: RATE LIMIT CHECK
            # ==========================================
            result.current_stage = ExecutionStage.RATE_LIMITED
            
            if not self._check_rate_limit(request.context.user_id, tool_def):
                result.error = f"Rate limit exceeded for tool {request.tool_name}"
                result.error_type = "RateLimitError"
                result.current_stage = ExecutionStage.FAILED
                self._stats["rate_limited"] += 1
                await self._log_execution(request, result)
                return result
            
            result.stages_completed.append(ExecutionStage.RATE_LIMITED)
            result.stage_times["rate_limit"] = time.time() - start_time
            
            # ==========================================
            # STAGE 4: CONFIRMATION CHECK (if required)
            # ==========================================
            if tool_def.requires_confirmation:
                if not self._verify_confirmation(request):
                    result.error = "Confirmation required for this action"
                    result.error_type = "ConfirmationRequired"
                    result.data = {
                        "confirmation_token": self._generate_confirmation_token(request),
                        "message": f"Please confirm execution of {request.tool_name}",
                    }
                    result.current_stage = ExecutionStage.FAILED
                    await self._log_execution(request, result)
                    return result
            
            # ==========================================
            # STAGE 5: CONCURRENCY CHECK
            # ==========================================
            if not await self.concurrency.acquire(tool_def):
                result.error = f"Concurrency limit reached for {request.tool_name}"
                result.error_type = "ConcurrencyError"
                result.current_stage = ExecutionStage.FAILED
                await self._log_execution(request, result)
                return result
            
            try:
                # ==========================================
                # STAGE 6: SANDBOX SETUP & EXECUTE
                # ==========================================
                result.current_stage = ExecutionStage.SANDBOXED
                result.stages_completed.append(ExecutionStage.SANDBOXED)
                
                # Run pre-execute hooks
                for hook in self._pre_execute_hooks:
                    await hook(request, tool_def)
                
                result.current_stage = ExecutionStage.EXECUTING
                exec_start = time.time()
                
                # Execute in sandbox
                sandbox = ExecutionSandbox(tool_def)
                async with sandbox:
                    try:
                        # Execute with timeout
                        execution_result = await asyncio.wait_for(
                            self._execute_tool(tool_def, request),
                            timeout=tool_def.timeout_seconds,
                        )
                        result.data = execution_result
                        
                    except asyncio.TimeoutError:
                        result.error = f"Execution timeout after {tool_def.timeout_seconds}s"
                        result.error_type = "TimeoutError"
                        result.current_stage = ExecutionStage.FAILED
                        self._stats["timeouts"] += 1
                        await self._log_execution(request, result)
                        return result
                
                # Check sandbox violations
                if sandbox.violations:
                    result.sandbox_violations = sandbox.violations
                    result.error = f"Sandbox violations: {sandbox.violations}"
                    result.error_type = "SandboxViolation"
                    result.current_stage = ExecutionStage.FAILED
                    self._stats["sandbox_violations"] += 1
                    await self._log_execution(request, result)
                    return result
                
                result.stage_times["execution"] = time.time() - exec_start
                result.stages_completed.append(ExecutionStage.EXECUTING)
                
                # ==========================================
                # STAGE 7: OUTPUT VALIDATION
                # ==========================================
                result.current_stage = ExecutionStage.OUTPUT_VALIDATED
                
                if tool_def.output_validator:
                    valid, reason = tool_def.output_validator(result.data)
                    if not valid:
                        result.error = f"Output validation failed: {reason}"
                        result.error_type = "OutputValidationError"
                        result.validation_errors.append(reason)
                        result.current_stage = ExecutionStage.FAILED
                        self._stats["validation_failed"] += 1
                        await self._log_execution(request, result)
                        return result
                
                result.output_validation_passed = True
                result.stages_completed.append(ExecutionStage.OUTPUT_VALIDATED)
                
                # Run post-execute hooks
                for hook in self._post_execute_hooks:
                    await hook(request, tool_def, result)
                
                # ==========================================
                # STAGE 8: SUCCESS
                # ==========================================
                result.success = True
                result.current_stage = ExecutionStage.COMPLETED
                result.stages_completed.append(ExecutionStage.LOGGED)
                result.stages_completed.append(ExecutionStage.COMPLETED)
                self._stats["successful_executions"] += 1
                
            finally:
                # Always release concurrency slot
                await self.concurrency.release(tool_def)
            
        except Exception as e:
            result.success = False
            result.error = str(e)
            result.error_type = type(e).__name__
            result.error_traceback = traceback.format_exc()
            result.current_stage = ExecutionStage.FAILED
            self._stats["failed_executions"] += 1
            
            logger.error(
                "Tool execution failed",
                tool=request.tool_name,
                error=str(e),
                traceback=result.error_traceback,
            )
        
        finally:
            result.completed_at = datetime.utcnow()
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            # Log execution
            await self._log_execution(request, result)
            
            # Add to history
            self._add_to_history(result)
        
        return result
    
    async def _execute_tool(
        self,
        tool_def: ToolDefinition,
        request: ExecutionRequest,
    ) -> Any:
        """Execute the actual tool handler."""
        handler = tool_def.handler
        
        # Check if handler needs context
        sig = inspect.signature(handler)
        params = sig.parameters
        
        # Build kwargs
        kwargs = request.parameters.copy()
        
        # Inject context if handler accepts it
        if "context" in params or "security_context" in params:
            kwargs["context"] = request.context
        
        if "request" in params or "execution_request" in params:
            kwargs["request"] = request
        
        # Execute
        if asyncio.iscoroutinefunction(handler):
            return await handler(**kwargs)
        else:
            # Run sync handler in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: handler(**kwargs))
    
    def _check_rate_limit(self, user_id: str, tool_def: ToolDefinition) -> bool:
        """Check if user is within rate limit for tool."""
        tool_name = tool_def.name
        limit = tool_def.rate_limit_per_minute
        window = 60.0
        current_time = time.time()
        
        # Clean old entries
        self._rate_limits[user_id][tool_name] = [
            ts for ts in self._rate_limits[user_id][tool_name]
            if ts > current_time - window
        ]
        
        # Check limit
        if len(self._rate_limits[user_id][tool_name]) >= limit:
            return False
        
        # Record request
        self._rate_limits[user_id][tool_name].append(current_time)
        return True
    
    def _generate_confirmation_token(self, request: ExecutionRequest) -> str:
        """Generate confirmation token for destructive actions."""
        token = str(uuid.uuid4())
        expiry = datetime.utcnow() + timedelta(minutes=5)
        self._confirmation_tokens[token] = (request.request_id, expiry)
        return token
    
    def _verify_confirmation(self, request: ExecutionRequest) -> bool:
        """Verify confirmation token for request."""
        if not request.confirmation_token:
            return False
        
        token_data = self._confirmation_tokens.get(request.confirmation_token)
        if not token_data:
            return False
        
        request_id, expiry = token_data
        
        # Check expiry
        if datetime.utcnow() > expiry:
            del self._confirmation_tokens[request.confirmation_token]
            return False
        
        # Token valid, remove it (one-time use)
        del self._confirmation_tokens[request.confirmation_token]
        return True
    
    async def _log_execution(
        self,
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> None:
        """Log execution to audit log."""
        tool_def = self._tools.get(request.tool_name)
        
        # Sanitize parameters for logging
        log_params = copy.deepcopy(request.parameters)
        if tool_def and not tool_def.audit_inputs:
            log_params = {"redacted": True}
        else:
            # Redact sensitive fields
            sensitive_fields = {"password", "secret", "token", "key", "credential"}
            for key in list(log_params.keys()):
                if any(s in key.lower() for s in sensitive_fields):
                    log_params[key] = "[REDACTED]"
        
        # Sanitize output for logging
        log_output = None
        if tool_def and tool_def.audit_outputs and result.success:
            log_output = str(result.data)[:1000]  # Truncate large outputs
        
        try:
            audit_logger.log(
                action=f"tool_execution:{request.tool_name}",
                user_id=request.context.user_id,
                resource_type="tool",
                resource_id=request.tool_name,
                details={
                    "request_id": request.request_id,
                    "parameters": log_params,
                    "result_success": result.success,
                    "result_output": log_output,
                    "result_error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                    "stages_completed": [s.name for s in result.stages_completed],
                    "sandbox_violations": result.sandbox_violations,
                },
                status="success" if result.success else "failure",
                ip_address=request.context.ip_address,
                error_message=result.error,
            )
        except Exception as e:
            logger.error("Failed to log tool execution", error=str(e))
    
    def _add_to_history(self, result: ExecutionResult) -> None:
        """Add execution result to history."""
        self._execution_history.append(result)
        
        # Trim history if needed
        if len(self._execution_history) > self._history_max_size:
            self._execution_history = self._execution_history[-self._history_max_size:]
    
    def add_pre_execute_hook(self, hook: Callable) -> None:
        """Add hook to run before tool execution."""
        self._pre_execute_hooks.append(hook)
    
    def add_post_execute_hook(self, hook: Callable) -> None:
        """Add hook to run after tool execution."""
        self._post_execute_hooks.append(hook)
    
    def get_stats(self) -> Dict[str, int]:
        """Get dispatcher statistics."""
        return self._stats.copy()
    
    def get_execution_history(
        self,
        limit: int = 100,
        tool_name: Optional[str] = None,
        user_id: Optional[str] = None,
        success_only: bool = False,
    ) -> List[ExecutionResult]:
        """Get execution history with optional filters."""
        history = self._execution_history[-limit:]
        
        if tool_name:
            history = [r for r in history if r.tool_name == tool_name]
        
        if success_only:
            history = [r for r in history if r.success]
        
        return history


# Global dispatcher instance
tool_dispatcher = ToolDispatcher()


def register_tool(
    name: str,
    category: ToolCategory,
    description: str,
    permissions: Set[Permission],
    handler: Optional[Callable] = None,
    timeout: int = 30,
    rate_limit: int = 30,
    sandbox: bool = True,
    allow_network: bool = False,
    allow_filesystem: bool = False,
    requires_confirmation: bool = False,
    is_destructive: bool = False,
    input_validator: Optional[Callable] = None,
    output_validator: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to register a function as a tool.
    
    Usage:
        @register_tool(
            name="read_memory",
            category=ToolCategory.MEMORY,
            description="Read from AI memory",
            permissions={Permission.READ_MEMORY},
        )
        async def read_memory(key: str, context: SecurityContext) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_def = ToolDefinition(
            name=name,
            category=category,
            description=description,
            handler=func,
            required_permissions=permissions,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit,
            sandbox_enabled=sandbox,
            allow_network=allow_network,
            allow_filesystem=allow_filesystem,
            requires_confirmation=requires_confirmation,
            is_destructive=is_destructive,
            input_validator=input_validator,
            output_validator=output_validator,
        )
        
        tool_dispatcher.register_tool(tool_def)
        return func
    
    if handler is not None:
        # Called without decorator syntax
        return decorator(handler)
    
    return decorator


async def execute_tool(
    tool_name: str,
    context: SecurityContext,
    parameters: Dict[str, Any],
    **kwargs,
) -> ExecutionResult:
    """
    Convenience function to execute a tool.
    
    Creates an ExecutionRequest and dispatches through
    the mandatory pipeline.
    """
    request = ExecutionRequest.create(
        tool_name=tool_name,
        context=context,
        parameters=parameters,
        **kwargs,
    )
    
    return await tool_dispatcher.dispatch(request)


class ToolExecutionContext:
    """
    Context manager for tool execution.
    
    Usage:
        async with ToolExecutionContext("memory_read", context, {"key": "user_name"}) as result:
            if result.success:
                print(result.data)
    """
    
    def __init__(
        self,
        tool_name: str,
        context: SecurityContext,
        parameters: Dict[str, Any],
    ):
        self.tool_name = tool_name
        self.context = context
        self.parameters = parameters
        self.result: Optional[ExecutionResult] = None
    
    async def __aenter__(self) -> ExecutionResult:
        """Execute tool and return result."""
        self.result = await execute_tool(
            self.tool_name,
            self.context,
            self.parameters,
        )
        return self.result
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Clean up after execution."""
        return False
