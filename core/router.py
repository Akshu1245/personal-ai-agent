"""
JARVIS Router Module
Maps intents to tools and executes them

Author: Rashi AI
Built for: Akshay
"""

import os
import json
from typing import Dict, Any, Optional, Callable

# Import all tools
from tools import pc_control
from tools import file_ops
from tools import browser
from tools import web_search
from tools import code_runner
from tools import focus_mode
from tools import crypto_watch
from tools import notes
from tools import scheduler
from tools import clipboard
from tools import system_info


class Router:
    """JARVIS Router - Intent to Tool Mapping"""
    
    def __init__(self):
        # Tool registry
        self.tools: Dict[str, Callable] = {
            # PC Control
            'PC_CONTROL': self._handle_pc_control,
            'OPEN_APP': pc_control.open_app,
            'CLOSE_APP': pc_control.close_app,
            'TAKE_SCREENSHOT': pc_control.take_screenshot,
            'CLICK': pc_control.click,
            'TYPE': pc_control.type_text,
            'PRESS_KEY': pc_control.press_key,
            'GET_SYSTEM_INFO': system_info.get_system_info,
            
            # File Operations
            'FILE_OPS': self._handle_file_ops,
            'READ_FILE': file_ops.read_file,
            'WRITE_FILE': file_ops.write_file,
            'DELETE_FILE': file_ops.delete_file,
            'MOVE_FILE': file_ops.move_file,
            'LIST_FILES': file_ops.list_files,
            'CREATE_FOLDER': file_ops.create_folder,
            
            # Browser
            'BROWSER': self._handle_browser,
            'OPEN_URL': browser.open_url,
            'SEARCH_WEB': web_search.search,
            'SCRAPE_PAGE': browser.scrape_page,
            
            # Web Search
            'WEB_SEARCH': web_search.search,
            'SEARCH': web_search.search,
            
            # Code
            'CODE_GEN': self._handle_code,
            'RUN_CODE': code_runner.run_code,
            'EXECUTE': code_runner.run_code,
            
            # Clipboard
            'CLIPBOARD': self._handle_clipboard,
            'COPY': clipboard.copy_to_clipboard,
            'PASTE': clipboard.get_clipboard,
            
            # Memory
            'MEMORY': self._handle_memory,
            'REMEMBER': self._handle_memory,
            'RECALL': self._handle_memory,
            
            # Schedule
            'SCHEDULE': self._handle_schedule,
            'SET_REMINDER': scheduler.set_reminder,
            'SET_TIMER': scheduler.set_timer,
            
            # Focus Mode
            'FOCUS_MODE': focus_mode.start_focus_mode,
            'POMODORO': focus_mode.start_pomodoro,
            'STOP_FOCUS': focus_mode.stop_focus_mode,
            
            # Crypto
            'CRYPTO_WATCH': crypto_watch.get_ada_price,
            'CHECK_CRYPTO': crypto_watch.get_ada_price,
            
            # Notes
            'NOTES': notes.add_note,
            'ADD_NOTE': notes.add_note,
            'GET_NOTES': notes.get_notes,
            'JOURNAL': notes.add_journal_entry,
            
            # Voice
            'VOICE_OUT': self._handle_voice,
            'SPEAK': self._handle_voice,
            
            # Project Context
            'PROJECT_CTX': self._handle_project,
            'SWITCH_PROJECT': self._handle_project,
            
            # GitHub
            'GITHUB_OPS': self._handle_github,
            'COMMIT': self._handle_github,
        }
        
    def execute(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Execute a tool by name with given parameters
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool (supports both dict and JSON string)
            
        Returns:
            Tool execution result
        """
        # Normalize tool name
        tool_name = tool_name.upper().strip()
        
        # Handle JSON string parameters
        if isinstance(params, str):
            try:
                import json
                params = json.loads(params)
            except:
                params = {}
        
        # If params is a dict with 'parameters' key (new JSON format)
        if isinstance(params, dict) and 'parameters' in params:
            params = params['parameters']
        
        # If params is a dict with 'action' key, extract it
        if isinstance(params, dict) and 'action' in params:
            action = params.pop('action')
            # Create wrapper function that calls with action
            original_func = self.tools.get(tool_name)
            if original_func and callable(original_func):
                def action_wrapper(**kwargs):
                    kwargs['action'] = action
                    return original_func(**kwargs)
                self.tools[tool_name] = action_wrapper
        
        # Find and execute tool
        if tool_name in self.tools:
            try:
                result = self.tools[tool_name](**params)
                return {
                    'success': True,
                    'result': result
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        else:
            return {
                'success': False,
                'error': f'Unknown tool: {tool_name}'
            }
    
    def _handle_pc_control(self, **kwargs) -> Dict:
        """Handle PC control commands"""
        action = kwargs.get('action', '').lower()
        
        if action == 'open':
            return pc_control.open_app(kwargs.get('app', ''))
        elif action == 'close':
            return pc_control.close_app(kwargs.get('app', ''))
        elif action == 'screenshot':
            return pc_control.take_screenshot(kwargs.get('path', ''))
        else:
            return {'error': f'Unknown PC control action: {action}'}
    
    def _handle_file_ops(self, **kwargs) -> Dict:
        """Handle file operations"""
        operation = kwargs.get('operation', '').lower()
        
        if operation == 'read':
            return file_ops.read_file(kwargs.get('path', ''))
        elif operation == 'write':
            return file_ops.write_file(kwargs.get('path', ''), kwargs.get('content', ''))
        elif operation == 'delete':
            return file_ops.delete_file(kwargs.get('path', ''))
        else:
            return {'error': f'Unknown file operation: {operation}'}
    
    def _handle_browser(self, **kwargs) -> Dict:
        """Handle browser commands"""
        action = kwargs.get('action', '').lower()
        
        if action == 'open':
            return browser.open_url(kwargs.get('url', ''))
        elif action == 'search':
            return web_search.search(kwargs.get('query', ''))
        else:
            return {'error': f'Unknown browser action: {action}'}
    
    def _handle_code(self, **kwargs) -> Dict:
        """Handle code execution"""
        code = kwargs.get('code', '')
        language = kwargs.get('language', 'python')
        
        return code_runner.run_code(code, language)
    
    def _handle_clipboard(self, **kwargs) -> Dict:
        """Handle clipboard operations"""
        action = kwargs.get('action', '').lower()
        
        if action == 'copy':
            return clipboard.copy_to_clipboard(kwargs.get('text', ''))
        elif action == 'paste':
            return clipboard.get_clipboard()
        else:
            return {'error': f'Unknown clipboard action: {action}'}
    
    def _handle_memory(self, **kwargs) -> Dict:
        """Handle memory operations"""
        from core.memory import get_memory
        
        memory = get_memory()
        action = kwargs.get('action', '').lower() if 'action' in kwargs else 'add'
        
        if action == 'add' or action == 'remember':
            content = kwargs.get('content', '') or kwargs.get('query', '')
            memory.add(content)
            return {'success': True, 'message': 'Remembered!'}
        elif action == 'search' or action == 'recall':
            query = kwargs.get('query', '') or kwargs.get('content', '')
            results = memory.search(query)
            return {'success': True, 'results': results}
        else:
            return {'error': f'Unknown memory action: {action}'}
    
    def _handle_schedule(self, **kwargs) -> Dict:
        """Handle scheduling"""
        action = kwargs.get('action', '').lower()
        
        if action == 'reminder' or action == 'set_reminder':
            return scheduler.set_reminder(
                kwargs.get('message', ''),
                kwargs.get('time', '')
            )
        elif action == 'timer':
            return scheduler.set_timer(
                kwargs.get('minutes', 0)
            )
        else:
            return {'error': f'Unknown schedule action: {action}'}
    
    def _handle_voice(self, **kwargs) -> Dict:
        """Handle voice output"""
        from tools.voice_out import speak
        
        text = kwargs.get('text', '')
        speak(text)
        return {'success': True, 'message': 'Speaking...'}
    
    def _handle_project(self, **kwargs) -> Dict:
        """Handle project context"""
        from core.context import get_context_manager
        
        ctx = get_context_manager()
        action = kwargs.get('action', '').lower() if 'action' in kwargs else 'get'
        
        if action == 'switch':
            project = kwargs.get('project', '')
            ctx.switch_project(project)
            return {'success': True, 'message': f'Switched to {project}'}
        elif action == 'get':
            return ctx.get_context()
        else:
            return {'error': f'Unknown project action: {action}'}
    
    def _handle_github(self, **kwargs) -> Dict:
        """Handle GitHub operations"""
        action = kwargs.get('action', '').lower()
        
        if action == 'commit':
            from tools import github_ops
            return github_ops.commit(
                kwargs.get('message', ''),
                kwargs.get('path', '.')
            )
        elif action == 'push':
            from tools import github_ops
            return github_ops.push(kwargs.get('path', '.'))
        else:
            return {'error': f'Unknown github action: {action}'}
    
    def list_tools(self) -> list:
        """List all available tools"""
        return list(self.tools.keys())


# Singleton
_router = None

def get_router() -> Router:
    """Get router singleton"""
    global _router
    if _router is None:
        _router = Router()
    return _router
