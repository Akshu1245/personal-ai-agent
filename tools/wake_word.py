"""
JARVIS Wake Word Module
Detect "Hey JARVIS" wake word

Author: Rashi AI
Built for: Akshay
"""

import threading
import time
from typing import Dict, Any, Callable, Optional

# Try to import openWakeWord
try:
    import openwakeword
    from openwakeword.model import Model
    WAKEWORD_AVAILABLE = True
except ImportError:
    WAKEWORD_AVAILABLE = False


class WakeWordDetector:
    """Wake word detection handler"""
    
    def __init__(self, wake_word: str = 'hey jarvis'):
        self.wake_word = wake_word.lower()
        self.model = None
        self.is_listening = False
        self.callback: Optional[Callable] = None
        self.thread = None
        
    def load_model(self):
        """Load wake word model"""
        if not WAKEWORD_AVAILABLE:
            return False
            
        try:
            # Load default models
            self.model = Model( wakeword_ids=['hey_jarvis'])
            return True
        except:
            return False
    
    def start(self, callback: Callable = None) -> Dict[str, Any]:
        """
        Start listening for wake word
        
        Args:
            callback: Function to call when wake word detected
            
        Returns:
            Dict with result
        """
        if not WAKEWORD_AVAILABLE:
            return {
                'success': False,
                'error': 'openWakeWord not installed'
            }
        
        if self.is_listening:
            return {
                'success': False,
                'error': 'Already listening'
            }
        
        self.callback = callback
        self.is_listening = True
        
        # Start detection thread
        self.thread = threading.Thread(target=self._detect_loop, daemon=True)
        self.thread.start()
        
        return {
            'success': True,
            'message': 'Listening for wake word...'
        }
    
    def stop(self) -> Dict[str, Any]:
        """Stop listening"""
        self.is_listening = False
        if self.thread:
            self.thread.join(timeout=2)
        
        return {
            'success': True,
            'message': 'Stopped listening'
        }
    
    def _detect_loop(self):
        """Detection loop (simplified)"""
        # Note: Full implementation would use microphone streaming
        # This is a placeholder
        pass


# Singleton
_detector = None

def get_detector() -> WakeWordDetector:
    """Get wake word detector singleton"""
    global _detector
    if _detector is None:
        _detector = WakeWordDetector()
    return _detector


def start_listening(callback: Callable = None) -> Dict[str, Any]:
    """Start wake word detection"""
    detector = get_detector()
    return detector.start(callback)


def stop_listening() -> Dict[str, Any]:
    """Stop wake word detection"""
    detector = get_detector()
    return detector.stop()


# Simple version using SpeechRecognition as fallback
def listen_for_wake_word_simple(wake_word: str = 'jarvis', timeout: int = 10) -> bool:
    """
    Simple wake word detection using SpeechRecognition
    
    Args:
        wake_word: Word to listen for
        timeout: Timeout in seconds
        
    Returns:
        True if wake word detected
    """
    try:
        import speech_recognition as sr
        
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source)
            print(f"Listening for '{wake_word}'...")
            audio = recognizer.listen(source, timeout=timeout)
        
        # Use Google Speech Recognition
        text = recognizer.recognize_google(audio).lower()
        return wake_word.lower() in text
        
    except Exception as e:
        print(f"Wake word detection error: {e}")
        return False
