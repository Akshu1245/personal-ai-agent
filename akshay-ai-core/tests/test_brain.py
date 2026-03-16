"""
============================================================
AKSHAY AI CORE — Brain Module Tests
============================================================
"""

import pytest
import asyncio


class TestLLMConnector:
    """Tests for LLM connector."""
    
    def test_connector_initialization(self):
        """Test LLM connector initializes."""
        from core.brain.llm_connector import LLMConnector
        
        connector = LLMConnector()
        
        assert connector.available_providers is not None
        assert isinstance(connector.available_providers, list)
    
    def test_message_dataclass(self):
        """Test Message dataclass."""
        from core.brain.llm_connector import Message
        
        msg = Message(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_llm_response_dataclass(self):
        """Test LLMResponse dataclass."""
        from core.brain.llm_connector import LLMResponse
        
        response = LLMResponse(
            content="Hello!",
            model="test",
            provider="test",
        )
        
        assert response.content == "Hello!"
        assert response.tokens_used == 0


@pytest.mark.asyncio
class TestMemoryManager:
    """Tests for memory manager."""
    
    async def test_store_memory(self):
        """Test storing a memory."""
        from core.brain.memory import MemoryManager, MemoryType
        
        manager = MemoryManager()
        await manager.initialize()
        
        entry = await manager.store(
            content="Test memory content",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.5,
        )
        
        assert entry.id is not None
        assert entry.content == "Test memory content"
    
    async def test_recall_memory(self):
        """Test recalling memories."""
        from core.brain.memory import MemoryManager, MemoryType
        
        manager = MemoryManager()
        await manager.initialize()
        
        # Store a memory
        await manager.store(
            content="Python is a programming language",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.7,
        )
        
        # Recall
        memories = await manager.recall("programming", limit=5)
        
        assert isinstance(memories, list)
    
    async def test_memory_stats(self):
        """Test memory statistics."""
        from core.brain.memory import MemoryManager
        
        manager = MemoryManager()
        await manager.initialize()
        
        stats = manager.get_stats()
        
        assert "short_term_count" in stats
        assert "long_term_count" in stats


class TestCommandRouter:
    """Tests for command router."""
    
    def test_router_initialization(self):
        """Test router initializes."""
        from core.brain.command_router import CommandRouter
        
        router = CommandRouter()
        
        assert router is not None
    
    @pytest.mark.asyncio
    async def test_pattern_matching(self):
        """Test pattern-based routing."""
        from core.brain.command_router import CommandRouter
        
        router = CommandRouter()
        
        result = await router.route("open chrome")
        
        assert result.intent is not None
        assert result.intent.category is not None
    
    @pytest.mark.asyncio
    async def test_intent_classification(self):
        """Test intent classification."""
        from core.brain.command_router import CommandRouter, IntentCategory
        
        router = CommandRouter()
        
        # Test question
        result = await router.route("What is the weather?")
        assert result.intent.category == IntentCategory.QUERY
        
        # Test command
        result = await router.route("shutdown the computer")
        # Should be COMMAND or SYSTEM
        assert result.intent.category in [IntentCategory.COMMAND, IntentCategory.SYSTEM]


class TestTruthChecker:
    """Tests for truth checker."""
    
    def test_checker_initialization(self):
        """Test truth checker initializes."""
        from core.brain.truth_check import TruthChecker
        
        checker = TruthChecker()
        
        assert checker is not None
    
    @pytest.mark.asyncio
    async def test_verify_claim(self):
        """Test claim verification."""
        from core.brain.truth_check import TruthChecker
        
        checker = TruthChecker()
        
        results = await checker.verify(
            "The sky is blue.",
            deep_check=False,
        )
        
        assert isinstance(results, list)
    
    def test_verification_status_enum(self):
        """Test verification status values."""
        from core.brain.truth_check import VerificationStatus
        
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.FALSE.value == "false"
