"""
JARVIS Browser Module
Browser automation

Author: Rashi AI
Built for: Akshay
"""

import webbrowser
from typing import Dict, Any


def open_url(url: str) -> Dict[str, Any]:
    """
    Open a URL in browser
    
    Args:
        url: URL to open
        
    Returns:
        Dict with success status
    """
    try:
        # Add https if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        webbrowser.open(url)
        return {'success': True, 'message': f'Opened {url}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def search_google(query: str) -> Dict[str, Any]:
    """Search Google"""
    return open_url(f'https://google.com/search?q={query}')


def search_duckduckgo(query: str) -> Dict[str, Any]:
    """Search DuckDuckGo"""
    return open_url(f'https://duckduckgo.com/?q={query}')
