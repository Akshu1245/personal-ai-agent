"""
AKSHAY AI CORE — Policy Store

Versioned policy storage with:
- Atomic writes
- Version history
- Rollback support
- Key registry persistence
- Thread-safe operations

STORAGE STRUCTURE:
config/policies/
├── active.yaml              # Symlink/pointer to active policy
├── versions/
│   ├── 1.0.0.yaml
│   ├── 1.1.0.yaml
│   └── 1.2.0.yaml
├── keys/
│   ├── public_keys.yaml     # Public key registry
│   └── key_history.yaml     # Key lifecycle events
└── history.yaml             # Policy change history
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import yaml
from pydantic import BaseModel, Field, ConfigDict

from core.policy.errors import (
    PolicyStoreError,
    PolicyVersionError,
    PolicyRollbackError,
    PolicyLoadError,
    PolicyKeyError,
    PolicyErrorCode,
)
from core.policy.schema import (
    SignatureAlgorithm,
    PolicyDocument,
)
from core.policy.signer import KeyTrust


# =============================================================================
# CONSTANTS
# =============================================================================

# Default paths
DEFAULT_POLICIES_DIR = Path("config/policies")
DEFAULT_KEYS_DIR = Path("config/policies/keys")
DEFAULT_VERSIONS_DIR = Path("config/policies/versions")

# File names
ACTIVE_POLICY_FILE = "active.yaml"
ACTIVE_POINTER_FILE = ".active_version"
PUBLIC_KEYS_FILE = "public_keys.yaml"
KEY_HISTORY_FILE = "key_history.yaml"
POLICY_HISTORY_FILE = "history.yaml"

# Maximum versions to keep
MAX_VERSION_HISTORY = 50


# =============================================================================
# MODELS
# =============================================================================

class PolicyChangeType(str, Enum):
    """Types of policy changes."""
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    ACTIVATED = "ACTIVATED"
    ROLLBACK = "ROLLBACK"
    DEPRECATED = "DEPRECATED"


class KeyChangeType(str, Enum):
    """Types of key changes."""
    CREATED = "CREATED"
    REGISTERED = "REGISTERED"
    DEPRECATED = "DEPRECATED"
    REVOKED = "REVOKED"
    REMOVED = "REMOVED"
    ROTATED = "ROTATED"


@dataclass
class PolicyVersionInfo:
    """Information about a stored policy version."""
    version: str
    name: str
    created_at: datetime
    signed_by: Optional[str]
    signature_valid: Optional[bool]
    file_path: Path
    is_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "signed_by": self.signed_by,
            "signature_valid": self.signature_valid,
            "file_path": str(self.file_path),
            "is_active": self.is_active,
        }


@dataclass
class PolicyChangeRecord:
    """Record of a policy change for history."""
    timestamp: datetime
    change_type: PolicyChangeType
    version: str
    policy_name: str
    changed_by: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "change_type": self.change_type.value,
            "version": self.version,
            "policy_name": self.policy_name,
            "changed_by": self.changed_by,
            "details": self.details,
        }


@dataclass
class KeyChangeRecord:
    """Record of a key change for history."""
    timestamp: datetime
    change_type: KeyChangeType
    key_id: str
    changed_by: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "change_type": self.change_type.value,
            "key_id": self.key_id,
            "changed_by": self.changed_by,
            "details": self.details,
        }


class StoredPublicKey(BaseModel):
    """Public key stored in registry."""
    
    model_config = ConfigDict(extra="forbid")
    
    key_id: str
    algorithm: SignatureAlgorithm
    trust: str = KeyTrust.OPERATOR
    description: str = ""
    public_key_pem: Optional[str] = None
    hmac_secret_b64: Optional[str] = None  # Only for dev/testing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    deprecated: bool = False
    revoked: bool = False


# =============================================================================
# POLICY STORE
# =============================================================================

class PolicyStore:
    """
    Versioned policy storage with thread-safe operations.
    
    Features:
    - Atomic policy writes
    - Version history
    - Active policy pointer
    - Rollback support
    - Key registry
    """
    
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        create_dirs: bool = True,
    ):
        """
        Initialize policy store.
        
        Args:
            base_dir: Base directory for policy storage
            create_dirs: Whether to create directories if they don't exist
        """
        self._base_dir = Path(base_dir) if base_dir else DEFAULT_POLICIES_DIR
        self._versions_dir = self._base_dir / "versions"
        self._keys_dir = self._base_dir / "keys"
        
        self._lock = threading.RLock()
        self._active_version: Optional[str] = None
        self._versions_cache: Dict[str, PolicyVersionInfo] = {}
        self._keys_cache: Dict[str, StoredPublicKey] = {}
        
        if create_dirs:
            self._ensure_directories()
        
        # Load existing state
        self._load_state()
    
    def _ensure_directories(self) -> None:
        """Create required directories."""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._versions_dir.mkdir(parents=True, exist_ok=True)
        self._keys_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_state(self) -> None:
        """Load existing state from disk."""
        with self._lock:
            # Load active version pointer
            pointer_file = self._base_dir / ACTIVE_POINTER_FILE
            if pointer_file.exists():
                self._active_version = pointer_file.read_text().strip()
            
            # Load version cache
            self._versions_cache.clear()
            if self._versions_dir.exists():
                for policy_file in self._versions_dir.glob("*.yaml"):
                    try:
                        info = self._load_version_info(policy_file)
                        if info:
                            self._versions_cache[info.version] = info
                    except Exception:
                        pass  # Skip invalid files
            
            # Load keys cache
            self._keys_cache.clear()
            keys_file = self._keys_dir / PUBLIC_KEYS_FILE
            if keys_file.exists():
                try:
                    with open(keys_file, "r", encoding="utf-8") as f:
                        keys_data = yaml.safe_load(f) or {}
                    for key_id, key_data in keys_data.get("keys", {}).items():
                        key_data["key_id"] = key_id
                        self._keys_cache[key_id] = StoredPublicKey(**key_data)
                except Exception:
                    pass  # Start with empty cache
    
    def _load_version_info(self, file_path: Path) -> Optional[PolicyVersionInfo]:
        """Load version info from a policy file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data or "metadata" not in data:
                return None
            
            metadata = data["metadata"]
            signature = data.get("signature", {})
            
            return PolicyVersionInfo(
                version=metadata.get("version", "unknown"),
                name=metadata.get("name", "unknown"),
                created_at=datetime.fromisoformat(
                    metadata.get("created_at", datetime.now(timezone.utc).isoformat())
                ),
                signed_by=signature.get("key_id"),
                signature_valid=None,  # Not verified yet
                file_path=file_path,
                is_active=(metadata.get("version") == self._active_version),
            )
        except Exception:
            return None
    
    # =========================================================================
    # POLICY OPERATIONS
    # =========================================================================
    
    def store_policy(
        self,
        policy: PolicyDocument,
        changed_by: str = "system",
    ) -> PolicyVersionInfo:
        """
        Store a policy version.
        
        Args:
            policy: Policy document to store
            changed_by: User/system that made the change
            
        Returns:
            PolicyVersionInfo for the stored policy
        """
        with self._lock:
            version = policy.metadata.version
            file_path = self._versions_dir / f"{version}.yaml"
            
            # Check if version already exists
            if file_path.exists():
                raise PolicyVersionError(
                    version=version,
                    message=f"Policy version {version} already exists",
                )
            
            # Convert to YAML
            policy_data = policy.model_dump(mode="json")
            yaml_content = yaml.dump(
                policy_data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            
            # Atomic write
            temp_path = file_path.with_suffix(".tmp")
            try:
                temp_path.write_text(yaml_content, encoding="utf-8")
                temp_path.rename(file_path)
            except Exception as e:
                temp_path.unlink(missing_ok=True)
                raise PolicyStoreError(
                    message=f"Failed to store policy: {e}",
                    code=PolicyErrorCode.STORE_WRITE_FAILED,
                    cause=e,
                )
            
            # Update cache
            info = PolicyVersionInfo(
                version=version,
                name=policy.metadata.name,
                created_at=policy.metadata.created_at,
                signed_by=policy.signature.key_id if policy.signature else None,
                signature_valid=None,
                file_path=file_path,
                is_active=False,
            )
            self._versions_cache[version] = info
            
            # Record change
            self._record_policy_change(
                PolicyChangeRecord(
                    timestamp=datetime.now(timezone.utc),
                    change_type=PolicyChangeType.CREATED,
                    version=version,
                    policy_name=policy.metadata.name,
                    changed_by=changed_by,
                )
            )
            
            # Cleanup old versions
            self._cleanup_old_versions()
            
            return info
    
    def load_policy(self, version: str) -> PolicyDocument:
        """
        Load a specific policy version.
        
        Args:
            version: Version string to load
            
        Returns:
            PolicyDocument
            
        Raises:
            PolicyVersionError: If version not found
        """
        with self._lock:
            file_path = self._versions_dir / f"{version}.yaml"
            
            if not file_path.exists():
                raise PolicyVersionError(
                    version=version,
                    message=f"Policy version {version} not found",
                )
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return PolicyDocument(**data)
            except Exception as e:
                raise PolicyLoadError(
                    message=f"Failed to load policy {version}: {e}",
                    file_path=str(file_path),
                    cause=e,
                )
    
    def load_active_policy(self) -> Optional[PolicyDocument]:
        """
        Load the currently active policy.
        
        Returns:
            PolicyDocument or None if no active policy
        """
        with self._lock:
            if not self._active_version:
                return None
            return self.load_policy(self._active_version)
    
    def activate_policy(
        self,
        version: str,
        changed_by: str = "system",
    ) -> PolicyVersionInfo:
        """
        Set a policy version as active.
        
        Args:
            version: Version to activate
            changed_by: User/system making the change
            
        Returns:
            PolicyVersionInfo for the activated policy
        """
        with self._lock:
            if version not in self._versions_cache:
                raise PolicyVersionError(
                    version=version,
                    message=f"Policy version {version} not found",
                )
            
            old_version = self._active_version
            
            # Update pointer file
            pointer_file = self._base_dir / ACTIVE_POINTER_FILE
            try:
                pointer_file.write_text(version, encoding="utf-8")
            except Exception as e:
                raise PolicyStoreError(
                    message=f"Failed to activate policy: {e}",
                    code=PolicyErrorCode.STORE_WRITE_FAILED,
                    cause=e,
                )
            
            # Update state
            self._active_version = version
            
            # Update cache
            for v, info in self._versions_cache.items():
                self._versions_cache[v] = PolicyVersionInfo(
                    version=info.version,
                    name=info.name,
                    created_at=info.created_at,
                    signed_by=info.signed_by,
                    signature_valid=info.signature_valid,
                    file_path=info.file_path,
                    is_active=(v == version),
                )
            
            # Record change
            self._record_policy_change(
                PolicyChangeRecord(
                    timestamp=datetime.now(timezone.utc),
                    change_type=PolicyChangeType.ACTIVATED,
                    version=version,
                    policy_name=self._versions_cache[version].name,
                    changed_by=changed_by,
                    details={"previous_version": old_version},
                )
            )
            
            return self._versions_cache[version]
    
    def rollback_policy(
        self,
        target_version: Optional[str] = None,
        changed_by: str = "system",
    ) -> PolicyVersionInfo:
        """
        Rollback to a previous policy version.
        
        Args:
            target_version: Version to rollback to (None for previous)
            changed_by: User/system making the change
            
        Returns:
            PolicyVersionInfo for the activated policy
        """
        with self._lock:
            if target_version:
                if target_version not in self._versions_cache:
                    raise PolicyRollbackError(
                        target_version=target_version,
                        reason="Version not found",
                    )
                return self.activate_policy(target_version, changed_by)
            
            # Find previous version
            versions = sorted(
                self._versions_cache.keys(),
                key=lambda v: self._versions_cache[v].created_at,
                reverse=True,
            )
            
            if len(versions) < 2:
                raise PolicyRollbackError(
                    target_version="previous",
                    reason="No previous version available",
                    code=PolicyErrorCode.ROLLBACK_NO_PREVIOUS_VERSION,
                )
            
            # Find current active position
            current_idx = 0
            if self._active_version in versions:
                current_idx = versions.index(self._active_version)
            
            # Get previous (older) version
            if current_idx >= len(versions) - 1:
                raise PolicyRollbackError(
                    target_version="previous",
                    reason="No previous version available",
                    code=PolicyErrorCode.ROLLBACK_NO_PREVIOUS_VERSION,
                )
            
            previous_version = versions[current_idx + 1]
            
            # Record rollback
            self._record_policy_change(
                PolicyChangeRecord(
                    timestamp=datetime.now(timezone.utc),
                    change_type=PolicyChangeType.ROLLBACK,
                    version=previous_version,
                    policy_name=self._versions_cache[previous_version].name,
                    changed_by=changed_by,
                    details={"from_version": self._active_version},
                )
            )
            
            return self.activate_policy(previous_version, changed_by)
    
    def list_versions(self) -> List[PolicyVersionInfo]:
        """
        List all stored policy versions.
        
        Returns:
            List of PolicyVersionInfo sorted by creation date (newest first)
        """
        with self._lock:
            return sorted(
                self._versions_cache.values(),
                key=lambda v: v.created_at,
                reverse=True,
            )
    
    def get_active_version(self) -> Optional[str]:
        """Get the currently active policy version."""
        with self._lock:
            return self._active_version
    
    def _cleanup_old_versions(self) -> None:
        """Remove old versions beyond the limit."""
        versions = sorted(
            self._versions_cache.keys(),
            key=lambda v: self._versions_cache[v].created_at,
        )
        
        while len(versions) > MAX_VERSION_HISTORY:
            old_version = versions.pop(0)
            
            # Don't delete active version
            if old_version == self._active_version:
                continue
            
            # Delete file
            info = self._versions_cache.get(old_version)
            if info and info.file_path.exists():
                info.file_path.unlink()
            
            # Remove from cache
            self._versions_cache.pop(old_version, None)
    
    def _record_policy_change(self, record: PolicyChangeRecord) -> None:
        """Record a policy change to history file."""
        history_file = self._base_dir / POLICY_HISTORY_FILE
        
        try:
            if history_file.exists():
                with open(history_file, "r", encoding="utf-8") as f:
                    history = yaml.safe_load(f) or {"changes": []}
            else:
                history = {"changes": []}
            
            history["changes"].append(record.to_dict())
            
            # Keep only last 1000 records
            history["changes"] = history["changes"][-1000:]
            
            with open(history_file, "w", encoding="utf-8") as f:
                yaml.dump(history, f, default_flow_style=False)
        except Exception:
            pass  # Don't fail on history write
    
    # =========================================================================
    # KEY OPERATIONS
    # =========================================================================
    
    def store_public_key(
        self,
        key: StoredPublicKey,
        changed_by: str = "system",
    ) -> None:
        """
        Store a public key in the registry.
        
        Args:
            key: Public key to store
            changed_by: User/system making the change
        """
        with self._lock:
            self._keys_cache[key.key_id] = key
            self._save_keys()
            
            self._record_key_change(
                KeyChangeRecord(
                    timestamp=datetime.now(timezone.utc),
                    change_type=KeyChangeType.REGISTERED,
                    key_id=key.key_id,
                    changed_by=changed_by,
                    details={
                        "algorithm": key.algorithm.value,
                        "trust": key.trust,
                    },
                )
            )
    
    def load_public_key(self, key_id: str) -> Optional[StoredPublicKey]:
        """
        Load a public key from the registry.
        
        Args:
            key_id: Key ID to load
            
        Returns:
            StoredPublicKey or None if not found
        """
        with self._lock:
            return self._keys_cache.get(key_id)
    
    def list_public_keys(self) -> List[StoredPublicKey]:
        """
        List all public keys in the registry.
        
        Returns:
            List of StoredPublicKey
        """
        with self._lock:
            return list(self._keys_cache.values())
    
    def deprecate_key(
        self,
        key_id: str,
        changed_by: str = "system",
    ) -> None:
        """Mark a key as deprecated."""
        with self._lock:
            if key_id in self._keys_cache:
                old = self._keys_cache[key_id]
                self._keys_cache[key_id] = StoredPublicKey(
                    key_id=old.key_id,
                    algorithm=old.algorithm,
                    trust=old.trust,
                    description=old.description,
                    public_key_pem=old.public_key_pem,
                    hmac_secret_b64=old.hmac_secret_b64,
                    created_at=old.created_at,
                    expires_at=old.expires_at,
                    deprecated=True,
                    revoked=old.revoked,
                )
                self._save_keys()
                
                self._record_key_change(
                    KeyChangeRecord(
                        timestamp=datetime.now(timezone.utc),
                        change_type=KeyChangeType.DEPRECATED,
                        key_id=key_id,
                        changed_by=changed_by,
                    )
                )
    
    def revoke_key(
        self,
        key_id: str,
        changed_by: str = "system",
    ) -> None:
        """Revoke a key."""
        with self._lock:
            if key_id in self._keys_cache:
                old = self._keys_cache[key_id]
                self._keys_cache[key_id] = StoredPublicKey(
                    key_id=old.key_id,
                    algorithm=old.algorithm,
                    trust=old.trust,
                    description=old.description,
                    public_key_pem=old.public_key_pem,
                    hmac_secret_b64=old.hmac_secret_b64,
                    created_at=old.created_at,
                    expires_at=old.expires_at,
                    deprecated=True,
                    revoked=True,
                )
                self._save_keys()
                
                self._record_key_change(
                    KeyChangeRecord(
                        timestamp=datetime.now(timezone.utc),
                        change_type=KeyChangeType.REVOKED,
                        key_id=key_id,
                        changed_by=changed_by,
                    )
                )
    
    def remove_key(
        self,
        key_id: str,
        changed_by: str = "system",
    ) -> bool:
        """Remove a key from the registry."""
        with self._lock:
            if key_id in self._keys_cache:
                del self._keys_cache[key_id]
                self._save_keys()
                
                self._record_key_change(
                    KeyChangeRecord(
                        timestamp=datetime.now(timezone.utc),
                        change_type=KeyChangeType.REMOVED,
                        key_id=key_id,
                        changed_by=changed_by,
                    )
                )
                return True
            return False
    
    def _save_keys(self) -> None:
        """Save keys cache to disk."""
        keys_file = self._keys_dir / PUBLIC_KEYS_FILE
        
        keys_data = {
            "keys": {
                key_id: {
                    "algorithm": key.algorithm.value,
                    "trust": key.trust,
                    "description": key.description,
                    "public_key_pem": key.public_key_pem,
                    "hmac_secret_b64": key.hmac_secret_b64,
                    "created_at": key.created_at.isoformat(),
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "deprecated": key.deprecated,
                    "revoked": key.revoked,
                }
                for key_id, key in self._keys_cache.items()
            }
        }
        
        with open(keys_file, "w", encoding="utf-8") as f:
            yaml.dump(keys_data, f, default_flow_style=False)
    
    def _record_key_change(self, record: KeyChangeRecord) -> None:
        """Record a key change to history file."""
        history_file = self._keys_dir / KEY_HISTORY_FILE
        
        try:
            if history_file.exists():
                with open(history_file, "r", encoding="utf-8") as f:
                    history = yaml.safe_load(f) or {"changes": []}
            else:
                history = {"changes": []}
            
            history["changes"].append(record.to_dict())
            
            # Keep only last 500 records
            history["changes"] = history["changes"][-500:]
            
            with open(history_file, "w", encoding="utf-8") as f:
                yaml.dump(history, f, default_flow_style=False)
        except Exception:
            pass  # Don't fail on history write
    
    # =========================================================================
    # HISTORY
    # =========================================================================
    
    def get_policy_history(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get policy change history.
        
        Args:
            limit: Maximum records to return
            
        Returns:
            List of change records (newest first)
        """
        history_file = self._base_dir / POLICY_HISTORY_FILE
        
        if not history_file.exists():
            return []
        
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = yaml.safe_load(f) or {"changes": []}
            return list(reversed(history.get("changes", [])))[:limit]
        except Exception:
            return []
    
    def get_key_history(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get key change history.
        
        Args:
            limit: Maximum records to return
            
        Returns:
            List of change records (newest first)
        """
        history_file = self._keys_dir / KEY_HISTORY_FILE
        
        if not history_file.exists():
            return []
        
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = yaml.safe_load(f) or {"changes": []}
            return list(reversed(history.get("changes", [])))[:limit]
        except Exception:
            return []


# =============================================================================
# MODULE-LEVEL STORE INSTANCE
# =============================================================================

_default_store: Optional[PolicyStore] = None
_store_lock = threading.Lock()


def get_store(base_dir: Optional[Path] = None) -> PolicyStore:
    """Get the default policy store instance."""
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = PolicyStore(base_dir=base_dir)
    return _default_store


def set_store(store: PolicyStore) -> None:
    """Set the default policy store instance."""
    global _default_store
    with _store_lock:
        _default_store = store
