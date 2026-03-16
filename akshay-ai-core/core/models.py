"""
============================================================
AKSHAY AI CORE — Database Models
============================================================
All SQLAlchemy models for the system database.
============================================================
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
    LargeBinary,
)
from sqlalchemy.orm import relationship

from core.init_db import Base


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


class User(Base):
    """User account model."""
    
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    pin_hash = Column(String(255), nullable=True)
    face_encoding = Column(LargeBinary, nullable=True)
    role = Column(String(50), default="user")  # admin, user, guest
    permissions = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_user_username", "username"),
        Index("idx_user_active", "is_active"),
    )


class Session(Base):
    """User session model for authentication tracking."""
    
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    auth_method = Column(String(50), nullable=False)  # face, pin, voice
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_token", "token_hash"),
        Index("idx_session_active", "is_active"),
    )


class AuditLog(Base):
    """Immutable audit log for security tracking."""
    
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(20), default="success")  # success, failure, error
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    checksum = Column(String(64), nullable=False)  # SHA-256 for immutability
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )


class Memory(Base):
    """Long-term memory storage for semantic and event memories."""
    
    __tablename__ = "memories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    memory_type = Column(String(50), nullable=False)  # semantic, event, conversation
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    embedding_id = Column(String(100), nullable=True)  # Reference to vector DB
    importance = Column(Float, default=0.5)  # 0.0 to 1.0
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    is_compressed = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="memories")
    
    __table_args__ = (
        Index("idx_memory_user", "user_id"),
        Index("idx_memory_type", "memory_type"),
        Index("idx_memory_importance", "importance"),
        Index("idx_memory_created", "created_at"),
    )


class SecureMemory(Base):
    """Encrypted secure memory for sensitive information."""
    
    __tablename__ = "secure_memories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)  # Encrypted
    encrypted_content = Column(LargeBinary, nullable=False)
    encryption_iv = Column(LargeBinary, nullable=False)
    category = Column(String(50), nullable=True)
    tags = Column(JSON, default=list)  # Encrypted tag hashes
    access_level = Column(String(20), default="private")  # private, restricted
    requires_reauth = Column(Boolean, default=True)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_secure_memory_user", "user_id"),
        Index("idx_secure_memory_category", "category"),
    )


class Plugin(Base):
    """Plugin registry and configuration."""
    
    __tablename__ = "plugins"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    version = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)
    entry_point = Column(String(255), nullable=False)
    permissions = Column(JSON, default=list)
    config = Column(JSON, default=dict)
    is_enabled = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=False)
    is_sandboxed = Column(Boolean, default=True)
    execution_count = Column(Integer, default=0)
    last_executed = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    installed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_plugin_name", "name"),
        Index("idx_plugin_enabled", "is_enabled"),
    )


class AutomationRule(Base):
    """Automation rules and scheduled tasks."""
    
    __tablename__ = "automation_rules"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(50), nullable=False)  # schedule, event, keyword, system
    trigger_config = Column(JSON, nullable=False)
    conditions = Column(JSON, default=list)
    actions = Column(JSON, nullable=False)
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=5)  # 1-10, higher = more priority
    max_retries = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=300)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_automation_trigger", "trigger_type"),
        Index("idx_automation_enabled", "is_enabled"),
        Index("idx_automation_priority", "priority"),
    )


class SystemConfig(Base):
    """System configuration key-value store."""
    
    __tablename__ = "system_config"
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=True)
    value_type = Column(String(20), default="string")  # string, int, float, bool, json
    description = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    is_readonly = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(36), nullable=True)


class ConversationHistory(Base):
    """Conversation history for context management."""
    
    __tablename__ = "conversation_history"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(36), nullable=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tokens = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_conversation_user", "user_id"),
        Index("idx_conversation_session", "session_id"),
        Index("idx_conversation_created", "created_at"),
    )


class TaskExecution(Base):
    """Track task executions for monitoring and debugging."""
    
    __tablename__ = "task_executions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    task_type = Column(String(50), nullable=False)  # command, automation, plugin
    task_name = Column(String(100), nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending, running, success, failure
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_task_user", "user_id"),
        Index("idx_task_type", "task_type"),
        Index("idx_task_status", "status"),
        Index("idx_task_created", "created_at"),
    )
