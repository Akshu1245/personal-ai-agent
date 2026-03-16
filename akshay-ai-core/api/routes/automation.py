"""
============================================================
AKSHAY AI CORE — Automation Routes
============================================================
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger("api.automation")
router = APIRouter()


class TriggerConfig(BaseModel):
    """Automation trigger configuration."""
    type: str  # schedule, event, keyword, system
    cron: Optional[str] = None  # For schedule type
    event: Optional[str] = None  # For event type
    keyword: Optional[str] = None  # For keyword type
    system_event: Optional[str] = None  # For system type


class ActionConfig(BaseModel):
    """Automation action configuration."""
    plugin: str
    command: str
    params: Optional[dict] = None


class AutomationRule(BaseModel):
    """Automation rule model."""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    trigger: TriggerConfig
    conditions: Optional[List[dict]] = None
    actions: List[ActionConfig]
    is_enabled: bool = True
    priority: int = 5


class AutomationRuleResponse(BaseModel):
    """Automation rule response."""
    id: str
    name: str
    description: Optional[str]
    trigger_type: str
    is_enabled: bool
    priority: int
    trigger_count: int
    success_count: int
    failure_count: int
    last_triggered: Optional[datetime]
    created_at: datetime


class JobStatus(BaseModel):
    """Job status model."""
    id: str
    rule_id: str
    rule_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    error: Optional[str]


@router.get("/rules", response_model=List[AutomationRuleResponse])
async def list_rules(enabled_only: bool = False):
    """
    List all automation rules.
    
    Args:
        enabled_only: Only return enabled rules
        
    Returns:
        List of automation rules
    """
    from automation.scheduler import scheduler
    
    rules = await scheduler.list_rules()
    
    if enabled_only:
        rules = [r for r in rules if r["is_enabled"]]
    
    return [
        AutomationRuleResponse(
            id=r["id"],
            name=r["name"],
            description=r.get("description"),
            trigger_type=r["trigger_type"],
            is_enabled=r["is_enabled"],
            priority=r["priority"],
            trigger_count=r.get("trigger_count", 0),
            success_count=r.get("success_count", 0),
            failure_count=r.get("failure_count", 0),
            last_triggered=r.get("last_triggered"),
            created_at=r["created_at"],
        )
        for r in rules
    ]


@router.post("/rules", response_model=AutomationRuleResponse)
async def create_rule(rule: AutomationRule, req: Request):
    """
    Create a new automation rule.
    
    Args:
        rule: Rule configuration
        
    Returns:
        Created rule
    """
    from automation.scheduler import scheduler
    
    created = await scheduler.create_rule(
        name=rule.name,
        description=rule.description,
        trigger=rule.trigger.model_dump(),
        conditions=rule.conditions,
        actions=[a.model_dump() for a in rule.actions],
        is_enabled=rule.is_enabled,
        priority=rule.priority,
    )
    
    return AutomationRuleResponse(
        id=created["id"],
        name=created["name"],
        description=created.get("description"),
        trigger_type=created["trigger_type"],
        is_enabled=created["is_enabled"],
        priority=created["priority"],
        trigger_count=0,
        success_count=0,
        failure_count=0,
        last_triggered=None,
        created_at=created["created_at"],
    )


@router.get("/rules/{rule_id}", response_model=AutomationRuleResponse)
async def get_rule(rule_id: str):
    """
    Get a specific automation rule.
    
    Args:
        rule_id: Rule identifier
        
    Returns:
        Rule details
    """
    from automation.scheduler import scheduler
    
    rule = await scheduler.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return AutomationRuleResponse(
        id=rule["id"],
        name=rule["name"],
        description=rule.get("description"),
        trigger_type=rule["trigger_type"],
        is_enabled=rule["is_enabled"],
        priority=rule["priority"],
        trigger_count=rule.get("trigger_count", 0),
        success_count=rule.get("success_count", 0),
        failure_count=rule.get("failure_count", 0),
        last_triggered=rule.get("last_triggered"),
        created_at=rule["created_at"],
    )


@router.put("/rules/{rule_id}", response_model=AutomationRuleResponse)
async def update_rule(rule_id: str, rule: AutomationRule, req: Request):
    """
    Update an automation rule.
    
    Args:
        rule_id: Rule to update
        rule: New configuration
        
    Returns:
        Updated rule
    """
    from automation.scheduler import scheduler
    
    updated = await scheduler.update_rule(
        rule_id=rule_id,
        name=rule.name,
        description=rule.description,
        trigger=rule.trigger.model_dump(),
        conditions=rule.conditions,
        actions=[a.model_dump() for a in rule.actions],
        is_enabled=rule.is_enabled,
        priority=rule.priority,
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return AutomationRuleResponse(
        id=updated["id"],
        name=updated["name"],
        description=updated.get("description"),
        trigger_type=updated["trigger_type"],
        is_enabled=updated["is_enabled"],
        priority=updated["priority"],
        trigger_count=updated.get("trigger_count", 0),
        success_count=updated.get("success_count", 0),
        failure_count=updated.get("failure_count", 0),
        last_triggered=updated.get("last_triggered"),
        created_at=updated["created_at"],
    )


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, req: Request):
    """
    Delete an automation rule.
    
    Args:
        rule_id: Rule to delete
        
    Returns:
        Deletion confirmation
    """
    from automation.scheduler import scheduler
    
    success = await scheduler.delete_rule(rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": "Rule deleted", "id": rule_id}


@router.post("/rules/{rule_id}/trigger")
async def trigger_rule(rule_id: str, req: Request):
    """
    Manually trigger an automation rule.
    
    Args:
        rule_id: Rule to trigger
        
    Returns:
        Execution result
    """
    from automation.scheduler import scheduler
    
    result = await scheduler.trigger_rule(rule_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return result


@router.post("/rules/{rule_id}/enable")
async def enable_rule(rule_id: str, req: Request):
    """Enable an automation rule."""
    from automation.scheduler import scheduler
    
    success = await scheduler.enable_rule(rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": f"Rule {rule_id} enabled"}


@router.post("/rules/{rule_id}/disable")
async def disable_rule(rule_id: str, req: Request):
    """Disable an automation rule."""
    from automation.scheduler import scheduler
    
    success = await scheduler.disable_rule(rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": f"Rule {rule_id} disabled"}


@router.get("/jobs", response_model=List[JobStatus])
async def list_jobs(
    limit: int = 50,
    status: Optional[str] = None,
):
    """
    List recent automation jobs.
    
    Args:
        limit: Maximum jobs to return
        status: Filter by status
        
    Returns:
        List of job statuses
    """
    from automation.scheduler import scheduler
    
    jobs = await scheduler.list_jobs(limit=limit, status=status)
    
    return [
        JobStatus(
            id=j["id"],
            rule_id=j["rule_id"],
            rule_name=j["rule_name"],
            status=j["status"],
            started_at=j["started_at"],
            completed_at=j.get("completed_at"),
            duration_ms=j.get("duration_ms"),
            error=j.get("error"),
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    """
    Get details of a specific job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job details
    """
    from automation.scheduler import scheduler
    
    job = await scheduler.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(
        id=job["id"],
        rule_id=job["rule_id"],
        rule_name=job["rule_name"],
        status=job["status"],
        started_at=job["started_at"],
        completed_at=job.get("completed_at"),
        duration_ms=job.get("duration_ms"),
        error=job.get("error"),
    )
