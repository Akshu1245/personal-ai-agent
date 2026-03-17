"""
JARVIS PC Control Module
Mouse, keyboard, app launcher, screenshots

Author: Rashi AI
Built for: Akshay
"""

import os
import subprocess
import pyautogui
import pynput
from pathlib import Path
from typing import Optional, Dict, Any

# Disable fail-safe for automated use (with caution)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


# ==================== APP LAUNCHER ====================

def open_app(app_name: str) -> Dict[str, Any]:
    """
    Open an application by name
    
    Args:
        app_name: Name of the app to open
        
    Returns:
        Dict with success status and message
    """
    # Common app paths on Windows
    app_paths = {
        'vscode': 'code',
        'visual studio code': 'code',
        'notepad': 'notepad',
        'calculator': 'calc',
        'cmd': 'cmd',
        'terminal': 'cmd',
        'powershell': 'powershell',
        'chrome': 'chrome',
        'firefox': 'firefox',
        'edge': 'msedge',
        'explorer': 'explorer',
        'file explorer': 'explorer',
        'spotify': 'spotify',
        'discord': 'discord',
        'slack': 'slack',
        'zoom': 'zoom',
        'teams': 'teams',
    }
    
    app_lower = app_name.lower()
    
    # Check if we have a direct command
    if app_lower in app_paths:
        command = app_paths[app_lower]
    else:
        # Try to use start command
        command = app_name
    
    try:
        # Use start command on Windows
        subprocess.Popen(f'start "" "{command}"', shell=True)
        return {'success': True, 'message': f'Opened {app_name}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def close_app(app_name: str) -> Dict[str, Any]:
    """
    Close an application by name
    
    Args:
        app_name: Name of the app to close
        
    Returns:
        Dict with success status and message
    """
    try:
        # Use taskkill to close the process
        subprocess.run(['taskkill', '/F', '/IM', f'{app_name}.exe'], check=True)
        return {'success': True, 'message': f'Closed {app_name}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== MOUSE CONTROL ====================

def move_mouse(x: int, y: int) -> Dict[str, Any]:
    """Move mouse to coordinates"""
    try:
        pyautogui.moveTo(x, y)
        return {'success': True, 'message': f'Moved to ({x}, {y})'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def click(x: Optional[int] = None, y: Optional[int] = None, button: str = 'left') -> Dict[str, Any]:
    """
    Click at coordinates
    
    Args:
        x: X coordinate (optional)
        y: Y coordinate (optional)
        button: Mouse button ('left', 'right', 'middle')
    """
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
        return {'success': True, 'message': f'Clicked {button} button'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def double_click(x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Double click"""
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.doubleClick()
        return {'success': True, 'message': 'Double clicked'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def right_click(x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Right click"""
    try:
        if x is not None and y is not None:
            pyautogui.rightClick(x, y)
        else:
            pyautogui.rightClick()
        return {'success': True, 'message': 'Right clicked'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def scroll(clicks: int) -> Dict[str, Any]:
    """Scroll mouse"""
    try:
        pyautogui.scroll(clicks)
        return {'success': True, 'message': f'Scrolled {clicks} clicks'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== KEYBOARD CONTROL ====================

def type_text(text: str, interval: float = 0.05) -> Dict[str, Any]:
    """
    Type text
    
    Args:
        text: Text to type
        interval: Delay between keystrokes
    """
    try:
        pyautogui.write(text, interval=interval)
        return {'success': True, 'message': f'Typed: {text[:50]}...'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def press_key(key: str) -> Dict[str, Any]:
    """
    Press a key
    
    Args:
        key: Key to press (e.g., 'enter', 'ctrl', 'alt', 'a')
    """
    try:
        pyautogui.press(key)
        return {'success': True, 'message': f'Pressed {key}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def hotkey(*keys) -> Dict[str, Any]:
    """
    Press hotkey combination
    
    Args:
        *keys: Keys to press together (e.g., 'ctrl', 'c')
    """
    try:
        pyautogui.hotkey(*keys)
        return {'success': True, 'message': f'Pressed {"+".join(keys)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== SCREENSHOT ====================

def take_screenshot(save_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Take a screenshot
    
    Args:
        save_path: Path to save screenshot (optional)
        
    Returns:
        Dict with success status and screenshot path
    """
    try:
        if save_path is None:
            # Default to desktop
            desktop = Path.home() / 'Desktop'
            save_path = desktop / f'jarvis_screenshot_{int(os.times().elapsed * 1000)}.png'
            
        screenshot = pyautogui.screenshot()
        screenshot.save(str(save_path))
        
        return {
            'success': True,
            'message': f'Screenshot saved to {save_path}',
            'path': str(save_path)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_screen_size() -> Dict[str, Any]:
    """Get screen dimensions"""
    try:
        width, height = pyautogui.size()
        return {
            'success': True,
            'width': width,
            'height': height
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== TERMINAL ====================

def run_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a terminal command
    
    Args:
        command: Command to run
        cwd: Working directory (optional)
        
    Returns:
        Dict with command output
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== WINDOW MANAGEMENT ====================

def minimize_window() -> Dict[str, Any]:
    """Minimize current window"""
    try:
        pyautogui.hotkey('win', 'down')
        return {'success': True, 'message': 'Window minimized'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def maximize_window() -> Dict[str, Any]:
    """Maximize current window"""
    try:
        pyautogui.hotkey('win', 'up')
        return {'success': True, 'message': 'Window maximized'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def switch_window() -> Dict[str, Any]:
    """Switch to next window"""
    try:
        pyautogui.hotkey('alt', 'tab')
        return {'success': True, 'message': 'Switched window'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== GET CURSOR POSITION ====================

def get_cursor_position() -> Dict[str, Any]:
    """Get current cursor position"""
    try:
        x, y = pyautogui.position()
        return {
            'success': True,
            'x': x,
            'y': y
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
