"""
============================================================
AKSHAY AI CORE — Interactive Shell
============================================================
Rich command-line interface for direct interaction.
============================================================
"""

import asyncio
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger("shell")
console = Console()


# Shell style
SHELL_STYLE = Style.from_dict({
    "prompt": "#00ff00 bold",
    "input": "#ffffff",
    "output": "#87ceeb",
    "error": "#ff0000",
})

# Command completions
COMMANDS = [
    "help", "exit", "quit", "clear", "status", "history",
    "memory", "plugins", "automation", "config", "auth",
    "brain", "chat", "execute", "search", "verify",
]


class InteractiveShell:
    """
    Interactive shell for AKSHAY AI CORE.
    
    Features:
    - Natural language input
    - Command history
    - Auto-completion
    - Rich output formatting
    - Streaming responses
    """
    
    def __init__(self):
        self._session: Optional[PromptSession] = None
        self._history: List[Dict] = []
        self._running = False
        self._user_id: Optional[str] = None
        self._authenticated = False
    
    async def start(self) -> None:
        """Start the interactive shell."""
        self._running = True
        
        # Print welcome banner
        self._print_banner()
        
        # Initialize components
        await self._initialize()
        
        # Create prompt session
        completer = WordCompleter(COMMANDS, ignore_case=True)
        history_file = settings.DATA_DIR / "shell_history"
        
        self._session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer,
            style=SHELL_STYLE,
        )
        
        # Main loop
        await self._main_loop()
    
    def _print_banner(self) -> None:
        """Print welcome banner."""
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
║                    ╔═╗╦  ╔═╗╔═╗╦═╗╔═╗                        ║
║                    ║  ║  ║ ║╠═╣╠╦╝║╣                         ║
║                    ╚═╝╩═╝╚═╝╩ ╩╩╚═╚═╝                        ║
║                                                               ║
║           Personal AI Operating System v1.0.0                 ║
║                                                               ║
║  Type 'help' for commands or just talk to me naturally.      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
        console.print(Text(banner, style="bold cyan"))
    
    async def _initialize(self) -> None:
        """Initialize shell components."""
        with console.status("[bold green]Initializing AKSHAY AI CORE..."):
            # Initialize brain
            try:
                from core.brain.memory import memory_manager
                await memory_manager.initialize()
                console.print("  ✓ Memory system initialized", style="green")
            except Exception as e:
                console.print(f"  ✗ Memory system failed: {e}", style="red")
            
            # Initialize plugins
            try:
                from plugins import plugin_manager
                await plugin_manager.load_all_plugins()
                console.print("  ✓ Plugins loaded", style="green")
            except Exception as e:
                console.print(f"  ✗ Plugin loading failed: {e}", style="red")
            
            # Initialize automation
            try:
                from automation import scheduler
                await scheduler.start()
                console.print("  ✓ Automation scheduler started", style="green")
            except Exception as e:
                console.print(f"  ✗ Automation failed: {e}", style="red")
        
        console.print()
    
    async def _main_loop(self) -> None:
        """Main input loop."""
        while self._running:
            try:
                # Get input
                prompt_text = "AKSHAY > " if self._authenticated else "AKSHAY [locked] > "
                user_input = await self._session.prompt_async(prompt_text)
                
                if not user_input.strip():
                    continue
                
                # Process input
                await self._process_input(user_input.strip())
                
            except KeyboardInterrupt:
                console.print("\nUse 'exit' to quit.", style="yellow")
            except EOFError:
                break
            except Exception as e:
                console.print(f"Error: {e}", style="red")
                logger.error("Shell error", error=str(e))
    
    async def _process_input(self, text: str) -> None:
        """Process user input."""
        # Add to history
        self._history.append({
            "input": text,
            "timestamp": datetime.utcnow(),
        })
        
        # Check for built-in commands
        cmd = text.lower().split()[0]
        
        if cmd in ["exit", "quit", "bye"]:
            await self._cmd_exit()
        elif cmd == "help":
            self._cmd_help()
        elif cmd == "clear":
            self._cmd_clear()
        elif cmd == "status":
            await self._cmd_status()
        elif cmd == "history":
            self._cmd_history()
        elif cmd == "plugins":
            await self._cmd_plugins(text)
        elif cmd == "memory":
            await self._cmd_memory(text)
        elif cmd == "config":
            self._cmd_config(text)
        elif cmd == "verify":
            await self._cmd_verify(text)
        else:
            # Process as natural language
            await self._process_natural(text)
    
    async def _process_natural(self, text: str) -> None:
        """Process natural language input."""
        with console.status("[bold cyan]Thinking..."):
            try:
                from core.brain.command_router import router
                
                # Route the command
                result = await router.route(text, user_id=self._user_id)
                
                # Check if needs confirmation
                if result.requires_confirmation:
                    console.print(
                        Panel(
                            f"This action requires confirmation:\n\n"
                            f"Intent: {result.intent.action}\n"
                            f"Targets: {[t.plugin_id for t in result.targets]}",
                            title="⚠️ Confirmation Required",
                            style="yellow",
                        )
                    )
                    
                    confirm = await self._session.prompt_async("Proceed? [y/N] ")
                    if confirm.lower() not in ["y", "yes"]:
                        console.print("Cancelled.", style="yellow")
                        return
                
                # Execute if we have targets
                if result.targets:
                    output = await router.execute_route(result, user_id=self._user_id)
                    self._display_result(output)
                
                # Fallback to LLM
                if result.fallback_to_llm:
                    await self._chat_with_llm(text)
                    
            except Exception as e:
                console.print(f"Error: {e}", style="red")
                logger.error("Natural processing failed", error=str(e))
    
    async def _chat_with_llm(self, text: str) -> None:
        """Chat with LLM."""
        try:
            from core.brain.llm_connector import llm, Message
            from core.brain.memory import memory_manager
            
            # Get relevant context
            context = await memory_manager.get_context(text, user_id=self._user_id)
            
            # Build messages
            messages = [
                Message(
                    role="system",
                    content=f"""You are AKSHAY, a personal AI assistant.
You are helpful, concise, and friendly.
Current time: {datetime.utcnow().isoformat()}

Relevant context:
{context}""",
                ),
                Message(role="user", content=text),
            ]
            
            # Stream response
            response_text = ""
            console.print()
            
            with Live(console=console, refresh_per_second=10) as live:
                async for chunk in llm.stream(messages):
                    response_text += chunk
                    live.update(Markdown(response_text))
            
            console.print()
            
            # Store in memory
            await memory_manager.store(
                content=f"User: {text}\nAssistant: {response_text[:500]}",
                importance=0.5,
                tags=["conversation"],
                user_id=self._user_id,
            )
            
        except Exception as e:
            console.print(f"LLM error: {e}", style="red")
    
    def _display_result(self, result: Dict[str, Any]) -> None:
        """Display command result."""
        console.print()
        
        for output in result.get("outputs", []):
            if "error" in output:
                console.print(
                    Panel(
                        f"Error: {output['error']}",
                        title=f"❌ {output['target']}:{output['command']}",
                        style="red",
                    )
                )
            else:
                # Format result based on type
                result_data = output.get("result", {})
                
                if isinstance(result_data, dict):
                    table = Table(show_header=True)
                    table.add_column("Key")
                    table.add_column("Value")
                    
                    for k, v in result_data.items():
                        table.add_row(str(k), str(v)[:100])
                    
                    console.print(
                        Panel(
                            table,
                            title=f"✅ {output['target']}:{output['command']}",
                            style="green",
                        )
                    )
                else:
                    console.print(
                        Panel(
                            str(result_data),
                            title=f"✅ {output['target']}:{output['command']}",
                            style="green",
                        )
                    )
    
    # Built-in commands
    
    async def _cmd_exit(self) -> None:
        """Exit the shell."""
        console.print("Goodbye! 👋", style="cyan")
        self._running = False
        
        # Cleanup
        try:
            from automation import scheduler
            await scheduler.stop()
        except:
            pass
    
    def _cmd_help(self) -> None:
        """Show help."""
        help_text = """
## AKSHAY AI CORE Commands

### System Commands
- `help` - Show this help
- `exit/quit` - Exit the shell
- `clear` - Clear the screen
- `status` - Show system status
- `history` - Show command history
- `config` - Show/modify configuration

### AI Commands
- `verify <text>` - Fact-check text
- Just type naturally to chat with AKSHAY

### Module Commands
- `plugins [list|enable|disable]` - Manage plugins
- `memory [stats|search|clear]` - Manage memory

### Examples
- "Open Chrome"
- "What's the weather like?"
- "Schedule a reminder for 5pm"
- "Search for Python tutorials"
"""
        console.print(Markdown(help_text))
    
    def _cmd_clear(self) -> None:
        """Clear screen."""
        console.clear()
        self._print_banner()
    
    async def _cmd_status(self) -> None:
        """Show system status."""
        from core.utils.system_check import SystemChecker
        
        checker = SystemChecker()
        health = await checker.check_system_health()
        
        table = Table(title="System Status")
        table.add_column("Component")
        table.add_column("Status")
        table.add_column("Details")
        
        for component, data in health.get("components", {}).items():
            status = "✅" if data.get("status") == "healthy" else "❌"
            details = str(data.get("details", ""))[:50]
            table.add_row(component, status, details)
        
        console.print(table)
    
    def _cmd_history(self) -> None:
        """Show command history."""
        table = Table(title="Command History")
        table.add_column("#")
        table.add_column("Time")
        table.add_column("Input")
        
        for i, entry in enumerate(self._history[-20:], 1):
            table.add_row(
                str(i),
                entry["timestamp"].strftime("%H:%M:%S"),
                entry["input"][:50],
            )
        
        console.print(table)
    
    async def _cmd_plugins(self, text: str) -> None:
        """Manage plugins."""
        from plugins import plugin_manager
        
        parts = text.split()
        subcmd = parts[1] if len(parts) > 1 else "list"
        
        if subcmd == "list":
            plugins = await plugin_manager.list_plugins()
            
            table = Table(title="Plugins")
            table.add_column("ID")
            table.add_column("Version")
            table.add_column("Status")
            
            for p in plugins:
                table.add_row(
                    p["id"],
                    p.get("version", "?"),
                    p.get("status", "unknown"),
                )
            
            console.print(table)
    
    async def _cmd_memory(self, text: str) -> None:
        """Manage memory."""
        from core.brain.memory import memory_manager
        
        parts = text.split()
        subcmd = parts[1] if len(parts) > 1 else "stats"
        
        if subcmd == "stats":
            stats = memory_manager.get_stats()
            
            table = Table(title="Memory Stats")
            table.add_column("Metric")
            table.add_column("Value")
            
            for k, v in stats.items():
                table.add_row(k, str(v))
            
            console.print(table)
            
        elif subcmd == "search":
            query = " ".join(parts[2:]) if len(parts) > 2 else ""
            if not query:
                console.print("Usage: memory search <query>", style="yellow")
                return
            
            memories = await memory_manager.recall(query, limit=5)
            
            for m in memories:
                console.print(
                    Panel(
                        m.content[:200],
                        title=f"{m.memory_type.value} | {m.importance:.2f}",
                    )
                )
    
    def _cmd_config(self, text: str) -> None:
        """Show configuration."""
        table = Table(title="Configuration")
        table.add_column("Setting")
        table.add_column("Value")
        
        # Show non-sensitive settings
        safe_settings = [
            "APP_NAME", "VERSION", "ENVIRONMENT", "AI_PROVIDER", "AI_MODEL",
            "HOST", "PORT", "LOG_LEVEL",
        ]
        
        for key in safe_settings:
            value = getattr(settings, key, None)
            if value is not None:
                table.add_row(key, str(value))
        
        console.print(table)
    
    async def _cmd_verify(self, text: str) -> None:
        """Verify facts."""
        query = text[6:].strip()  # Remove "verify "
        
        if not query:
            console.print("Usage: verify <text to fact-check>", style="yellow")
            return
        
        from core.brain.truth_check import truth_checker
        
        with console.status("[bold cyan]Verifying..."):
            results = await truth_checker.verify(query, deep_check=True)
        
        for result in results:
            status_color = {
                "verified": "green",
                "likely_true": "green",
                "uncertain": "yellow",
                "likely_false": "red",
                "false": "red",
                "unverifiable": "dim",
            }.get(result.status.value, "white")
            
            console.print(
                Panel(
                    f"**Claim:** {result.claim}\n\n"
                    f"**Status:** {result.status.value.upper()}\n"
                    f"**Confidence:** {result.confidence:.0%}\n\n"
                    f"{result.explanation}",
                    title="Verification Result",
                    style=status_color,
                )
            )


async def run_shell() -> None:
    """Run the interactive shell."""
    shell = InteractiveShell()
    await shell.start()


if __name__ == "__main__":
    asyncio.run(run_shell())
