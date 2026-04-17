"""
Jarvis Jr - Natural Language Command Line Interface
Main entry point and interactive CLI
"""
import os
import re
import typer
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from .llm_handler import LLMHandler
from .context import ConversationContext
from .executor import CommandExecutor
from .command_analyzer import SafetyLevel, CommandAnalyzer
from .config import config

# Create Typer app
app = typer.Typer(help="Jarvis Jr - Natural Language Command Line Interface")

# Create Rich console for beautiful output
console = Console()


# ---------- FIXED PREREQUISITE CHECKS ----------

def ollama_available() -> bool:
    """Check Ollama and required model via HTTP API"""
    try:
        res = requests.get(f"{config.ollama_host}/api/tags", timeout=2)
        models = res.json().get("models", [])
        return any(m["name"] == config.ollama_model for m in models)
    except Exception:
        return False


def check_prerequisites():
    """Check if Ollama is available"""
    issues = []

    # Ollama check
    if ollama_available():
        console.print("✓ Ollama and model available", style="green")
    else:
        issues.append(f"❌ Ollama or {config.ollama_model} model not available")
        issues.append("   Install: https://ollama.ai")
        issues.append(f"   Then run: ollama pull {config.ollama_model}")
    
    if issues:
        console.print("\n[red]Prerequisites not met:[/red]")
        for issue in issues:
            console.print(f"  {issue}")

        response = Prompt.ask("\nContinue anyway?", choices=["yes", "no"], default="no")
        if response == "no":
            raise typer.Exit(1)

    return True


# ---------- UI HELPERS ----------

def print_welcome():
    welcome_text = """
# 🤖 Jarvis Jr

Welcome! I'm your natural language command line assistant.

**How to use:**
- Type commands in plain English
- I will translate them to bash commands and execute them safely
- Please give single command clearly at once for best results
- By default every command assumes target location is current folder, unless you specify otherwise (e.g. "list python files in /home/user")
- Type 'help' for more info, 'exit' to quit
"""
    console.print(Panel(Markdown(welcome_text), border_style="cyan"))


def print_help():
    help_text = """
# Commands

**Special commands:**
- `help` - Show this help
- `exit` or `quit` or `q` - Exit Jarvis Jr

**Quick shortcuts:**
- `ls` / `dir` - List files
- `pwd` - Current directory
- `..` - Go to parent directory

**Examples:**
- "list all python files"
- "create a folder called test"
- "find files larger than 10MB"
- "delete all .tmp files"
"""
    console.print(Panel(Markdown(help_text), border_style="blue"))


def format_safety_level(safety_level: SafetyLevel) -> str:
    return "🟢" if safety_level == SafetyLevel.SAFE else "🟡" if safety_level == SafetyLevel.MODERATE else "🔴"


# ---------- CLI COMMANDS ----------

@app.command()
def interactive():
    """Start interactive Jarvis Jr session"""
    check_prerequisites()
    print_welcome()

    # Initialize with warmup spinner
    with Live(Spinner("dots", text="Loading AI model...", style="cyan"), console=console, transient=True):
        llm = LLMHandler(warmup=True)
    console.print("[green]✓ AI ready![/green]\n")
    
    context = ConversationContext()
    executor = CommandExecutor(context)
    
    # Input history for up/down arrow navigation
    input_history = InMemoryHistory()

    while True:
        try:
            console.print()
            # Use prompt_toolkit for history navigation (up/down arrows)
            folder = os.path.basename(context.working_directory)

            prompt_text = f"Jarvis:{folder} > "

            user_input = pt_prompt(
                prompt_text,
                history=input_history,
                auto_suggest=AutoSuggestFromHistory(),
            ).strip()
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("\n[cyan]Goodbye! 👋[/cyan]")
                break
            
            if user_input.lower() == "help":
                print_help()
                continue
            
            if user_input.lower() == "clear":
                console.print("[green]Context cleared[/green]")
                continue
            
            # Quick shortcuts - bypass LLM for common commands
            quick_commands = {
                 "ls": "ls",
                 "dir": "ls", 
                "pwd": "pwd",
                "..": "cd ..",
            }
            
            if user_input.lower() in quick_commands:
                cmd = quick_commands[user_input.lower()]
                if cmd:
                    console.print(f"[green]{config.assistant_symbol}[/green] {cmd}")
                    exit_code, stdout, stderr, safety = executor.execute(cmd)
                    if stdout:
                        console.print(stdout)
                    if stderr:
                        console.print(f"[red]{stderr}[/red]")
                    continue
                else:
                    console.print("[yellow]No previous command to repeat[/yellow]")
                    continue

            # Inline path detection: if user wrote something like
            # "list files in ./output" or "show logs in C:\\logs",
            # capture the path and set the conversation working directory.
            path_token = None
            m = re.search(r"\b(?:in|at|inside|within|under)\s+(?:the\s+(?:folder|directory)\s+)?(?P<path>\"[^\"]+\"|'[^']+'|[A-Za-z]:\\\\[^\s,;]+|/[^\s,;]+|\./[^\s,;]+|\.\.[^\s,;]*|~[^\s,;]*)", user_input, flags=re.I)
            if m:
                candidate = m.group('path').strip()
                # strip surrounding quotes if present
                if (candidate.startswith('"') and candidate.endswith('"')) or (candidate.startswith("'") and candidate.endswith("'")):
                    candidate = candidate[1:-1]
                candidate = candidate.rstrip('.,;')
                path_token = candidate
            else:
                # quick heuristics for short tokens meaning 'here'
                short_tokens = ['.', 'here', 'this', 'current', 'cwd' ,'present directory' , 'present folder'],
                words = [w.strip('.,;') for w in user_input.lower().split()]
                for tok in short_tokens:
                    if tok in words:
                        path_token = tok
                        break

            if path_token:
                try:
                    if path_token in ('.', 'here', 'this', 'current', 'cwd'):
                        new_dir = os.getcwd()
                    elif path_token.startswith('~'):
                        new_dir = os.path.abspath(os.path.expanduser(path_token))
                    else:
                        new_dir = os.path.abspath(path_token)

                    if os.path.isdir(new_dir):
                        context.update_working_directory(new_dir)
                        console.print(f"[cyan]Working directory set to: {context.working_directory}[/cyan]\n")
                    else:
                        console.print(f"[yellow]Note: Path '{path_token}' not found; using current directory.[/yellow]")
                except Exception:
                    console.print(f"[yellow]Note: Couldn't resolve path '{path_token}'; using current directory.[/yellow]")
            
            # Prepare recent context for LLM (working directory only)
            recent_context = context.get_recent_context()

            # If we composed a new input, call the LLM with that; otherwise use the raw user input
            call_input = user_input

            # Show spinner while waiting for LLM
            with Live(Spinner("dots", text="Thinking...", style="cyan"), console=console, transient=True):
                try:
                    response, is_command = llm.generate_command(call_input, recent_context)
                except ValueError as e:
                    console.print(f"[red]Invalid input: {str(e)}[/red]")
                    continue
                except Exception as e:
                    console.print(f"[red]Error generating command: {str(e)}[/red]")
                    continue

            # Defensive sanitization: strip any echoed RECENT CONVERSATION HISTORY
            if isinstance(response, str) and "RECENT CONVERSATION HISTORY:" in response:
                # Try remove bounded block ending with '---', else remove until end
                response = re.sub(r'RECENT CONVERSATION HISTORY:.*?---\s*', '', response, flags=re.S).strip()
                if "RECENT CONVERSATION HISTORY:" in response:
                    response = re.sub(r'RECENT CONVERSATION HISTORY:.*$', '', response, flags=re.S).strip()

            if not is_command:
                console.print(f"[yellow]{config.assistant_symbol}[/yellow] {response}")
                continue

            # Extract the actual command (remove markdown, backticks, explanations, etc.)
            # BEFORE analyzing for safety or executing
            command = llm._extract_command(response)
            
            #  Block install/network commands (offline mode)
            install_keywords = ["pip install", "apt install", "apt-get install", "npm install", "yarn add"]

            if any(command.startswith(k) for k in install_keywords):
                console.print(f"[yellow]{config.assistant_symbol} Suggestion (not executed):[/yellow] {command}")
                console.print("[cyan]This is an installation command. Please run it manually (requires internet).[/cyan]")
                continue

            if not command:
                console.print(f"[yellow]{config.assistant_symbol}[/yellow] {response}")
                continue

            #  ADD THIS BLOCK HERE
            if command.strip().startswith("sudo"):
                console.print("[red]Sudo commands are not allowed.[/red]")
                continue

            # Analyze safety
            analyzer = CommandAnalyzer()
            safety, reason = analyzer.analyze(command)

            # Print command
            console.print(f"[green]{config.assistant_symbol}[/green] {command}")
            
            if safety == SafetyLevel.DANGEROUS:
                console.print(f"\n[bold red]⚠️  WARNING: Dangerous command![/bold red]")
                console.print(f"[yellow]Reason: {reason}[/yellow]")
                confirm = Prompt.ask("Proceed?", choices=["yes", "no"], default="no")
                if confirm != "yes":
                    console.print("[yellow]Command cancelled.[/yellow]")
                    continue
            
            # Show where command will run
            console.print(f"[dim]💻 Running on host...[/dim]")

            interactive_cmds = {"nano", "vim", "vi", "less", "more", "top", "htop", "man", "pico", "emacs"}

            first = command.split()[0]

            if first in interactive_cmds:
                console.print(f"[yellow]Running interactive command:[/yellow] {command}")
                exit_code, stdout, stderr, safety = executor.execute(command, auto_confirm=True)
            else:
                with Live(Spinner("dots", text="Executing...", style="yellow"), console=console, transient=True):
                    exit_code, stdout, stderr, safety = executor.execute(command, auto_confirm=True)
            console.print(
                f"{format_safety_level(safety)} [dim]{'Success' if exit_code == 0 else 'Failed'}[/dim]"
            )

            # Show output or explicit 'nothing' when there's no stdout/stderr
            if stdout:
                console.print("\n[bold]Output:[/bold]")
                console.print(stdout)
            elif stderr:
                console.print("\n[bold red]Errors:[/bold red]")
                console.print(stderr)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")

    executor.cleanup()


@app.command()
def version():
    """Show version information"""
    console.print("[cyan]Jarvis Jr v0.1.0[/cyan]")
    console.print(f"Model: {config.ollama_model}")


if __name__ == "__main__":
    app()