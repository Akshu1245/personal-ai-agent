"""
JARVIS GPU Monitor Module
Monitor NVIDIA RTX 3050 GPU

Author: Rashi AI
Built for: Akshay
"""

import subprocess
import re
from typing import Dict, Any, Optional, List

# Try to import GPUtil
try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False


def get_gpu_info() -> Dict[str, Any]:
    """
    Get GPU information
    
    Returns:
        Dict with GPU info
    """
    # Try nvidia-smi first (most reliable on Windows)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = [p.strip() for p in output.split(',')]
                if len(parts) >= 6:
                    return {
                        'success': True,
                        'name': parts[0],
                        'memory_total_mb': int(parts[1]),
                        'memory_used_mb': int(parts[2]),
                        'memory_free_mb': int(parts[3]),
                        'utilization_percent': int(parts[4]),
                        'temperature_c': int(parts[5]),
                        'memory_percent': round(int(parts[2]) / int(parts[1]) * 100, 1)
                    }
    except:
        pass
    
    # Fallback to GPUtil
    if GPUTIL_AVAILABLE:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                return {
                    'success': True,
                    'name': gpu.name,
                    'memory_total_mb': gpu.memoryTotal,
                    'memory_used_mb': gpu.memoryUsed,
                    'memory_free_mb': gpu.memoryFree,
                    'utilization_percent': gpu.load * 100,
                    'temperature_c': gpu.temperature,
                    'memory_percent': (gpu.memoryUsed / gpu.memoryTotal) * 100
                }
        except:
            pass
    
    return {
        'success': False,
        'error': 'Could not get GPU info. Install nvidia-smi or GPUtil.'
    }


def get_gpu_usage() -> Dict[str, Any]:
    """Get GPU utilization percentage"""
    info = get_gpu_info()
    if info.get('success'):
        return {
            'success': True,
            'utilization': info['utilization_percent'],
            'memory': info['memory_percent'],
            'temperature': info['temperature_c']
        }
    return info


def is_gpu_available() -> bool:
    """Check if GPU is available"""
    info = get_gpu_info()
    return info.get('success', False)
