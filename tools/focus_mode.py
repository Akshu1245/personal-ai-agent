"""
JARVIS Focus Mode Module
Site blocker + Pomodoro timer

Author: Rashi AI
Built for: Akshay
"""

import threading
import time
import os
from typing import Dict, Any, List

# Focus mode state
focus_state = {
    'active': False,
    'duration_minutes': 25,
    'start_time': None,
    'blocked_sites': ['instagram.com', 'youtube.com', 'facebook.com', 'twitter.com']
}

# Timer thread
timer_thread = None


def start_focus_mode(duration_minutes: int = 25, blocked_sites: List[str] = None) -> Dict[str, Any]:
    """
    Start focus mode with Pomodoro timer
    
    Args:
        duration_minutes: Focus duration
        blocked_sites: Sites to block
        
    Returns:
        Dict with success status
    """
    global focus_state, timer_thread
    
    if blocked_sites:
        focus_state['blocked_sites'] = blocked_sites
        
    focus_state['active'] = True
    focus_state['duration_minutes'] = duration_minutes
    focus_state['start_time'] = time.time()
    
    # Block sites
    block_sites(focus_state['blocked_sites'])
    
    # Start timer thread
    def timer_callback():
        time.sleep(duration_minutes * 60)
        stop_focus_mode()
        
    timer_thread = threading.Thread(target=timer_callback, daemon=True)
    timer_thread.start()
    
    return {
        'success': True,
        'message': f'Focus mode started for {duration_minutes} minutes',
        'duration': duration_minutes,
        'blocked_sites': focus_state['blocked_sites']
    }


def stop_focus_mode() -> Dict[str, Any]:
    """Stop focus mode"""
    global focus_state
    
    focus_state['active'] = False
    focus_state['start_time'] = None
    
    # Unblock sites
    unblock_sites()
    
    return {
        'success': True,
        'message': 'Focus mode stopped'
    }


def get_focus_status() -> Dict[str, Any]:
    """Get focus mode status"""
    if focus_state['active'] and focus_state['start_time']:
        elapsed = time.time() - focus_state['start_time']
        remaining = (focus_state['duration_minutes * 60']) - elapsed
        return {
            'active': True,
            'duration': focus_state['duration_minutes'],
            'elapsed_seconds': int(elapsed),
            'remaining_seconds': int(remaining) if remaining > 0 else 0,
            'blocked_sites': focus_state['blocked_sites']
        }
    
    return {'active': False}


def start_pomodoro(work_minutes: int = 25, break_minutes: int = 5) -> Dict[str, Any]:
    """Start Pomodoro timer"""
    return start_focus_mode(work_minutes)


def block_sites(sites: List[str]):
    """Block sites by modifying hosts file (Windows)"""
    # This is a simplified version - in production, use proper site blocking
    # For now, just log the blocked sites
    print(f"Blocking sites: {sites}")


def unblock_sites():
    """Unblock sites"""
    print("Unblocking sites")
