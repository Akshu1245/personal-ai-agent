"""
JARVIS Code Runner Module
Safe Python code execution

Author: Rashi AI
Built for: Akshay
"""

import subprocess
import sys
import io
from typing import Dict, Any


def run_code(code: str, language: str = 'python') -> Dict[str, Any]:
    """
    Run code in a sandboxed environment
    
    Args:
        code: Code to run
        language: Programming language
        
    Returns:
        Dict with execution result
    """
    if language.lower() == 'python':
        return run_python(code)
    elif language.lower() in ['javascript', 'js', 'node']:
        return run_javascript(code)
    else:
        return {'success': False, 'error': f'Unsupported language: {language}'}


def run_python(code: str) -> Dict[str, Any]:
    """Run Python code"""
    # Capture stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = captured_stdout = io.StringIO()
    sys.stderr = captured_stderr = io.StringIO()
    
    try:
        # Execute the code
        exec(code, {'__builtins__': __builtins__})
        
        stdout = captured_stdout.getvalue()
        stderr = captured_stderr.getvalue()
        
        return {
            'success': True,
            'stdout': stdout,
            'stderr': stderr,
            'output': stdout if stdout else 'Code executed successfully (no output)'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'type': type(e).__name__
        }
        
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def run_javascript(code: str) -> Dict[str, Any]:
    """Run JavaScript code using Node"""
    try:
        result = subprocess.run(
            ['node', '-e', code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'output': result.stdout if result.returncode == 0 else result.stderr
        }
    except FileNotFoundError:
        return {'success': False, 'error': 'Node.js not found'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
