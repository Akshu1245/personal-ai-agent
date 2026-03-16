"""
============================================================
AKSHAY AI CORE — Security Bootstrap Module
============================================================
Establishes cryptographic root of trust for the system.
============================================================
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import base64


class DeviceIdentity:
    """Generates and manages device identity."""
    
    def __init__(self, install_path: Path):
        self.install_path = Path(install_path)
        self.device_file = self.install_path / ".akshay" / "device.json"
    
    def _get_hardware_fingerprint(self) -> str:
        """Generate hardware fingerprint from system identifiers."""
        components = []
        
        # CPU info
        try:
            if platform.system() == "Windows":
                # Get processor ID on Windows
                result = subprocess.run(
                    ["wmic", "cpu", "get", "ProcessorId"],
                    capture_output=True, text=True, timeout=5
                )
                cpu_id = result.stdout.strip().split('\n')[-1].strip()
                if cpu_id and cpu_id != "ProcessorId":
                    components.append(f"cpu:{cpu_id}")
            else:
                # Linux/Mac - use /proc/cpuinfo or sysctl
                components.append(f"cpu:{platform.processor()}")
        except Exception:
            components.append(f"cpu:{platform.processor()}")
        
        # Disk serial (Windows)
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "diskdrive", "get", "SerialNumber"],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                if len(lines) > 1:
                    disk_serial = lines[1]
                    if disk_serial and disk_serial != "SerialNumber":
                        components.append(f"disk:{disk_serial}")
        except Exception:
            pass
        
        # Machine ID fallback
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "UUID"],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                if len(lines) > 1:
                    machine_uuid = lines[1]
                    if machine_uuid and machine_uuid != "UUID":
                        components.append(f"machine:{machine_uuid}")
        except Exception:
            pass
        
        # If no hardware identifiers, use hostname + username as fallback
        if not components:
            components.append(f"host:{platform.node()}")
            components.append(f"user:{os.getenv('USERNAME', os.getenv('USER', 'unknown'))}")
        
        # Create SHA-256 hash of all components
        fingerprint_data = "|".join(sorted(components))
        fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()
        
        return fingerprint
    
    def generate(self) -> dict:
        """Generate new device identity."""
        device_id = str(uuid.uuid4())
        hardware_fingerprint = self._get_hardware_fingerprint()
        
        identity = {
            "device_id": device_id,
            "hardware_fingerprint": hardware_fingerprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "python_version": platform.python_version(),
            "os_version": f"{platform.system()} {platform.release()}",
            "hostname": platform.node(),
        }
        
        return identity
    
    def save(self, identity: dict) -> None:
        """Save device identity to file."""
        self.device_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.device_file, 'w') as f:
            json.dump(identity, f, indent=2)
        
        # Set read-only permissions (suppress output)
        if platform.system() == "Windows":
            subprocess.run(f'attrib +R "{self.device_file}"', shell=True, capture_output=True)
    
    def load(self) -> Optional[dict]:
        """Load existing device identity."""
        if self.device_file.exists():
            with open(self.device_file, 'r') as f:
                return json.load(f)
        return None
    
    def exists(self) -> bool:
        """Check if device identity exists."""
        return self.device_file.exists()


class RootKeyManager:
    """Manages Ed25519 root keypair for system sovereignty."""
    
    def __init__(self, install_path: Path):
        self.install_path = Path(install_path)
        self.keys_dir = self.install_path / ".akshay" / "keys"
        self.private_key_file = self.keys_dir / "root_private.key"
        self.public_key_file = self.keys_dir / "root_public.key"
        self.recovery_key_file = self.keys_dir / "recovery.key"
    
    def generate_keypair(self) -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Generate new Ed25519 keypair using cryptographically secure RNG."""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key
    
    def save_keypair_unencrypted(
        self, 
        private_key: Ed25519PrivateKey, 
        public_key: Ed25519PublicKey
    ) -> None:
        """
        Save keypair without encryption (temporary, for bootstrap).
        Private key will be encrypted later during first-run wizard.
        """
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Save private key (PEM format, unencrypted - TEMPORARY)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(self.private_key_file, 'wb') as f:
            f.write(private_pem)
        
        # Set restrictive permissions on private key (suppress output)
        if platform.system() == "Windows":
            # Remove inheritance and set owner-only access
            subprocess.run(
                f'icacls "{self.private_key_file}" /inheritance:r /grant:r "%USERNAME%":F',
                shell=True, capture_output=True
            )
        else:
            os.chmod(self.private_key_file, 0o600)
        
        # Save public key (PEM format)
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        with open(self.public_key_file, 'wb') as f:
            f.write(public_pem)
        
        # Public key can be read-only (suppress output)
        if platform.system() == "Windows":
            subprocess.run(f'attrib +R "{self.public_key_file}"', shell=True, capture_output=True)
        else:
            os.chmod(self.public_key_file, 0o644)
    
    def encrypt_private_key(self, private_key: Ed25519PrivateKey, pin: str) -> bytes:
        """
        Encrypt private key using PIN with scrypt KDF.
        Returns encrypted key bytes.
        """
        # Generate salt
        salt = os.urandom(16)
        
        # Derive key from PIN using scrypt
        kdf = Scrypt(
            salt=salt,
            length=32,
            n=2**14,  # CPU/memory cost
            r=8,      # Block size
            p=1,      # Parallelization
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(pin.encode()))
        
        # Get private key bytes
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Encrypt with Fernet
        fernet = Fernet(key)
        encrypted = fernet.encrypt(private_pem)
        
        # Prepend salt to encrypted data
        return salt + encrypted
    
    def save_encrypted_private_key(self, encrypted_data: bytes) -> None:
        """Save encrypted private key, replacing unencrypted version."""
        # Write encrypted key with marker
        with open(self.private_key_file, 'wb') as f:
            f.write(b"AKSHAY_ENCRYPTED_V1\n")
            f.write(encrypted_data)
        
        # Restrictive permissions (suppress output)
        if platform.system() == "Windows":
            subprocess.run(
                f'icacls "{self.private_key_file}" /inheritance:r /grant:r "%USERNAME%":F',
                shell=True, capture_output=True
            )
        else:
            os.chmod(self.private_key_file, 0o600)
    
    def decrypt_private_key(self, pin: str) -> Optional[Ed25519PrivateKey]:
        """Decrypt and load private key using PIN."""
        if not self.private_key_file.exists():
            return None
        
        with open(self.private_key_file, 'rb') as f:
            content = f.read()
        
        # Check if encrypted
        if content.startswith(b"AKSHAY_ENCRYPTED_V1\n"):
            encrypted_data = content[len(b"AKSHAY_ENCRYPTED_V1\n"):]
            
            # Extract salt (first 16 bytes)
            salt = encrypted_data[:16]
            encrypted = encrypted_data[16:]
            
            # Derive key from PIN
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=2**14,
                r=8,
                p=1,
                backend=default_backend()
            )
            
            try:
                key = base64.urlsafe_b64encode(kdf.derive(pin.encode()))
                fernet = Fernet(key)
                private_pem = fernet.decrypt(encrypted)
            except Exception:
                return None  # Wrong PIN or corrupted
        else:
            # Unencrypted (legacy/bootstrap)
            private_pem = content
        
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_pem,
            password=None,
            backend=default_backend()
        )
        
        return private_key
    
    def load_public_key(self) -> Optional[Ed25519PublicKey]:
        """Load public key from file."""
        if not self.public_key_file.exists():
            return None
        
        with open(self.public_key_file, 'rb') as f:
            public_pem = f.read()
        
        public_key = serialization.load_pem_public_key(
            public_pem,
            backend=default_backend()
        )
        
        return public_key
    
    def get_public_key_fingerprint(self) -> Optional[str]:
        """Get SHA-256 fingerprint of public key."""
        public_key = self.load_public_key()
        if not public_key:
            return None
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        return hashlib.sha256(public_bytes).hexdigest()
    
    def is_private_key_encrypted(self) -> bool:
        """Check if private key is encrypted."""
        if not self.private_key_file.exists():
            return False
        
        with open(self.private_key_file, 'rb') as f:
            header = f.read(20)
        
        return header.startswith(b"AKSHAY_ENCRYPTED_V1")
    
    def generate_recovery_key(self) -> str:
        """
        Generate one-time recovery key.
        Returns printable recovery token.
        """
        # Generate 256-bit random token
        token_bytes = os.urandom(32)
        token = base64.b32encode(token_bytes).decode().rstrip('=')
        
        # Format as groups of 4 for readability
        formatted = '-'.join([token[i:i+4] for i in range(0, len(token), 4)])
        
        # Hash token for storage (never store plaintext)
        token_hash = hashlib.sha256(token_bytes).hexdigest()
        
        # Save hashed token
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        recovery_data = {
            "token_hash": token_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used": False,
            "use_count": 0,
            "max_uses": 1  # One-time use
        }
        
        with open(self.recovery_key_file, 'w') as f:
            json.dump(recovery_data, f, indent=2)
        
        # Restrictive permissions (suppress output)
        if platform.system() == "Windows":
            subprocess.run(
                f'icacls "{self.recovery_key_file}" /inheritance:r /grant:r "%USERNAME%":F',
                shell=True, capture_output=True
            )
        else:
            os.chmod(self.recovery_key_file, 0o600)
        
        return formatted
    
    def verify_recovery_key(self, token: str) -> bool:
        """Verify recovery key token."""
        if not self.recovery_key_file.exists():
            return False
        
        with open(self.recovery_key_file, 'r') as f:
            recovery_data = json.load(f)
        
        if recovery_data.get("used", False):
            return False
        
        # Remove formatting and decode
        clean_token = token.replace('-', '')
        # Pad to multiple of 8 for base32
        padding = (8 - len(clean_token) % 8) % 8
        clean_token += '=' * padding
        
        try:
            token_bytes = base64.b32decode(clean_token)
        except Exception:
            return False
        
        # Verify hash
        token_hash = hashlib.sha256(token_bytes).hexdigest()
        
        return token_hash == recovery_data.get("token_hash")
    
    def mark_recovery_key_used(self) -> None:
        """Mark recovery key as used."""
        if self.recovery_key_file.exists():
            with open(self.recovery_key_file, 'r') as f:
                recovery_data = json.load(f)
            
            recovery_data["used"] = True
            recovery_data["use_count"] = recovery_data.get("use_count", 0) + 1
            recovery_data["used_at"] = datetime.now(timezone.utc).isoformat()
            
            with open(self.recovery_key_file, 'w') as f:
                json.dump(recovery_data, f, indent=2)


class PolicySigner:
    """Signs and verifies policies using Ed25519."""
    
    def __init__(self, install_path: Path):
        self.install_path = Path(install_path)
        self.key_manager = RootKeyManager(install_path)
    
    def sign_policy(self, policy_content: bytes, private_key: Ed25519PrivateKey) -> bytes:
        """Sign policy content and return signature."""
        signature = private_key.sign(policy_content)
        return signature
    
    def verify_policy(self, policy_content: bytes, signature: bytes) -> bool:
        """Verify policy signature using public key."""
        public_key = self.key_manager.load_public_key()
        if not public_key:
            return False
        
        try:
            public_key.verify(signature, policy_content)
            return True
        except Exception:
            return False
    
    def get_policy_hash(self, policy_content: bytes) -> str:
        """Get SHA-256 hash of policy content."""
        return hashlib.sha256(policy_content).hexdigest()


class InstallAudit:
    """Manages installation audit records."""
    
    def __init__(self, install_path: Path):
        self.install_path = Path(install_path)
        self.audit_file = self.install_path / "logs" / "install_audit.json"
    
    def create_record(
        self,
        device_id: str,
        policy_hash: str,
        public_key_fingerprint: str,
        installer_version: str,
        mode: str = "normal"
    ) -> dict:
        """Create installation audit record."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id,
            "policy_hash": policy_hash,
            "public_key_fingerprint": public_key_fingerprint,
            "installer_version": installer_version,
            "install_mode": mode,
            "python_version": platform.python_version(),
            "os_info": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine()
            },
            "events": []
        }
        
        return record
    
    def add_event(self, record: dict, event_type: str, details: str = "") -> dict:
        """Add event to audit record."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "details": details
        }
        record["events"].append(event)
        return record
    
    def save(self, record: dict) -> None:
        """Save audit record to file."""
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.audit_file, 'w') as f:
            json.dump(record, f, indent=2)
    
    def load(self) -> Optional[dict]:
        """Load existing audit record."""
        if self.audit_file.exists():
            with open(self.audit_file, 'r') as f:
                return json.load(f)
        return None


class SecurityBootstrap:
    """Main bootstrap orchestrator."""
    
    def __init__(self, install_path: Path, version: str = "1.0.0", mode: str = "normal"):
        self.install_path = Path(install_path)
        self.version = version
        self.mode = mode
        
        self.device = DeviceIdentity(install_path)
        self.keys = RootKeyManager(install_path)
        self.signer = PolicySigner(install_path)
        self.audit = InstallAudit(install_path)
        
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key: Optional[Ed25519PublicKey] = None
        self._device_identity: Optional[dict] = None
        self._audit_record: Optional[dict] = None
    
    def step1_generate_device_identity(self) -> dict:
        """Step 1: Generate and save device identity."""
        if self.device.exists():
            # Load existing identity
            self._device_identity = self.device.load()
            return self._device_identity
        
        # Generate new identity
        self._device_identity = self.device.generate()
        self.device.save(self._device_identity)
        
        return self._device_identity
    
    def step2_generate_root_keypair(self) -> Tuple[str, str]:
        """
        Step 2: Generate Ed25519 root keypair.
        Returns (private_key_path, public_key_path).
        Private key is unencrypted at this stage.
        """
        # Check if keys already exist
        if self.keys.public_key_file.exists():
            self._public_key = self.keys.load_public_key()
            # Also load private key for signing (unencrypted at this stage)
            self._private_key = self.keys.decrypt_private_key("")  # Empty PIN for unencrypted
            fingerprint = self.keys.get_public_key_fingerprint()
            return (str(self.keys.private_key_file), str(self.keys.public_key_file))
        
        # Generate new keypair
        self._private_key, self._public_key = self.keys.generate_keypair()
        
        # Save unencrypted (will be encrypted during first-run wizard)
        self.keys.save_keypair_unencrypted(self._private_key, self._public_key)
        
        return (str(self.keys.private_key_file), str(self.keys.public_key_file))
    
    def step3_create_default_policy(self) -> Tuple[str, str]:
        """
        Step 3: Create and sign default policy files.
        Returns (base_policy_path, active_policy_path).
        """
        policies_dir = self.install_path / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)
        
        base_policy_path = policies_dir / "base.yaml"
        active_policy_path = policies_dir / "active.yaml"
        signature_path = policies_dir / "active.yaml.sig"
        
        # Default policy content
        base_policy = """# ============================================================
# AKSHAY AI CORE — Base Security Policy
# ============================================================
# This policy defines the default security boundaries.
# DO NOT MODIFY - create custom policies in policies/custom/
# ============================================================

version: "1.0"
policy_id: "base-default"
created_at: "{timestamp}"

# Trust Zones
trust_zones:
  owner:
    description: "Full system owner with all permissions"
    level: 100
  admin:
    description: "Administrator with elevated permissions"
    level: 80
  user:
    description: "Standard user with normal permissions"
    level: 50
  guest:
    description: "Guest with limited permissions"
    level: 20
  demo:
    description: "Demo mode with restricted capabilities"
    level: 10

# Default Permissions
permissions:
  terminal:
    enabled: true
    require_confirmation: true
    blocked_commands:
      - "rm -rf /"
      - "format"
      - "del /s /q"
    max_execution_time: 300
  
  file_system:
    enabled: true
    allowed_paths:
      - "$INSTALL_PATH/data"
      - "$INSTALL_PATH/config"
      - "$INSTALL_PATH/logs"
    denied_paths:
      - "$INSTALL_PATH/.akshay/keys"
      - "$SYSTEM_ROOT"
      - "$WINDOWS"
    require_confirmation_for_write: true
    require_confirmation_for_delete: true
  
  web:
    enabled: false  # Disabled by default
    allowed_domains: []
    require_confirmation: true
    max_request_size: 10485760  # 10MB
  
  device:
    enabled: false  # Disabled by default
    allowed_devices:
      - camera  # For face auth
    require_confirmation: true
  
  demo_mode:
    enabled: true
    restrictions:
      - no_persistent_memory
      - no_api_keys
      - no_file_writes
      - no_external_connections

# Policy Management
policy_management:
  editing_requires: "root_key"
  signing_requires: "root_key"
  verification_required: true

# Safe Mode
safe_mode:
  enabled: true
  trigger_conditions:
    - policy_verification_failed
    - multiple_auth_failures
    - system_integrity_violation
  restrictions:
    - read_only_mode
    - no_external_connections
    - local_auth_only

# Audit Settings
audit:
  enabled: true
  log_level: "INFO"
  sensitive_operations:
    - key_access
    - policy_change
    - auth_attempt
    - file_modification
""".format(timestamp=datetime.now(timezone.utc).isoformat())
        
        # Write base policy (binary mode to preserve line endings for signature)
        with open(base_policy_path, 'wb') as f:
            f.write(base_policy.encode('utf-8'))
        
        # Active policy starts as copy of base
        active_policy = base_policy.replace(
            'policy_id: "base-default"',
            'policy_id: "active-default"'
        )
        
        # Write active policy (binary mode to preserve line endings for signature)
        policy_bytes = active_policy.encode('utf-8')
        with open(active_policy_path, 'wb') as f:
            f.write(policy_bytes)
        
        # Sign active policy
        if self._private_key:
            signature = self.signer.sign_policy(policy_bytes, self._private_key)
            
            # Save signature (base64 encoded)
            with open(signature_path, 'wb') as f:
                f.write(base64.b64encode(signature))
        
        return (str(base_policy_path), str(active_policy_path))
    
    def step4_create_audit_record(self) -> dict:
        """Step 4: Create installation audit record."""
        device_id = self._device_identity.get("device_id", "unknown")
        
        # Get policy hash
        active_policy_path = self.install_path / "policies" / "active.yaml"
        policy_hash = ""
        if active_policy_path.exists():
            with open(active_policy_path, 'rb') as f:
                policy_hash = self.signer.get_policy_hash(f.read())
        
        # Get public key fingerprint
        fingerprint = self.keys.get_public_key_fingerprint() or "unknown"
        
        # Create record
        self._audit_record = self.audit.create_record(
            device_id=device_id,
            policy_hash=policy_hash,
            public_key_fingerprint=fingerprint,
            installer_version=self.version,
            mode=self.mode
        )
        
        # Add bootstrap events
        self.audit.add_event(self._audit_record, "DEVICE_IDENTITY_CREATED")
        self.audit.add_event(self._audit_record, "ROOT_KEYPAIR_GENERATED")
        self.audit.add_event(self._audit_record, "DEFAULT_POLICY_CREATED")
        self.audit.add_event(self._audit_record, "POLICY_SIGNED")
        
        # Save
        self.audit.save(self._audit_record)
        
        return self._audit_record
    
    def step5_verify_installation(self) -> Tuple[bool, list]:
        """Step 5: Verify security bootstrap was successful."""
        errors = []
        
        # Check device identity
        if not self.device.exists():
            errors.append("Device identity file missing")
        
        # Check keys
        if not self.keys.public_key_file.exists():
            errors.append("Public key file missing")
        
        if not self.keys.private_key_file.exists():
            errors.append("Private key file missing")
        
        # Check policy
        active_policy = self.install_path / "policies" / "active.yaml"
        signature_file = self.install_path / "policies" / "active.yaml.sig"
        
        if not active_policy.exists():
            errors.append("Active policy file missing")
        
        if not signature_file.exists():
            errors.append("Policy signature file missing")
        else:
            # Verify signature
            try:
                with open(active_policy, 'rb') as f:
                    policy_content = f.read()
                
                with open(signature_file, 'rb') as f:
                    sig_data = f.read()
                    try:
                        signature = base64.b64decode(sig_data)
                    except Exception:
                        errors.append("Policy signature is corrupted (invalid base64)")
                        signature = None
                
                if signature and not self.signer.verify_policy(policy_content, signature):
                    errors.append("Policy signature verification failed")
            except Exception as e:
                errors.append(f"Policy signature verification error: {e}")
        
        # Check audit
        if not self.audit.audit_file.exists():
            errors.append("Audit record file missing")
        
        return (len(errors) == 0, errors)
    
    def run_bootstrap(self) -> Tuple[bool, dict]:
        """Run complete bootstrap process."""
        result = {
            "device_identity": None,
            "keypair": None,
            "policy": None,
            "audit": None,
            "verification": None,
            "errors": []
        }
        
        try:
            # Step 1: Device Identity
            result["device_identity"] = self.step1_generate_device_identity()
            
            # Step 2: Root Keypair
            result["keypair"] = self.step2_generate_root_keypair()
            
            # Step 3: Default Policy
            result["policy"] = self.step3_create_default_policy()
            
            # Step 4: Audit Record
            result["audit"] = self.step4_create_audit_record()
            
            # Step 5: Verification
            verified, errors = self.step5_verify_installation()
            result["verification"] = verified
            result["errors"] = errors
            
            return (verified, result)
            
        except Exception as e:
            result["errors"].append(str(e))
            return (False, result)


# CLI interface for PowerShell integration
def main():
    """CLI entry point for PowerShell integration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AKSHAY AI CORE Security Bootstrap")
    parser.add_argument("--install-path", required=True, help="Installation path")
    parser.add_argument("--version", default="1.0.0", help="Installer version")
    parser.add_argument("--mode", default="normal", choices=["normal", "demo", "portable"])
    parser.add_argument("--action", required=True, 
                       choices=["bootstrap", "verify", "device-id", "keypair", "policy", "audit"])
    parser.add_argument("--output", default="json", choices=["json", "text"])
    
    args = parser.parse_args()
    
    bootstrap = SecurityBootstrap(
        install_path=Path(args.install_path),
        version=args.version,
        mode=args.mode
    )
    
    result = {}
    
    if args.action == "bootstrap":
        success, result = bootstrap.run_bootstrap()
        result["success"] = success
    
    elif args.action == "device-id":
        result["device_identity"] = bootstrap.step1_generate_device_identity()
        result["success"] = True
    
    elif args.action == "keypair":
        private_path, public_path = bootstrap.step2_generate_root_keypair()
        result["private_key_path"] = private_path
        result["public_key_path"] = public_path
        result["fingerprint"] = bootstrap.keys.get_public_key_fingerprint()
        result["success"] = True
    
    elif args.action == "policy":
        # Need keypair first
        bootstrap.step1_generate_device_identity()
        bootstrap.step2_generate_root_keypair()
        base_path, active_path = bootstrap.step3_create_default_policy()
        result["base_policy_path"] = base_path
        result["active_policy_path"] = active_path
        result["success"] = True
    
    elif args.action == "audit":
        # Need all previous steps
        bootstrap.step1_generate_device_identity()
        bootstrap.step2_generate_root_keypair()
        bootstrap.step3_create_default_policy()
        result["audit_record"] = bootstrap.step4_create_audit_record()
        result["success"] = True
    
    elif args.action == "verify":
        success, errors = bootstrap.step5_verify_installation()
        result["success"] = success
        result["errors"] = errors
    
    if args.output == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()
