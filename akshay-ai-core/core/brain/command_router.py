"""
============================================================
AKSHAY AI CORE — Command Router
============================================================
Intent recognition and command routing to plugins.
============================================================
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.config import settings
from core.utils.logger import get_logger, audit_logger

logger = get_logger("brain.router")


class IntentCategory(str, Enum):
    """High-level intent categories."""
    QUERY = "query"                # Information request
    COMMAND = "command"            # Action execution
    CONVERSATION = "conversation"  # Chat/discussion
    SYSTEM = "system"              # System control
    AUTOMATION = "automation"      # Automation task
    CREATIVE = "creative"          # Content creation


@dataclass
class Intent:
    """Parsed intent from user input."""
    category: IntentCategory
    action: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteTarget:
    """Target for routing a command."""
    plugin_id: str
    command: str
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class RoutingResult:
    """Result of command routing."""
    intent: Intent
    targets: List[RouteTarget]
    requires_confirmation: bool = False
    fallback_to_llm: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CommandRouter:
    """
    Command router with intent recognition.
    
    Features:
    - Intent classification
    - Entity extraction
    - Plugin routing
    - Fallback handling
    - Pattern matching
    """
    
    def __init__(self):
        self._patterns: List[Tuple[re.Pattern, str, str, Dict]] = []
        self._plugin_commands: Dict[str, List[str]] = {}
        self._intent_handlers: Dict[str, Callable] = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self) -> None:
        """Initialize command patterns."""
        patterns = [
            # System commands
            (r"(shut\s*down|power\s*off|turn\s*off)\s*(the\s*)?(computer|system|pc)?", "system_control", "shutdown", {}),
            (r"(restart|reboot)\s*(the\s*)?(computer|system|pc)?", "system_control", "restart", {}),
            (r"(lock)\s*(the\s*)?(computer|screen|system)?", "system_control", "lock", {}),
            (r"(sleep|hibernate)\s*(the\s*)?(computer|system)?", "system_control", "sleep", {}),
            
            # File operations
            (r"(open|launch|start|run)\s+(.+)", "system_control", "open_application", {"app": 2}),
            (r"(create|make)\s+(a\s+)?(new\s+)?(file|document)\s+(?:named\s+)?(.+)", "file_vault", "store", {"name": 5}),
            (r"(delete|remove)\s+(the\s+)?file\s+(.+)", "file_vault", "delete", {"path": 3}),
            
            # Web automation
            (r"(go\s+to|open|navigate\s+to|visit)\s+(https?://\S+|www\.\S+|\S+\.\S+)", "web_automation", "navigate", {"url": 2}),
            (r"(search|google|look\s+up)\s+(?:for\s+)?(.+)", "web_automation", "search", {"query": 2}),
            (r"(take\s+a\s+)?screenshot\s*(of\s+)?(.+)?", "web_automation", "screenshot", {"target": 3}),
            (r"(scrape|extract)\s+(?:data\s+)?(?:from\s+)?(.+)", "web_automation", "scrape", {"url": 2}),
            
            # Data analysis
            (r"(analyze|process)\s+(?:the\s+)?(?:data\s+)?(?:in\s+)?(.+)", "data_analysis", "load_data", {"path": 2}),
            (r"(show|display|describe)\s+(?:the\s+)?statistics\s+(?:for\s+)?(.+)?", "data_analysis", "describe", {"name": 2}),
            
            # Automation
            (r"(schedule|set\s+up|create)\s+(?:a\s+)?(?:task|job|automation)\s+(?:to\s+)?(.+)", "automation", "create_rule", {"description": 2}),
            (r"(every|at)\s+(\d+)\s*(hour|minute|day|second)s?\s+(.+)", "automation", "schedule", {"interval": 2, "unit": 3, "action": 4}),
            
            # IoT commands
            (r"(turn|switch)\s+(on|off)\s+(?:the\s+)?(.+)", "esp32_iot", "send_command", {"state": 2, "device": 3}),
            (r"(dim|brighten|set)\s+(?:the\s+)?(.+)\s+(?:to\s+)?(\d+)%?", "esp32_iot", "send_command", {"device": 2, "value": 3}),
            
            # Security tools
            (r"(scan|check)\s+(?:the\s+)?ports?\s+(?:on\s+)?(.+)", "cyber_tools", "port_scan", {"host": 2}),
            (r"(hash|checksum)\s+(?:the\s+)?(?:file\s+)?(.+)", "cyber_tools", "hash_file", {"path": 2}),
            (r"(encode|decode)\s+(.+)\s+(?:as|to|from)\s+(base64|url|hex)", "cyber_tools", "encode_decode", {"data": 2, "encoding": 3}),
        ]
        
        for pattern, plugin, command, params in patterns:
            self._patterns.append((
                re.compile(pattern, re.IGNORECASE),
                plugin,
                command,
                params,
            ))
    
    def register_plugin(self, plugin_id: str, commands: List[str]) -> None:
        """Register a plugin's available commands."""
        self._plugin_commands[plugin_id] = commands
        logger.debug(f"Registered plugin commands: {plugin_id}", commands=commands)
    
    def register_intent_handler(
        self,
        intent_action: str,
        handler: Callable,
    ) -> None:
        """Register a custom intent handler."""
        self._intent_handlers[intent_action] = handler
    
    async def route(
        self,
        text: str,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> RoutingResult:
        """
        Route user input to appropriate handlers.
        
        Args:
            text: User input text
            context: Additional context
            user_id: User ID for permissions
            
        Returns:
            RoutingResult with targets
        """
        context = context or {}
        
        # Step 1: Pattern matching
        pattern_result = await self._match_patterns(text)
        if pattern_result:
            return pattern_result
        
        # Step 2: Intent classification (using LLM if available)
        intent = await self._classify_intent(text, context)
        
        # Step 3: Entity extraction
        entities = await self._extract_entities(text, intent)
        intent.entities = entities
        
        # Step 4: Route to plugins
        targets = await self._find_targets(intent)
        
        # Step 5: Check if confirmation needed
        requires_confirmation = self._requires_confirmation(intent, targets)
        
        # Step 6: Fallback to LLM for conversation
        fallback_to_llm = len(targets) == 0 or intent.category == IntentCategory.CONVERSATION
        
        result = RoutingResult(
            intent=intent,
            targets=targets,
            requires_confirmation=requires_confirmation,
            fallback_to_llm=fallback_to_llm,
        )
        
        audit_logger.log(
            action="command_routed",
            user_id=user_id,
            details={
                "input": text[:100],
                "intent": intent.action,
                "category": intent.category.value,
                "targets": len(targets),
                "fallback": fallback_to_llm,
            },
        )
        
        return result
    
    async def _match_patterns(self, text: str) -> Optional[RoutingResult]:
        """Match text against predefined patterns."""
        for pattern, plugin_id, command, param_groups in self._patterns:
            match = pattern.search(text)
            if match:
                # Extract parameters
                params = {}
                for param_name, group_num in param_groups.items():
                    if group_num <= len(match.groups()):
                        value = match.group(group_num)
                        if value:
                            params[param_name] = value.strip()
                
                intent = Intent(
                    category=IntentCategory.COMMAND,
                    action=command,
                    confidence=0.9,
                    entities=params,
                    raw_input=text,
                )
                
                target = RouteTarget(
                    plugin_id=plugin_id,
                    command=command,
                    params=params,
                    confidence=0.9,
                )
                
                return RoutingResult(
                    intent=intent,
                    targets=[target],
                    requires_confirmation=self._requires_confirmation(intent, [target]),
                )
        
        return None
    
    async def _classify_intent(
        self,
        text: str,
        context: Dict,
    ) -> Intent:
        """Classify the intent of user input."""
        text_lower = text.lower().strip()
        
        # Simple keyword-based classification
        if any(q in text_lower for q in ["what", "who", "where", "when", "why", "how", "?"]):
            category = IntentCategory.QUERY
            action = "question"
        elif any(c in text_lower for c in ["open", "run", "start", "launch", "execute", "do", "create", "delete", "send"]):
            category = IntentCategory.COMMAND
            action = "execute"
        elif any(s in text_lower for s in ["shutdown", "restart", "lock", "sleep", "status"]):
            category = IntentCategory.SYSTEM
            action = "system_control"
        elif any(a in text_lower for a in ["schedule", "automate", "every", "remind", "alert"]):
            category = IntentCategory.AUTOMATION
            action = "schedule"
        elif any(c in text_lower for c in ["write", "compose", "generate", "create", "draft"]):
            category = IntentCategory.CREATIVE
            action = "generate"
        else:
            category = IntentCategory.CONVERSATION
            action = "chat"
        
        # Try LLM classification for better accuracy
        if settings.AI_PROVIDER:
            try:
                intent = await self._llm_classify_intent(text, context)
                if intent.confidence > 0.7:
                    return intent
            except Exception as e:
                logger.warning("LLM intent classification failed", error=str(e))
        
        return Intent(
            category=category,
            action=action,
            confidence=0.6,
            raw_input=text,
        )
    
    async def _llm_classify_intent(
        self,
        text: str,
        context: Dict,
    ) -> Intent:
        """Use LLM for intent classification."""
        from core.brain.llm_connector import llm, Message
        
        system_prompt = """You are an intent classifier. Classify the user's input into one of these categories:
- QUERY: Questions, information requests
- COMMAND: Actions to execute, tasks to perform
- CONVERSATION: General chat, discussion
- SYSTEM: System control (shutdown, restart, etc.)
- AUTOMATION: Scheduling, reminders, automated tasks
- CREATIVE: Content creation, writing, generating

Respond with JSON:
{"category": "CATEGORY", "action": "specific_action", "confidence": 0.0-1.0}"""
        
        response = await llm.complete(
            messages=[
                Message(role="system", content=system_prompt),
                Message(role="user", content=text),
            ],
            max_tokens=100,
            temperature=0.1,
        )
        
        import json
        try:
            data = json.loads(response.content)
            return Intent(
                category=IntentCategory(data["category"].lower()),
                action=data.get("action", "unknown"),
                confidence=data.get("confidence", 0.7),
                raw_input=text,
            )
        except:
            return Intent(
                category=IntentCategory.CONVERSATION,
                action="chat",
                confidence=0.5,
                raw_input=text,
            )
    
    async def _extract_entities(
        self,
        text: str,
        intent: Intent,
    ) -> Dict[str, Any]:
        """Extract entities from text."""
        entities = {}
        
        # URL extraction
        urls = re.findall(r'https?://\S+|www\.\S+', text)
        if urls:
            entities["urls"] = urls
        
        # File path extraction
        paths = re.findall(r'[A-Za-z]:\\[\w\\.-]+|/[\w/.-]+', text)
        if paths:
            entities["paths"] = paths
        
        # Number extraction
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
        if numbers:
            entities["numbers"] = [float(n) if '.' in n else int(n) for n in numbers]
        
        # Time extraction
        times = re.findall(r'\b(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\b', text)
        if times:
            entities["times"] = times
        
        # Date extraction
        dates = re.findall(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', text)
        if dates:
            entities["dates"] = dates
        
        # Email extraction
        emails = re.findall(r'\b[\w.-]+@[\w.-]+\.\w+\b', text)
        if emails:
            entities["emails"] = emails
        
        return entities
    
    async def _find_targets(self, intent: Intent) -> List[RouteTarget]:
        """Find plugin targets for intent."""
        targets = []
        
        # Map intent categories to plugins
        category_plugins = {
            IntentCategory.COMMAND: ["system_control", "file_vault", "web_automation"],
            IntentCategory.SYSTEM: ["system_control"],
            IntentCategory.AUTOMATION: ["automation"],
            IntentCategory.QUERY: ["data_analysis", "cyber_tools"],
        }
        
        potential_plugins = category_plugins.get(intent.category, [])
        
        for plugin_id in potential_plugins:
            if plugin_id in self._plugin_commands:
                # Try to match action to command
                commands = self._plugin_commands[plugin_id]
                
                for cmd in commands:
                    if intent.action in cmd or cmd in intent.action:
                        targets.append(RouteTarget(
                            plugin_id=plugin_id,
                            command=cmd,
                            params=intent.entities,
                            confidence=0.7,
                        ))
                        break
        
        return targets
    
    def _requires_confirmation(
        self,
        intent: Intent,
        targets: List[RouteTarget],
    ) -> bool:
        """Check if action requires user confirmation."""
        # Dangerous actions
        dangerous_actions = [
            "shutdown", "restart", "delete", "remove", "kill", "terminate",
            "format", "wipe", "destroy",
        ]
        
        if intent.action in dangerous_actions:
            return True
        
        for target in targets:
            if target.command in dangerous_actions:
                return True
        
        return False
    
    async def execute_route(
        self,
        result: RoutingResult,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the routed command."""
        from plugins import plugin_manager
        
        outputs = []
        
        for target in result.targets:
            try:
                output = await plugin_manager.execute_plugin(
                    plugin_id=target.plugin_id,
                    command=target.command,
                    params=target.params,
                    user_id=user_id,
                )
                outputs.append({
                    "target": target.plugin_id,
                    "command": target.command,
                    "result": output,
                })
            except Exception as e:
                outputs.append({
                    "target": target.plugin_id,
                    "command": target.command,
                    "error": str(e),
                })
        
        return {
            "intent": {
                "category": result.intent.category.value,
                "action": result.intent.action,
                "confidence": result.intent.confidence,
            },
            "outputs": outputs,
            "fallback_to_llm": result.fallback_to_llm,
        }


# Global router instance
router = CommandRouter()
