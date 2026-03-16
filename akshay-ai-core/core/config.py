"""
============================================================
AKSHAY AI CORE — Configuration Management
============================================================
Centralized configuration with environment variable support,
validation, and type safety using Pydantic Settings.
============================================================
"""

import secrets
from pathlib import Path
from typing import Any, List, Optional
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    All settings can be overridden via environment variables or .env file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # =========================
    # System Configuration
    # =========================
    APP_NAME: str = "AKSHAY_AI_CORE"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SYSTEM_ID: str = Field(default_factory=lambda: secrets.token_hex(16))
    
    # =========================
    # Paths
    # =========================
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = Field(default=Path("./data"))
    LOGS_DIR: Path = Field(default=Path("./logs"))
    PLUGINS_DIR: Path = Field(default=Path("./plugins"))
    CONFIG_DIR: Path = Field(default=Path("./config"))
    
    # =========================
    # Security Configuration
    # =========================
    MASTER_ENCRYPTION_KEY: Optional[str] = None
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    
    # Face authentication
    FACE_AUTH_ENABLED: bool = True
    FACE_AUTH_CONFIDENCE_THRESHOLD: float = 0.85
    FACE_AUTH_MAX_REGISTRATION_IMAGES: int = 10
    
    # PIN authentication
    PIN_ENABLED: bool = True
    PIN_MIN_LENGTH: int = 6
    PIN_MAX_LENGTH: int = 12
    
    # Voice lock
    VOICE_LOCK_PHRASE: str = "LOCK SYSTEM"
    VOICE_LOCK_ENABLED: bool = True
    
    # =========================
    # AI Model Configuration
    # =========================
    PRIMARY_AI_PROVIDER: str = "openai"  # openai, anthropic, google, ollama
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.7
    
    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"
    ANTHROPIC_MAX_TOKENS: int = 4096
    
    # Google
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_MODEL: str = "gemini-pro"
    GOOGLE_MAX_TOKENS: int = 4096
    
    # Ollama (Local)
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2"
    OLLAMA_KEEP_ALIVE: str = "5m"
    
    # =========================
    # Memory System
    # =========================
    VECTOR_DB_TYPE: str = "chromadb"
    VECTOR_DB_PATH: Path = Field(default=Path("./data/vector_db"))
    VECTOR_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    MEMORY_SHORT_TERM_LIMIT: int = 100
    MEMORY_COMPRESSION_INTERVAL_DAYS: int = 7
    MEMORY_MAX_CONTEXT_TOKENS: int = 8000
    
    # =========================
    # Database Configuration
    # =========================
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/akshay_core.db"
    DATABASE_ENCRYPTION_ENABLED: bool = True
    
    # Redis
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # =========================
    # API Configuration
    # =========================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_RELOAD: bool = True
    
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 100
    
    # =========================
    # Plugin Configuration
    # =========================
    PLUGINS_ENABLED: bool = True
    PLUGINS_SANDBOX_ENABLED: bool = True
    PLUGINS_MAX_EXECUTION_TIME: int = 300
    
    PLUGIN_WEB_AUTOMATION: bool = True
    PLUGIN_SYSTEM_CONTROL: bool = True
    PLUGIN_ESP32_IOT: bool = True
    PLUGIN_FILE_VAULT: bool = True
    PLUGIN_CYBER_TOOLS: bool = True
    PLUGIN_DATA_ANALYSIS: bool = True
    
    # =========================
    # Automation Configuration
    # =========================
    AUTOMATION_ENABLED: bool = True
    AUTOMATION_MAX_CONCURRENT_JOBS: int = 10
    AUTOMATION_JOB_TIMEOUT_SECONDS: int = 3600
    AUTOMATION_RULES_FILE: Path = Field(default=Path("./config/automation_rules.yaml"))
    
    # =========================
    # Logging Configuration
    # =========================
    LOG_MAX_SIZE_MB: int = 100
    LOG_BACKUP_COUNT: int = 10
    LOG_FORMAT: str = "json"
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_LOG_IMMUTABLE: bool = True
    
    # =========================
    # UI Configuration
    # =========================
    WEB_UI_ENABLED: bool = True
    WEB_UI_PORT: int = 3000
    
    DESKTOP_START_MINIMIZED: bool = False
    DESKTOP_SYSTEM_TRAY: bool = True
    
    VOICE_INTERFACE_ENABLED: bool = True
    VOICE_WAKE_WORD: str = "hey akshay"
    VOICE_TTS_ENABLED: bool = True
    VOICE_TTS_VOICE: str = "en-US-Neural2-J"
    
    # =========================
    # External Services
    # =========================
    ESP32_HUB_HOST: Optional[str] = None
    ESP32_HUB_PORT: int = 1883
    ESP32_HUB_USERNAME: Optional[str] = None
    ESP32_HUB_PASSWORD: Optional[str] = None
    
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    
    # =========================
    # Development Settings
    # =========================
    DEV_BYPASS_AUTH: bool = False
    DEV_MOCK_AI_RESPONSES: bool = False
    DEV_VERBOSE_LOGGING: bool = False
    
    # =========================
    # Validators
    # =========================
    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "testing"}
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v.lower()
    
    @field_validator("PRIMARY_AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        allowed = {"openai", "anthropic", "google", "ollama"}
        if v.lower() not in allowed:
            raise ValueError(f"AI provider must be one of: {allowed}")
        return v.lower()
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()
    
    @model_validator(mode="after")
    def validate_encryption_key(self) -> "Settings":
        """Ensure encryption key exists for production."""
        if self.ENVIRONMENT == "production" and not self.MASTER_ENCRYPTION_KEY:
            raise ValueError("MASTER_ENCRYPTION_KEY is required in production")
        return self
    
    # =========================
    # Helper Methods
    # =========================
    def get_database_path(self) -> Path:
        """Extract database file path from URL."""
        if "sqlite" in self.DATABASE_URL:
            path_str = self.DATABASE_URL.split("///")[-1]
            return Path(path_str)
        return Path(self.DATA_DIR / "akshay_core.db")
    
    def get_ai_config(self, provider: Optional[str] = None) -> dict[str, Any]:
        """Get configuration for specified AI provider."""
        provider = provider or self.PRIMARY_AI_PROVIDER
        
        configs = {
            "openai": {
                "api_key": self.OPENAI_API_KEY,
                "model": self.OPENAI_MODEL,
                "max_tokens": self.OPENAI_MAX_TOKENS,
                "temperature": self.OPENAI_TEMPERATURE,
            },
            "anthropic": {
                "api_key": self.ANTHROPIC_API_KEY,
                "model": self.ANTHROPIC_MODEL,
                "max_tokens": self.ANTHROPIC_MAX_TOKENS,
            },
            "google": {
                "api_key": self.GOOGLE_API_KEY,
                "model": self.GOOGLE_MODEL,
                "max_tokens": self.GOOGLE_MAX_TOKENS,
            },
            "ollama": {
                "host": self.OLLAMA_HOST,
                "model": self.OLLAMA_MODEL,
                "keep_alive": self.OLLAMA_KEEP_ALIVE,
            },
        }
        
        return configs.get(provider, configs["openai"])
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development"
    
    # Backward compatibility properties for tests
    @property
    def AI_PROVIDER(self) -> str:
        """Backward compatibility - use PRIMARY_AI_PROVIDER."""
        return self.PRIMARY_AI_PROVIDER
    
    @property
    def HOST(self) -> str:
        """Backward compatibility - use API_HOST."""
        return self.API_HOST


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Global settings instance
settings = get_settings()
