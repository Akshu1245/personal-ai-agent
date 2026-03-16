"""
============================================================
AKSHAY AI CORE — Memory Governance Layer
============================================================
Provides namespace-based access control, TTL enforcement,
encryption at rest, quota management, and comprehensive
audit logging for the memory system.

SECURITY PRINCIPLES:
1. Namespace isolation - users can only access their namespaces
2. TTL enforcement - memories expire and are securely deleted
3. Encryption at rest - sensitive memories are encrypted
4. Quota management - prevent resource exhaustion
5. Audit logging - all access is logged immutably
============================================================
"""

import asyncio
import hashlib
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import threading
from collections import defaultdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.permissions import Permission, Role, ROLE_PERMISSIONS
from core.security.firewall import (
    permission_firewall,
    create_security_context,
    SecurityContext,
)

logger = get_logger("security.memory_governance")


class MemoryClassification(Enum):
    """Memory sensitivity classification levels."""
    PUBLIC = "public"           # Accessible to all users
    INTERNAL = "internal"       # Accessible to authenticated users
    CONFIDENTIAL = "confidential"  # Accessible to owner and shared users
    RESTRICTED = "restricted"   # Accessible to owner only
    TOP_SECRET = "top_secret"   # Encrypted and accessible to owner only
    
    # Backward compatibility
    PRIVATE = "restricted"  # alias for RESTRICTED


class MemoryAccessType(Enum):
    """Types of memory access for audit logging."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SEARCH = "search"
    SHARE = "share"
    REVOKE = "revoke"
    EXPORT = "export"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"


@dataclass
class MemoryNamespace:
    """
    Memory namespace configuration.
    
    Namespaces provide isolation between different memory contexts.
    """
    name: str
    owner_id: str
    
    # Access control
    classification: MemoryClassification = MemoryClassification.CONFIDENTIAL
    shared_with: Set[str] = field(default_factory=set)
    read_roles: Set[Role] = field(default_factory=lambda: {Role.ADMIN})
    write_roles: Set[Role] = field(default_factory=lambda: {Role.ADMIN})
    
    # Quotas
    max_memories: int = 10000
    max_size_bytes: int = 100 * 1024 * 1024  # 100MB
    current_count: int = 0
    current_size_bytes: int = 0
    
    # TTL settings
    default_ttl_days: Optional[int] = None  # None = no expiry
    max_ttl_days: int = 365 * 5  # 5 years max
    
    # Encryption
    encrypted: bool = False
    encryption_key_id: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def can_read(self, user_id: str, role: Role) -> bool:
        """Check if user can read from this namespace."""
        # Owner always has access
        if user_id == self.owner_id:
            return True
        
        # Admin has access to all
        if role == Role.ADMIN:
            return True
        
        # Check classification
        if self.classification == MemoryClassification.PUBLIC:
            return True
        
        if self.classification == MemoryClassification.INTERNAL:
            return role in {Role.ADMIN, Role.USER, Role.AUTOMATION}
        
        # Check shared access
        if user_id in self.shared_with:
            return True
        
        # Check role-based access
        if role in self.read_roles:
            return True
        
        return False
    
    def can_write(self, user_id: str, role: Role) -> bool:
        """Check if user can write to this namespace."""
        # Owner always has access
        if user_id == self.owner_id:
            return True
        
        # Admin has access to all
        if role == Role.ADMIN:
            return True
        
        # Check role-based access
        if role in self.write_roles:
            return True
        
        return False
    
    def can_delete(self, user_id: str, role: Role) -> bool:
        """Check if user can delete from this namespace."""
        # Only owner and admin can delete
        return user_id == self.owner_id or role == Role.ADMIN
    
    def has_quota_available(self, additional_bytes: int = 0) -> Tuple[bool, str]:
        """Check if namespace has quota available."""
        if self.current_count >= self.max_memories:
            return False, f"Memory count limit reached ({self.max_memories})"
        
        if self.current_size_bytes + additional_bytes > self.max_size_bytes:
            return False, f"Storage limit reached ({self.max_size_bytes / 1024 / 1024:.1f}MB)"
        
        return True, "Quota available"


@dataclass
class GovernedMemory:
    """
    A memory entry with governance metadata.
    """
    id: str
    namespace: str
    content: str
    memory_type: str
    
    # Governance metadata
    owner_id: str
    classification: MemoryClassification = MemoryClassification.CONFIDENTIAL
    
    # TTL
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Encryption
    encrypted: bool = False
    encryption_version: int = 1
    
    # Size tracking
    size_bytes: int = 0
    
    # Access tracking
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    
    # Audit
    created_by: str = ""
    last_modified_by: str = ""
    modification_count: int = 0
    
    # Tags and metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "content": "[ENCRYPTED]" if self.encrypted else self.content,
            "memory_type": self.memory_type,
            "owner_id": self.owner_id,
            "classification": self.classification.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "encrypted": self.encrypted,
            "size_bytes": self.size_bytes,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class MemoryEncryption:
    """
    Handles memory encryption at rest.
    
    Uses Fernet symmetric encryption with key derivation.
    """
    
    def __init__(self, master_key: Optional[str] = None):
        self._master_key = master_key or settings.MASTER_ENCRYPTION_KEY
        self._keys: Dict[str, bytes] = {}
        self._lock = threading.Lock()
        
        if not self._master_key:
            logger.warning("No master encryption key configured - using generated key")
            self._master_key = secrets.token_urlsafe(32)
    
    def _derive_key(self, key_id: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Derive encryption key from master key and key ID."""
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        
        key_material = f"{self._master_key}:{key_id}".encode()
        key = base64.urlsafe_b64encode(kdf.derive(key_material))
        
        return key, salt
    
    def generate_key(self, namespace: str) -> str:
        """Generate and store encryption key for namespace."""
        key_id = f"ns:{namespace}:{secrets.token_hex(8)}"
        key, salt = self._derive_key(key_id)
        
        with self._lock:
            self._keys[key_id] = {
                "key": key,
                "salt": salt,
                "created_at": datetime.utcnow(),
            }
        
        logger.info(f"Generated encryption key for namespace: {namespace}")
        return key_id
    
    def encrypt(self, plaintext: str, key_id: str) -> str:
        """Encrypt plaintext using key."""
        if key_id not in self._keys:
            raise ValueError(f"Unknown key ID: {key_id}")
        
        key = self._keys[key_id]["key"]
        fernet = Fernet(key)
        
        ciphertext = fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(ciphertext).decode()
    
    def decrypt(self, ciphertext: str, key_id: str) -> str:
        """Decrypt ciphertext using key."""
        if key_id not in self._keys:
            raise ValueError(f"Unknown key ID: {key_id}")
        
        key = self._keys[key_id]["key"]
        fernet = Fernet(key)
        
        ciphertext_bytes = base64.urlsafe_b64decode(ciphertext.encode())
        plaintext = fernet.decrypt(ciphertext_bytes)
        return plaintext.decode()
    
    def rotate_key(self, old_key_id: str, namespace: str) -> str:
        """Rotate encryption key for namespace."""
        new_key_id = self.generate_key(namespace)
        
        # Mark old key as deprecated but keep for decryption
        if old_key_id in self._keys:
            self._keys[old_key_id]["deprecated"] = True
            self._keys[old_key_id]["deprecated_at"] = datetime.utcnow()
        
        return new_key_id


class MemoryGovernanceLayer:
    """
    Memory Governance Layer.
    
    Provides comprehensive security controls for the memory system:
    - Namespace-based access control
    - TTL enforcement with automatic expiry
    - Encryption at rest
    - Quota management
    - Comprehensive audit logging
    
    ALL memory access MUST go through this layer.
    """
    
    _instance: Optional["MemoryGovernanceLayer"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "MemoryGovernanceLayer":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # Namespace management
        self._namespaces: Dict[str, MemoryNamespace] = {}
        self._namespace_lock = asyncio.Lock()
        
        # Encryption
        self._encryption = MemoryEncryption()
        
        # TTL enforcement
        self._expiry_queue: List[Tuple[datetime, str, str]] = []  # (expiry_time, namespace, memory_id)
        self._expiry_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            "reads": 0,
            "writes": 0,
            "deletes": 0,
            "access_denied": 0,
            "quota_exceeded": 0,
            "expired_cleaned": 0,
            "encrypted_operations": 0,
        }
        
        # Initialize system namespace
        self._create_system_namespace()
        
        logger.info("Memory Governance Layer initialized")
    
    def _create_system_namespace(self) -> None:
        """Create the system namespace for internal use."""
        system_ns = MemoryNamespace(
            name="system",
            owner_id="system",
            classification=MemoryClassification.INTERNAL,
            read_roles={Role.ADMIN, Role.USER, Role.AUTOMATION},
            write_roles={Role.ADMIN, Role.AUTOMATION},
            max_memories=100000,
            max_size_bytes=1024 * 1024 * 1024,  # 1GB
        )
        self._namespaces["system"] = system_ns
    
    async def create_namespace(
        self,
        name: str,
        owner_id: str,
        role: Role,
        classification: MemoryClassification = MemoryClassification.CONFIDENTIAL,
        encrypted: bool = False,
        default_ttl_days: Optional[int] = None,
        max_memories: int = 10000,
        max_size_bytes: int = 100 * 1024 * 1024,
    ) -> MemoryNamespace:
        """
        Create a new memory namespace.
        
        Args:
            name: Namespace name
            owner_id: Owner user ID
            role: Creator's role
            classification: Security classification
            encrypted: Enable encryption at rest
            default_ttl_days: Default TTL for memories
            max_memories: Maximum memory count
            max_size_bytes: Maximum storage size
            
        Returns:
            Created namespace
        """
        async with self._namespace_lock:
            if name in self._namespaces:
                raise ValueError(f"Namespace already exists: {name}")
            
            namespace = MemoryNamespace(
                name=name,
                owner_id=owner_id,
                classification=classification,
                default_ttl_days=default_ttl_days,
                max_memories=max_memories,
                max_size_bytes=max_size_bytes,
                encrypted=encrypted,
            )
            
            # Generate encryption key if needed
            if encrypted:
                namespace.encryption_key_id = self._encryption.generate_key(name)
            
            self._namespaces[name] = namespace
            
            # Audit log
            audit_logger.log(
                action="namespace_created",
                user_id=owner_id,
                resource_type="memory_namespace",
                resource_id=name,
                details={
                    "classification": classification.value,
                    "encrypted": encrypted,
                    "max_memories": max_memories,
                },
            )
            
            logger.info(f"Created namespace: {name}", owner=owner_id)
            return namespace
    
    async def get_or_create_user_namespace(
        self,
        user_id: str,
        role: Role,
    ) -> MemoryNamespace:
        """Get or create user's personal namespace."""
        namespace_name = f"user:{user_id}"
        
        if namespace_name not in self._namespaces:
            return await self.create_namespace(
                name=namespace_name,
                owner_id=user_id,
                role=role,
                classification=MemoryClassification.CONFIDENTIAL,
                encrypted=True,  # User namespaces are encrypted by default
            )
        
        return self._namespaces[namespace_name]
    
    async def store_memory(
        self,
        context: SecurityContext,
        namespace: str,
        content: str,
        memory_type: str,
        classification: MemoryClassification = MemoryClassification.CONFIDENTIAL,
        ttl_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GovernedMemory:
        """
        Store a memory with governance controls.
        
        Args:
            context: Security context
            namespace: Target namespace
            content: Memory content
            memory_type: Type of memory
            classification: Security classification
            ttl_days: Time-to-live in days
            tags: Memory tags
            metadata: Additional metadata
            
        Returns:
            Stored memory with governance metadata
        """
        # Check permission
        required_perms = {Permission.WRITE_MEMORY}
        if memory_type == "LONG_TERM":
            required_perms.add(Permission.ACCESS_LONG_TERM_MEMORY)
        
        context.action = "memory_write"
        context.resource_type = "memory"
        context.resource_id = f"{namespace}:new"
        
        result = await permission_firewall.evaluate(context, required_perms)
        if not result.allowed:
            self._stats["access_denied"] += 1
            raise PermissionError(f"Memory write denied: {result.reason}")
        
        # Get namespace
        ns = self._namespaces.get(namespace)
        if not ns:
            # Auto-create user namespace
            if namespace.startswith("user:"):
                ns = await self.get_or_create_user_namespace(
                    context.user_id,
                    context.role,
                )
            else:
                raise ValueError(f"Namespace not found: {namespace}")
        
        # Check namespace access
        if not ns.can_write(context.user_id, context.role):
            self._stats["access_denied"] += 1
            raise PermissionError(f"No write access to namespace: {namespace}")
        
        # Check quota
        content_size = len(content.encode())
        quota_ok, quota_msg = ns.has_quota_available(content_size)
        if not quota_ok:
            self._stats["quota_exceeded"] += 1
            raise ValueError(f"Quota exceeded: {quota_msg}")
        
        # Generate memory ID
        memory_id = hashlib.sha256(
            f"{namespace}:{content}:{datetime.utcnow().isoformat()}:{secrets.token_hex(8)}".encode()
        ).hexdigest()[:32]
        
        # Determine TTL
        if ttl_days is None:
            ttl_days = ns.default_ttl_days
        
        if ttl_days is not None:
            ttl_days = min(ttl_days, ns.max_ttl_days)
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)
        else:
            expires_at = None
        
        # Encrypt if needed
        encrypted_content = content
        encrypted = False
        
        if ns.encrypted and ns.encryption_key_id:
            encrypted_content = self._encryption.encrypt(content, ns.encryption_key_id)
            encrypted = True
            self._stats["encrypted_operations"] += 1
        
        # Create governed memory
        memory = GovernedMemory(
            id=memory_id,
            namespace=namespace,
            content=encrypted_content,
            memory_type=memory_type,
            owner_id=context.user_id,
            classification=classification,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            encrypted=encrypted,
            size_bytes=content_size,
            created_by=context.user_id,
            last_modified_by=context.user_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        
        # Update namespace stats
        ns.current_count += 1
        ns.current_size_bytes += content_size
        ns.updated_at = datetime.utcnow()
        
        # Add to expiry queue if TTL set
        if expires_at:
            self._expiry_queue.append((expires_at, namespace, memory_id))
            self._expiry_queue.sort(key=lambda x: x[0])
        
        self._stats["writes"] += 1
        
        # Audit log
        audit_logger.log(
            action="memory_stored",
            user_id=context.user_id,
            resource_type="memory",
            resource_id=memory_id,
            details={
                "namespace": namespace,
                "memory_type": memory_type,
                "classification": classification.value,
                "encrypted": encrypted,
                "size_bytes": content_size,
                "ttl_days": ttl_days,
            },
            ip_address=context.ip_address,
        )
        
        return memory
    
    async def recall_memory(
        self,
        context: SecurityContext,
        namespace: str,
        memory_id: str,
    ) -> Optional[GovernedMemory]:
        """
        Recall a specific memory with governance checks.
        
        Args:
            context: Security context
            namespace: Memory namespace
            memory_id: Memory ID
            
        Returns:
            Memory if accessible, None if not found
        """
        # Check permission
        context.action = "memory_read"
        context.resource_type = "memory"
        context.resource_id = f"{namespace}:{memory_id}"
        
        result = await permission_firewall.evaluate(context, {Permission.READ_MEMORY})
        if not result.allowed:
            self._stats["access_denied"] += 1
            raise PermissionError(f"Memory read denied: {result.reason}")
        
        # Get namespace
        ns = self._namespaces.get(namespace)
        if not ns:
            return None
        
        # Check namespace access
        if not ns.can_read(context.user_id, context.role):
            self._stats["access_denied"] += 1
            raise PermissionError(f"No read access to namespace: {namespace}")
        
        # This would integrate with actual memory storage
        # For now, return placeholder
        self._stats["reads"] += 1
        
        # Audit log
        audit_logger.log(
            action="memory_recalled",
            user_id=context.user_id,
            resource_type="memory",
            resource_id=memory_id,
            details={"namespace": namespace},
            ip_address=context.ip_address,
        )
        
        return None  # Actual implementation would return the memory
    
    async def search_memories(
        self,
        context: SecurityContext,
        query: str,
        namespaces: Optional[List[str]] = None,
        memory_types: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[GovernedMemory]:
        """
        Search memories across accessible namespaces.
        
        Args:
            context: Security context
            query: Search query
            namespaces: Namespaces to search (None = all accessible)
            memory_types: Filter by memory types
            limit: Maximum results
            
        Returns:
            List of matching memories
        """
        # Check permission
        context.action = "memory_search"
        context.resource_type = "memory"
        
        result = await permission_firewall.evaluate(context, {Permission.READ_MEMORY})
        if not result.allowed:
            self._stats["access_denied"] += 1
            raise PermissionError(f"Memory search denied: {result.reason}")
        
        # Determine accessible namespaces
        accessible_namespaces = []
        
        search_namespaces = namespaces or list(self._namespaces.keys())
        
        for ns_name in search_namespaces:
            ns = self._namespaces.get(ns_name)
            if ns and ns.can_read(context.user_id, context.role):
                accessible_namespaces.append(ns_name)
        
        if not accessible_namespaces:
            return []
        
        self._stats["reads"] += 1
        
        # Audit log
        audit_logger.log(
            action="memory_search",
            user_id=context.user_id,
            resource_type="memory",
            details={
                "query": query[:100],
                "namespaces": accessible_namespaces,
                "limit": limit,
            },
            ip_address=context.ip_address,
        )
        
        # Actual search would be implemented by memory backend
        return []
    
    async def delete_memory(
        self,
        context: SecurityContext,
        namespace: str,
        memory_id: str,
    ) -> bool:
        """
        Delete a memory with governance checks.
        
        Args:
            context: Security context
            namespace: Memory namespace
            memory_id: Memory ID
            
        Returns:
            True if deleted
        """
        # Check permission
        context.action = "memory_delete"
        context.resource_type = "memory"
        context.resource_id = f"{namespace}:{memory_id}"
        
        result = await permission_firewall.evaluate(context, {Permission.DELETE_MEMORY})
        if not result.allowed:
            self._stats["access_denied"] += 1
            raise PermissionError(f"Memory delete denied: {result.reason}")
        
        # Get namespace
        ns = self._namespaces.get(namespace)
        if not ns:
            return False
        
        # Check namespace access
        if not ns.can_delete(context.user_id, context.role):
            self._stats["access_denied"] += 1
            raise PermissionError(f"No delete access to namespace: {namespace}")
        
        self._stats["deletes"] += 1
        
        # Audit log
        audit_logger.log(
            action="memory_deleted",
            user_id=context.user_id,
            resource_type="memory",
            resource_id=memory_id,
            details={"namespace": namespace},
            ip_address=context.ip_address,
        )
        
        # Actual deletion would be implemented by memory backend
        return True
    
    async def share_namespace(
        self,
        context: SecurityContext,
        namespace: str,
        share_with_user_id: str,
    ) -> bool:
        """
        Share a namespace with another user.
        
        Args:
            context: Security context
            namespace: Namespace to share
            share_with_user_id: User to share with
            
        Returns:
            True if shared
        """
        ns = self._namespaces.get(namespace)
        if not ns:
            raise ValueError(f"Namespace not found: {namespace}")
        
        # Only owner can share
        if ns.owner_id != context.user_id and context.role != Role.ADMIN:
            raise PermissionError("Only namespace owner can share")
        
        ns.shared_with.add(share_with_user_id)
        
        # Audit log
        audit_logger.log(
            action="namespace_shared",
            user_id=context.user_id,
            resource_type="memory_namespace",
            resource_id=namespace,
            details={"shared_with": share_with_user_id},
            ip_address=context.ip_address,
        )
        
        return True
    
    async def revoke_share(
        self,
        context: SecurityContext,
        namespace: str,
        user_id: str,
    ) -> bool:
        """
        Revoke namespace sharing.
        
        Args:
            context: Security context
            namespace: Namespace
            user_id: User to revoke
            
        Returns:
            True if revoked
        """
        ns = self._namespaces.get(namespace)
        if not ns:
            raise ValueError(f"Namespace not found: {namespace}")
        
        if ns.owner_id != context.user_id and context.role != Role.ADMIN:
            raise PermissionError("Only namespace owner can revoke shares")
        
        ns.shared_with.discard(user_id)
        
        # Audit log
        audit_logger.log(
            action="namespace_share_revoked",
            user_id=context.user_id,
            resource_type="memory_namespace",
            resource_id=namespace,
            details={"revoked_from": user_id},
            ip_address=context.ip_address,
        )
        
        return True
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired memories.
        
        Returns:
            Number of memories cleaned up
        """
        cleaned = 0
        now = datetime.utcnow()
        
        # Process expiry queue
        while self._expiry_queue and self._expiry_queue[0][0] <= now:
            expires_at, namespace, memory_id = self._expiry_queue.pop(0)
            
            # Create system context for cleanup
            context = create_security_context(
                user_id="system",
                role=Role.ADMIN,
                action="memory_expire",
            )
            
            try:
                await self.delete_memory(context, namespace, memory_id)
                cleaned += 1
            except Exception as e:
                logger.error(
                    f"Failed to clean up expired memory",
                    namespace=namespace,
                    memory_id=memory_id,
                    error=str(e),
                )
        
        if cleaned > 0:
            self._stats["expired_cleaned"] += cleaned
            logger.info(f"Cleaned up {cleaned} expired memories")
        
        return cleaned
    
    async def get_namespace_stats(
        self,
        context: SecurityContext,
        namespace: str,
    ) -> Dict[str, Any]:
        """
        Get namespace statistics.
        
        Args:
            context: Security context
            namespace: Namespace name
            
        Returns:
            Namespace statistics
        """
        ns = self._namespaces.get(namespace)
        if not ns:
            raise ValueError(f"Namespace not found: {namespace}")
        
        if not ns.can_read(context.user_id, context.role):
            raise PermissionError(f"No access to namespace: {namespace}")
        
        return {
            "name": ns.name,
            "owner_id": ns.owner_id,
            "classification": ns.classification.value,
            "encrypted": ns.encrypted,
            "current_count": ns.current_count,
            "max_memories": ns.max_memories,
            "current_size_bytes": ns.current_size_bytes,
            "max_size_bytes": ns.max_size_bytes,
            "shared_with_count": len(ns.shared_with),
            "created_at": ns.created_at.isoformat(),
            "updated_at": ns.updated_at.isoformat(),
        }
    
    def get_governance_stats(self) -> Dict[str, Any]:
        """Get overall governance statistics."""
        return {
            "namespace_count": len(self._namespaces),
            "pending_expiries": len(self._expiry_queue),
            **self._stats,
        }
    
    async def start_expiry_monitor(self) -> None:
        """Start background task for expiry monitoring."""
        async def monitor():
            while True:
                try:
                    await self.cleanup_expired()
                except Exception as e:
                    logger.error("Expiry monitor error", error=str(e))
                await asyncio.sleep(300)  # Check every 5 minutes
        
        self._expiry_task = asyncio.create_task(monitor())
    
    async def stop_expiry_monitor(self) -> None:
        """Stop expiry monitor."""
        if self._expiry_task:
            self._expiry_task.cancel()
            try:
                await self._expiry_task
            except asyncio.CancelledError:
                pass


# Global instance
memory_governance = MemoryGovernanceLayer()
