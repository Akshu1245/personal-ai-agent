"""
============================================================
AKSHAY AI CORE — Test Configuration
============================================================
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_data/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API tests."""
    from api.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create temporary test data directory."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def sample_user() -> dict:
    """Sample user data for tests."""
    return {
        "id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "role": "admin",
    }


@pytest.fixture
def sample_plugin_config() -> dict:
    """Sample plugin configuration."""
    return {
        "name": "test_plugin",
        "version": "1.0.0",
        "enabled": True,
        "sandboxed": True,
        "permissions": ["file:read"],
    }
