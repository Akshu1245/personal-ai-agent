"""
JARVIS Voice Input Module
Whisper-based speech-to-text

Author: Rashi AI
Built for: Akshay
"""

import os
import io
import tempfile
from typing import Optional, Dict, Any

# Try to import whisper, fallback to speech_recognition
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False


class VoiceInput:
    """JARVIS Voice Input Handler"""
    
    def __init__(self, model: str = 'base'):
        self.model_name = model
        self.recognizer = None
        self.microphone = None
        self.whisper_model = None
        
        # Initialize
        self._init_whisper()
        self._init_speech_recognition()
        
    def _init_whisper(self):
        """Initialize Whisper model"""
        if WHISPER_AVAILABLE:
            try:
                # Use base model for speed
                self.whisper_model = whisper.load_model(self.model_name)
                print(f"Whisper model '{self.model_name}' loaded")
            except Exception as e:
                print(f"Failed to load Whisper: {e}")
                self.whisper_model = None
                
    def _init_speech_recognition(self):
        """Initialize speech recognition"""
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                # Calibrate for ambient noise
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source)
                print("Speech recognition initialized")
            except Exception as e:
                print(f"Failed to initialize microphone: {e}")
                self.recognizer = None
                self.microphone = None
                
    def transcribe_file(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe an audio file
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dict with transcription
        """
        if not WHISPER_AVAILABLE:
            return {'success': False, 'error': 'Whisper not available'}
            
        try:
            result = self.whisper_model.transcribe(audio_path)
            return {
                'success': True,
                'text': result['text'].strip(),
                'language': result.get('language', 'unknown')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def transcribe_microphone(self, duration: int = 5) -> Dict[str, Any]:
        """
        Transcribe microphone input
        
        Args:
            duration: Recording duration in seconds
            
        Returns:
            Dict with transcription
        """
        if not SPEECH_RECOGNITION_AVAILABLE:
            return {'success': False, 'error': 'Speech recognition not available'}
            
        if not self.microphone or not self.recognizer:
            return {'success': False, 'error': 'Microphone not initialized'}
            
        try:
            with self.microphone as source:
                print(f"Listening for {duration} seconds...")
                audio = self.recognizer.listen(source, timeout=duration)
                
            # Try Whisper first if available
            if self.whisper_model:
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                    temp_path = f.name
                    
                # Note: Would need to save audio data here
                # For now, use Google Speech Recognition as fallback
                
            # Use Google Speech Recognition
            text = self.recognizer.recognize_google(audio)
            
            return {
                'success': True,
                'text': text
            }
        except sr.WaitTimeoutError:
            return {'success': False, 'error': 'Timeout - no speech detected'}
        except sr.UnknownValueError:
            return {'success': False, 'error': 'Could not understand audio'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def listen_for_wake_word(self, wake_word: str = 'jarvis') -> bool:
        """
        Listen for wake word
        
        Args:
            wake_word: Word to listen for
            
        Returns:
            True if wake word detected
        """
        # This is a simplified version - in production,
        # you'd use a proper wake word detection library
        if not SPEECH_RECOGNITION_AVAILABLE:
            return False
            
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5)
                
            text = self.recognizer.recognize_google(audio).lower()
            return wake_word.lower() in text
            
        except:
            return False


# Singleton
_voice_input = None

def get_voice_input() -> VoiceInput:
    """Get voice input singleton"""
    global _voice_input
    if _voice_input is None:
        _voice_input = VoiceInput()
    return _voice_input
