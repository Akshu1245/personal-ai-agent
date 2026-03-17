"""
JARVIS Startup Module
Auto-launch JARVIS on Windows boot

Author: Rashi AI
Built for: Akshay
"""

import os
import subprocess
import winreg
from pathlib import Path
from typing import Dict, Any


def add_to_startup() -> Dict[str, Any]:
    """
    Add JARVIS to Windows startup
    
    Returns:
        Dict with result
    """
    try:
        # Get current file path
        exe_path = Path(__file__).parent.parent / 'main.py'
        
        # Add to registry
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0,
            winreg.KEY_SET_VALUE
        )
        
        winreg.SetValueEx(key, 'JARVIS', 0, winreg.REG_SZ, f'python "{exe_path}"')
        winreg.CloseKey(key)
        
        return {
            'success': True,
            'message': 'JARVIS added to startup'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def remove_from_startup() -> Dict[str, Any]:
    """
    Remove JARVIS from Windows startup
    
    Returns:
        Dict with result
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0,
            winreg.KEY_SET_VALUE
        )
        
        try:
            winreg.DeleteValue(key, 'JARVIS')
        except:
            pass
        
        winreg.CloseKey(key)
        
        return {
            'success': True,
            'message': 'JARVIS removed from startup'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def is_in_startup() -> bool:
    """Check if JARVIS is in startup"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0,
            winreg.KEY_READ
        )
        
        try:
            value, _ = winreg.QueryValueEx(key, 'JARVIS')
            return True
        except:
            return False
        
    except:
        return False


def create_task() -> Dict[str, Any]:
    """
    Create Windows Task Scheduler task
    
    Returns:
        Dict with result
    """
    try:
        exe_path = Path(__file__).parent.parent / 'main.py'
        
        # Create task using schtasks
        cmd = f'schtasks /create /tn "JARVIS" /tr "python \\"{exe_path}\\"" /sc onlogon /rl limited /f'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': 'Task created successfully'
            }
        else:
            return {
                'success': False,
                'error': result.stderr
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
