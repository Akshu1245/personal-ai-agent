"""
JARVIS System Info Module
CPU, RAM, battery, GPU info

Author: Rashi AI
Built for: Akshay
"""

import platform
from typing import Dict, Any

# Try to import psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_system_info() -> Dict[str, Any]:
    """
    Get system information
    
    Returns:
        Dict with system info
    """
    info = {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'platform_release': platform.release(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'hostname': platform.node(),
    }
    
    if PSUTIL_AVAILABLE:
        # CPU info
        info['cpu'] = {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'usage_percent': psutil.cpu_percent(interval=1),
            'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        }
        
        # Memory info
        mem = psutil.virtual_memory()
        info['memory'] = {
            'total_gb': round(mem.total / (1024**3), 2),
            'available_gb': round(mem.available / (1024**3), 2),
            'used_gb': round(mem.used / (1024**3), 2),
            'percent': mem.percent
        }
        
        # Disk info
        disk = psutil.disk_usage('/')
        info['disk'] = {
            'total_gb': round(disk.total / (1024**3), 2),
            'used_gb': round(disk.used / (1024**3), 2),
            'free_gb': round(disk.free / (1024**3), 2),
            'percent': disk.percent
        }
        
        # Battery info (if available)
        try:
            battery = psutil.sensors_battery()
            if battery:
                info['battery'] = {
                    'percent': battery.percent,
                    'charging': battery.power_plugged
                }
        except:
            pass
        
        # Network
        info['network'] = {
            'connections': len(psutil.net_connections())
        }
    
    return info


def get_cpu_usage() -> Dict[str, Any]:
    """Get CPU usage"""
    if not PSUTIL_AVAILABLE:
        return {'error': 'psutil not available'}
        
    return {
        'usage_percent': psutil.cpu_percent(interval=1),
        'per_cpu': psutil.cpu_percent(interval=1, percpu=True)
    }


def get_memory_usage() -> Dict[str, Any]:
    """Get memory usage"""
    if not PSUTIL_AVAILABLE:
        return {'error': 'psutil not available'}
        
    mem = psutil.virtual_memory()
    return {
        'total_gb': round(mem.total / (1024**3), 2),
        'available_gb': round(mem.available / (1024**3), 2),
        'used_gb': round(mem.used / (1024**3), 2),
        'percent': mem.percent
    }


def get_battery_status() -> Dict[str, Any]:
    """Get battery status"""
    if not PSUTIL_AVAILABLE:
        return {'error': 'psutil not available'}
        
    try:
        battery = psutil.sensors_battery()
        if battery:
            return {
                'percent': battery.percent,
                'charging': battery.power_plugged,
                'time_left_minutes': battery.secsleft / 60 if battery.secsleft > 0 else None
            }
    except:
        pass
    
    return {'error': 'Battery info not available'}
