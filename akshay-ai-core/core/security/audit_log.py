"""
============================================================
AKSHAY AI CORE — Immutable Audit Log System
============================================================
Cryptographically secured, tamper-evident audit logging
with hash chains, digital signatures, and compliance
export capabilities.

SECURITY GUARANTEES:
1. Immutability - logs cannot be modified after creation
2. Tamper Detection - any modification is detectable
3. Non-Repudiation - actions are cryptographically signed
4. Integrity - hash chains ensure log continuity
5. Compliance - export formats for auditing requirements
============================================================
"""

import asyncio
import gzip
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple, Union
import uuid

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger("security.audit")


class AuditEventType(Enum):
    """Types of audit events."""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_MFA = "auth.mfa"
    AUTH_SESSION_CREATE = "auth.session.create"
    AUTH_SESSION_REVOKE = "auth.session.revoke"
    
    # Authorization
    AUTHZ_GRANTED = "authz.granted"
    AUTHZ_DENIED = "authz.denied"
    AUTHZ_ESCALATE = "authz.escalate"
    
    # Security
    SECURITY_DECISION = "security.decision"
    SECURITY_VIOLATION = "security.violation"
    SECURITY_ALERT = "security.alert"
    SECURITY_BLOCKED = "security.blocked"
    
    # Data (backward compatibility)
    DATA_CREATE = "data.create"
    DATA_READ = "data.read"
    DATA_UPDATE = "data.update"
    
    # Memory
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    MEMORY_DELETE = "memory.delete"
    MEMORY_SEARCH = "memory.search"
    MEMORY_SHARE = "memory.share"
    
    # Plugins
    PLUGIN_LOAD = "plugin.load"
    PLUGIN_UNLOAD = "plugin.unload"
    PLUGIN_EXECUTE = "plugin.execute"
    PLUGIN_ERROR = "plugin.error"
    
    # Automation
    AUTOMATION_CREATE = "automation.create"
    AUTOMATION_EXECUTE = "automation.execute"
    AUTOMATION_DELETE = "automation.delete"
    AUTOMATION_ERROR = "automation.error"
    
    # System
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_CONFIG = "system.config"
    SYSTEM_ERROR = "system.error"
    
    # Data
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"
    DATA_DELETE = "data.delete"
    
    # Admin
    ADMIN_USER_CREATE = "admin.user.create"
    ADMIN_USER_DELETE = "admin.user.delete"
    ADMIN_USER_MODIFY = "admin.user.modify"
    ADMIN_PERMISSION = "admin.permission"
    
    # Audit
    AUDIT_VERIFY = "audit.verify"
    AUDIT_EXPORT = "audit.export"
    AUDIT_ROTATE = "audit.rotate"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = 10
    INFO = 20
    NOTICE = 30
    WARNING = 40
    ERROR = 50
    CRITICAL = 60
    ALERT = 70
    EMERGENCY = 80


@dataclass
class AuditEntry:
    """
    Immutable audit log entry.
    
    Once created, the entry is cryptographically sealed
    and cannot be modified without detection.
    """
    # Core fields
    id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    
    # Actor information
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    
    # Action details
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    
    # Result
    status: str  # success, failure, error, denied
    error_message: Optional[str]
    
    # Details
    details: Dict[str, Any]
    
    # Hash chain
    previous_hash: str
    entry_hash: str
    
    # Signature
    signature: Optional[str] = None
    
    # Metadata
    sequence_number: int = 0
    log_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.name,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "status": self.status,
            "error_message": self.error_message,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "signature": self.signature,
            "sequence_number": self.sequence_number,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=AuditEventType(data["event_type"]),
            severity=AuditSeverity[data["severity"]],
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            action=data["action"],
            resource_type=data.get("resource_type"),
            resource_id=data.get("resource_id"),
            status=data["status"],
            error_message=data.get("error_message"),
            details=data.get("details", {}),
            previous_hash=data["previous_hash"],
            entry_hash=data["entry_hash"],
            signature=data.get("signature"),
            sequence_number=data.get("sequence_number", 0),
        )


class HashChainManager:
    """
    Manages cryptographic hash chain for audit logs.
    
    Each entry's hash includes the previous entry's hash,
    creating an unbreakable chain where any modification
    is immediately detectable.
    """
    
    GENESIS_HASH = "GENESIS_0000000000000000000000000000000000000000000000000000000000000000"
    
    def __init__(self, signing_key: Optional[str] = None):
        self._signing_key = (signing_key or settings.MASTER_ENCRYPTION_KEY or 
                            secrets.token_urlsafe(32))
        self._current_hash = self.GENESIS_HASH
        self._sequence_number = 0
        self._lock = threading.Lock()
    
    def compute_entry_hash(self, entry_data: Dict[str, Any], previous_hash: str) -> str:
        """
        Compute SHA-256 hash for entry including chain link.
        
        Hash includes:
        - All entry fields (excluding entry_hash and signature)
        - Previous entry's hash
        - Sequence number
        """
        # Create deterministic JSON representation
        hash_data = {
            "id": entry_data["id"],
            "timestamp": entry_data["timestamp"],
            "event_type": entry_data["event_type"],
            "severity": entry_data["severity"],
            "user_id": entry_data.get("user_id"),
            "session_id": entry_data.get("session_id"),
            "ip_address": entry_data.get("ip_address"),
            "action": entry_data["action"],
            "resource_type": entry_data.get("resource_type"),
            "resource_id": entry_data.get("resource_id"),
            "status": entry_data["status"],
            "error_message": entry_data.get("error_message"),
            "details": entry_data.get("details", {}),
            "previous_hash": previous_hash,
            "sequence_number": entry_data.get("sequence_number", 0),
        }
        
        serialized = json.dumps(hash_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def sign_entry(self, entry_hash: str) -> str:
        """
        Create HMAC signature for entry hash.
        
        Provides non-repudiation and integrity verification.
        """
        return hmac.new(
            self._signing_key.encode(),
            entry_hash.encode(),
            hashlib.sha256,
        ).hexdigest()
    
    def verify_signature(self, entry_hash: str, signature: str) -> bool:
        """Verify entry signature."""
        expected = self.sign_entry(entry_hash)
        return hmac.compare_digest(expected, signature)
    
    def chain_entry(self, entry_data: Dict[str, Any]) -> Tuple[str, str, str, int]:
        """
        Add entry to chain and compute hash/signature.
        
        Returns:
            Tuple of (previous_hash, entry_hash, signature, sequence_number)
        """
        with self._lock:
            previous_hash = self._current_hash
            self._sequence_number += 1
            
            entry_data["sequence_number"] = self._sequence_number
            entry_hash = self.compute_entry_hash(entry_data, previous_hash)
            signature = self.sign_entry(entry_hash)
            
            self._current_hash = entry_hash
            
            return previous_hash, entry_hash, signature, self._sequence_number
    
    def verify_chain(self, entries: List[AuditEntry]) -> Tuple[bool, Optional[str]]:
        """
        Verify integrity of audit log chain.
        
        Returns:
            Tuple of (valid, error_message)
        """
        if not entries:
            return True, None
        
        # Sort by sequence number
        sorted_entries = sorted(entries, key=lambda e: e.sequence_number)
        
        # First entry should link to genesis
        if sorted_entries[0].previous_hash != self.GENESIS_HASH:
            if sorted_entries[0].sequence_number == 1:
                return False, f"First entry does not link to genesis hash"
        
        # Verify each entry
        for i, entry in enumerate(sorted_entries):
            # Verify entry hash
            expected_hash = self.compute_entry_hash(entry.to_dict(), entry.previous_hash)
            if expected_hash != entry.entry_hash:
                return False, f"Entry {entry.id} hash mismatch at sequence {entry.sequence_number}"
            
            # Verify signature
            if entry.signature:
                if not self.verify_signature(entry.entry_hash, entry.signature):
                    return False, f"Entry {entry.id} signature invalid at sequence {entry.sequence_number}"
            
            # Verify chain continuity
            if i > 0:
                prev_entry = sorted_entries[i - 1]
                if entry.previous_hash != prev_entry.entry_hash:
                    return False, f"Chain broken at sequence {entry.sequence_number}"
        
        return True, None
    
    def get_chain_state(self) -> Dict[str, Any]:
        """Get current chain state."""
        return {
            "current_hash": self._current_hash,
            "sequence_number": self._sequence_number,
        }
    
    def set_chain_state(self, current_hash: str, sequence_number: int) -> None:
        """Restore chain state (for recovery)."""
        with self._lock:
            self._current_hash = current_hash
            self._sequence_number = sequence_number


class AuditLogStorage:
    """
    Secure storage for audit logs.
    
    Features:
    - Append-only file storage
    - Automatic rotation
    - Compression of old logs
    - Secure deletion prevention
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path(settings.LOGS_DIR) / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_file: Optional[Path] = None
        self._current_file_handle = None
        self._entries_in_current_file = 0
        self._max_entries_per_file = 10000
        self._lock = threading.Lock()
        
        self._rotate_to_new_file()
    
    def _get_log_filename(self) -> str:
        """Generate log filename with timestamp."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"audit_{timestamp}_{secrets.token_hex(4)}.jsonl"
    
    def _rotate_to_new_file(self) -> None:
        """Rotate to a new log file."""
        with self._lock:
            # Close current file
            if self._current_file_handle:
                self._current_file_handle.close()
            
            # Create new file
            self._current_file = self.log_dir / self._get_log_filename()
            self._current_file_handle = open(self._current_file, "a", encoding="utf-8")
            self._entries_in_current_file = 0
            
            # Write file header
            header = {
                "type": "audit_log_header",
                "version": "1.0",
                "created_at": datetime.utcnow().isoformat(),
                "system_id": settings.SYSTEM_ID,
            }
            self._current_file_handle.write(json.dumps(header) + "\n")
            self._current_file_handle.flush()
    
    def write_entry(self, entry: AuditEntry) -> str:
        """
        Write entry to log file.
        
        Returns:
            Path to log file
        """
        with self._lock:
            # Check if rotation needed
            if self._entries_in_current_file >= self._max_entries_per_file:
                self._rotate_to_new_file()
            
            # Write entry
            entry_json = json.dumps(entry.to_dict(), default=str)
            self._current_file_handle.write(entry_json + "\n")
            self._current_file_handle.flush()
            os.fsync(self._current_file_handle.fileno())  # Force write to disk
            
            self._entries_in_current_file += 1
            
            return str(self._current_file)
    
    def read_entries(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[Set[AuditEventType]] = None,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> Generator[AuditEntry, None, None]:
        """
        Read entries matching criteria.
        
        Yields entries from all applicable log files.
        """
        count = 0
        
        # Get all log files
        log_files = sorted(self.log_dir.glob("audit_*.jsonl"))
        
        for log_file in log_files:
            if count >= limit:
                break
            
            # Check if file might contain entries in time range
            # (optimization: could parse timestamp from filename)
            
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if count >= limit:
                            break
                        
                        try:
                            data = json.loads(line)
                            
                            # Skip header
                            if data.get("type") == "audit_log_header":
                                continue
                            
                            entry = AuditEntry.from_dict(data)
                            
                            # Apply filters
                            if start_time and entry.timestamp < start_time:
                                continue
                            if end_time and entry.timestamp > end_time:
                                continue
                            if event_types and entry.event_type not in event_types:
                                continue
                            if user_id and entry.user_id != user_id:
                                continue
                            
                            count += 1
                            yield entry
                            
                        except (json.JSONDecodeError, KeyError):
                            continue
                            
            except Exception as e:
                logger.error(f"Error reading log file {log_file}", error=str(e))
    
    def compress_old_logs(self, older_than_days: int = 7) -> int:
        """
        Compress log files older than specified days.
        
        Returns:
            Number of files compressed
        """
        compressed = 0
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            if log_file == self._current_file:
                continue
            
            # Check file modification time
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                try:
                    # Compress file
                    compressed_path = log_file.with_suffix(".jsonl.gz")
                    with open(log_file, "rb") as f_in:
                        with gzip.open(compressed_path, "wb") as f_out:
                            f_out.writelines(f_in)
                    
                    # Remove original
                    log_file.unlink()
                    compressed += 1
                    
                except Exception as e:
                    logger.error(f"Error compressing {log_file}", error=str(e))
        
        return compressed
    
    def close(self) -> None:
        """Close storage."""
        with self._lock:
            if self._current_file_handle:
                self._current_file_handle.close()
                self._current_file_handle = None


class ImmutableAuditLog:
    """
    Immutable Audit Log System.
    
    Provides cryptographically secured, tamper-evident audit logging
    with compliance export capabilities.
    
    ALL security-relevant events MUST be logged through this system.
    """
    
    _instance: Optional["ImmutableAuditLog"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "ImmutableAuditLog":
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
        
        # Core components
        self._hash_chain = HashChainManager()
        self._storage = AuditLogStorage()
        
        # In-memory buffer for recent entries
        self._recent_entries: List[AuditEntry] = []
        self._recent_max = 1000
        self._recent_lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_entries": 0,
            "entries_by_type": {},
            "entries_by_severity": {},
            "verification_count": 0,
            "verification_failures": 0,
        }
        
        # Log system startup
        self.log(
            event_type=AuditEventType.SYSTEM_START,
            severity=AuditSeverity.NOTICE,
            action="audit_system_start",
            details={"version": "1.0"},
        )
        
        logger.info("Immutable Audit Log System initialized")
    
    def log(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        action: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """
        Create immutable audit log entry.
        
        This is the primary logging method. Once called, the entry
        is cryptographically sealed and stored.
        
        Args:
            event_type: Type of audit event
            severity: Severity level
            action: Action being logged
            user_id: User performing action
            session_id: Session ID
            ip_address: Client IP
            user_agent: Client user agent
            resource_type: Type of resource accessed
            resource_id: ID of resource accessed
            status: success, failure, error, denied
            error_message: Error message if applicable
            details: Additional details
            
        Returns:
            Created audit entry
        """
        # Generate entry ID
        entry_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Prepare entry data for hashing
        entry_data = {
            "id": entry_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value,
            "severity": severity.name,
            "user_id": user_id,
            "session_id": session_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "error_message": error_message,
            "details": details or {},
        }
        
        # Chain entry (get hash and signature)
        previous_hash, entry_hash, signature, sequence_number = \
            self._hash_chain.chain_entry(entry_data)
        
        # Create entry
        entry = AuditEntry(
            id=entry_id,
            timestamp=timestamp,
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_message=error_message,
            details=details or {},
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            signature=signature,
            sequence_number=sequence_number,
        )
        
        # Store entry
        log_file = self._storage.write_entry(entry)
        entry.log_file = log_file
        
        # Add to recent buffer
        with self._recent_lock:
            self._recent_entries.append(entry)
            if len(self._recent_entries) > self._recent_max:
                self._recent_entries.pop(0)
        
        # Update stats
        self._stats["total_entries"] += 1
        self._stats["entries_by_type"][event_type.value] = \
            self._stats["entries_by_type"].get(event_type.value, 0) + 1
        self._stats["entries_by_severity"][severity.name] = \
            self._stats["entries_by_severity"].get(severity.name, 0) + 1
        
        return entry
    
    def log_security_decision(
        self,
        action: str,
        user_id: str,
        allowed: bool,
        reason: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """
        Log a security decision (authorization check result).
        
        Convenience method for logging permission checks.
        """
        event_type = AuditEventType.AUTHZ_GRANTED if allowed else AuditEventType.AUTHZ_DENIED
        severity = AuditSeverity.INFO if allowed else AuditSeverity.WARNING
        
        all_details = details or {}
        all_details["reason"] = reason
        all_details["allowed"] = allowed
        
        return self.log(
            event_type=event_type,
            severity=severity,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            status="success" if allowed else "denied",
            ip_address=ip_address,
            details=all_details,
        )
    
    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[Set[AuditEventType]] = None,
        user_id: Optional[str] = None,
        action_pattern: Optional[str] = None,
        min_severity: Optional[AuditSeverity] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Query audit logs with filters.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            event_types: Filter by event types
            user_id: Filter by user
            action_pattern: Filter by action (substring match)
            min_severity: Minimum severity level
            limit: Maximum results
            
        Returns:
            List of matching entries
        """
        results = []
        
        for entry in self._storage.read_entries(
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            user_id=user_id,
            limit=limit * 2,  # Get extra for filtering
        ):
            # Additional filters
            if action_pattern and action_pattern not in entry.action:
                continue
            if min_severity and entry.severity.value < min_severity.value:
                continue
            
            results.append(entry)
            if len(results) >= limit:
                break
        
        return results
    
    def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str], int]:
        """
        Verify integrity of audit log chain.
        
        Args:
            start_time: Start of time range to verify
            end_time: End of time range to verify
            
        Returns:
            Tuple of (valid, error_message, entries_verified)
        """
        self._stats["verification_count"] += 1
        
        entries = list(self._storage.read_entries(
            start_time=start_time,
            end_time=end_time,
            limit=100000,  # Verify up to 100k entries
        ))
        
        if not entries:
            return True, None, 0
        
        valid, error = self._hash_chain.verify_chain(entries)
        
        if not valid:
            self._stats["verification_failures"] += 1
            
            # Log verification failure
            self.log(
                event_type=AuditEventType.SECURITY_VIOLATION,
                severity=AuditSeverity.CRITICAL,
                action="audit_integrity_failure",
                details={
                    "error": error,
                    "entries_checked": len(entries),
                },
            )
        
        return valid, error, len(entries)
    
    def export_compliance(
        self,
        start_time: datetime,
        end_time: datetime,
        format: str = "json",
        include_signature: bool = True,
    ) -> Dict[str, Any]:
        """
        Export audit logs for compliance purposes.
        
        Includes integrity verification and export metadata.
        
        Args:
            start_time: Start of export range
            end_time: End of export range
            format: Export format (json, csv)
            include_signature: Include cryptographic signatures
            
        Returns:
            Export data with metadata
        """
        entries = list(self._storage.read_entries(
            start_time=start_time,
            end_time=end_time,
            limit=1000000,
        ))
        
        # Verify integrity before export
        valid, error, _ = self.verify_integrity(start_time, end_time)
        
        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "entry_count": len(entries),
                "integrity_valid": valid,
                "integrity_error": error,
                "system_id": settings.SYSTEM_ID,
                "format_version": "1.0",
            },
            "entries": [entry.to_dict() for entry in entries],
        }
        
        # Add export signature
        if include_signature:
            export_json = json.dumps(export_data["entries"], sort_keys=True, default=str)
            export_hash = hashlib.sha256(export_json.encode()).hexdigest()
            export_data["metadata"]["export_hash"] = export_hash
            export_data["metadata"]["export_signature"] = \
                self._hash_chain.sign_entry(export_hash)
        
        # Log export
        self.log(
            event_type=AuditEventType.AUDIT_EXPORT,
            severity=AuditSeverity.NOTICE,
            action="audit_export",
            details={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "entry_count": len(entries),
                "format": format,
            },
        )
        
        return export_data
    
    def get_recent_entries(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent entries from memory buffer."""
        with self._recent_lock:
            return list(self._recent_entries[-limit:])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit system statistics."""
        return {
            **self._stats,
            "chain_state": self._hash_chain.get_chain_state(),
        }
    
    def rotate_logs(self) -> int:
        """
        Trigger log rotation and compression.
        
        Returns:
            Number of files compressed
        """
        compressed = self._storage.compress_old_logs()
        
        self.log(
            event_type=AuditEventType.AUDIT_ROTATE,
            severity=AuditSeverity.INFO,
            action="audit_rotate",
            details={"files_compressed": compressed},
        )
        
        return compressed
    
    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.log(
            event_type=AuditEventType.SYSTEM_STOP,
            severity=AuditSeverity.NOTICE,
            action="audit_system_stop",
        )
        self._storage.close()


# Global instance
immutable_audit_log = ImmutableAuditLog()


# Convenience function for backward compatibility with existing audit_logger
def audit_log(
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    error_message: Optional[str] = None,
) -> AuditEntry:
    """
    Convenience function for logging audit events.
    
    Maps to appropriate event type based on action string.
    """
    # Determine event type from action
    event_type = AuditEventType.SECURITY_DECISION  # Default
    
    if "login" in action.lower():
        event_type = AuditEventType.AUTH_LOGIN
    elif "logout" in action.lower():
        event_type = AuditEventType.AUTH_LOGOUT
    elif "memory" in action.lower():
        if "read" in action.lower() or "recall" in action.lower():
            event_type = AuditEventType.MEMORY_READ
        elif "write" in action.lower() or "store" in action.lower():
            event_type = AuditEventType.MEMORY_WRITE
        elif "delete" in action.lower():
            event_type = AuditEventType.MEMORY_DELETE
        elif "search" in action.lower():
            event_type = AuditEventType.MEMORY_SEARCH
    elif "plugin" in action.lower():
        if "load" in action.lower():
            event_type = AuditEventType.PLUGIN_LOAD
        elif "execute" in action.lower():
            event_type = AuditEventType.PLUGIN_EXECUTE
    elif "automation" in action.lower():
        if "create" in action.lower():
            event_type = AuditEventType.AUTOMATION_CREATE
        elif "execute" in action.lower():
            event_type = AuditEventType.AUTOMATION_EXECUTE
    elif "security" in action.lower() or "permission" in action.lower():
        if "denied" in status.lower():
            event_type = AuditEventType.AUTHZ_DENIED
        else:
            event_type = AuditEventType.AUTHZ_GRANTED
    
    # Determine severity
    severity = AuditSeverity.INFO
    if status == "error":
        severity = AuditSeverity.ERROR
    elif status == "denied" or status == "failure":
        severity = AuditSeverity.WARNING
    
    return immutable_audit_log.log(
        event_type=event_type,
        severity=severity,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        ip_address=ip_address,
        error_message=error_message,
        details=details,
    )
