"""
============================================================
AKSHAY AI CORE — System Control Plugin
============================================================
OS-level control and automation for system management.
============================================================
"""

import os
import platform
import subprocess
from typing import Any, Dict, List, Optional
from pathlib import Path

from plugins.base import BuiltinPlugin, PluginMetadata, PluginConfig
from core.utils.logger import get_logger

logger = get_logger("plugin.system_control")


class SystemControlPlugin(BuiltinPlugin):
    """
    System control plugin for OS-level operations.
    
    Commands:
    - run_command: Execute a shell command
    - get_system_info: Get system information
    - list_processes: List running processes
    - kill_process: Terminate a process
    - file_operations: File system operations
    - open_application: Open an application
    """
    
    metadata = PluginMetadata(
        name="system_control",
        version="1.0.0",
        description="OS-level control and system management",
        author="AKSHAY AI CORE",
        tags=["system", "os", "control", "automation"],
    )
    
    config = PluginConfig(
        enabled=True,
        sandboxed=True,
        max_execution_time=60,
        permissions=["system:control", "file:read", "file:write"],
        settings={
            "allowed_commands": [],  # Empty = all allowed (in dev)
            "blocked_commands": ["rm -rf /", "format", "del /s /q"],
            "max_output_size": 100000,
        },
    )
    
    async def on_load(self) -> None:
        """Initialize system control plugin."""
        self.register_command("run_command", self._cmd_run_command, "Execute shell command")
        self.register_command("get_system_info", self._cmd_system_info, "Get system information")
        self.register_command("list_processes", self._cmd_list_processes, "List running processes")
        self.register_command("kill_process", self._cmd_kill_process, "Terminate a process")
        self.register_command("file_operations", self._cmd_file_ops, "File system operations")
        self.register_command("open_application", self._cmd_open_app, "Open an application")
        
        self._system = platform.system().lower()
        logger.info(f"System control plugin loaded (OS: {self._system})")
    
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a system control command."""
        return await self.dispatch_command(command, params)
    
    def _is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed to execute."""
        blocked = self.config.settings.get("blocked_commands", [])
        
        for blocked_cmd in blocked:
            if blocked_cmd.lower() in command.lower():
                return False
        
        allowed = self.config.settings.get("allowed_commands", [])
        if allowed:
            return any(cmd.lower() in command.lower() for cmd in allowed)
        
        return True
    
    async def _cmd_run_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command."""
        command = params.get("command")
        if not command:
            return {"status": "error", "error": "Command required"}
        
        if not self._is_command_allowed(command):
            return {"status": "error", "error": "Command not allowed"}
        
        timeout = params.get("timeout", 30)
        cwd = params.get("cwd")
        
        try:
            if self._system == "windows":
                shell = True
            else:
                shell = True
            
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            
            max_output = self.config.settings.get("max_output_size", 100000)
            stdout = result.stdout[:max_output] if result.stdout else ""
            stderr = result.stderr[:max_output] if result.stderr else ""
            
            return {
                "status": "success",
                "return_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_system_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get system information."""
        import psutil
        
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "status": "success",
            "data": {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "python_version": platform.python_version(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "count_logical": psutil.cpu_count(logical=True),
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": round(disk.percent, 2),
                },
            },
        }
    
    async def _cmd_list_processes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List running processes."""
        import psutil
        
        limit = params.get("limit", 50)
        sort_by = params.get("sort_by", "memory")  # memory, cpu, name
        filter_name = params.get("filter")
        
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                
                if filter_name and filter_name.lower() not in info['name'].lower():
                    continue
                
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu_percent": info['cpu_percent'],
                    "memory_percent": round(info['memory_percent'], 2),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort
        if sort_by == "memory":
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
        elif sort_by == "cpu":
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        else:
            processes.sort(key=lambda x: x['name'].lower())
        
        return {
            "status": "success",
            "processes": processes[:limit],
            "total": len(processes),
        }
    
    async def _cmd_kill_process(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Terminate a process."""
        import psutil
        
        pid = params.get("pid")
        name = params.get("name")
        
        if not pid and not name:
            return {"status": "error", "error": "PID or process name required"}
        
        killed = []
        
        try:
            if pid:
                proc = psutil.Process(pid)
                proc.terminate()
                killed.append(pid)
            elif name:
                for proc in psutil.process_iter(['pid', 'name']):
                    if name.lower() in proc.info['name'].lower():
                        proc.terminate()
                        killed.append(proc.info['pid'])
            
            return {
                "status": "success",
                "killed_pids": killed,
            }
            
        except psutil.NoSuchProcess:
            return {"status": "error", "error": "Process not found"}
        except psutil.AccessDenied:
            return {"status": "error", "error": "Access denied"}
    
    async def _cmd_file_ops(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """File system operations."""
        operation = params.get("operation")
        path = params.get("path")
        
        if not operation:
            return {"status": "error", "error": "Operation required"}
        
        if operation == "list":
            target = Path(path) if path else Path.cwd()
            if not target.exists():
                return {"status": "error", "error": "Path not found"}
            
            items = []
            for item in target.iterdir():
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None,
                })
            
            return {"status": "success", "path": str(target), "items": items}
        
        elif operation == "read":
            if not path:
                return {"status": "error", "error": "Path required"}
            
            file_path = Path(path)
            if not file_path.exists():
                return {"status": "error", "error": "File not found"}
            
            content = file_path.read_text()
            return {"status": "success", "path": str(file_path), "content": content}
        
        elif operation == "write":
            if not path:
                return {"status": "error", "error": "Path required"}
            
            content = params.get("content", "")
            file_path = Path(path)
            file_path.write_text(content)
            
            return {"status": "success", "path": str(file_path), "written": True}
        
        elif operation == "delete":
            if not path:
                return {"status": "error", "error": "Path required"}
            
            file_path = Path(path)
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                import shutil
                shutil.rmtree(file_path)
            else:
                return {"status": "error", "error": "Path not found"}
            
            return {"status": "success", "deleted": str(file_path)}
        
        return {"status": "error", "error": f"Unknown operation: {operation}"}
    
    async def _cmd_open_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Open an application."""
        app = params.get("application")
        if not app:
            return {"status": "error", "error": "Application required"}
        
        try:
            if self._system == "windows":
                os.startfile(app)
            elif self._system == "darwin":  # macOS
                subprocess.run(["open", app])
            else:  # Linux
                subprocess.run(["xdg-open", app])
            
            return {"status": "success", "opened": app}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
