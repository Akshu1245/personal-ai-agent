"""
============================================================
AKSHAY AI CORE — Database Initialization
============================================================
"""

import asyncio
from pathlib import Path

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import settings

# Create base class for models
Base = declarative_base()


async def initialize_database():
    """Initialize the database and create all tables."""
    from core.models import (
        User,
        Session,
        AuditLog,
        Memory,
        SecureMemory,
        Plugin,
        AutomationRule,
        SystemConfig,
    )
    
    # Ensure data directory exists
    db_path = settings.get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    
    return True


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


if __name__ == "__main__":
    asyncio.run(initialize_database())
