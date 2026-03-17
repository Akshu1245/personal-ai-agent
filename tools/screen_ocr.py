"""
JARVIS Screen OCR Module
Read text from screenshots using Tesseract

Author: Rashi AI
Built for: Akshay
"""

import pytesseract
from PIL import Image
import pyautogui
from pathlib import Path
from typing import Dict, Any, Optional

# Try to import, handle if not available
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def capture_and_read(x: int = None, y: int = None, width: int = None, height: int = None) -> Dict[str, Any]:
    """
    Capture screen region and read text
    
    Args:
        x, y, width, height: Region to capture (optional - captures full screen if not provided)
        
    Returns:
        Dict with extracted text
    """
    if not TESSERACT_AVAILABLE:
        return {'success': False, 'error': 'pytesseract not installed'}
    
    try:
        # Take screenshot
        screenshot = pyautogui.screenshot()
        
        # Crop if coordinates provided
        if x is not None and y is not None and width is not None and height is not None:
            screenshot = screenshot.crop((x, y, x + width, y + height))
        
        # Extract text
        text = pytesseract.image_to_string(screenshot)
        
        return {
            'success': True,
            'text': text.strip(),
            'length': len(text)
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def read_image(image_path: str) -> Dict[str, Any]:
    """
    Read text from an image file
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dict with extracted text
    """
    if not TESSERACT_AVAILABLE:
        return {'success': False, 'error': 'pytesseract not installed'}
    
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        
        return {
            'success': True,
            'text': text.strip(),
            'path': image_path
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def capture_region(x: int, y: int, width: int, height: int, save_path: str = None) -> Dict[str, Any]:
    """
    Capture a specific screen region
    
    Args:
        x, y: Top-left corner
        width, height: Region dimensions
        save_path: Path to save screenshot
        
    Returns:
        Dict with screenshot path
    """
    try:
        screenshot = pyautogui.screenshot()
        cropped = screenshot.crop((x, y, x + width, y + height))
        
        if save_path is None:
            from datetime import datetime
            save_path = f'screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        
        cropped.save(save_path)
        
        return {
            'success': True,
            'path': save_path
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
