"""
JARVIS File Operations Module
File/folder CRUD operations

Author: Rashi AI
Built for: Akshay
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional


# ==================== FILE OPERATIONS ====================

def read_file(file_path: str) -> Dict[str, Any]:
    """
    Read a file's contents
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dict with file contents
    """
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {'success': False, 'error': 'File not found'}
            
        if path.is_dir():
            return {'success': False, 'error': 'Path is a directory'}
            
        # Read file
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return {
            'success': True,
            'content': content,
            'path': str(path),
            'size': path.stat().st_size,
            'lines': len(content.splitlines())
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def write_file(file_path: str, content: str, append: bool = False) -> Dict[str, Any]:
    """
    Write content to a file
    
    Args:
        file_path: Path to the file
        content: Content to write
        append: Append to file instead of overwriting
        
    Returns:
        Dict with success status
    """
    try:
        path = Path(file_path).resolve()
        
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
            
        return {
            'success': True,
            'message': f'{"Appended to" if append else "Written to"} {path}',
            'path': str(path),
            'size': path.stat().st_size
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_file(file_path: str, force: bool = False) -> Dict[str, Any]:
    """
    Delete a file or folder
    
    Args:
        file_path: Path to delete
        force: Skip confirmation for system files
        
    Returns:
        Dict with success status
    """
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {'success': False, 'error': 'Path not found'}
            
        # Safety check - don't delete system directories
        system_paths = ['C:\\Windows', '/System', '/bin', '/usr']
        if not force and any(str(path).startswith(sp) for sp in system_paths):
            return {'success': False, 'error': 'Cannot delete system paths'}
            
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
            
        return {
            'success': True,
            'message': f'Deleted {path}'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def move_file(source: str, destination: str) -> Dict[str, Any]:
    """
    Move or rename a file/folder
    
    Args:
        source: Source path
        destination: Destination path
        
    Returns:
        Dict with success status
    """
    try:
        src_path = Path(source).resolve()
        dst_path = Path(destination).resolve()
        
        if not src_path.exists():
            return {'success': False, 'error': 'Source not found'}
            
        # Create parent directories if needed
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move
        shutil.move(str(src_path), str(dst_path))
        
        return {
            'success': True,
            'message': f'Moved {src_path} to {dst_path}',
            'new_path': str(dst_path)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def copy_file(source: str, destination: str) -> Dict[str, Any]:
    """
    Copy a file or folder
    
    Args:
        source: Source path
        destination: Destination path
        
    Returns:
        Dict with success status
    """
    try:
        src_path = Path(source).resolve()
        dst_path = Path(destination).resolve()
        
        if not src_path.exists():
            return {'success': False, 'error': 'Source not found'}
            
        # Create parent directories if needed
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy
        if src_path.is_file():
            shutil.copy2(str(src_path), str(dst_path))
        elif src_path.is_dir():
            shutil.copytree(str(src_path), str(dst_path), dirs_exist_ok=True)
        
        return {
            'success': True,
            'message': f'Copied {src_path} to {dst_path}',
            'new_path': str(dst_path)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== FOLDER OPERATIONS ====================

def create_folder(folder_path: str) -> Dict[str, Any]:
    """
    Create a folder
    
    Args:
        folder_path: Path to create
        
    Returns:
        Dict with success status
    """
    try:
        path = Path(folder_path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        
        return {
            'success': True,
            'message': f'Created folder {path}',
            'path': str(path)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def list_files(folder_path: str = '.', pattern: str = '*', recursive: bool = False) -> Dict[str, Any]:
    """
    List files in a folder
    
    Args:
        folder_path: Path to list
        pattern: File pattern (glob)
        recursive: Search recursively
        
    Returns:
        Dict with file list
    """
    try:
        path = Path(folder_path).resolve()
        
        if not path.exists():
            return {'success': False, 'error': 'Folder not found'}
            
        if not path.is_dir():
            return {'success': False, 'error': 'Path is not a directory'}
            
        # Get files
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))
            
        # Format results
        results = []
        for f in files:
            stat = f.stat()
            results.append({
                'name': f.name,
                'path': str(f),
                'is_dir': f.is_dir(),
                'size': stat.st_size,
                'modified': stat.st_mtime
            })
            
        return {
            'success': True,
            'path': str(path),
            'count': len(results),
            'files': results
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==================== FILE INFO ====================

def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get file/folder information"""
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {'success': False, 'error': 'Path not found'}
            
        stat = path.stat()
        
        return {
            'success': True,
            'name': path.name,
            'path': str(path),
            'is_dir': path.is_dir(),
            'is_file': path.is_file(),
            'size': stat.st_size,
            'created': stat.st_ctime,
            'modified': stat.st_mtime,
            'extension': path.suffix
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def search_files(folder_path: str, query: str) -> Dict[str, Any]:
    """Search for files by name"""
    try:
        path = Path(folder_path).resolve()
        
        if not path.exists():
            return {'success': False, 'error': 'Folder not found'}
            
        # Search recursively
        query_lower = query.lower()
        results = []
        
        for f in path.rglob('*'):
            if query_lower in f.name.lower():
                results.append({
                    'name': f.name,
                    'path': str(f),
                    'is_dir': f.is_dir()
                })
                
        return {
            'success': True,
            'query': query,
            'count': len(results),
            'results': results[:50]  # Limit results
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
