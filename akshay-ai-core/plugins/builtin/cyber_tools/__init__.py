"""
============================================================
AKSHAY AI CORE — Cyber Tools Plugin
============================================================
Security analysis and network tools.
============================================================
"""

from typing import Any, Dict, List, Optional

from plugins.base import BuiltinPlugin, PluginMetadata, PluginConfig
from core.utils.logger import get_logger

logger = get_logger("plugin.cyber_tools")


class CyberToolsPlugin(BuiltinPlugin):
    """
    Cybersecurity tools plugin.
    
    Commands:
    - port_scan: Scan ports on a host
    - dns_lookup: DNS resolution
    - whois: WHOIS lookup
    - hash_file: Generate file hashes
    - check_password: Password strength check
    - encode_decode: Encode/decode data
    """
    
    metadata = PluginMetadata(
        name="cyber_tools",
        version="1.0.0",
        description="Security analysis and network tools",
        author="AKSHAY AI CORE",
        tags=["security", "network", "analysis", "tools"],
    )
    
    config = PluginConfig(
        enabled=True,
        sandboxed=True,
        max_execution_time=120,
        permissions=["network:external", "tool:cyber"],
        settings={
            "max_ports": 1000,
            "timeout": 5,
        },
    )
    
    async def on_load(self) -> None:
        """Initialize cyber tools plugin."""
        self.register_command("port_scan", self._cmd_port_scan, "Scan ports on a host")
        self.register_command("dns_lookup", self._cmd_dns_lookup, "DNS resolution")
        self.register_command("whois", self._cmd_whois, "WHOIS lookup")
        self.register_command("hash_file", self._cmd_hash_file, "Generate file hashes")
        self.register_command("check_password", self._cmd_check_password, "Password strength check")
        self.register_command("encode_decode", self._cmd_encode_decode, "Encode/decode data")
        
        logger.info("Cyber tools plugin loaded")
    
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a cyber tool command."""
        return await self.dispatch_command(command, params)
    
    async def _cmd_port_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scan ports on a host."""
        import socket
        import asyncio
        
        host = params.get("host")
        ports = params.get("ports", range(1, 1025))
        timeout = params.get("timeout", self.config.settings.get("timeout", 5))
        
        if not host:
            return {"status": "error", "error": "Host required"}
        
        if isinstance(ports, str):
            # Parse port range
            if "-" in ports:
                start, end = map(int, ports.split("-"))
                ports = range(start, end + 1)
            else:
                ports = [int(p) for p in ports.split(",")]
        
        open_ports = []
        
        async def check_port(port: int) -> Optional[int]:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                return port
            except:
                return None
        
        # Scan ports concurrently
        tasks = [check_port(p) for p in ports]
        results = await asyncio.gather(*tasks)
        open_ports = [p for p in results if p is not None]
        
        return {
            "status": "success",
            "host": host,
            "open_ports": sorted(open_ports),
            "scanned": len(list(ports)),
        }
    
    async def _cmd_dns_lookup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform DNS lookup."""
        import socket
        
        domain = params.get("domain")
        record_type = params.get("type", "A")
        
        if not domain:
            return {"status": "error", "error": "Domain required"}
        
        try:
            if record_type == "A":
                result = socket.gethostbyname_ex(domain)
                return {
                    "status": "success",
                    "domain": domain,
                    "hostname": result[0],
                    "aliases": result[1],
                    "addresses": result[2],
                }
            else:
                # For other record types, use dnspython if available
                return {"status": "error", "error": f"Record type {record_type} not supported"}
                
        except socket.gaierror as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_whois(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform WHOIS lookup."""
        domain = params.get("domain")
        
        if not domain:
            return {"status": "error", "error": "Domain required"}
        
        try:
            import whois
            result = whois.whois(domain)
            
            return {
                "status": "success",
                "domain": domain,
                "registrar": result.registrar,
                "creation_date": str(result.creation_date),
                "expiration_date": str(result.expiration_date),
                "name_servers": result.name_servers,
            }
        except ImportError:
            return {"status": "error", "error": "python-whois not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_hash_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate file hashes."""
        import hashlib
        from pathlib import Path
        
        file_path = params.get("path")
        algorithms = params.get("algorithms", ["md5", "sha256"])
        
        if not file_path:
            return {"status": "error", "error": "File path required"}
        
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "error": "File not found"}
        
        content = path.read_bytes()
        hashes = {}
        
        for algo in algorithms:
            if hasattr(hashlib, algo):
                h = getattr(hashlib, algo)()
                h.update(content)
                hashes[algo] = h.hexdigest()
        
        return {
            "status": "success",
            "path": str(path),
            "size": len(content),
            "hashes": hashes,
        }
    
    async def _cmd_check_password(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check password strength."""
        import re
        
        password = params.get("password")
        
        if not password:
            return {"status": "error", "error": "Password required"}
        
        score = 0
        feedback = []
        
        # Length
        if len(password) >= 8:
            score += 1
        else:
            feedback.append("Use at least 8 characters")
        
        if len(password) >= 12:
            score += 1
        
        if len(password) >= 16:
            score += 1
        
        # Character types
        if re.search(r"[a-z]", password):
            score += 1
        else:
            feedback.append("Add lowercase letters")
        
        if re.search(r"[A-Z]", password):
            score += 1
        else:
            feedback.append("Add uppercase letters")
        
        if re.search(r"\d", password):
            score += 1
        else:
            feedback.append("Add numbers")
        
        if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            score += 1
        else:
            feedback.append("Add special characters")
        
        # Common patterns
        if re.search(r"(.)\1{2,}", password):
            score -= 1
            feedback.append("Avoid repeated characters")
        
        if re.search(r"(012|123|234|345|456|567|678|789|890)", password):
            score -= 1
            feedback.append("Avoid sequential numbers")
        
        strength = "weak"
        if score >= 6:
            strength = "strong"
        elif score >= 4:
            strength = "medium"
        
        return {
            "status": "success",
            "strength": strength,
            "score": max(0, score),
            "max_score": 7,
            "feedback": feedback,
        }
    
    async def _cmd_encode_decode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Encode or decode data."""
        import base64
        import urllib.parse
        
        data = params.get("data")
        operation = params.get("operation", "encode")
        encoding = params.get("encoding", "base64")
        
        if not data:
            return {"status": "error", "error": "Data required"}
        
        try:
            if encoding == "base64":
                if operation == "encode":
                    result = base64.b64encode(data.encode()).decode()
                else:
                    result = base64.b64decode(data).decode()
            
            elif encoding == "url":
                if operation == "encode":
                    result = urllib.parse.quote(data)
                else:
                    result = urllib.parse.unquote(data)
            
            elif encoding == "hex":
                if operation == "encode":
                    result = data.encode().hex()
                else:
                    result = bytes.fromhex(data).decode()
            
            else:
                return {"status": "error", "error": f"Unknown encoding: {encoding}"}
            
            return {
                "status": "success",
                "operation": operation,
                "encoding": encoding,
                "result": result,
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
