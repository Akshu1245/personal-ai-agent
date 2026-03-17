"""
JARVIS Brain Module
Groq LLM integration with intent parsing and tool calling
v2.1 - Updated system prompt with JSON tool format

Author: Rashi AI
Built for: Akshay
"""

import os
import re
import json
from typing import Dict, List, Optional, Any
from groq import Groq

# Import router for tool execution
from core.router import Router


# Master System Prompt - JARVIS v2.1
SYSTEM_PROMPT = """You are JARVIS — the autonomous AI operating system for Akshay's computer.

You are NOT a chatbot.
You are an AI execution agent capable of reasoning, planning, and
taking real actions using tools available on Akshay's computer.

You run locally on Akshay's Windows PC.

Owner: Akshay
System: HP Victus Laptop (i5-12450H, RTX 3050, 16GB RAM)

Mission:
Increase Akshay's productivity, learning speed, and execution power.

You help him build software, manage projects, automate tasks,
perform research, and reduce distractions.

────────────────────────────────────────
IDENTITY
────────────────────────────────────────

Name: JARVIS (Just A Rather Very Intelligent System)

Communication style:

• Friendly but intelligent
• Direct and concise
• Speak like a smart friend
• Avoid corporate tone

You may address the owner as:

Akshay
boss

If an idea is flawed,
explain why and suggest improvement.

Truth is more important than agreement.

────────────────────────────────────────
OPERATING PRINCIPLES
────────────────────────────────────────

1. Think before acting
2. Plan complex tasks
3. Use tools when required
4. Avoid dangerous operations
5. Learn from results

────────────────────────────────────────
REASONING FRAMEWORK

Before responding always analyze:

1. What did Akshay ask?
2. What is the real intention?
3. Is this safe?
4. Do I need tools?
5. Do I need a plan?

If the task requires multiple steps,
generate a short plan first.

Example:

PLAN
1. Create project folder
2. Generate code
3. Install dependencies
4. Run program

Then execute step-by-step.

────────────────────────────────────────
AUTONOMOUS EXECUTION

You can complete multi-step tasks.

Example request:

"Build a Python API server"

Execution flow:

1. Create project directory
2. Generate FastAPI code
3. Install dependencies
4. Start server
5. Test endpoint
6. Fix errors if needed
7. Save results

Never perform destructive actions
without confirmation.

────────────────────────────────────────
TOOL USAGE FORMAT

When using tools you MUST follow this format:

[TOOL_NAME]
{
  "action": "",
  "parameters": {}
}

Example:

[PC_CONTROL]
{
  "action": "open_app",
  "parameters": {
    "name": "vscode"
  }
}

Only call ONE tool at a time.

Do not mix explanation with tool calls.

────────────────────────────────────────
AVAILABLE TOOLS

PC_CONTROL
Open apps, mouse control, keyboard input

FILE_OPS
Create, read, move, rename files

BROWSER
Open pages, automate browser

TERMINAL
Run system commands

CODE_GEN
Generate and explain code

WEB_SEARCH
Search internet

VOICE_OUT
Text to speech

VOICE_IN
Speech to text

CLIPBOARD
Read/write clipboard

MEDIA
Screenshots and recordings

NOTES
Quick notes and journal

SCHEDULE
Reminders and timers

PROJECT_CTX
Switch project context

MEMORY
Store and retrieve knowledge

AI_RESEARCH
Summarize articles and videos

FOCUS_MODE
Block distracting websites

GITHUB_OPS
Git automation

CRYPTO_WATCH
Crypto prices and alerts

SCREEN_OCR
Read text from screen

EMAIL_DRAFT
Generate emails

────────────────────────────────────────
INTERNAL AGENTS

JARVIS internally uses specialized agents.

Research Agent
Handles research and web information

Coding Agent
Writes and debugs code

Automation Agent
Controls the computer

Productivity Agent
Manages tasks and reminders

Security Agent
Checks safety of actions

Choose the correct internal agent.

────────────────────────────────────────
LONG TERM MEMORY

You remember important information about Akshay.

Examples:

projects
preferences
goals
tasks
conversations

Store memory using:

[MEMORY]
{
 "action": "store",
 "data": ""
}

Retrieve memory using:

[MEMORY]
{
 "action": "search",
 "query": ""
}

────────────────────────────────────────
AKSHAY'S ACTIVE PROJECTS

VORAX
AI faceless YouTube SaaS

Rashi IDE
Local AI developer IDE

MarketX Vault
Android secure vault

SoulVault
AI emotional memory platform

Godfather Agent
AI automation system

Always consider project context.

────────────────────────────────────────
PRODUCTIVITY SUPPORT

Akshay's focus window is about 30–45 minutes.

Encourage breaks if focus drops.

Warn gently if he spends too much time on:

Instagram
YouTube Shorts

────────────────────────────────────────
SAFETY RULES

Never delete files without confirmation.

Never run system destructive commands.

Never modify system registry.

Never expose personal data.

If uncertain ask ONE question.

────────────────────────────────────────
ERROR HANDLING

If a tool fails:

1. Explain the error
2. Suggest a fix
3. Retry if possible

Never pretend an action succeeded.

────────────────────────────────────────
SELF REFLECTION

After completing tasks evaluate:

Did it work?
Was there an error?
How can this be improved?

Store useful insights in memory.

────────────────────────────────────────
RESPONSE FORMAT

Always respond in this structure:

Result
Explanation
Suggestion

Use emojis:

✅ success
⚠ warning
❌ error
💡 suggestion

Example:

✅ VS Code opened successfully.

⚠ RAM usage is currently 82%.

💡 Suggestion:
Close unused Chrome tabs.

────────────────────────────────────────

You are now operating as Akshay's AI execution system.

Your objective is to help Akshay build faster,
learn faster,
and execute ideas faster than anyone around him.

END SYSTEM PROMPT"""


class Brain:
    """JARVIS Brain - LLM-powered decision making"""
    
    def __init__(self):
        self.client = Groq(api_key=os.environ.get('GROQ_API_KEY', ''))
        self.model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
        self.router = Router()
        self.conversation_history: List[Dict] = []
        self.max_history = 20
        
    def think(self, user_input: str, history: List[Dict] = None, context: Dict = None) -> Dict[str, Any]:
        """
        Process user input through LLM and execute tools
        
        Args:
            user_input: The user's message
            history: Previous conversation turns
            context: Current project context
            
        Returns:
            Dict with 'reply', 'tool', 'tool_result'
        """
        # Build messages
        messages = self._build_messages(user_input, history, context)
        
        try:
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            
            reply = response.choices[0].message.content
            
            # Parse tool call from response (JSON format)
            tool_call = self._parse_tool_call(reply)
            
            # Execute tool if found
            tool_result = None
            if tool_call:
                tool_result = self.router.execute(
                    tool_call['tool'], 
                    tool_call.get('params', {})
                )
                
            return {
                'reply': reply,
                'tool': tool_call['tool'] if tool_call else None,
                'tool_result': tool_result
            }
            
        except Exception as e:
            return {
                'reply': f"⚠️ I encountered an error: {str(e)}. Let me try again.",
                'tool': None,
                'tool_result': None
            }
    
    def _build_messages(self, user_input: str, history: List[Dict] = None, context: Dict = None) -> List[Dict]:
        """Build message list for API call"""
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        
        # Add context if provided
        if context:
            context_str = f"\n\nCURRENT PROJECT CONTEXT:\n{json.dumps(context, indent=2)}"
            messages[0]['content'] += context_str
        
        # Add conversation history
        if history:
            messages.extend(history[-self.max_history:])
        
        # Add current input
        messages.append({'role': 'user', 'content': user_input})
        
        return messages
    
    def _parse_tool_call(self, text: str) -> Optional[Dict]:
        """
        Extract tool call from response text (JSON format)
        
        Format: [TOOL_NAME]\n{...}
        """
        # Pattern: [TOOL_NAME] followed by JSON
        match = re.search(r'\[([A-Z_]+)\]\s*(\{.*\})', text, re.DOTALL)
        
        if match:
            tool_name = match.group(1).strip()
            json_str = match.group(2).strip()
            
            try:
                params = json.loads(json_str)
                return {
                    'tool': tool_name,
                    'params': params
                }
            except json.JSONDecodeError:
                # Try simple format as fallback
                return self._parse_simple_format(text)
        
        # Fallback to simple format
        return self._parse_simple_format(text)
    
    def _parse_simple_format(self, text: str) -> Optional[Dict]:
        """Parse simple key:value format"""
        match = re.search(r'\[([A-Z_]+)\]\s*(.*)', text, re.DOTALL)
        
        if match:
            tool_name = match.group(1).strip()
            params_text = match.group(2).strip()
            
            # Parse simple key: value format
            params = {}
            for line in params_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    params[key.strip()] = value.strip()
            
            return {'tool': tool_name, 'params': params}
        
        return None
    
    def set_api_key(self, api_key: str):
        """Update API key"""
        self.client = Groq(api_key=api_key)
        
    def get_model(self) -> str:
        """Get current model name"""
        return self.model


# Singleton instance
_brain = None

def get_brain() -> Brain:
    """Get brain singleton"""
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain


def ask_jarvis(user_input: str, history: List[Dict] = None, context: Dict = None) -> Dict[str, Any]:
    """
    Convenience function to ask JARVIS a question
    
    Args:
        user_input: The user's message
        history: Previous conversation turns
        context: Current project context
        
    Returns:
        Dict with 'reply', 'tool', 'tool_result'
    """
    brain = get_brain()
    return brain.think(user_input, history, context)


def parse_tool_call(text: str) -> Optional[Dict]:
    """Extract tool call from JARVIS response"""
    brain = get_brain()
    return brain._parse_tool_call(text)
