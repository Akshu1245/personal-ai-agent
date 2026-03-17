"""
JARVIS Voice Output Module
Text-to-speech engine

Author: Rashi AI
Built for: Akshay
"""

import os
import threading
from typing import Optional

# Try to import TTS libraries
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False


class VoiceOutput:
    """JARVIS Voice Output Handler"""
    
    def __init__(self, engine: str = 'pyttsx3', rate: int = 150, volume: float = 1.0):
        self.engine_type = engine
        self.rate = rate
        self.volume = volume
        self.engine = None
        self.coqui_tts = None
        self.is_speaking = False
        
        # Initialize engine
        self._init_engine()
        
    def _init_engine(self):
        """Initialize TTS engine"""
        if self.engine_type == 'pyttsx3' and PYTTSX3_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', self.rate)
                self.engine.setProperty('volume', self.volume)
                print("pyttsx3 engine initialized")
            except Exception as e:
                print(f"Failed to init pyttsx3: {e}")
                self.engine = None
                
        elif self.engine_type == 'coqui' and COQUI_AVAILABLE:
            try:
                # Use single speaker model
                self.coqui_tts = TTS(model_path="coqui/tts/models--multilingual--multi-speaker--XTTS_v1", gpu=False)
                print("Coqui TTS initialized")
            except Exception as e:
                print(f"Failed to init Coqui: {e}")
                self.coqui_tts = None
                
    def speak(self, text: str, async_mode: bool = True):
        """
        Speak text
        
        Args:
            text: Text to speak
            async_mode: Speak asynchronously
        """
        if async_mode:
            thread = threading.Thread(target=self._speak, args=(text,))
            thread.daemon = True
            thread.start()
        else:
            self._speak(text)
            
    def _speak(self, text: str):
        """Internal speak method"""
        self.is_speaking = True
        
        try:
            if self.engine_type == 'pyttsx3' and self.engine:
                self.engine.say(text)
                self.engine.runAndWait()
                
            elif self.engine_type == 'coqui' and self.coqui_tts:
                # Generate speech
                self.coqui_tts.tts_to_file(
                    text=text,
                    file_path="output.wav",
                    speaker="Ana Florence",
                    language="en"
                )
                # Play audio (platform specific)
                import playsound
                playsound.playsound("output.wav")
                os.remove("output.wav")
                
            else:
                # Fallback - just print
                print(f"[JARVIS]: {text}")
                
        except Exception as e:
            print(f"TTS error: {e}")
            # Fallback to print
            print(f"[JARVIS]: {text}")
            
        finally:
            self.is_speaking = False
            
    def stop(self):
        """Stop speaking"""
        if self.engine:
            self.engine.stop()
        self.is_speaking = False
        
    def set_rate(self, rate: int):
        """Set speech rate"""
        self.rate = rate
        if self.engine:
            self.engine.setProperty('rate', rate)
            
    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)"""
        self.volume = volume
        if self.engine:
            self.engine.setProperty('volume', volume)
            
    def get_voices(self):
        """Get available voices"""
        if self.engine:
            return self.engine.getProperty('voices')
        return []


# Singleton
_voice_output = None

def get_voice_output() -> VoiceOutput:
    """Get voice output singleton"""
    global _voice_output
    if _voice_output is None:
        _voice_output = VoiceOutput()
    return _voice_output


def speak(text: str, async_mode: bool = True):
    """Convenience function to speak text"""
    voice = get_voice_output()
    voice.speak(text, async_mode)
