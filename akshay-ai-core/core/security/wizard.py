"""
============================================================
AKSHAY AI CORE — First-Run Setup Wizard
============================================================
Interactive setup wizard that runs on first launch.
Handles PIN setup, admin creation, and system configuration.
============================================================
"""

import argparse
import getpass
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# Rich console for beautiful output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class FirstRunWizard:
    """Interactive first-run setup wizard."""
    
    def __init__(self, install_path: Path):
        self.install_path = Path(install_path)
        self.config_dir = self.install_path / "config"
        self.akshay_dir = self.install_path / ".akshay"
        self.first_run_file = self.akshay_dir / "first_run.json"
        self.admin_file = self.config_dir / "admin.json"
        
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
        
        # Wizard state
        self.admin_name = ""
        self.pin = ""
        self.voice_enabled = True
        self.mode = "normal"
        self.recovery_key = ""
    
    def print(self, message: str, style: str = None):
        """Print message with optional styling."""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
    
    def print_header(self, title: str):
        """Print a section header."""
        if self.console:
            self.console.print()
            self.console.print(Panel(title, style="bold cyan"))
        else:
            print(f"\n{'=' * 60}")
            print(f"  {title}")
            print('=' * 60)
    
    def print_step(self, step: int, total: int, description: str):
        """Print step indicator."""
        if self.console:
            self.console.print(f"\n[dim]Step {step}/{total}[/dim]")
            self.console.print(f"[bold]{description}[/bold]\n")
        else:
            print(f"\n--- Step {step}/{total}: {description} ---\n")
    
    def get_input(self, prompt: str, default: str = None, password: bool = False) -> str:
        """Get user input."""
        if self.console and not password:
            return Prompt.ask(prompt, default=default or "")
        else:
            if default:
                prompt = f"{prompt} [{default}]"
            prompt = f"  {prompt}: "
            
            if password:
                return getpass.getpass(prompt)
            else:
                value = input(prompt)
                return value if value else (default or "")
    
    def get_confirm(self, prompt: str, default: bool = True) -> bool:
        """Get yes/no confirmation."""
        if self.console:
            return Confirm.ask(prompt, default=default)
        else:
            suffix = "[Y/n]" if default else "[y/N]"
            response = input(f"  {prompt} {suffix}: ").strip().lower()
            if not response:
                return default
            return response in ('y', 'yes')
    
    def run(self) -> bool:
        """Run the complete wizard."""
        try:
            # Check if already completed
            if self.first_run_file.exists():
                self.print("\n[yellow]First-run setup already completed.[/yellow]")
                if not self.get_confirm("Run setup again?", default=False):
                    return True
            
            # Welcome screen
            if not self._screen_welcome():
                return False
            
            # Admin user setup
            if not self._screen_admin_user():
                return False
            
            # PIN setup
            if not self._screen_pin_setup():
                return False
            
            # Voice setup
            if not self._screen_voice_setup():
                return False
            
            # Mode selection
            if not self._screen_mode_select():
                return False
            
            # Recovery key display
            if not self._screen_recovery_key():
                return False
            
            # Finish
            if not self._screen_finish():
                return False
            
            return True
            
        except KeyboardInterrupt:
            self.print("\n\n[yellow]Setup cancelled by user.[/yellow]")
            return False
        except Exception as e:
            self.print(f"\n[red]Error during setup: {e}[/red]")
            return False
    
    def _screen_welcome(self) -> bool:
        """Welcome screen."""
        self.print_header("Welcome to AKSHAY AI CORE")
        
        welcome_text = """
    Thank you for installing AKSHAY AI CORE!
    
    This wizard will help you set up:
    
    • Admin account (your identity)
    • Security PIN (protects your keys)
    • Voice interface (optional)
    • Operating mode
    • Recovery key (one-time display)
    
    This will only take a minute.
        """
        
        self.print(welcome_text)
        
        return self.get_confirm("Ready to begin?", default=True)
    
    def _screen_admin_user(self) -> bool:
        """Admin user creation screen."""
        self.print_step(1, 5, "Create Admin User")
        
        self.print("  Your name will be used for personalization and audit logs.\n")
        
        # Get name
        default_name = os.environ.get('USERNAME', os.environ.get('USER', 'Admin'))
        self.admin_name = self.get_input("Your name", default=default_name)
        
        if not self.admin_name:
            self.admin_name = "Admin"
        
        self.print(f"\n  [green]✓[/green] Admin user: {self.admin_name} (role: ROOT)")
        
        return True
    
    def _screen_pin_setup(self) -> bool:
        """PIN setup screen."""
        self.print_step(2, 5, "Set Security PIN")
        
        self.print("""  Your PIN protects the root encryption key.
  
  Requirements:
  • 6-12 digits only
  • No common patterns (123456, 000000)
  • You'll need this PIN to:
    - Sign policies
    - Access admin functions
    - Recover from lockout
        """)
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            # Get PIN
            pin1 = self.get_input("Enter PIN (6-12 digits)", password=True)
            
            # Validate format
            if not pin1.isdigit():
                self.print("  [red]PIN must contain only digits[/red]")
                continue
            
            if len(pin1) < 6:
                self.print("  [red]PIN must be at least 6 digits[/red]")
                continue
            
            if len(pin1) > 12:
                self.print("  [red]PIN must be at most 12 digits[/red]")
                continue
            
            # Check for weak patterns
            if pin1 == pin1[0] * len(pin1):
                self.print("  [red]PIN cannot be all the same digit[/red]")
                continue
            
            if pin1 in ("123456", "654321", "000000", "111111", "123456789012"):
                self.print("  [red]PIN is too common, choose a stronger one[/red]")
                continue
            
            # Confirm PIN
            pin2 = self.get_input("Confirm PIN", password=True)
            
            if pin1 != pin2:
                self.print("  [red]PINs do not match[/red]")
                continue
            
            self.pin = pin1
            self.print("\n  [green]✓[/green] PIN set successfully")
            return True
        
        self.print("  [red]Too many failed attempts[/red]")
        return False
    
    def _screen_voice_setup(self) -> bool:
        """Voice setup screen."""
        self.print_step(3, 5, "Voice Interface Setup")
        
        self.print("""  The voice interface allows hands-free interaction.
  
  Features:
  • Wake word: "Hey Akshay"
  • Voice commands for common tasks
  • Confirmation required for sensitive actions
  
  Note: Voice has reduced trust for security.
  Admin actions still require PIN confirmation.
        """)
        
        self.voice_enabled = self.get_confirm("Enable voice interface?", default=True)
        
        status = "enabled" if self.voice_enabled else "disabled"
        self.print(f"\n  [green]✓[/green] Voice interface: {status}")
        
        return True
    
    def _screen_mode_select(self) -> bool:
        """Mode selection screen."""
        self.print_step(4, 5, "Select Operating Mode")
        
        self.print("""  Choose how AKSHAY AI CORE will operate:
  
  [1] NORMAL MODE (Recommended)
      Full functionality with security controls.
      All features enabled.
  
  [2] DEMO MODE
      Restricted mode for testing/demos.
      • Mock devices and filesystem
      • No persistent changes
      • Safe for sharing
        """)
        
        choice = self.get_input("Select mode [1/2]", default="1")
        
        if choice == "2":
            self.mode = "demo"
            self.print("\n  [yellow]✓[/yellow] Demo Mode selected")
            self.print("    You can switch to Normal Mode later with: ai.ps1")
        else:
            self.mode = "normal"
            self.print("\n  [green]✓[/green] Normal Mode selected")
        
        return True
    
    def _screen_recovery_key(self) -> bool:
        """Recovery key display screen."""
        self.print_step(5, 5, "Recovery Key")
        
        self.print("""  [bold red]⚠️  IMPORTANT: READ THIS CAREFULLY[/bold red]
  
  A recovery key will be generated for emergencies.
  
  This key can:
  • Reset your PIN if locked out
  • Recover from failed authentication
  
  [bold]This key is shown ONCE and cannot be retrieved later.[/bold]
        """)
        
        if not self.get_confirm("Ready to view recovery key?", default=True):
            self.print("\n  [yellow]Skipping recovery key generation.[/yellow]")
            self.print("  [yellow]Warning: You won't be able to recover if locked out![/yellow]")
            return self.get_confirm("Continue without recovery key?", default=False)
        
        # Generate recovery key
        from core.security.bootstrap import RootKeyManager
        
        key_manager = RootKeyManager(self.install_path)
        self.recovery_key = key_manager.generate_recovery_key()
        
        self.print("\n" + "=" * 60)
        self.print("  [bold red]YOUR RECOVERY KEY[/bold red]")
        self.print("=" * 60)
        self.print(f"\n  [bold yellow]{self.recovery_key}[/bold yellow]\n")
        self.print("=" * 60)
        self.print("\n  [bold]Write this down and store it safely![/bold]")
        self.print("  This will NOT be shown again.\n")
        
        # Verify user has saved it
        if not self.get_confirm("Have you saved the recovery key?", default=False):
            self.print("\n  Please save the recovery key before continuing.")
            if not self.get_confirm("Have you saved the recovery key?", default=False):
                return False
        
        self.print("\n  [green]✓[/green] Recovery key generated")
        return True
    
    def _screen_finish(self) -> bool:
        """Finish screen - apply all settings."""
        self.print_header("Applying Settings")
        
        try:
            # 1. Set up PIN encryption
            self.print("  [*] Encrypting root key with PIN...")
            
            from core.security.keystore import KeyStore
            
            keystore = KeyStore(self.install_path)
            success, error = keystore.setup_pin(self.pin)
            
            if not success:
                self.print(f"  [red]✗[/red] Failed to encrypt key: {error}")
                return False
            
            self.print("  [green]✓[/green] Root key encrypted")
            
            # 2. Save admin config
            self.print("  [*] Saving admin configuration...")
            
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            admin_config = {
                "name": self.admin_name,
                "role": "ROOT",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "voice_enabled": self.voice_enabled,
                "default_mode": self.mode,
            }
            
            with open(self.admin_file, 'w') as f:
                json.dump(admin_config, f, indent=2)
            
            self.print("  [green]✓[/green] Admin configuration saved")
            
            # 3. Save first-run flag
            self.print("  [*] Marking setup complete...")
            
            first_run_data = {
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
                "admin_name": self.admin_name,
                "voice_enabled": self.voice_enabled,
                "mode": self.mode,
                "recovery_key_generated": bool(self.recovery_key),
            }
            
            self.akshay_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.first_run_file, 'w') as f:
                json.dump(first_run_data, f, indent=2)
            
            self.print("  [green]✓[/green] Setup complete")
            
            # Show summary
            self.print("\n" + "=" * 60)
            self.print("  [bold green]SETUP COMPLETE![/bold green]")
            self.print("=" * 60)
            
            if self.console:
                table = Table(show_header=False, box=None)
                table.add_column("Setting", style="dim")
                table.add_column("Value", style="bold")
                table.add_row("Admin", self.admin_name)
                table.add_row("Role", "ROOT")
                table.add_row("Voice", "Enabled" if self.voice_enabled else "Disabled")
                table.add_row("Mode", self.mode.upper())
                table.add_row("Key Encrypted", "Yes")
                table.add_row("Recovery Key", "Generated" if self.recovery_key else "Skipped")
                self.console.print(table)
            else:
                self.print(f"  Admin: {self.admin_name}")
                self.print(f"  Role: ROOT")
                self.print(f"  Voice: {'Enabled' if self.voice_enabled else 'Disabled'}")
                self.print(f"  Mode: {self.mode.upper()}")
                self.print(f"  Key Encrypted: Yes")
                self.print(f"  Recovery Key: {'Generated' if self.recovery_key else 'Skipped'}")
            
            self.print("\n  AKSHAY AI CORE is ready to use!")
            self.print("  Run 'ai.ps1' to start the system.\n")
            
            return True
            
        except Exception as e:
            self.print(f"\n  [red]✗[/red] Setup failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="AKSHAY AI CORE First-Run Wizard")
    parser.add_argument("--install-path", required=True, help="Installation path")
    
    args = parser.parse_args()
    
    wizard = FirstRunWizard(Path(args.install_path))
    success = wizard.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
