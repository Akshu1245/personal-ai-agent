"""
JARVIS GitHub Operations Module
Git automation using GitPython

Author: Rashi AI
Built for: Akshay
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

# Try to import GitPython
try:
    import git
    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False


def get_repo(path: str = '.') -> Optional[Any]:
    """Get git repository"""
    if not GITPYTHON_AVAILABLE:
        return None
    
    try:
        return git.Repo(path)
    except:
        return None


def commit(message: str, path: str = '.') -> Dict[str, Any]:
    """
    Commit changes to git
    
    Args:
        message: Commit message
        path: Repository path
        
    Returns:
        Dict with commit result
    """
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        # Stage all changes
        repo.git.add(A=True)
        
        # Commit
        commit = repo.index.commit(message)
        
        return {
            'success': True,
            'message': f'Committed: {message[:50]}...',
            'commit_hash': str(commit)[:8]
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def push(path: str = '.', remote: str = 'origin', branch: str = None) -> Dict[str, Any]:
    """
    Push to remote
    
    Args:
        path: Repository path
        remote: Remote name
        branch: Branch name (optional)
        
    Returns:
        Dict with push result
    """
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        # Get current branch if not specified
        if branch is None:
            branch = repo.active_branch.name
            
        # Push
        origin = repo.remote(remote)
        result = origin.push(branch)
        
        return {
            'success': True,
            'message': f'Pushed to {remote}/{branch}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def pull(path: str = '.', remote: str = 'origin', branch: str = None) -> Dict[str, Any]:
    """
    Pull from remote
    
    Args:
        path: Repository path
        remote: Remote name
        branch: Branch name (optional)
        
    Returns:
        Dict with pull result
    """
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        if branch is None:
            branch = repo.active_branch.name
            
        origin = repo.remote(remote)
        result = origin.pull(branch)
        
        return {
            'success': True,
            'message': f'Pulled from {remote}/{branch}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_status(path: str = '.') -> Dict[str, Any]:
    """
    Get git status
    
    Args:
        path: Repository path
        
    Returns:
        Dict with status
    """
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        status = repo.git.status()
        
        return {
            'success': True,
            'status': status
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_diff(path: str = '.') -> Dict[str, Any]:
    """Get uncommitted changes"""
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        diff = repo.git.diff()
        
        return {
            'success': True,
            'diff': diff
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def create_branch(branch_name: str, path: str = '.') -> Dict[str, Any]:
    """Create a new branch"""
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        
        return {
            'success': True,
            'message': f'Created and switched to branch: {branch_name}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def switch_branch(branch_name: str, path: str = '.') -> Dict[str, Any]:
    """Switch to a branch"""
    if not GITPYTHON_AVAILABLE:
        return {'success': False, 'error': 'GitPython not installed'}
    
    try:
        repo = get_repo(path)
        if not repo:
            return {'success': False, 'error': 'Not a git repository'}
        
        repo.git.checkout(branch_name)
        
        return {
            'success': True,
            'message': f'Switched to branch: {branch_name}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
