"""
JARVIS Configuration Module
Handles API keys, settings, and user profile

Author: Rashi AI
Built for: Akshay
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """JARVIS Configuration"""
    
    def __init__(self):
        """Initialize configuration"""
        self.user_name = "Akshay"
        self.assistant_name = "JARVIS"
        self.project_path = Path(__file__).parent.parent
        self.memory_path = self.project_path / "memory"
        self.memory_path.mkdir(exist_ok=True)
        
        # API Keys
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # LLM Settings
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        
        # Voice settings
        self.voice_enabled = os.getenv("VOICE_ENABLED", "true").lower() == "true"
        self.wake_word_enabled = os.getenv("WAKE_WORD_ENABLED", "false").lower() == "true"  # Disabled due to compilation issues
        self.wake_word = os.getenv("WAKE_WORD", "hey jarvis")
        self.tts_engine = os.getenv("TTS_ENGINE", "pyttsx3")
        self.tts_rate = int(os.getenv("TTS_RATE", "150"))
        self.tts_volume = float(os.getenv("TTS_VOLUME", "1.0"))
        self.whisper_model = os.getenv("WHISPER_MODEL", "base")
        
        # Browser settings
        self.default_browser = os.getenv("DEFAULT_BROWSER", "chrome")
        self.headless_browser = os.getenv("HEADLESS_BROWSER", "false").lower() == "true"
        
        # System settings
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.require_auth = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
        
        # Productivity settings
        self.daily_briefing_time = os.getenv("DAILY_BRIEFING_TIME", "09:00")
        self.focus_duration = int(os.getenv("FOCUS_DURATION", "30"))
        self.ada_alert_price = float(os.getenv("ADA_ALERT_PRICE", "50"))
        
        # Security
        self.secret_key = os.getenv("SECRET_KEY", "change-this-to-a-random-string")
        
        print(f"✅ JARVIS Config initialized for {self.user_name}")
        print(f"🧠 Using model: {self.groq_model}")
        print(f"🔊 Voice enabled: {self.voice_enabled}")
        if self.debug:
            print("🐛 Debug mode enabled")
    
    def load(self):
        """Load configuration from files if they exist"""
        # Load preferences if exists
        prefs_file = self.get_data_path('user_preferences.json')
        if prefs_file.exists():
            with open(prefs_file, 'r') as f:
                prefs = json.load(f)
                for key, value in prefs.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        
        # Create directories if they don't exist
        self.memory_path.mkdir(exist_ok=True)
        self.get_data_path('').mkdir(exist_ok=True)
        self.get_journal_path('').mkdir(exist_ok=True)
    
    def get_data_path(self, filename):
        """Get path for data file"""
        data_path = self.project_path / "data"
        data_path.mkdir(exist_ok=True)
        return data_path / filename
    
    def get_journal_path(self, filename):
        """Get path for journal file"""
        journal_path = self.project_path / "journal"
        journal_path.mkdir(exist_ok=True)
        return journal_path / filename
    
    def save_user_preferences(self, preferences):
        """Save user preferences"""
        prefs_file = self.get_data_path("user_preferences.json")
        with open(prefs_file, 'w') as f:
            json.dump(preferences, f, indent=2)
    
    def load_user_preferences(self):
        """Load user preferences"""
        prefs_file = self.get_data_path("user_preferences.json")
        if prefs_file.exists():
            with open(prefs_file, 'r') as f:
                return json.load(f)
        return {}

# Global config instance
config = Config()