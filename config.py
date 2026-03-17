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
        # Project paths
        self.project_root = Path(__file__).parent
        self.data_dir = self.project_root / 'data'
        self.memory_dir = self.project_root / 'memory'
        
        # API Keys - Groq (Primary)
        self.groq_api_key = os.environ.get('GROQ_API_KEY', '')
        self.groq_model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
        
        # Fallback LLM - Anthropic Claude
        self.anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        
        # Voice Settings
        self.voice_enabled = os.environ.get('VOICE_ENABLED', 'true').lower() == 'true'
        self.wake_word_enabled = os.environ.get('WAKE_WORD_ENABLED', 'true').lower() == 'true'
        self.wake_word = os.environ.get('WAKE_WORD', 'hey jarvis')
        
        # TTS Settings
        self.tts_engine = os.environ.get('TTS_ENGINE', 'pyttsx3')  # pyttsx3 or coqui
        self.tts_rate = int(os.environ.get('TTS_RATE', '150'))
        self.tts_volume = float(os.environ.get('TTS_VOLUME', '1.0'))
        
        # Whisper Settings
        self.whisper_model = os.environ.get('WHISPER_MODEL', 'base')  # tiny, base, small, medium, large
        
        # Browser Settings
        self.default_browser = os.environ.get('DEFAULT_BROWSER', 'chrome')
        self.headless_browser = os.environ.get('HEADLESS_BROWSER', 'false').lower() == 'true'
        
        # System Settings
        self.debug = os.environ.get('DEBUG', 'false').lower() == 'true'
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO')
        
        # Security
        self.require_auth = os.environ.get('REQUIRE_AUTH', 'false').lower() == 'true'
        
        # Scheduler
        self.daily_briefing_time = os.environ.get('DAILY_BRIEFING_TIME', '09:00')
        
        # User Profile - Akshay
        self.user_name = "Akshay"
        self.user_title = "BCA Student"
        self.user_college = "New Horizon College of Engineering, Bangalore"
        self.user_location = "Anekal, Bangalore"
        self.user_from = "Bellary"
        self.user_girlfriend = "Anushree"
        self.user_friends = ["Dhanush Gowda", "Dhanush Yadav", "Darshan"]
        
        # Time wasters
        self.time_wasters = ['instagram.com', 'youtube.com', 'facebook.com']
        
        # Focus settings
        self.focus_duration_minutes = int(os.environ.get('FOCUS_DURATION', '30'))
        
        # Crypto
        self.crypto_alert_ada_price = float(os.environ.get('ADA_ALERT_PRICE', '50'))
        
        # Projects
        self.active_projects = [
            {
                'name': 'VORAX',
                'description': 'AI faceless YouTube video SaaS',
                'stack': 'FastAPI + Vite React TS',
                'tech': 'Groq/Llama scripting, Sarvam AI voice, Pexels footage, Shotstack'
            },
            {
                'name': 'Rashi IDE',
                'description': 'Local Replit-style IDE with 5 agent modes',
                'stack': 'Flask backend'
            },
            {
                'name': 'MarketX Vault',
                'description': 'Flutter Android vault disguised as trading app',
                'stack': 'Flutter'
            },
            {
                'name': 'SoulVault',
                'description': 'AI emotional memory simulation app',
                'stack': 'Flutter/Firebase'
            },
            {
                'name': 'Godfather Agent',
                'description': 'Make.com 15-route automation agent',
                'stack': 'Make.com'
            }
        ]
        
    def load(self):
        """Load configuration from files if they exist"""
        # Load preferences if exists
        prefs_file = self.data_dir / 'preferences.json'
        if prefs_file.exists():
            with open(prefs_file, 'r') as f:
                prefs = json.load(f)
                for key, value in prefs.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
                        
        # Create directories if they don't exist
        self.data_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        
    def save(self):
        """Save configuration to files"""
        # Save preferences
        prefs = {
            'voice_enabled': self.voice_enabled,
            'wake_word_enabled': self.wake_word_enabled,
            'focus_duration_minutes': self.focus_duration_minutes,
            'daily_briefing_time': self.daily_briefing_time
        }
        with open(self.data_dir / 'preferences.json', 'w') as f:
            json.dump(prefs, f, indent=2)
            
    def get_api_key(self, service: str) -> str:
        """Get API key for a service"""
        keys = {
            'groq': self.groq_api_key,
            'anthropic': self.anthropic_api_key,
        }
        return keys.get(service.lower(), '')
    
    def validate(self) -> list:
        """Validate configuration and return list of issues"""
        issues = []
        
        if not self.groq_api_key:
            issues.append("GROQ_API_KEY not set - please add to .env")
            
        if not self.voice_enabled:
            issues.append("Voice is disabled - set VOICE_ENABLED=true to enable")
            
        return issues
        
    def __repr__(self):
        return f"<Config user={self.user_name}, model={self.groq_model}, voice={self.voice_enabled}>"


# Singleton instance
_config = None

def get_config() -> Config:
    """Get configuration singleton"""
    global _config
    if _config is None:
        _config = Config()
    return _config
