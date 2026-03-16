"""
============================================================
AKSHAY AI CORE — Encryption Engine
============================================================
AES-256 encryption for data at rest with secure key management.
============================================================
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Union

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger("encryption")


class EncryptionEngine:
    """
    AES-256 encryption engine for secure data storage.
    
    Features:
    - AES-256-CBC encryption
    - PBKDF2 key derivation
    - Secure IV generation
    - Password-based encryption support
    """
    
    # Constants
    KEY_SIZE = 32  # 256 bits
    IV_SIZE = 16   # 128 bits
    SALT_SIZE = 32
    ITERATIONS = 100_000
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption engine.
        
        Args:
            master_key: Base64-encoded master key (uses env if not provided)
        """
        self._master_key = self._load_master_key(master_key)
        self._backend = default_backend()
    
    def _load_master_key(self, provided_key: Optional[str] = None) -> bytes:
        """
        Load or generate master encryption key.
        
        Args:
            provided_key: Optional base64-encoded key
            
        Returns:
            32-byte encryption key
        """
        if provided_key:
            return base64.b64decode(provided_key)
        
        if settings.MASTER_ENCRYPTION_KEY:
            return base64.b64decode(settings.MASTER_ENCRYPTION_KEY)
        
        # Generate new key for development/testing (WARNING: not persistent!)
        if settings.is_development() or settings.ENVIRONMENT == "testing":
            logger.warning(
                f"No master key configured for {settings.ENVIRONMENT} mode, generating temporary key. "
                "Set MASTER_ENCRYPTION_KEY for persistence."
            )
            return secrets.token_bytes(self.KEY_SIZE)
        
        raise ValueError(
            "MASTER_ENCRYPTION_KEY must be set in production. "
            "Generate with: python -c \"import secrets, base64; "
            "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    
    def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
    ) -> tuple[bytes, bytes]:
        """
        Derive encryption key from password using PBKDF2.
        
        Args:
            password: User password
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(self.SALT_SIZE)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.ITERATIONS,
            backend=self._backend,
        )
        
        key = kdf.derive(password.encode("utf-8"))
        return key, salt
    
    def encrypt(
        self,
        plaintext: Union[str, bytes],
        key: Optional[bytes] = None,
    ) -> tuple[bytes, bytes]:
        """
        Encrypt data using AES-256-CBC.
        
        Args:
            plaintext: Data to encrypt
            key: Optional encryption key (uses master key if not provided)
            
        Returns:
            Tuple of (ciphertext, iv)
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        
        key = key or self._master_key
        iv = secrets.token_bytes(self.IV_SIZE)
        
        # Pad plaintext to block size
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()
        
        # Encrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self._backend,
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return ciphertext, iv
    
    def decrypt(
        self,
        ciphertext: bytes,
        iv: bytes,
        key: Optional[bytes] = None,
    ) -> bytes:
        """
        Decrypt data using AES-256-CBC.
        
        Args:
            ciphertext: Encrypted data
            iv: Initialization vector
            key: Optional decryption key (uses master key if not provided)
            
        Returns:
            Decrypted plaintext bytes
        """
        key = key or self._master_key
        
        # Decrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self._backend,
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Unpad
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_data) + unpadder.finalize()
        
        return plaintext
    
    def encrypt_string(self, plaintext: str, key: Optional[bytes] = None) -> str:
        """
        Encrypt string and return base64-encoded result.
        
        Args:
            plaintext: String to encrypt
            key: Optional encryption key
            
        Returns:
            Base64-encoded string: "iv:ciphertext"
        """
        ciphertext, iv = self.encrypt(plaintext, key)
        
        iv_b64 = base64.b64encode(iv).decode("utf-8")
        ct_b64 = base64.b64encode(ciphertext).decode("utf-8")
        
        return f"{iv_b64}:{ct_b64}"
    
    def decrypt_string(self, encrypted: str, key: Optional[bytes] = None) -> str:
        """
        Decrypt base64-encoded encrypted string.
        
        Args:
            encrypted: Base64-encoded "iv:ciphertext" string
            key: Optional decryption key
            
        Returns:
            Decrypted string
        """
        iv_b64, ct_b64 = encrypted.split(":", 1)
        
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ct_b64)
        
        plaintext = self.decrypt(ciphertext, iv, key)
        return plaintext.decode("utf-8")
    
    def encrypt_with_password(
        self,
        plaintext: Union[str, bytes],
        password: str,
    ) -> dict:
        """
        Encrypt data with password-derived key.
        
        Args:
            plaintext: Data to encrypt
            password: Encryption password
            
        Returns:
            Dict with salt, iv, and ciphertext (all base64 encoded)
        """
        key, salt = self.derive_key(password)
        ciphertext, iv = self.encrypt(plaintext, key)
        
        return {
            "salt": base64.b64encode(salt).decode("utf-8"),
            "iv": base64.b64encode(iv).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        }
    
    def decrypt_with_password(
        self,
        encrypted_data: dict,
        password: str,
    ) -> bytes:
        """
        Decrypt data encrypted with password.
        
        Args:
            encrypted_data: Dict with salt, iv, and ciphertext
            password: Decryption password
            
        Returns:
            Decrypted bytes
        """
        salt = base64.b64decode(encrypted_data["salt"])
        iv = base64.b64decode(encrypted_data["iv"])
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        
        key, _ = self.derive_key(password, salt)
        return self.decrypt(ciphertext, iv, key)
    
    def hash_data(self, data: Union[str, bytes]) -> str:
        """
        Create SHA-256 hash of data.
        
        Args:
            data: Data to hash
            
        Returns:
            Hex-encoded hash string
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        return hashlib.sha256(data).hexdigest()
    
    def secure_compare(self, a: str, b: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            True if strings are equal
        """
        return secrets.compare_digest(a, b)
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new random encryption key.
        
        Returns:
            Base64-encoded 256-bit key
        """
        key = secrets.token_bytes(32)
        return base64.b64encode(key).decode("utf-8")
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate a secure random token.
        
        Args:
            length: Token length in bytes
            
        Returns:
            URL-safe base64-encoded token
        """
        return secrets.token_urlsafe(length)


# Global encryption engine instance
encryption_engine = EncryptionEngine()
