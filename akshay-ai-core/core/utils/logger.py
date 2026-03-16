"""
============================================================
AKSHAY AI CORE — Logging System
============================================================
Structured logging with file rotation, JSON formatting,
and immutable audit log support.
============================================================
"""

import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

import structlog
from loguru import logger

from core.config import settings


def setup_logging() -> None:
    """
    Configure the logging system.
    
    Sets up:
    - Console output with rich formatting
    - JSON file logging with rotation
    - Structured logging with context
    """
    # Remove default handler
    logger.remove()
    
    # Ensure log directory exists
    log_dir = Path(settings.LOGS_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Console handler with color
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    if settings.DEBUG or settings.DEV_VERBOSE_LOGGING:
        logger.add(
            sys.stderr,
            format=log_format,
            level="DEBUG",
            colorize=True,
        )
    else:
        logger.add(
            sys.stderr,
            format=log_format,
            level=settings.LOG_LEVEL,
            colorize=True,
        )
    
    # JSON file handler with rotation
    logger.add(
        str(log_dir / "akshay_core_{time:YYYY-MM-DD}.log"),
        format="{message}",
        level=settings.LOG_LEVEL,
        rotation=f"{settings.LOG_MAX_SIZE_MB} MB",
        retention=settings.LOG_BACKUP_COUNT,
        compression="gz",
        serialize=True,
    )
    
    # Error file handler
    logger.add(
        str(log_dir / "errors_{time:YYYY-MM-DD}.log"),
        format="{message}",
        level="ERROR",
        rotation=f"{settings.LOG_MAX_SIZE_MB} MB",
        retention=settings.LOG_BACKUP_COUNT,
        compression="gz",
        serialize=True,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, settings.LOG_LEVEL, structlog.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger with the given name.
    
    Args:
        name: Logger name (usually module name)
        
    Returns:
        Configured structlog bound logger
    """
    return structlog.get_logger(name)


class AuditLogger:
    """
    Immutable audit logging system.
    
    Creates tamper-evident logs with checksums for security auditing.
    """
    
    def __init__(self):
        self.log_dir = Path(settings.LOGS_DIR) / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._previous_checksum: Optional[str] = None
        self._load_last_checksum()
    
    def _load_last_checksum(self) -> None:
        """Load the last checksum from the audit chain."""
        checksum_file = self.log_dir / ".audit_chain"
        if checksum_file.exists():
            self._previous_checksum = checksum_file.read_text().strip()
    
    def _save_checksum(self, checksum: str) -> None:
        """Save the current checksum to maintain the chain."""
        checksum_file = self.log_dir / ".audit_chain"
        checksum_file.write_text(checksum)
        self._previous_checksum = checksum
    
    def _compute_checksum(self, data: dict) -> str:
        """
        Compute SHA-256 checksum for audit entry.
        
        Includes previous checksum to create a chain.
        """
        # Include previous checksum in the hash chain
        chain_data = {
            **data,
            "previous_checksum": self._previous_checksum or "GENESIS",
        }
        
        serialized = json.dumps(chain_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def log(
        self,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> dict:
        """
        Create an immutable audit log entry.
        
        Args:
            action: Action performed (e.g., "login", "access_data")
            user_id: User who performed the action
            resource_type: Type of resource accessed
            resource_id: ID of resource accessed
            details: Additional details
            status: success, failure, or error
            ip_address: Client IP address
            error_message: Error message if applicable
            
        Returns:
            The audit log entry with checksum
        """
        timestamp = datetime.utcnow().isoformat()
        
        entry = {
            "timestamp": timestamp,
            "action": action,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "status": status,
            "ip_address": ip_address,
            "error_message": error_message,
        }
        
        # Compute checksum (includes chain)
        checksum = self._compute_checksum(entry)
        entry["checksum"] = checksum
        
        # Write to audit log file
        log_file = self.log_dir / f"audit_{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        
        # Update chain
        self._save_checksum(checksum)
        
        # Also log to main logger
        log = get_logger("audit")
        log.info(
            "audit_event",
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            status=status,
        )
        
        return entry
    
    def verify_chain(self, date: Optional[str] = None) -> tuple[bool, list[dict]]:
        """
        Verify the integrity of the audit log chain.
        
        Args:
            date: Date to verify (YYYY-MM-DD), defaults to today
            
        Returns:
            Tuple of (is_valid, invalid_entries)
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        log_file = self.log_dir / f"audit_{date}.jsonl"
        
        if not log_file.exists():
            return True, []
        
        invalid_entries = []
        previous_checksum = None
        
        with open(log_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = json.loads(line.strip())
                    stored_checksum = entry.pop("checksum", None)
                    
                    # Recompute checksum
                    chain_data = {
                        **entry,
                        "previous_checksum": previous_checksum or "GENESIS",
                    }
                    computed = hashlib.sha256(
                        json.dumps(chain_data, sort_keys=True, default=str).encode()
                    ).hexdigest()
                    
                    if computed != stored_checksum:
                        invalid_entries.append({
                            "line": line_num,
                            "entry": entry,
                            "expected": computed,
                            "stored": stored_checksum,
                        })
                    
                    previous_checksum = stored_checksum
                    
                except json.JSONDecodeError as e:
                    invalid_entries.append({
                        "line": line_num,
                        "error": f"Invalid JSON: {e}",
                    })
        
        return len(invalid_entries) == 0, invalid_entries


# Global audit logger instance
audit_logger = AuditLogger()
