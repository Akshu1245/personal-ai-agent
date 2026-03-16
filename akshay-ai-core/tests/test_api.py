"""
============================================================
AKSHAY AI CORE — API Tests
============================================================
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    async def test_health_check(self, async_client: AsyncClient):
        """Test health endpoint returns OK."""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    async def test_root_redirect(self, async_client: AsyncClient):
        """Test root redirects to docs or dashboard."""
        response = await async_client.get("/", follow_redirects=False)
        
        # Should redirect or return content
        assert response.status_code in [200, 307, 308]


@pytest.mark.asyncio
class TestSystemEndpoints:
    """Tests for system status endpoints."""
    
    async def test_system_status(self, async_client: AsyncClient):
        """Test system status endpoint."""
        response = await async_client.get("/api/system/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "system" in data or "status" in data


@pytest.mark.asyncio
class TestPluginEndpoints:
    """Tests for plugin management endpoints."""
    
    async def test_list_plugins(self, async_client: AsyncClient):
        """Test listing plugins."""
        response = await async_client.get("/api/plugins/")
        
        assert response.status_code == 200
        data = response.json()
        assert "plugins" in data
        assert isinstance(data["plugins"], list)


@pytest.mark.asyncio
class TestBrainEndpoints:
    """Tests for AI brain endpoints."""
    
    async def test_chat_endpoint_exists(self, async_client: AsyncClient):
        """Test chat endpoint exists."""
        response = await async_client.post(
            "/api/brain/chat",
            json={"message": "Hello"}
        )
        
        # Should return 200 or 401 (if auth required)
        assert response.status_code in [200, 401, 422]
