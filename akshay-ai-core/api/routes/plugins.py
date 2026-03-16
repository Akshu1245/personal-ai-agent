"""
============================================================
AKSHAY AI CORE — Plugin Routes
============================================================
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger("api.plugins")
router = APIRouter()


class PluginInfo(BaseModel):
    """Plugin information model."""
    id: str
    name: str
    version: str
    description: Optional[str]
    author: Optional[str]
    is_enabled: bool
    is_builtin: bool
    permissions: List[str]
    execution_count: int
    last_executed: Optional[datetime]


class PluginExecuteRequest(BaseModel):
    """Plugin execution request."""
    command: str
    params: Optional[dict] = None
    timeout: int = 300


class PluginExecuteResponse(BaseModel):
    """Plugin execution response."""
    plugin_id: str
    status: str
    result: Optional[dict]
    error: Optional[str]
    execution_time_ms: float


@router.get("/", response_model=List[PluginInfo])
async def list_plugins(
    enabled_only: bool = False,
    builtin_only: bool = False,
):
    """
    List all installed plugins.
    
    Args:
        enabled_only: Only return enabled plugins
        builtin_only: Only return built-in plugins
        
    Returns:
        List of plugin information
    """
    from plugins import plugin_manager
    
    plugins = await plugin_manager.list_plugins()
    
    if enabled_only:
        plugins = [p for p in plugins if p["is_enabled"]]
    if builtin_only:
        plugins = [p for p in plugins if p["is_builtin"]]
    
    return [
        PluginInfo(
            id=p["id"],
            name=p["name"],
            version=p["version"],
            description=p.get("description"),
            author=p.get("author"),
            is_enabled=p["is_enabled"],
            is_builtin=p["is_builtin"],
            permissions=p.get("permissions", []),
            execution_count=p.get("execution_count", 0),
            last_executed=p.get("last_executed"),
        )
        for p in plugins
    ]


@router.get("/{plugin_id}", response_model=PluginInfo)
async def get_plugin(plugin_id: str):
    """
    Get details of a specific plugin.
    
    Args:
        plugin_id: Plugin identifier
        
    Returns:
        Plugin information
    """
    from plugins import plugin_manager
    
    plugin = await plugin_manager.get_plugin(plugin_id)
    
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    return PluginInfo(
        id=plugin["id"],
        name=plugin["name"],
        version=plugin["version"],
        description=plugin.get("description"),
        author=plugin.get("author"),
        is_enabled=plugin["is_enabled"],
        is_builtin=plugin["is_builtin"],
        permissions=plugin.get("permissions", []),
        execution_count=plugin.get("execution_count", 0),
        last_executed=plugin.get("last_executed"),
    )


@router.post("/{plugin_id}/execute", response_model=PluginExecuteResponse)
async def execute_plugin(
    plugin_id: str,
    request: PluginExecuteRequest,
    req: Request,
):
    """
    Execute a plugin command.
    
    Args:
        plugin_id: Plugin to execute
        request: Execution parameters
        
    Returns:
        Execution result
    """
    user_id = getattr(req.state, "user_id", "anonymous")
    
    from plugins import plugin_manager
    
    start_time = datetime.utcnow()
    
    try:
        result = await plugin_manager.execute_plugin(
            plugin_id=plugin_id,
            command=request.command,
            params=request.params or {},
            user_id=user_id,
            timeout=request.timeout,
        )
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return PluginExecuteResponse(
            plugin_id=plugin_id,
            status="success",
            result=result,
            error=None,
            execution_time_ms=execution_time,
        )
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            "Plugin execution failed",
            plugin_id=plugin_id,
            error=str(e),
            user_id=user_id,
        )
        
        return PluginExecuteResponse(
            plugin_id=plugin_id,
            status="error",
            result=None,
            error=str(e),
            execution_time_ms=execution_time,
        )


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str, req: Request):
    """
    Enable a plugin.
    
    Args:
        plugin_id: Plugin to enable
        
    Returns:
        Status message
    """
    from plugins import plugin_manager
    
    success = await plugin_manager.enable_plugin(plugin_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    return {"message": f"Plugin {plugin_id} enabled"}


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str, req: Request):
    """
    Disable a plugin.
    
    Args:
        plugin_id: Plugin to disable
        
    Returns:
        Status message
    """
    from plugins import plugin_manager
    
    success = await plugin_manager.disable_plugin(plugin_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    return {"message": f"Plugin {plugin_id} disabled"}


@router.get("/{plugin_id}/config")
async def get_plugin_config(plugin_id: str):
    """
    Get plugin configuration.
    
    Args:
        plugin_id: Plugin identifier
        
    Returns:
        Plugin configuration
    """
    from plugins import plugin_manager
    
    config = await plugin_manager.get_plugin_config(plugin_id)
    
    if config is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    return config


@router.put("/{plugin_id}/config")
async def update_plugin_config(plugin_id: str, config: dict, req: Request):
    """
    Update plugin configuration.
    
    Args:
        plugin_id: Plugin identifier
        config: New configuration
        
    Returns:
        Updated configuration
    """
    from plugins import plugin_manager
    
    success = await plugin_manager.update_plugin_config(plugin_id, config)
    
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    return {"message": "Configuration updated", "config": config}
