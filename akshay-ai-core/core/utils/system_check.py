"""
============================================================
AKSHAY AI CORE — System Health Checker
============================================================
Verifies system components, dependencies, and configurations.
============================================================
"""

import asyncio
import platform
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from core.config import settings

console = Console()


class SystemChecker:
    """System health and dependency checker."""
    
    def __init__(self):
        self.checks = []
        self.warnings = []
        self.errors = []
    
    async def run_checks(self) -> bool:
        """Run all system checks and display results."""
        console.print(Panel.fit(
            "[bold cyan]AKSHAY AI CORE — System Health Check[/bold cyan]",
            border_style="cyan"
        ))
        
        # Create results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Check", style="cyan", width=30)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Details", style="dim")
        
        # Run all checks
        await self._check_python_version(table)
        await self._check_directories(table)
        await self._check_environment(table)
        await self._check_database(table)
        await self._check_ai_providers(table)
        await self._check_dependencies(table)
        await self._check_security(table)
        
        console.print(table)
        console.print()
        
        # Summary
        if self.errors:
            console.print(f"[red]✗ {len(self.errors)} error(s) found[/red]")
            for error in self.errors:
                console.print(f"  [red]• {error}[/red]")
        
        if self.warnings:
            console.print(f"[yellow]⚠ {len(self.warnings)} warning(s)[/yellow]")
            for warning in self.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
        
        if not self.errors and not self.warnings:
            console.print("[green]✓ All checks passed![/green]")
        
        return len(self.errors) == 0
    
    async def _check_python_version(self, table: Table) -> None:
        """Check Python version."""
        version = platform.python_version()
        major, minor, _ = map(int, version.split("."))
        
        if major >= 3 and minor >= 11:
            table.add_row("Python Version", "[green]✓ OK[/green]", f"v{version}")
        else:
            table.add_row("Python Version", "[red]✗ FAIL[/red]", f"v{version} (need 3.11+)")
            self.errors.append(f"Python 3.11+ required, found {version}")
    
    async def _check_directories(self, table: Table) -> None:
        """Check required directories."""
        dirs = {
            "Data": settings.DATA_DIR,
            "Logs": settings.LOGS_DIR,
            "Plugins": settings.PLUGINS_DIR,
            "Config": settings.CONFIG_DIR,
        }
        
        all_ok = True
        missing = []
        
        for name, path in dirs.items():
            if not Path(path).exists():
                missing.append(name)
                all_ok = False
        
        if all_ok:
            table.add_row("Directories", "[green]✓ OK[/green]", "All required directories exist")
        else:
            table.add_row("Directories", "[yellow]⚠ WARN[/yellow]", f"Missing: {', '.join(missing)}")
            self.warnings.append(f"Run 'python main.py init' to create missing directories")
    
    async def _check_environment(self, table: Table) -> None:
        """Check environment configuration."""
        env_file = Path(".env")
        
        if env_file.exists():
            table.add_row("Environment", "[green]✓ OK[/green]", ".env file found")
        else:
            table.add_row("Environment", "[yellow]⚠ WARN[/yellow]", ".env file not found")
            self.warnings.append("Copy .env.example to .env and configure")
    
    async def _check_database(self, table: Table) -> None:
        """Check database connectivity."""
        db_path = settings.get_database_path()
        
        if db_path.exists():
            size = db_path.stat().st_size / 1024  # KB
            table.add_row("Database", "[green]✓ OK[/green]", f"SQLite ({size:.1f} KB)")
        else:
            table.add_row("Database", "[yellow]⚠ WARN[/yellow]", "Database not initialized")
            self.warnings.append("Run 'python main.py init' to initialize database")
    
    async def _check_ai_providers(self, table: Table) -> None:
        """Check AI provider configuration."""
        provider = settings.PRIMARY_AI_PROVIDER
        config = settings.get_ai_config()
        
        if provider == "ollama":
            # Check Ollama connection
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{settings.OLLAMA_HOST}/api/tags")
                    if response.status_code == 200:
                        table.add_row("AI Provider", "[green]✓ OK[/green]", f"Ollama ({settings.OLLAMA_MODEL})")
                    else:
                        table.add_row("AI Provider", "[red]✗ FAIL[/red]", "Ollama not responding")
                        self.errors.append("Cannot connect to Ollama server")
            except Exception:
                table.add_row("AI Provider", "[yellow]⚠ WARN[/yellow]", "Ollama not reachable")
                self.warnings.append("Ollama server not running (needed for local AI)")
        else:
            # Check API key
            api_key = config.get("api_key")
            if api_key:
                masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "****"
                table.add_row("AI Provider", "[green]✓ OK[/green]", f"{provider.title()} (key: {masked})")
            else:
                table.add_row("AI Provider", "[red]✗ FAIL[/red]", f"{provider.title()} API key missing")
                self.errors.append(f"Set {provider.upper()}_API_KEY in .env")
    
    async def _check_dependencies(self, table: Table) -> None:
        """Check critical dependencies."""
        missing = []
        
        deps = [
            ("fastapi", "FastAPI"),
            ("mediapipe", "MediaPipe"),
            ("chromadb", "ChromaDB"),
            ("cryptography", "Cryptography"),
        ]
        
        for module, name in deps:
            try:
                __import__(module)
            except ImportError:
                missing.append(name)
        
        if not missing:
            table.add_row("Dependencies", "[green]✓ OK[/green]", "All critical packages installed")
        else:
            table.add_row("Dependencies", "[red]✗ FAIL[/red]", f"Missing: {', '.join(missing)}")
            self.errors.append("Run 'pip install -r requirements.txt'")
    
    async def _check_security(self, table: Table) -> None:
        """Check security configuration."""
        issues = []
        
        if settings.is_production():
            if not settings.MASTER_ENCRYPTION_KEY:
                issues.append("No encryption key")
            if settings.DEV_BYPASS_AUTH:
                issues.append("Auth bypass enabled")
            if settings.DEBUG:
                issues.append("Debug mode enabled")
        
        if issues:
            table.add_row("Security", "[red]✗ FAIL[/red]", "; ".join(issues))
            for issue in issues:
                self.errors.append(f"Security issue in production: {issue}")
        else:
            table.add_row("Security", "[green]✓ OK[/green]", "Configuration secure")


async def main():
    """Run system check from command line."""
    checker = SystemChecker()
    await checker.run_checks()


if __name__ == "__main__":
    asyncio.run(main())
