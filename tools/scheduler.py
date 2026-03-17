"""
JARVIS Scheduler Module
Daily briefings and reminders

Author: Rashi AI
Built for: Akshay
"""

import time
import threading
import schedule
from datetime import datetime
from typing import Dict, Any, List

# Scheduler state
scheduler_running = False
reminders: List[Dict] = []


def start_scheduler():
    """Start the scheduler background thread"""
    global scheduler_running
    
    def run_schedule():
        while scheduler_running:
            schedule.run_pending()
            time.sleep(1)
    
    scheduler_running = True
    thread = threading.Thread(target=run_schedule, daemon=True)
    thread.start()
    
    # Schedule daily briefing at 9 AM
    schedule.every().day.at("09:00").do(daily_briefing)
    
    print("Scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    global scheduler_running
    scheduler_running = False


def set_reminder(message: str, time_str: str = None) -> Dict[str, Any]:
    """
    Set a reminder
    
    Args:
        message: Reminder message
        time_str: Time in HH:MM format (optional)
        
    Returns:
        Dict with success status
    """
    if time_str:
        try:
            schedule.every().day.at(time_str).do(print_reminder, message=message)
            return {
                'success': True,
                'message': f'Reminder set for {time_str}: {message}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    else:
        # Just log for now
        return {
            'success': True,
            'message': f'Reminder noted: {message}'
        }


def print_reminder(message: str):
    """Print reminder"""
    print(f"🔔 REMINDER: {message}")


def set_timer(minutes: int) -> Dict[str, Any]:
    """
    Set a timer
    
    Args:
        minutes: Minutes to wait
        
    Returns:
        Dict with success status
    """
    def timer_done():
        print(f"⏰ Timer complete: {minutes} minutes")
        
    schedule.every(minutes).minutes.do(timer_done)
    
    return {
        'success': True,
        'message': f'Timer set for {minutes} minutes'
    }


def daily_briefing():
    """Run daily briefing"""
    from core.memory import get_memory
    from core.context import get_context_manager
    
    memory = get_memory()
    ctx = get_context_manager()
    
    # Get tasks
    tasks = memory.get_tasks(completed=False)
    
    # Get active projects
    projects = ctx.get_active_projects()
    
    # Format briefing
    briefing = "Good morning, Akshay! Here's your daily briefing.\n"
    
    if tasks:
        briefing += f"\n📋 You have {len(tasks)} pending tasks:\n"
        for task in tasks[:5]:
            briefing += f"  - {task['title']}\n"
    
    if projects:
        briefing += f"\n🚀 Active projects: {', '.join([p['name'] for p in projects[:3]])}"
    
    print(briefing)
    return briefing


def get_schedule() -> Dict[str, Any]:
    """Get scheduled jobs"""
    jobs = []
    for job in schedule.jobs:
        jobs.append({
            'job_func': str(job.job_func),
            'next_run': str(job.next_run) if job.next_run else None
        })
    
    return {
        'success': True,
        'jobs': jobs,
        'pending_count': len(jobs)
    }
