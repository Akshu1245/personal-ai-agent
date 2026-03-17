"""
JARVIS Clipboard Module
Clipboard read/write operations

Author: Rashi AI
Built for: Akshay
"""

from typing import Dict, Any

# Try to import pyperclip
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


def copy_to_clipboard(text: str) -> Dict[str, Any]:
    """
    Copy text to clipboard
    
    Args:
        text: Text to copy
        
    Returns:
        Dict with success status
    """
    if not PYPERCLIP_AVAILABLE:
        return {'success': False, 'error': 'pyperclip not available'}
        
    try:
        pyperclip.copy(text)
        return {
            'success': True,
            'message': f'Copied to clipboard: {text[:50]}...'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_clipboard() -> Dict[str, Any]:
    """
    Get text from clipboard
    
    Returns:
        Dict with clipboard content
    """
    if not PYPERCLIP_AVAILABLE:
        return {'success': False, 'error': 'pyperclip not available'}
        
    try:
        text = pyperclip.paste()
        return {
            'success': True,
            'text': text,
            'length': len(text)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
