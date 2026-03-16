"""
============================================================
AKSHAY AI CORE — Automation Scheduler
============================================================
Task scheduling, triggers, and background job execution.

SECURITY: All automation execution flows through the
Automation Safety Layer for rate limits, quotas, approval
workflows, and kill switch support.
============================================================
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.automation_safety import (
    automation_safety,
    AutomationState,
    SafeAutomationRule,
    AutomationQuota,
    RuleCategory,
)
from core.security.firewall import create_security_context
from core.security.permissions import Role

logger = get_logger("automation")


class AutomationScheduler:
    """
    Automation scheduler for background tasks.
    
    Features:
    - Cron-based scheduling
    - Event-based triggers
    - Keyword triggers
    - System event triggers
    - Job queuing and execution
    
    SECURITY: All executions route through AutomationSafetyLayer for:
    - Rate limiting
    - Quota enforcement
    - Approval workflows
    - Kill switch support
    - Dry-run mode
    """
    
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._rules: Dict[str, Dict] = {}
        self._jobs: Dict[str, Dict] = {}
        self._job_history: List[Dict] = []
        self._running = False
        self._max_history = 1000
        
        # Register kill switch callback
        automation_safety.register_kill_switch_callback(self._on_kill_switch)
    
    async def start(self) -> None:
        """Start the automation scheduler."""
        if self._running:
            return
        
        # Check if automation is allowed
        state = automation_safety.get_state()
        if state == AutomationState.EMERGENCY_STOP:
            logger.warning("Cannot start scheduler - kill switch active")
            return
        
        self._scheduler.start()
        self._running = True
        
        # Load rules from database/config
        await self._load_rules()
        
        logger.info("Automation scheduler started")
        audit_logger.log(action="automation_started")
    
    async def stop(self) -> None:
        """Stop the automation scheduler."""
        if not self._running:
            return
        
        self._scheduler.shutdown(wait=True)
        self._running = False
        
        logger.info("Automation scheduler stopped")
        audit_logger.log(action="automation_stopped")
    
    def _on_kill_switch(self, reason: str) -> None:
        """Handle kill switch activation."""
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        
        # Pause all jobs immediately
        if self._scheduler.running:
            self._scheduler.pause()
        
        # Note: Don't fully stop - allow recovery when kill switch deactivated
    
    async def _load_rules(self) -> None:
        """Load automation rules from storage."""
        # In production, load from database
        # For now, load from config file if exists
        import yaml
        from pathlib import Path
        
        rules_file = Path(settings.AUTOMATION_RULES_FILE)
        
        if rules_file.exists():
            try:
                with open(rules_file) as f:
                    rules_data = yaml.safe_load(f)
                
                for rule_data in rules_data.get("rules", []):
                    await self.create_rule(**rule_data)
                    
            except Exception as e:
                logger.error("Failed to load automation rules", error=str(e))
    
    async def create_rule(
        self,
        name: str,
        trigger: Dict[str, Any],
        actions: List[Dict[str, Any]],
        description: Optional[str] = None,
        conditions: Optional[List[Dict]] = None,
        is_enabled: bool = True,
        priority: int = 5,
        category: str = "system",
        requires_approval: bool = False,
        quota: Optional[Dict[str, Any]] = None,
        owner_id: str = "system",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new automation rule.
        
        Args:
            name: Rule name
            trigger: Trigger configuration
            actions: List of actions to execute
            description: Rule description
            conditions: Optional conditions to check
            is_enabled: Whether rule is active
            priority: Execution priority (1-10)
            category: Rule category (data, system, network, iot, notification, integration, maintenance)
            requires_approval: Whether rule requires approval before execution
            quota: Custom quota settings
            owner_id: Rule owner
            
        Returns:
            Created rule dictionary
        """
        rule_id = str(uuid4())[:8]
        
        rule = {
            "id": rule_id,
            "name": name,
            "description": description,
            "trigger_type": trigger.get("type"),
            "trigger_config": trigger,
            "conditions": conditions or [],
            "actions": actions,
            "is_enabled": is_enabled,
            "priority": priority,
            "category": category,
            "requires_approval": requires_approval,
            "owner_id": owner_id,
            "trigger_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_triggered": None,
            "last_error": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        self._rules[rule_id] = rule
        
        # Register with Safety Layer
        try:
            rule_category = RuleCategory[category.upper()] if category else RuleCategory.SYSTEM
        except KeyError:
            rule_category = RuleCategory.SYSTEM
        
        safe_rule = SafeAutomationRule(
            id=rule_id,
            name=name,
            description=description or "",
            owner_id=owner_id,
            category=rule_category,
            quota=AutomationQuota(**(quota or {})),
            requires_approval=requires_approval,
            enabled=is_enabled,
        )
        automation_safety.register_rule(safe_rule)
        
        # Schedule if enabled
        if is_enabled:
            await self._schedule_rule(rule)
        
        audit_logger.log(
            action="automation_rule_created",
            resource_type="automation_rule",
            resource_id=rule_id,
            details={"name": name, "trigger_type": trigger.get("type")},
        )
        
        return rule
    
    async def _schedule_rule(self, rule: Dict[str, Any]) -> None:
        """Schedule a rule based on its trigger type."""
        trigger_type = rule["trigger_config"].get("type")
        trigger_config = rule["trigger_config"]
        
        job_id = f"rule_{rule['id']}"
        
        # Remove existing job if any
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
        
        if trigger_type == "schedule":
            # Cron-based trigger
            cron_expr = trigger_config.get("cron")
            if cron_expr:
                trigger = CronTrigger.from_crontab(cron_expr)
                self._scheduler.add_job(
                    self._execute_rule,
                    trigger=trigger,
                    id=job_id,
                    args=[rule["id"]],
                    name=rule["name"],
                )
        
        elif trigger_type == "interval":
            # Interval-based trigger
            seconds = trigger_config.get("seconds", 0)
            minutes = trigger_config.get("minutes", 0)
            hours = trigger_config.get("hours", 0)
            
            trigger = IntervalTrigger(
                seconds=seconds,
                minutes=minutes,
                hours=hours,
            )
            self._scheduler.add_job(
                self._execute_rule,
                trigger=trigger,
                id=job_id,
                args=[rule["id"]],
                name=rule["name"],
            )
        
        elif trigger_type == "once":
            # One-time trigger
            run_at = trigger_config.get("run_at")
            if run_at:
                if isinstance(run_at, str):
                    run_at = datetime.fromisoformat(run_at)
                
                trigger = DateTrigger(run_date=run_at)
                self._scheduler.add_job(
                    self._execute_rule,
                    trigger=trigger,
                    id=job_id,
                    args=[rule["id"]],
                    name=rule["name"],
                )
        
        # Event and keyword triggers are handled separately
    
    async def _execute_rule(self, rule_id: str, user_id: str = "automation") -> Dict[str, Any]:
        """
        Execute an automation rule through the Safety Layer.
        
        All execution flows through AutomationSafetyLayer for:
        - Rate limit checking
        - Quota enforcement  
        - Approval workflow
        - Kill switch checking
        """
        rule = self._rules.get(rule_id)
        if not rule:
            return {"status": "error", "error": "Rule not found"}
        
        if not rule["is_enabled"]:
            return {"status": "skipped", "reason": "Rule disabled"}
        
        # Create security context for automation execution
        context = create_security_context(
            user_id=user_id,
            role=Role.AUTOMATION,
            action=f"automation_execute:{rule_id}",
            resource_type="automation_rule",
            resource_id=rule_id,
        )
        
        # Define the actual executor
        async def execute_actions(r_id: str, params: Optional[Dict]) -> Dict[str, Any]:
            """Execute the rule actions."""
            job_id = str(uuid4())[:8]
            job = {
                "id": job_id,
                "rule_id": r_id,
                "rule_name": rule["name"],
                "status": "running",
                "started_at": datetime.utcnow(),
                "completed_at": None,
                "duration_ms": None,
                "error": None,
            }
            
            self._jobs[job_id] = job
            
            try:
                # Check conditions
                if rule["conditions"]:
                    conditions_met = await self._check_conditions(rule["conditions"])
                    if not conditions_met:
                        job["status"] = "skipped"
                        job["completed_at"] = datetime.utcnow()
                        return {"status": "skipped", "reason": "Conditions not met"}
                
                # Execute actions
                results = []
                for action in rule["actions"]:
                    result = await self._execute_action(action)
                    results.append(result)
                    
                    # Stop on failure
                    if result.get("status") == "error":
                        raise Exception(result.get("error", "Action failed"))
                
                # Update stats
                rule["trigger_count"] += 1
                rule["success_count"] += 1
                rule["last_triggered"] = datetime.utcnow()
                
                job["status"] = "success"
                job["completed_at"] = datetime.utcnow()
                job["duration_ms"] = int(
                    (job["completed_at"] - job["started_at"]).total_seconds() * 1000
                )
                
                return {"status": "success", "results": results}
                
            except Exception as e:
                rule["trigger_count"] += 1
                rule["failure_count"] += 1
                rule["last_error"] = str(e)
                
                job["status"] = "failure"
                job["error"] = str(e)
                job["completed_at"] = datetime.utcnow()
                job["duration_ms"] = int(
                    (job["completed_at"] - job["started_at"]).total_seconds() * 1000
                )
                
                raise
            
            finally:
                # Add to history
                self._job_history.append(job)
                if len(self._job_history) > self._max_history:
                    self._job_history = self._job_history[-self._max_history:]
        
        # Execute through safety layer
        try:
            record = await automation_safety.execute_rule(
                rule_id=rule_id,
                context=context,
                params=None,
                executor=execute_actions,
            )
            
            if record.success:
                return {"status": "success", "execution_id": record.id, "output": record.output}
            else:
                return {"status": "error", "error": record.error, "execution_id": record.id}
                
        except Exception as e:
            logger.error(f"Automation rule execution failed", rule_id=rule_id, error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _check_conditions(self, conditions: List[Dict]) -> bool:
        """Check if conditions are met."""
        # Implement condition checking logic
        for condition in conditions:
            condition_type = condition.get("type")
            
            if condition_type == "time_range":
                # Check if current time is within range
                start = condition.get("start")
                end = condition.get("end")
                now = datetime.utcnow().time()
                
                if start and end:
                    start_time = datetime.strptime(start, "%H:%M").time()
                    end_time = datetime.strptime(end, "%H:%M").time()
                    
                    if not (start_time <= now <= end_time):
                        return False
            
            # Add more condition types as needed
        
        return True
    
    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action."""
        from plugins import plugin_manager
        
        plugin_id = action.get("plugin")
        command = action.get("command")
        params = action.get("params", {})
        
        if not plugin_id or not command:
            return {"status": "error", "error": "Invalid action configuration"}
        
        try:
            result = await plugin_manager.execute_plugin(
                plugin_id=plugin_id,
                command=command,
                params=params,
                user_id="automation",
                timeout=settings.AUTOMATION_JOB_TIMEOUT_SECONDS,
            )
            return result
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def trigger_rule(self, rule_id: str, user_id: str = "manual") -> Optional[Dict[str, Any]]:
        """Manually trigger a rule."""
        if rule_id not in self._rules:
            return None
        
        return await self._execute_rule(rule_id, user_id=user_id)
    
    async def trigger_by_event(self, event: str, data: Optional[Dict] = None) -> int:
        """Trigger rules by event."""
        triggered = 0
        
        for rule in self._rules.values():
            if not rule["is_enabled"]:
                continue
            
            if rule["trigger_config"].get("type") == "event":
                if rule["trigger_config"].get("event") == event:
                    await self._execute_rule(rule["id"], user_id="event_trigger")
                    triggered += 1
        
        return triggered
    
    async def trigger_by_keyword(self, text: str, user_id: str = "keyword_trigger") -> int:
        """Trigger rules by keyword in text."""
        triggered = 0
        
        for rule in self._rules.values():
            if not rule["is_enabled"]:
                continue
            
            if rule["trigger_config"].get("type") == "keyword":
                keyword = rule["trigger_config"].get("keyword", "").lower()
                if keyword and keyword in text.lower():
                    await self._execute_rule(rule["id"], user_id=user_id)
                    triggered += 1
        
        return triggered
    
    # Safety Layer Control Methods
    
    def activate_kill_switch(self, reason: str, activated_by: str = "system") -> None:
        """Activate the global automation kill switch."""
        automation_safety.activate_kill_switch(reason, activated_by)
    
    def deactivate_kill_switch(self, deactivated_by: str = "system") -> None:
        """Deactivate the kill switch and resume automation."""
        automation_safety.deactivate_kill_switch(deactivated_by)
        
        # Resume scheduler if it was paused
        if self._scheduler.state == 2:  # PAUSED state
            self._scheduler.resume()
    
    def enable_dry_run_mode(self) -> None:
        """Enable dry-run mode for all automation."""
        automation_safety.enable_dry_run_mode()
    
    def disable_dry_run_mode(self) -> None:
        """Disable dry-run mode."""
        automation_safety.disable_dry_run_mode()
    
    def get_safety_stats(self) -> Dict[str, Any]:
        """Get automation safety layer statistics."""
        return automation_safety.get_stats()
    
    # CRUD operations
    
    async def list_rules(self) -> List[Dict[str, Any]]:
        """List all automation rules."""
        return list(self._rules.values())
    
    async def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific rule."""
        return self._rules.get(rule_id)
    
    async def update_rule(self, rule_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            return None
        
        # Update fields
        for key, value in kwargs.items():
            if key in rule and key not in ("id", "created_at"):
                rule[key] = value
        
        rule["updated_at"] = datetime.utcnow()
        
        # Reschedule if trigger changed
        if "trigger" in kwargs:
            rule["trigger_config"] = kwargs["trigger"]
            rule["trigger_type"] = kwargs["trigger"].get("type")
            await self._schedule_rule(rule)
        
        return rule
    
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        if rule_id not in self._rules:
            return False
        
        # Remove scheduled job
        job_id = f"rule_{rule_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
        
        del self._rules[rule_id]
        
        audit_logger.log(
            action="automation_rule_deleted",
            resource_type="automation_rule",
            resource_id=rule_id,
        )
        
        return True
    
    async def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        
        rule["is_enabled"] = True
        await self._schedule_rule(rule)
        return True
    
    async def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        
        rule["is_enabled"] = False
        
        # Remove scheduled job
        job_id = f"rule_{rule_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
        
        return True
    
    async def list_jobs(
        self,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List job history."""
        jobs = self._job_history.copy()
        
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        
        # Sort by started_at descending
        jobs.sort(key=lambda x: x["started_at"], reverse=True)
        
        return jobs[:limit]
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job."""
        return self._jobs.get(job_id)


# Global scheduler instance
scheduler = AutomationScheduler()
