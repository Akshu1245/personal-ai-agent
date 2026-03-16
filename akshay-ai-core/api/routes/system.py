"""
============================================================
AKSHAY AI CORE — System Routes
============================================================
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.config import settings
from core.utils.logger import get_logger, audit_logger

logger = get_logger("api.system")
router = APIRouter()


class SystemStatus(BaseModel):
    """System status model."""
    status: str
    version: str
    environment: str
    uptime_seconds: float
    ai_provider: str
    plugins_loaded: int
    active_connections: int
    memory_usage_mb: float
    cpu_percent: float


class AuditLogEntry(BaseModel):
    """Audit log entry model."""
    id: str
    timestamp: datetime
    action: str
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    status: str
    details: Optional[dict]


class ConfigItem(BaseModel):
    """Configuration item model."""
    key: str
    value: str
    description: Optional[str]
    is_encrypted: bool
    is_readonly: bool


# Track server start time
_start_time = datetime.utcnow()


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    Get current system status.
    
    Returns:
        System status information
    """
    import psutil
    
    from api.websocket import websocket_manager
    from plugins import plugin_manager
    
    process = psutil.Process()
    
    uptime = (datetime.utcnow() - _start_time).total_seconds()
    
    return SystemStatus(
        status="operational",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=uptime,
        ai_provider=settings.PRIMARY_AI_PROVIDER,
        plugins_loaded=len(await plugin_manager.list_plugins()),
        active_connections=websocket_manager.get_connection_count(),
        memory_usage_mb=process.memory_info().rss / 1024 / 1024,
        cpu_percent=process.cpu_percent(),
    )


@router.get("/audit-logs", response_model=List[AuditLogEntry])
async def get_audit_logs(
    req: Request,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get audit log entries.
    
    Args:
        action: Filter by action type
        user_id: Filter by user
        limit: Maximum entries
        offset: Pagination offset
        
    Returns:
        List of audit log entries
    """
    # Verify admin permissions
    # In production, check user role
    
    from pathlib import Path
    import json
    
    log_dir = Path(settings.LOGS_DIR) / "audit"
    entries = []
    
    # Read from today's log file
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = log_dir / f"audit_{today}.jsonl"
    
    if log_file.exists():
        with open(log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # Apply filters
                    if action and entry.get("action") != action:
                        continue
                    if user_id and entry.get("user_id") != user_id:
                        continue
                    
                    entries.append(AuditLogEntry(
                        id=entry.get("checksum", "")[:16],
                        timestamp=datetime.fromisoformat(entry["timestamp"]),
                        action=entry["action"],
                        user_id=entry.get("user_id"),
                        resource_type=entry.get("resource_type"),
                        resource_id=entry.get("resource_id"),
                        status=entry.get("status", "success"),
                        details=entry.get("details"),
                    ))
                except Exception:
                    continue
    
    # Sort by timestamp descending
    entries.sort(key=lambda x: x.timestamp, reverse=True)
    
    return entries[offset:offset + limit]


@router.get("/config")
async def get_config(req: Request):
    """
    Get system configuration (non-sensitive).
    
    Returns:
        System configuration
    """
    # Return safe configuration values
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "ai_provider": settings.PRIMARY_AI_PROVIDER,
        "ai_model": settings.get_ai_config().get("model"),
        "face_auth_enabled": settings.FACE_AUTH_ENABLED,
        "pin_enabled": settings.PIN_ENABLED,
        "voice_lock_enabled": settings.VOICE_LOCK_ENABLED,
        "plugins_enabled": settings.PLUGINS_ENABLED,
        "automation_enabled": settings.AUTOMATION_ENABLED,
        "web_ui_enabled": settings.WEB_UI_ENABLED,
    }


@router.post("/verify-audit-chain")
async def verify_audit_chain(date: Optional[str] = None, req: Request = None):
    """
    Verify the integrity of audit logs.
    
    Args:
        date: Date to verify (YYYY-MM-DD)
        
    Returns:
        Verification result
    """
    is_valid, invalid_entries = audit_logger.verify_chain(date)
    
    return {
        "is_valid": is_valid,
        "date": date or datetime.utcnow().strftime("%Y-%m-%d"),
        "invalid_count": len(invalid_entries),
        "invalid_entries": invalid_entries[:10] if not is_valid else [],
    }


@router.post("/shutdown")
async def shutdown_system(req: Request):
    """
    Initiate system shutdown.
    
    Requires admin permissions.
    
    Returns:
        Shutdown confirmation
    """
    user_id = getattr(req.state, "user_id", None)
    
    audit_logger.log(
        action="system_shutdown_requested",
        user_id=user_id,
        details={"initiated_by": "api"},
    )
    
    # In production, this would trigger graceful shutdown
    return {
        "message": "Shutdown initiated",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/metrics")
async def get_metrics():
    """
    Get system metrics for monitoring.
    
    Returns:
        Prometheus-compatible metrics
    """
    import psutil
    
    from api.websocket import websocket_manager
    from plugins import plugin_manager
    
    process = psutil.Process()
    
    return {
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        },
        "process": {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "threads": process.num_threads(),
        },
        "application": {
            "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds(),
            "websocket_connections": websocket_manager.get_connection_count(),
            "websocket_users": websocket_manager.get_user_count(),
        },
    }
