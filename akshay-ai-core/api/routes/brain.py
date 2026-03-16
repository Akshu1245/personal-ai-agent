"""
============================================================
AKSHAY AI CORE — AI Brain Routes
============================================================
SECURITY: All routes are protected by Permission Firewall.
============================================================
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from core.config import settings
from core.utils.logger import get_logger
from core.security.permissions import Permission, Role
from core.security.firewall import (
    permission_firewall,
    create_security_context,
    SecurityContext,
)

logger = get_logger("api.brain")
router = APIRouter()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_security_context(request: Request) -> SecurityContext:
    """Extract security context from request."""
    user_id = getattr(request.state, "user_id", "anonymous")
    role_str = getattr(request.state, "role", "guest")
    session_id = getattr(request.state, "session_id", None)
    request_id = getattr(request.state, "request_id", None)
    
    # Convert role string to Role enum
    try:
        role = Role(role_str) if isinstance(role_str, str) else role_str
    except ValueError:
        role = Role.GUEST
    
    # Get client IP
    ip_address = None
    if hasattr(request, "client") and request.client:
        ip_address = request.client.host
    
    return create_security_context(
        user_id=user_id,
        role=role,
        session_id=session_id,
        ip_address=ip_address,
        request_id=request_id,
    )


async def check_permission(
    context: SecurityContext,
    action: str,
    required_permissions: set,
    resource_type: str = "",
    resource_id: str = None,
) -> None:
    """Check permission through firewall, raise HTTPException if denied."""
    context.action = action
    context.resource_type = resource_type
    context.resource_id = resource_id
    
    result = await permission_firewall.evaluate(context, required_permissions)
    
    if not result.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Permission denied",
                "reason": result.reason,
                "decision": result.decision.name,
                "missing_permissions": [p.value for p in result.missing_permissions],
            }
        )


# =============================================================================
# MODELS
# =============================================================================

class QueryRequest(BaseModel):
    """AI query request model."""
    message: str
    context: Optional[dict] = None
    stream: bool = False
    model: Optional[str] = None
    truth_check: bool = False


class QueryResponse(BaseModel):
    """AI query response model."""
    response: str
    model: str
    tokens_used: int
    processing_time_ms: float
    truth_check_result: Optional[dict] = None


class MemoryEntry(BaseModel):
    """Memory entry model."""
    id: str
    content: str
    memory_type: str
    importance: float
    created_at: datetime
    tags: List[str]


class MemoryCreateRequest(BaseModel):
    """Create memory request."""
    content: str
    memory_type: str = "semantic"
    importance: float = 0.5
    tags: List[str] = []


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/query", response_model=QueryResponse)
async def query_ai(request: QueryRequest, req: Request):
    """
    Send a query to the AI brain.
    
    PERMISSION REQUIRED: QUERY_AI
    
    Args:
        request: Query parameters
        
    Returns:
        AI response with metadata
    """
    # Get security context
    context = await get_security_context(req)
    
    # Determine required permissions
    required_perms = {Permission.AI_QUERY}
    if request.model and request.model in ["gpt-4", "claude-3-opus", "gemini-ultra"]:
        required_perms.add(Permission.AI_CONFIG)
    
    # Check permission through firewall
    await check_permission(
        context=context,
        action="query",
        required_permissions=required_perms,
        resource_type="ai_model",
        resource_id=request.model or settings.PRIMARY_AI_PROVIDER,
    )
    
    # Import brain engine
    from core.brain import brain_engine
    
    start_time = datetime.utcnow()
    
    try:
        response = await brain_engine.query(
            user_id=context.user_id,
            message=request.message,
            context=request.context,
            model=request.model,
        )
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = QueryResponse(
            response=response["content"],
            model=response["model"],
            tokens_used=response.get("tokens", 0),
            processing_time_ms=processing_time,
        )
        
        # Run truth check if requested
        if request.truth_check:
            truth_result = await brain_engine.truth_check(response["content"])
            result.truth_check_result = truth_result
        
        return result
        
    except Exception as e:
        logger.error("Query failed", error=str(e), user_id=context.user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory", response_model=List[MemoryEntry])
async def get_memories(
    req: Request,
    memory_type: Optional[str] = None,
    limit: int = 50,
    search: Optional[str] = None,
):
    """
    Retrieve memories from long-term storage.
    
    PERMISSION REQUIRED: READ_MEMORY
    Additional: ACCESS_LONG_TERM_MEMORY for long_term type
    
    Args:
        memory_type: Filter by type (semantic, event, conversation)
        limit: Maximum entries to return
        search: Semantic search query
        
    Returns:
        List of memory entries
    """
    # Get security context
    context = await get_security_context(req)
    
    # Determine required permissions
    required_perms = {Permission.AI_MEMORY_READ}
    if memory_type == "long_term":
        required_perms.add(Permission.AI_SECURE_MEMORY)
    
    # Check permission through firewall
    await check_permission(
        context=context,
        action="memory_read",
        required_permissions=required_perms,
        resource_type="memory",
    )
    
    from core.brain.memory import memory_system
    
    memories = await memory_system.get_memories(
        user_id=context.user_id,
        memory_type=memory_type,
        limit=limit,
        search_query=search,
    )
    
    return [
        MemoryEntry(
            id=m["id"],
            content=m["content"],
            memory_type=m["memory_type"],
            importance=m["importance"],
            created_at=m["created_at"],
            tags=m.get("tags", []),
        )
        for m in memories
    ]


@router.post("/memory", response_model=MemoryEntry)
async def create_memory(request: MemoryCreateRequest, req: Request):
    """
    Store a new memory.
    
    PERMISSION REQUIRED: WRITE_MEMORY
    
    Args:
        request: Memory content and metadata
        
    Returns:
        Created memory entry
    """
    # Get security context
    context = await get_security_context(req)
    
    # Check permission through firewall
    await check_permission(
        context=context,
        action="memory_write",
        required_permissions={Permission.AI_MEMORY_WRITE},
        resource_type="memory",
    )
    
    from core.brain.memory import memory_system
    
    memory = await memory_system.store_memory(
        user_id=context.user_id,
        content=request.content,
        memory_type=request.memory_type,
        importance=request.importance,
        tags=request.tags,
    )
    
    return MemoryEntry(
        id=memory["id"],
        content=memory["content"],
        memory_type=memory["memory_type"],
        importance=memory["importance"],
        created_at=memory["created_at"],
        tags=memory.get("tags", []),
    )


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str, req: Request):
    """
    Delete a memory entry.
    
    PERMISSION REQUIRED: DELETE_MEMORY
    
    Args:
        memory_id: ID of memory to delete
        
    Returns:
        Deletion confirmation
    """
    # Get security context
    context = await get_security_context(req)
    
    # Check permission through firewall
    await check_permission(
        context=context,
        action="memory_delete",
        required_permissions={Permission.AI_MEMORY_DELETE},
        resource_type="memory",
        resource_id=memory_id,
    )
    
    from core.brain.memory import memory_system
    
    success = await memory_system.delete_memory(context.user_id, memory_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {"message": "Memory deleted", "id": memory_id}


@router.get("/models")
async def get_available_models(req: Request):
    """
    Get list of available AI models.
    
    PERMISSION REQUIRED: QUERY_AI
    
    Returns:
        Available models and their status
    """
    # Get security context
    context = await get_security_context(req)
    
    # Check permission through firewall
    await check_permission(
        context=context,
        action="list_models",
        required_permissions={Permission.AI_QUERY},
        resource_type="ai_model",
    )
    
    from core.brain.llm_connector import llm_connector
    
    models = await llm_connector.get_available_models()
    
    return {
        "primary": settings.PRIMARY_AI_PROVIDER,
        "models": models,
    }


@router.post("/compress-memory")
async def trigger_memory_compression(req: Request):
    """
    Manually trigger memory compression.
    
    PERMISSION REQUIRED: ADMIN_SETTINGS (admin-only operation)
    
    Creates weekly summaries and archives old memories.
    
    Returns:
        Compression results
    """
    # Get security context
    context = await get_security_context(req)
    
    # Check permission - this is an admin operation
    await check_permission(
        context=context,
        action="memory_compress",
        required_permissions={Permission.SYSTEM_ADMIN},
        resource_type="memory",
    )
    
    from core.brain.memory import memory_system
    
    result = await memory_system.compress_memories(context.user_id)
    
    return {
        "compressed": result["compressed_count"],
        "archived": result["archived_count"],
        "summary_created": result["summary_id"],
    }
