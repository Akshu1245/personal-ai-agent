"""
============================================================
AKSHAY AI CORE — File Vault Plugin
============================================================
Encrypted file storage with secure access controls.
============================================================
"""

import os
import shutil
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from plugins.base import BuiltinPlugin, PluginMetadata, PluginConfig
from core.security.encryption import encryption_engine
from core.utils.logger import get_logger

logger = get_logger("plugin.file_vault")


class FileVaultPlugin(BuiltinPlugin):
    """
    Encrypted file vault plugin.
    
    Commands:
    - store: Encrypt and store a file
    - retrieve: Decrypt and retrieve a file
    - list: List vault contents
    - delete: Remove a file from vault
    - backup: Backup vault to encrypted archive
    """
    
    metadata = PluginMetadata(
        name="file_vault",
        version="1.0.0",
        description="Encrypted file storage with secure access",
        author="AKSHAY AI CORE",
        tags=["security", "encryption", "storage", "files"],
    )
    
    config = PluginConfig(
        enabled=True,
        sandboxed=True,
        max_execution_time=300,
        permissions=["file:vault", "file:read", "file:write"],
        settings={
            "vault_path": "./data/vault",
            "max_file_size_mb": 100,
            "allowed_extensions": [],  # Empty = all allowed
        },
    )
    
    def __init__(self):
        super().__init__()
        self._vault_path: Optional[Path] = None
        self._index: Dict[str, Dict] = {}
    
    async def on_load(self) -> None:
        """Initialize file vault."""
        self._vault_path = Path(self.config.settings.get("vault_path", "./data/vault"))
        self._vault_path.mkdir(parents=True, exist_ok=True)
        
        # Load index
        await self._load_index()
        
        self.register_command("store", self._cmd_store, "Store a file in vault")
        self.register_command("retrieve", self._cmd_retrieve, "Retrieve a file from vault")
        self.register_command("list", self._cmd_list, "List vault contents")
        self.register_command("delete", self._cmd_delete, "Delete a file from vault")
        self.register_command("backup", self._cmd_backup, "Backup vault")
        
        logger.info(f"File vault plugin loaded (path: {self._vault_path})")
    
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a vault command."""
        return await self.dispatch_command(command, params)
    
    async def _load_index(self) -> None:
        """Load vault index from disk."""
        import json
        
        index_path = self._vault_path / ".index.json"
        
        if index_path.exists():
            try:
                encrypted_data = index_path.read_bytes()
                decrypted = encryption_engine.decrypt(
                    encrypted_data[16:],
                    encrypted_data[:16],
                )
                self._index = json.loads(decrypted.decode())
            except Exception as e:
                logger.error("Failed to load vault index", error=str(e))
                self._index = {}
        else:
            self._index = {}
    
    async def _save_index(self) -> None:
        """Save vault index to disk."""
        import json
        
        index_path = self._vault_path / ".index.json"
        
        data = json.dumps(self._index).encode()
        ciphertext, iv = encryption_engine.encrypt(data)
        
        index_path.write_bytes(iv + ciphertext)
    
    async def _cmd_store(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Store a file in the vault."""
        source_path = params.get("path")
        vault_name = params.get("name")
        password = params.get("password")  # Optional additional encryption
        
        if not source_path:
            return {"status": "error", "error": "Source path required"}
        
        source = Path(source_path)
        if not source.exists():
            return {"status": "error", "error": "Source file not found"}
        
        # Check file size
        max_size = self.config.settings.get("max_file_size_mb", 100) * 1024 * 1024
        if source.stat().st_size > max_size:
            return {"status": "error", "error": f"File exceeds maximum size ({max_size // (1024*1024)} MB)"}
        
        # Generate vault name
        if not vault_name:
            vault_name = source.name
        
        vault_id = encryption_engine.hash_data(f"{vault_name}_{datetime.utcnow().isoformat()}")[:16]
        
        # Read and encrypt file
        content = source.read_bytes()
        
        if password:
            encrypted_data = encryption_engine.encrypt_with_password(content, password)
            # Store as JSON
            import json
            vault_content = json.dumps(encrypted_data).encode()
            ciphertext, iv = encryption_engine.encrypt(vault_content)
            has_password = True
        else:
            ciphertext, iv = encryption_engine.encrypt(content)
            has_password = False
        
        # Save to vault
        vault_file = self._vault_path / f"{vault_id}.vault"
        vault_file.write_bytes(iv + ciphertext)
        
        # Update index
        self._index[vault_id] = {
            "name": vault_name,
            "original_name": source.name,
            "size": source.stat().st_size,
            "has_password": has_password,
            "stored_at": datetime.utcnow().isoformat(),
        }
        
        await self._save_index()
        
        return {
            "status": "success",
            "vault_id": vault_id,
            "name": vault_name,
        }
    
    async def _cmd_retrieve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve a file from the vault."""
        vault_id = params.get("vault_id")
        output_path = params.get("output")
        password = params.get("password")
        
        if not vault_id:
            return {"status": "error", "error": "Vault ID required"}
        
        if vault_id not in self._index:
            return {"status": "error", "error": "File not found in vault"}
        
        entry = self._index[vault_id]
        
        if entry["has_password"] and not password:
            return {"status": "error", "error": "Password required for this file"}
        
        vault_file = self._vault_path / f"{vault_id}.vault"
        encrypted_data = vault_file.read_bytes()
        
        # Decrypt
        decrypted = encryption_engine.decrypt(
            encrypted_data[16:],
            encrypted_data[:16],
        )
        
        if entry["has_password"]:
            import json
            password_encrypted = json.loads(decrypted.decode())
            content = encryption_engine.decrypt_with_password(password_encrypted, password)
        else:
            content = decrypted
        
        # Output
        if output_path:
            output = Path(output_path)
            output.write_bytes(content)
            return {
                "status": "success",
                "vault_id": vault_id,
                "output": str(output),
            }
        else:
            # Return content (for small files)
            if len(content) > 1024 * 1024:  # 1MB
                return {"status": "error", "error": "File too large to return directly. Specify output path."}
            
            try:
                return {
                    "status": "success",
                    "vault_id": vault_id,
                    "content": content.decode("utf-8"),
                }
            except UnicodeDecodeError:
                return {
                    "status": "success",
                    "vault_id": vault_id,
                    "content_base64": content.hex(),
                }
    
    async def _cmd_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List vault contents."""
        files = []
        
        for vault_id, entry in self._index.items():
            files.append({
                "vault_id": vault_id,
                "name": entry["name"],
                "original_name": entry["original_name"],
                "size": entry["size"],
                "has_password": entry["has_password"],
                "stored_at": entry["stored_at"],
            })
        
        # Sort by stored date
        files.sort(key=lambda x: x["stored_at"], reverse=True)
        
        return {
            "status": "success",
            "count": len(files),
            "files": files,
        }
    
    async def _cmd_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file from the vault."""
        vault_id = params.get("vault_id")
        
        if not vault_id:
            return {"status": "error", "error": "Vault ID required"}
        
        if vault_id not in self._index:
            return {"status": "error", "error": "File not found in vault"}
        
        # Delete file
        vault_file = self._vault_path / f"{vault_id}.vault"
        if vault_file.exists():
            vault_file.unlink()
        
        # Remove from index
        del self._index[vault_id]
        await self._save_index()
        
        return {
            "status": "success",
            "deleted": vault_id,
        }
    
    async def _cmd_backup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Backup the entire vault."""
        output_path = params.get("output")
        password = params.get("password")
        
        if not password:
            return {"status": "error", "error": "Backup password required"}
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if not output_path:
            output_path = f"./vault_backup_{timestamp}.enc"
        
        # Create tarball of vault
        import tarfile
        import io
        
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            tar.add(self._vault_path, arcname="vault")
        
        # Encrypt backup
        tar_data = tar_buffer.getvalue()
        encrypted = encryption_engine.encrypt_with_password(tar_data, password)
        
        # Save
        import json
        output = Path(output_path)
        output.write_text(json.dumps(encrypted))
        
        return {
            "status": "success",
            "backup_path": str(output),
            "size": len(tar_data),
            "files_backed_up": len(self._index),
        }
