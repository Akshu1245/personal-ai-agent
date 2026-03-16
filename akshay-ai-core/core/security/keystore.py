"""
============================================================
AKSHAY AI CORE — Secure Key Store
============================================================
PIN-protected key management with lockout protection.
============================================================
"""

import hashlib
import json
import os
import platform
import secrets
import subprocess
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

import base64


class KeyStoreState(Enum):
    """Key store states."""
    UNINITIALIZED = "uninitialized"  # No keys exist
    UNLOCKED = "unlocked"            # Keys decrypted and available
    LOCKED = "locked"                # Keys encrypted, PIN required
    SAFE_MODE = "safe_mode"          # Locked out due to failed attempts


class KeyStoreError(Exception):
    """Key store operation error."""
    pass


class PINValidationError(KeyStoreError):
    """Invalid PIN format."""
    pass


class KeyStoreLockedError(KeyStoreError):
    """Key store is locked and requires PIN."""
    pass


class SafeModeError(KeyStoreError):
    """System is in safe mode due to failed attempts."""
    pass


class KeyStore:
    """
    Secure key store with PIN protection.
    
    Manages:
    - Root Ed25519 keypair
    - PIN-based encryption (scrypt + Fernet)
    - Attempt tracking and lockout
    - Secure key operations
    """
    
    # Constants
    MIN_PIN_LENGTH = 6
    MAX_PIN_LENGTH = 12
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 300  # 5 minutes
    SCRYPT_N = 2**14  # CPU/memory cost
    SCRYPT_R = 8      # Block size
    SCRYPT_P = 1      # Parallelization
    SALT_LENGTH = 16
    ENCRYPTION_MARKER = b"AKSHAY_ENCRYPTED_V1\n"
    
    def __init__(self, install_path: Path):
        self.install_path = Path(install_path)
        self.keys_dir = self.install_path / ".akshay" / "keys"
        self.private_key_file = self.keys_dir / "root_private.key"
        self.encrypted_key_file = self.keys_dir / "root_private.enc"
        self.public_key_file = self.keys_dir / "root_public.key"
        self.state_file = self.keys_dir / "keystore.json"
        self.audit_log = self.install_path / "logs" / "keystore_audit.log"
        
        # Runtime state
        self._state = KeyStoreState.UNINITIALIZED
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key: Optional[Ed25519PublicKey] = None
        self._unlock_time: Optional[float] = None
        
        # Initialize state
        self._load_state()
    
    def _load_state(self) -> None:
        """Load key store state from disk."""
        if not self.keys_dir.exists():
            self._state = KeyStoreState.UNINITIALIZED
            return
        
        if self.encrypted_key_file.exists():
            # Keys are encrypted
            state_data = self._read_state_file()
            if state_data.get("safe_mode", False):
                # Check if lockout has expired
                lockout_until = state_data.get("lockout_until", 0)
                if time.time() < lockout_until:
                    self._state = KeyStoreState.SAFE_MODE
                else:
                    # Lockout expired, reset
                    self._clear_lockout()
                    self._state = KeyStoreState.LOCKED
            else:
                self._state = KeyStoreState.LOCKED
        elif self.private_key_file.exists():
            # Check if key is encrypted (bootstrap stage)
            with open(self.private_key_file, 'rb') as f:
                content = f.read()
            
            if content.startswith(self.ENCRYPTION_MARKER):
                self._state = KeyStoreState.LOCKED
            else:
                # Unencrypted (needs PIN setup)
                self._state = KeyStoreState.UNLOCKED
                self._load_unencrypted_keys()
        else:
            self._state = KeyStoreState.UNINITIALIZED
    
    def _load_unencrypted_keys(self) -> None:
        """Load unencrypted keys (bootstrap stage only)."""
        if self.private_key_file.exists():
            with open(self.private_key_file, 'rb') as f:
                content = f.read()
            
            if not content.startswith(self.ENCRYPTION_MARKER):
                self._private_key = serialization.load_pem_private_key(
                    content,
                    password=None,
                    backend=default_backend()
                )
        
        if self.public_key_file.exists():
            with open(self.public_key_file, 'rb') as f:
                public_pem = f.read()
            
            self._public_key = serialization.load_pem_public_key(
                public_pem,
                backend=default_backend()
            )
    
    def _read_state_file(self) -> dict:
        """Read key store state file."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _write_state_file(self, data: dict) -> None:
        """Write key store state file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _audit_log_event(self, event_type: str, details: str = "", success: bool = True) -> None:
        """Log security event to audit log."""
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).isoformat()
        status = "SUCCESS" if success else "FAILURE"
        
        log_entry = f"{timestamp} | {event_type} | {status} | {details}\n"
        
        with open(self.audit_log, 'a') as f:
            f.write(log_entry)
    
    @property
    def state(self) -> KeyStoreState:
        """Get current key store state."""
        return self._state
    
    @property
    def is_unlocked(self) -> bool:
        """Check if key store is unlocked."""
        return self._state == KeyStoreState.UNLOCKED
    
    @property
    def is_locked(self) -> bool:
        """Check if key store is locked."""
        return self._state in (KeyStoreState.LOCKED, KeyStoreState.SAFE_MODE)
    
    @property
    def is_safe_mode(self) -> bool:
        """Check if in safe mode (lockout)."""
        return self._state == KeyStoreState.SAFE_MODE
    
    @property
    def needs_pin_setup(self) -> bool:
        """Check if PIN setup is needed (unencrypted keys exist)."""
        if not self.private_key_file.exists():
            return False
        
        with open(self.private_key_file, 'rb') as f:
            content = f.read()
        
        return not content.startswith(self.ENCRYPTION_MARKER)
    
    def validate_pin_format(self, pin: str) -> Tuple[bool, str]:
        """
        Validate PIN format.
        Returns (is_valid, error_message).
        """
        if not pin:
            return False, "PIN cannot be empty"
        
        if not pin.isdigit():
            return False, "PIN must contain only digits"
        
        if len(pin) < self.MIN_PIN_LENGTH:
            return False, f"PIN must be at least {self.MIN_PIN_LENGTH} digits"
        
        if len(pin) > self.MAX_PIN_LENGTH:
            return False, f"PIN must be at most {self.MAX_PIN_LENGTH} digits"
        
        # Check for weak patterns
        if pin == pin[0] * len(pin):  # All same digit
            return False, "PIN cannot be all the same digit"
        
        if pin in ("123456", "654321", "000000", "111111", "123456789012"):
            return False, "PIN is too common, choose a stronger one"
        
        return True, ""
    
    def _derive_key(self, pin: str, salt: bytes) -> bytes:
        """Derive encryption key from PIN using scrypt."""
        kdf = Scrypt(
            salt=salt,
            length=32,
            n=self.SCRYPT_N,
            r=self.SCRYPT_R,
            p=self.SCRYPT_P,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(pin.encode()))
    
    def _encrypt_key(self, private_key: Ed25519PrivateKey, pin: str) -> bytes:
        """Encrypt private key with PIN."""
        # Generate salt
        salt = os.urandom(self.SALT_LENGTH)
        
        # Derive encryption key
        encryption_key = self._derive_key(pin, salt)
        
        # Get private key bytes
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Encrypt with Fernet
        fernet = Fernet(encryption_key)
        encrypted = fernet.encrypt(private_pem)
        
        # Return salt + encrypted data
        return salt + encrypted
    
    def _decrypt_key(self, encrypted_data: bytes, pin: str) -> Optional[Ed25519PrivateKey]:
        """Decrypt private key with PIN."""
        # Extract salt
        salt = encrypted_data[:self.SALT_LENGTH]
        encrypted = encrypted_data[self.SALT_LENGTH:]
        
        try:
            # Derive key
            encryption_key = self._derive_key(pin, salt)
            
            # Decrypt
            fernet = Fernet(encryption_key)
            private_pem = fernet.decrypt(encrypted)
            
            # Load key
            private_key = serialization.load_pem_private_key(
                private_pem,
                password=None,
                backend=default_backend()
            )
            
            return private_key
        except Exception:
            return None
    
    def _secure_delete(self, file_path: Path) -> bool:
        """Securely delete a file by overwriting before deletion."""
        if not file_path.exists():
            return True
        
        try:
            # Get file size
            file_size = file_path.stat().st_size
            
            # Overwrite with random data 3 times
            for _ in range(3):
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            # Overwrite with zeros
            with open(file_path, 'wb') as f:
                f.write(b'\x00' * file_size)
                f.flush()
                os.fsync(f.fileno())
            
            # Delete file
            file_path.unlink()
            
            return True
        except Exception:
            # Fallback to regular delete
            try:
                file_path.unlink()
                return True
            except Exception:
                return False
    
    def _record_attempt(self, success: bool) -> int:
        """Record a PIN attempt. Returns remaining attempts."""
        state_data = self._read_state_file()
        
        if success:
            # Reset attempts on success
            state_data["failed_attempts"] = 0
            state_data["last_attempt"] = None
            state_data["safe_mode"] = False
            state_data["lockout_until"] = 0
        else:
            # Increment failed attempts
            attempts = state_data.get("failed_attempts", 0) + 1
            state_data["failed_attempts"] = attempts
            state_data["last_attempt"] = datetime.now(timezone.utc).isoformat()
            
            if attempts >= self.MAX_ATTEMPTS:
                # Trigger safe mode
                state_data["safe_mode"] = True
                state_data["lockout_until"] = time.time() + self.LOCKOUT_DURATION
                self._state = KeyStoreState.SAFE_MODE
        
        self._write_state_file(state_data)
        
        remaining = max(0, self.MAX_ATTEMPTS - state_data.get("failed_attempts", 0))
        return remaining
    
    def _clear_lockout(self) -> None:
        """Clear lockout state."""
        state_data = self._read_state_file()
        state_data["failed_attempts"] = 0
        state_data["safe_mode"] = False
        state_data["lockout_until"] = 0
        self._write_state_file(state_data)
    
    def get_attempts_remaining(self) -> int:
        """Get remaining PIN attempts before lockout."""
        state_data = self._read_state_file()
        attempts = state_data.get("failed_attempts", 0)
        return max(0, self.MAX_ATTEMPTS - attempts)
    
    def get_lockout_remaining(self) -> int:
        """Get seconds remaining in lockout. Returns 0 if not locked out."""
        state_data = self._read_state_file()
        lockout_until = state_data.get("lockout_until", 0)
        remaining = int(lockout_until - time.time())
        return max(0, remaining)
    
    def setup_pin(self, pin: str) -> Tuple[bool, str]:
        """
        Set up PIN encryption for unencrypted keys.
        This is called during first-run wizard.
        
        Returns (success, error_message).
        """
        # Validate PIN format
        valid, error = self.validate_pin_format(pin)
        if not valid:
            raise PINValidationError(error)
        
        # Check if unencrypted key exists
        if not self.private_key_file.exists():
            return False, "No private key to encrypt"
        
        # Read current key
        with open(self.private_key_file, 'rb') as f:
            content = f.read()
        
        if content.startswith(self.ENCRYPTION_MARKER):
            return False, "Key is already encrypted"
        
        # Load the unencrypted key
        try:
            private_key = serialization.load_pem_private_key(
                content,
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            return False, f"Failed to load private key: {e}"
        
        # Encrypt the key
        encrypted_data = self._encrypt_key(private_key, pin)
        
        # Write encrypted key to new file
        self.encrypted_key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.encrypted_key_file, 'wb') as f:
            f.write(self.ENCRYPTION_MARKER)
            f.write(encrypted_data)
        
        # Set restrictive permissions
        if platform.system() == "Windows":
            subprocess.run(
                f'icacls "{self.encrypted_key_file}" /inheritance:r /grant:r "%USERNAME%":F',
                shell=True, capture_output=True
            )
        else:
            os.chmod(self.encrypted_key_file, 0o600)
        
        # Securely delete unencrypted key
        if not self._secure_delete(self.private_key_file):
            # Rollback - delete encrypted and keep unencrypted
            self.encrypted_key_file.unlink(missing_ok=True)
            return False, "Failed to securely delete unencrypted key"
        
        # Store PIN hash for verification (not for decryption)
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        state_data = self._read_state_file()
        state_data["pin_hash"] = pin_hash
        state_data["pin_set_at"] = datetime.now(timezone.utc).isoformat()
        state_data["failed_attempts"] = 0
        state_data["safe_mode"] = False
        self._write_state_file(state_data)
        
        # Update state
        self._state = KeyStoreState.LOCKED
        self._private_key = None
        
        self._audit_log_event("PIN_SETUP", "PIN encryption configured")
        
        return True, ""
    
    def unlock(self, pin: str) -> Tuple[bool, str]:
        """
        Unlock the key store with PIN.
        
        Returns (success, error_message).
        """
        # Check for safe mode
        if self._state == KeyStoreState.SAFE_MODE:
            remaining = self.get_lockout_remaining()
            if remaining > 0:
                raise SafeModeError(
                    f"System is in safe mode. Try again in {remaining} seconds."
                )
            else:
                # Lockout expired
                self._clear_lockout()
                self._state = KeyStoreState.LOCKED
        
        # Already unlocked?
        if self._state == KeyStoreState.UNLOCKED:
            return True, ""
        
        # Load encrypted key
        key_file = self.encrypted_key_file if self.encrypted_key_file.exists() else self.private_key_file
        
        if not key_file.exists():
            return False, "No encrypted key found"
        
        with open(key_file, 'rb') as f:
            content = f.read()
        
        if not content.startswith(self.ENCRYPTION_MARKER):
            # Unencrypted - just load
            self._load_unencrypted_keys()
            self._state = KeyStoreState.UNLOCKED
            return True, ""
        
        # Extract encrypted data
        encrypted_data = content[len(self.ENCRYPTION_MARKER):]
        
        # Try to decrypt
        private_key = self._decrypt_key(encrypted_data, pin)
        
        if private_key is None:
            # Wrong PIN
            remaining = self._record_attempt(False)
            self._audit_log_event("UNLOCK_ATTEMPT", f"Failed. {remaining} attempts remaining", success=False)
            
            if remaining == 0:
                raise SafeModeError("Too many failed attempts. System entering safe mode.")
            
            return False, f"Invalid PIN. {remaining} attempts remaining."
        
        # Success
        self._record_attempt(True)
        self._private_key = private_key
        self._public_key = self._private_key.public_key() if self._private_key else None
        self._state = KeyStoreState.UNLOCKED
        self._unlock_time = time.time()
        
        self._audit_log_event("UNLOCK", "Key store unlocked")
        
        return True, ""
    
    def lock(self) -> None:
        """Lock the key store, clearing keys from memory."""
        self._private_key = None
        self._unlock_time = None
        
        if self.encrypted_key_file.exists() or self._has_encrypted_key():
            self._state = KeyStoreState.LOCKED
        
        self._audit_log_event("LOCK", "Key store locked")
    
    def _has_encrypted_key(self) -> bool:
        """Check if private key file contains encrypted key."""
        if self.private_key_file.exists():
            with open(self.private_key_file, 'rb') as f:
                return f.read(len(self.ENCRYPTION_MARKER)) == self.ENCRYPTION_MARKER
        return False
    
    def change_pin(self, old_pin: str, new_pin: str) -> Tuple[bool, str]:
        """
        Change the PIN.
        
        Returns (success, error_message).
        """
        # Validate new PIN
        valid, error = self.validate_pin_format(new_pin)
        if not valid:
            raise PINValidationError(error)
        
        # Unlock with old PIN
        success, error = self.unlock(old_pin)
        if not success:
            return False, error
        
        # Re-encrypt with new PIN
        encrypted_data = self._encrypt_key(self._private_key, new_pin)
        
        # Write new encrypted key
        with open(self.encrypted_key_file, 'wb') as f:
            f.write(self.ENCRYPTION_MARKER)
            f.write(encrypted_data)
        
        # Update PIN hash
        pin_hash = hashlib.sha256(new_pin.encode()).hexdigest()
        state_data = self._read_state_file()
        state_data["pin_hash"] = pin_hash
        state_data["pin_changed_at"] = datetime.now(timezone.utc).isoformat()
        self._write_state_file(state_data)
        
        # Lock again
        self.lock()
        
        self._audit_log_event("PIN_CHANGE", "PIN changed successfully")
        
        return True, ""
    
    def get_private_key(self) -> Ed25519PrivateKey:
        """
        Get the private key (requires unlocked state).
        
        Raises KeyStoreLockedError if locked.
        """
        if self._state != KeyStoreState.UNLOCKED:
            raise KeyStoreLockedError("Key store is locked. Call unlock() first.")
        
        if self._private_key is None:
            raise KeyStoreLockedError("Private key not loaded.")
        
        self._audit_log_event("KEY_ACCESS", "Private key accessed")
        
        return self._private_key
    
    def get_public_key(self) -> Optional[Ed25519PublicKey]:
        """Get the public key (does not require unlocked state)."""
        if self._public_key:
            return self._public_key
        
        if self.public_key_file.exists():
            with open(self.public_key_file, 'rb') as f:
                public_pem = f.read()
            
            self._public_key = serialization.load_pem_public_key(
                public_pem,
                backend=default_backend()
            )
            return self._public_key
        
        return None
    
    def sign(self, data: bytes) -> bytes:
        """
        Sign data with the private key (requires unlocked state).
        
        Returns signature bytes.
        """
        private_key = self.get_private_key()
        signature = private_key.sign(data)
        
        self._audit_log_event("SIGN", f"Signed {len(data)} bytes")
        
        return signature
    
    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify a signature (does not require unlocked state)."""
        public_key = self.get_public_key()
        if not public_key:
            return False
        
        try:
            public_key.verify(signature, data)
            return True
        except Exception:
            return False
    
    def get_status(self) -> dict:
        """Get key store status information."""
        state_data = self._read_state_file()
        
        return {
            "state": self._state.value,
            "is_unlocked": self.is_unlocked,
            "is_locked": self.is_locked,
            "is_safe_mode": self.is_safe_mode,
            "needs_pin_setup": self.needs_pin_setup,
            "attempts_remaining": self.get_attempts_remaining(),
            "lockout_remaining": self.get_lockout_remaining(),
            "pin_set_at": state_data.get("pin_set_at"),
            "has_public_key": self.public_key_file.exists(),
            "has_encrypted_key": self.encrypted_key_file.exists() or self._has_encrypted_key(),
        }
    
    def reset_for_recovery(self, recovery_token: str) -> Tuple[bool, str]:
        """
        Reset PIN using recovery key (clears lockout).
        This should be called from recovery mode.
        
        Returns (success, error_message).
        """
        # Verify recovery token
        from .bootstrap import RootKeyManager
        
        key_manager = RootKeyManager(self.install_path)
        if not key_manager.verify_recovery_key(recovery_token):
            self._audit_log_event("RECOVERY_ATTEMPT", "Invalid recovery token", success=False)
            return False, "Invalid recovery token"
        
        # Clear lockout
        self._clear_lockout()
        self._state = KeyStoreState.LOCKED
        
        # Mark recovery key as used
        key_manager.mark_recovery_key_used()
        
        self._audit_log_event("RECOVERY", "Lockout cleared via recovery key")
        
        return True, "Lockout cleared. Please set a new PIN."


# ============================================================
# CLI Interface for PowerShell Integration
# ============================================================

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AKSHAY AI CORE Key Store")
    parser.add_argument("--install-path", required=True, help="Installation path")
    parser.add_argument("--action", required=True,
                        choices=["status", "setup-pin", "unlock", "lock", "change-pin", "reset"],
                        help="Action to perform")
    parser.add_argument("--pin", help="PIN for operations")
    parser.add_argument("--new-pin", help="New PIN for change-pin")
    parser.add_argument("--recovery-token", help="Recovery token for reset")
    parser.add_argument("--output", choices=["json", "text"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    keystore = KeyStore(Path(args.install_path))
    result = {}
    
    try:
        if args.action == "status":
            result = keystore.get_status()
            result["success"] = True
        
        elif args.action == "setup-pin":
            if not args.pin:
                result = {"success": False, "error": "PIN required for setup-pin"}
            else:
                success, error = keystore.setup_pin(args.pin)
                result = {"success": success, "error": error if not success else None}
        
        elif args.action == "unlock":
            if not args.pin:
                result = {"success": False, "error": "PIN required for unlock"}
            else:
                success, error = keystore.unlock(args.pin)
                result = {
                    "success": success,
                    "error": error if not success else None,
                    "state": keystore.state.value
                }
        
        elif args.action == "lock":
            keystore.lock()
            result = {"success": True, "state": keystore.state.value}
        
        elif args.action == "change-pin":
            if not args.pin or not args.new_pin:
                result = {"success": False, "error": "Both --pin and --new-pin required"}
            else:
                success, error = keystore.change_pin(args.pin, args.new_pin)
                result = {"success": success, "error": error if not success else None}
        
        elif args.action == "reset":
            if not args.recovery_token:
                result = {"success": False, "error": "Recovery token required for reset"}
            else:
                success, error = keystore.reset_for_recovery(args.recovery_token)
                result = {"success": success, "error": error if not success else None}
    
    except PINValidationError as e:
        result = {"success": False, "error": str(e), "error_type": "pin_validation"}
    except KeyStoreLockedError as e:
        result = {"success": False, "error": str(e), "error_type": "locked"}
    except SafeModeError as e:
        result = {"success": False, "error": str(e), "error_type": "safe_mode"}
    except Exception as e:
        result = {"success": False, "error": str(e), "error_type": "unknown"}
    
    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            for key, value in result.items():
                if key != "success":
                    print(f"{key}: {value}")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")
    
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
