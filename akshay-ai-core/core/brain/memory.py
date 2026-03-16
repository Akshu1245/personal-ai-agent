"""
============================================================
AKSHAY AI CORE — Memory System
============================================================
Persistent memory with short-term, long-term, and semantic memory.
============================================================
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from core.config import settings
from core.utils.logger import get_logger

if TYPE_CHECKING:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

logger = get_logger("brain.memory")


class MemoryType(str, Enum):
    """Types of memory."""
    SHORT_TERM = "short_term"      # Recent context, conversation
    LONG_TERM = "long_term"        # Persistent facts, preferences
    EPISODIC = "episodic"          # Events, experiences
    SEMANTIC = "semantic"          # Concepts, relationships
    PROCEDURAL = "procedural"      # How-to knowledge


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5  # 0-1 scale
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    decay_rate: float = 0.1
    tags: List[str] = field(default_factory=list)


class MemoryManager:
    """
    Memory management system.
    
    Features:
    - Short-term memory (conversation context)
    - Long-term memory (persistent facts)
    - Semantic memory (vector-based retrieval)
    - Memory consolidation
    - Importance-based retention
    - Decay and forgetting
    """
    
    def __init__(self):
        self._short_term: Dict[str, MemoryEntry] = {}
        self._long_term: Dict[str, MemoryEntry] = {}
        self._vector_store = None
        self._max_short_term = 100
        self._max_long_term = 10000
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the memory system."""
        if self._initialized:
            return
        
        # Initialize vector store (ChromaDB)
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            self._chroma_client = chromadb.PersistentClient(
                path=str(settings.VECTOR_DB_PATH),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                ),
            )
            
            self._vector_collection = self._chroma_client.get_or_create_collection(
                name="memory",
                metadata={"hnsw:space": "cosine"},
            )
            
            logger.info("Vector store initialized")
            
        except ImportError:
            logger.warning("ChromaDB not available, semantic memory disabled")
            self._chroma_client = None
            self._vector_collection = None
        
        # Load persisted memories
        await self._load_persisted_memories()
        
        self._initialized = True
        logger.info("Memory system initialized")
    
    async def _load_persisted_memories(self) -> None:
        """Load memories from database."""
        # In production, load from SQLite/PostgreSQL
        pass
    
    async def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        importance: float = 0.5,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> MemoryEntry:
        """
        Store a new memory.
        
        Args:
            content: Memory content
            memory_type: Type of memory
            importance: Importance score (0-1)
            metadata: Additional metadata
            tags: Tags for categorization
            user_id: User who owns this memory
            
        Returns:
            Created MemoryEntry
        """
        memory_id = str(uuid4())[:12]
        
        # Generate embedding for semantic search
        embedding = None
        if self._vector_collection:
            try:
                from core.brain.llm_connector import llm
                embedding = await llm.embed(content)
            except Exception as e:
                logger.warning("Failed to generate embedding", error=str(e))
        
        entry = MemoryEntry(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            embedding=embedding,
            metadata=metadata or {},
            tags=tags or [],
        )
        
        if user_id:
            entry.metadata["user_id"] = user_id
        
        # Store based on type
        if memory_type == MemoryType.SHORT_TERM:
            self._short_term[memory_id] = entry
            await self._prune_short_term()
        else:
            self._long_term[memory_id] = entry
            await self._prune_long_term()
        
        # Store in vector database
        if embedding and self._vector_collection:
            self._vector_collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[{
                    "memory_type": memory_type.value,
                    "importance": importance,
                    "created_at": entry.created_at.isoformat(),
                    "tags": ",".join(tags or []),
                    **(metadata or {}),
                }],
            )
        
        logger.debug(f"Stored memory: {memory_id}", memory_type=memory_type.value)
        
        return entry
    
    async def recall(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
        min_importance: float = 0.0,
        user_id: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        Recall memories based on semantic similarity.
        
        Args:
            query: Search query
            memory_type: Filter by memory type
            limit: Maximum results
            min_importance: Minimum importance threshold
            user_id: Filter by user
            
        Returns:
            List of relevant memories
        """
        results = []
        
        # Search vector store
        if self._vector_collection:
            try:
                from core.brain.llm_connector import llm
                
                query_embedding = await llm.embed(query)
                
                where_filter = {}
                if memory_type:
                    where_filter["memory_type"] = memory_type.value
                if min_importance > 0:
                    where_filter["importance"] = {"$gte": min_importance}
                
                search_results = self._vector_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where=where_filter if where_filter else None,
                )
                
                for i, doc_id in enumerate(search_results["ids"][0]):
                    # Get full entry
                    entry = self._short_term.get(doc_id) or self._long_term.get(doc_id)
                    
                    if entry:
                        # Update access
                        entry.accessed_at = datetime.utcnow()
                        entry.access_count += 1
                        results.append(entry)
                    else:
                        # Reconstruct from vector store
                        entry = MemoryEntry(
                            id=doc_id,
                            content=search_results["documents"][0][i],
                            memory_type=MemoryType(
                                search_results["metadatas"][0][i].get("memory_type", "short_term")
                            ),
                            importance=search_results["metadatas"][0][i].get("importance", 0.5),
                            metadata=search_results["metadatas"][0][i],
                        )
                        results.append(entry)
                        
            except Exception as e:
                logger.error("Vector search failed", error=str(e))
        
        # Fallback to keyword search
        if not results:
            results = await self._keyword_search(query, memory_type, limit)
        
        return results
    
    async def _keyword_search(
        self,
        query: str,
        memory_type: Optional[MemoryType],
        limit: int,
    ) -> List[MemoryEntry]:
        """Fallback keyword search."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        
        # Search both stores
        for store in [self._short_term, self._long_term]:
            for entry in store.values():
                if memory_type and entry.memory_type != memory_type:
                    continue
                
                content_lower = entry.content.lower()
                content_words = set(content_lower.split())
                
                # Simple scoring
                word_overlap = len(query_words & content_words)
                if word_overlap > 0 or query_lower in content_lower:
                    score = word_overlap / len(query_words) if query_words else 0
                    if query_lower in content_lower:
                        score += 0.5
                    score *= entry.importance
                    scored.append((score, entry))
        
        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [entry for _, entry in scored[:limit]]
    
    async def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID."""
        entry = self._short_term.get(memory_id) or self._long_term.get(memory_id)
        
        if entry:
            entry.accessed_at = datetime.utcnow()
            entry.access_count += 1
        
        return entry
    
    async def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[MemoryEntry]:
        """Update a memory."""
        entry = self._short_term.get(memory_id) or self._long_term.get(memory_id)
        
        if not entry:
            return None
        
        if content:
            entry.content = content
            # Re-generate embedding
            if self._vector_collection:
                try:
                    from core.brain.llm_connector import llm
                    entry.embedding = await llm.embed(content)
                    
                    self._vector_collection.update(
                        ids=[memory_id],
                        embeddings=[entry.embedding],
                        documents=[content],
                    )
                except Exception as e:
                    logger.warning("Failed to update embedding", error=str(e))
        
        if importance is not None:
            entry.importance = importance
        
        if metadata:
            entry.metadata.update(metadata)
        
        if tags:
            entry.tags = tags
        
        return entry
    
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        deleted = False
        
        if memory_id in self._short_term:
            del self._short_term[memory_id]
            deleted = True
        
        if memory_id in self._long_term:
            del self._long_term[memory_id]
            deleted = True
        
        # Remove from vector store
        if self._vector_collection:
            try:
                self._vector_collection.delete(ids=[memory_id])
            except:
                pass
        
        return deleted
    
    async def consolidate(self) -> int:
        """
        Consolidate memories.
        
        Moves important short-term memories to long-term.
        Removes low-importance, old memories.
        
        Returns:
            Number of memories consolidated
        """
        consolidated = 0
        now = datetime.utcnow()
        
        # Move important short-term to long-term
        for memory_id, entry in list(self._short_term.items()):
            # Check if important enough and accessed recently
            age = (now - entry.created_at).total_seconds() / 3600  # hours
            
            should_consolidate = (
                entry.importance >= 0.7 or
                entry.access_count >= 3 or
                (age >= 1 and entry.importance >= 0.5)
            )
            
            if should_consolidate:
                entry.memory_type = MemoryType.LONG_TERM
                self._long_term[memory_id] = entry
                del self._short_term[memory_id]
                consolidated += 1
        
        # Decay old short-term memories
        for memory_id, entry in list(self._short_term.items()):
            age_hours = (now - entry.created_at).total_seconds() / 3600
            decay = entry.decay_rate * age_hours
            entry.importance = max(0, entry.importance - decay)
            
            # Remove if importance too low
            if entry.importance < 0.1:
                del self._short_term[memory_id]
                if self._vector_collection:
                    try:
                        self._vector_collection.delete(ids=[memory_id])
                    except:
                        pass
        
        logger.info(f"Memory consolidation complete", consolidated=consolidated)
        
        return consolidated
    
    async def _prune_short_term(self) -> None:
        """Prune short-term memory if too large."""
        if len(self._short_term) <= self._max_short_term:
            return
        
        # Sort by importance and recency
        entries = sorted(
            self._short_term.items(),
            key=lambda x: (x[1].importance, x[1].accessed_at),
        )
        
        # Remove lowest importance
        to_remove = len(self._short_term) - self._max_short_term
        for memory_id, _ in entries[:to_remove]:
            del self._short_term[memory_id]
    
    async def _prune_long_term(self) -> None:
        """Prune long-term memory if too large."""
        if len(self._long_term) <= self._max_long_term:
            return
        
        # Sort by importance * access_count
        entries = sorted(
            self._long_term.items(),
            key=lambda x: x[1].importance * (x[1].access_count + 1),
        )
        
        to_remove = len(self._long_term) - self._max_long_term
        for memory_id, _ in entries[:to_remove]:
            del self._long_term[memory_id]
            if self._vector_collection:
                try:
                    self._vector_collection.delete(ids=[memory_id])
                except:
                    pass
    
    async def get_context(
        self,
        query: str,
        max_tokens: int = 2000,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Get relevant context for a query.
        
        Args:
            query: The query to get context for
            max_tokens: Maximum tokens of context
            user_id: User ID for filtering
            
        Returns:
            Formatted context string
        """
        memories = await self.recall(query, limit=10, user_id=user_id)
        
        if not memories:
            return ""
        
        # Build context string
        context_parts = []
        total_length = 0
        
        for memory in memories:
            part = f"[{memory.memory_type.value}] {memory.content}"
            part_length = len(part.split())  # Rough token estimate
            
            if total_length + part_length > max_tokens:
                break
            
            context_parts.append(part)
            total_length += part_length
        
        return "\n\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "short_term_count": len(self._short_term),
            "long_term_count": len(self._long_term),
            "vector_store_available": self._vector_collection is not None,
            "max_short_term": self._max_short_term,
            "max_long_term": self._max_long_term,
        }


# Global memory manager instance
memory_manager = MemoryManager()
