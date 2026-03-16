"""
============================================================
AKSHAY AI CORE — Voice Interface Package
============================================================
Voice input/output with wake word detection.
============================================================
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from core.config import settings
from core.utils.logger import get_logger

if TYPE_CHECKING:
    import pvporcupine

logger = get_logger("voice")


class VoiceState(str, Enum):
    """Voice interface states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class VoiceConfig:
    """Voice interface configuration."""
    wake_word: str = "hey akshay"
    language: str = "en-US"
    voice_id: str = "default"
    speech_rate: float = 1.0
    volume: float = 1.0
    listen_timeout: int = 10
    silence_threshold: float = 0.3


class VoiceInterface:
    """
    Voice interface for AKSHAY AI CORE.
    
    Features:
    - Wake word detection
    - Speech-to-text (STT)
    - Text-to-speech (TTS)
    - Voice activity detection
    - Multi-language support
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._state = VoiceState.IDLE
        self._stt_engine = None
        self._tts_engine = None
        self._wake_word_detector = None
        self._callback: Optional[Callable] = None
        self._running = False
    
    async def initialize(self) -> None:
        """Initialize voice components."""
        # Initialize STT (Speech-to-Text)
        try:
            import speech_recognition as sr
            self._stt_engine = sr.Recognizer()
            self._microphone = sr.Microphone()
            logger.info("STT engine initialized")
        except ImportError:
            logger.warning("speech_recognition not available")
        
        # Initialize TTS (Text-to-Speech)
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty('rate', int(150 * self.config.speech_rate))
            self._tts_engine.setProperty('volume', self.config.volume)
            logger.info("TTS engine initialized")
        except ImportError:
            logger.warning("pyttsx3 not available")
        
        # Initialize wake word detector
        try:
            # Using pvporcupine for wake word detection
            import pvporcupine
            # Note: Requires API key and wake word file
            logger.info("Wake word detector available")
        except ImportError:
            logger.warning("pvporcupine not available, wake word detection disabled")
    
    async def start(self, callback: Callable[[str], None]) -> None:
        """
        Start listening for voice input.
        
        Args:
            callback: Function to call with transcribed text
        """
        self._callback = callback
        self._running = True
        
        logger.info("Voice interface started")
        
        while self._running:
            try:
                # Wait for wake word
                if self._state == VoiceState.IDLE:
                    detected = await self._detect_wake_word()
                    if detected:
                        self._state = VoiceState.LISTENING
                        await self.speak("Yes?")
                
                # Listen for command
                if self._state == VoiceState.LISTENING:
                    text = await self.listen()
                    if text:
                        self._state = VoiceState.PROCESSING
                        if self._callback:
                            self._callback(text)
                    self._state = VoiceState.IDLE
                    
            except Exception as e:
                logger.error("Voice interface error", error=str(e))
                await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the voice interface."""
        self._running = False
        self._state = VoiceState.IDLE
        logger.info("Voice interface stopped")
    
    async def listen(self, timeout: Optional[int] = None) -> Optional[str]:
        """
        Listen for speech and transcribe.
        
        Args:
            timeout: Listen timeout in seconds
            
        Returns:
            Transcribed text or None
        """
        if not self._stt_engine:
            return None
        
        timeout = timeout or self.config.listen_timeout
        
        try:
            import speech_recognition as sr
            
            with self._microphone as source:
                self._stt_engine.adjust_for_ambient_noise(source, duration=0.5)
                
                logger.debug("Listening...")
                audio = self._stt_engine.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=15,
                )
            
            # Transcribe with Google STT
            text = self._stt_engine.recognize_google(
                audio,
                language=self.config.language,
            )
            
            logger.info(f"Transcribed: {text}")
            return text
            
        except Exception as e:
            logger.warning(f"STT failed: {e}")
            return None
    
    async def speak(self, text: str) -> None:
        """
        Convert text to speech.
        
        Args:
            text: Text to speak
        """
        if not self._tts_engine:
            logger.warning("TTS not available")
            return
        
        self._state = VoiceState.SPEAKING
        
        try:
            # Run TTS in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._tts_engine.say,
                text,
            )
            await loop.run_in_executor(
                None,
                self._tts_engine.runAndWait,
            )
            
            logger.debug(f"Spoke: {text[:50]}...")
            
        except Exception as e:
            logger.error(f"TTS failed: {e}")
        finally:
            self._state = VoiceState.IDLE
    
    async def _detect_wake_word(self) -> bool:
        """
        Detect wake word.
        
        Returns:
            True if wake word detected
        """
        # Simple wake word detection using STT
        # In production, use dedicated wake word engine (Porcupine, Snowboy)
        
        try:
            text = await self.listen(timeout=3)
            if text and self.config.wake_word.lower() in text.lower():
                return True
        except:
            pass
        
        return False
    
    @property
    def state(self) -> VoiceState:
        """Get current voice state."""
        return self._state
    
    def set_voice(self, voice_id: str) -> None:
        """Set TTS voice."""
        if self._tts_engine:
            try:
                voices = self._tts_engine.getProperty('voices')
                for voice in voices:
                    if voice_id in voice.id:
                        self._tts_engine.setProperty('voice', voice.id)
                        break
            except Exception as e:
                logger.warning(f"Failed to set voice: {e}")
    
    def get_available_voices(self) -> List[Dict[str, str]]:
        """Get available TTS voices."""
        voices = []
        
        if self._tts_engine:
            try:
                for voice in self._tts_engine.getProperty('voices'):
                    voices.append({
                        "id": voice.id,
                        "name": voice.name,
                        "languages": voice.languages,
                    })
            except:
                pass
        
        return voices


# Global voice interface instance
voice = VoiceInterface()
