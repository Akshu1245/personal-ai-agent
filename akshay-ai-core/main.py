"""
============================================================
AKSHAY AI CORE — Main Entry Point
============================================================
Personal AI Operating System
============================================================
"""

import asyncio
import sys
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import settings
from core.init_db import initialize_database
from core.security.auth_manager import AuthManager
from core.utils.logger import setup_logging, get_logger

# Initialize CLI app
cli = typer.Typer(
    name="akshay",
    help="AKSHAY AI CORE — Personal AI Operating System",
    add_completion=False,
)
console = Console()


def print_banner():
    """Print the AKSHAY AI CORE banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     █████╗ ██╗  ██╗███████╗██╗  ██╗ █████╗ ██╗   ██╗         ║
    ║    ██╔══██╗██║ ██╔╝██╔════╝██║  ██║██╔══██╗╚██╗ ██╔╝         ║
    ║    ███████║█████╔╝ ███████╗███████║███████║ ╚████╔╝          ║
    ║    ██╔══██║██╔═██╗ ╚════██║██╔══██║██╔══██║  ╚██╔╝           ║
    ║    ██║  ██║██║  ██╗███████║██║  ██║██║  ██║   ██║            ║
    ║    ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝            ║
    ║                                                               ║
    ║                      █████╗ ██╗                               ║
    ║                     ██╔══██╗██║                               ║
    ║                     ███████║██║                               ║
    ║                     ██╔══██║██║                               ║
    ║                     ██║  ██║██║                               ║
    ║                     ╚═╝  ╚═╝╚═╝                               ║
    ║                                                               ║
    ║               ██████╗ ██████╗ ██████╗ ███████╗                ║
    ║              ██╔════╝██╔═══██╗██╔══██╗██╔════╝                ║
    ║              ██║     ██║   ██║██████╔╝█████╗                  ║
    ║              ██║     ██║   ██║██╔══██╗██╔══╝                  ║
    ║              ╚██████╗╚██████╔╝██║  ██║███████╗                ║
    ║               ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝                ║
    ║                                                               ║
    ║         Personal AI Operating System v{version}               ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """.format(version=settings.APP_VERSION)
    
    console.print(Text(banner, style="bold cyan"))


@cli.command()
def run(
    host: str = typer.Option(None, "--host", "-h", help="API host"),
    port: int = typer.Option(None, "--port", "-p", help="API port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
):
    """Start the AKSHAY AI CORE system."""
    print_banner()
    
    # Setup logging
    setup_logging()
    logger = get_logger("main")
    
    # Use settings if not overridden
    api_host = host or settings.API_HOST
    api_port = port or settings.API_PORT
    
    console.print(Panel.fit(
        f"[green]Starting AKSHAY AI CORE[/green]\n"
        f"Host: {api_host}:{api_port}\n"
        f"Environment: {settings.ENVIRONMENT}\n"
        f"Debug: {settings.DEBUG}",
        title="System Status",
        border_style="green"
    ))
    
    logger.info(
        "Starting AKSHAY AI CORE",
        host=api_host,
        port=api_port,
        environment=settings.ENVIRONMENT
    )
    
    # Run the API server
    uvicorn.run(
        "api.main:app",
        host=api_host,
        port=api_port,
        reload=reload or settings.API_RELOAD,
        workers=workers if not reload else 1,
        log_level=settings.LOG_LEVEL.lower(),
    )


@cli.command()
def init():
    """Initialize the database and create required directories."""
    print_banner()
    console.print("[yellow]Initializing AKSHAY AI CORE...[/yellow]")
    
    # Create required directories
    directories = [
        Path("data"),
        Path("data/vector_db"),
        Path("data/face_data"),
        Path("data/vault"),
        Path("logs"),
        Path("plugins/custom"),
        Path("config"),
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        console.print(f"  [green]✓[/green] Created {directory}")
    
    # Initialize database
    asyncio.run(initialize_database())
    console.print("  [green]✓[/green] Database initialized")
    
    console.print("\n[green]✓ Initialization complete![/green]")
    console.print("[yellow]Next steps:[/yellow]")
    console.print("  1. Copy .env.example to .env")
    console.print("  2. Configure your API keys in .env")
    console.print("  3. Run: python main.py run")


@cli.command()
def setup_auth():
    """Setup initial authentication (face + PIN)."""
    print_banner()
    console.print("[yellow]Setting up authentication...[/yellow]")
    
    auth_manager = AuthManager()
    asyncio.run(auth_manager.interactive_setup())


@cli.command()
def status():
    """Check system status."""
    print_banner()
    
    from core.utils.system_check import SystemChecker
    
    checker = SystemChecker()
    asyncio.run(checker.run_checks())


@cli.command()
def shell():
    """Start interactive AI shell."""
    from core.shell import run_shell
    
    asyncio.run(run_shell())


@cli.command()
def version():
    """Show version information."""
    console.print(f"AKSHAY AI CORE v{settings.APP_VERSION}")
    console.print(f"Environment: {settings.ENVIRONMENT}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
