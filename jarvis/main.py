"""
Jarvis Jr - Natural Language Command Line Interface
Main entry point and interactive CLI
"""
import sys
import os
import re
import typer
import requests
import docker
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
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


def docker_available() -> bool:
    """Check Docker availability via SDK ping"""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def check_prerequisites():
    """Check if Ollama and Docker are available"""
    issues = []

    # Ollama check
    if ollama_available():
        console.print("✓ Ollama and model available", style="green")
    else:
        issues.append(f"❌ Ollama or {config.ollama_model} model not available")
        issues.append("   Install: https://ollama.ai")
        issues.append(f"   Then run: ollama pull {config.ollama_model}")

    # Docker check
    if docker_available():
        console.print("✓ Docker available", style="green")
    else:
        issues.append("❌ Docker not available")
        issues.append("   Install: https://docs.docker.com/get-docker/")
        issues.append("   For WSL, ensure Docker Desktop is running")

    if issues:
        console.print("\n[red]Prerequisites not met:[/red]")
        for issue in issues:
            console.print(f"  {issue}")

        console.print(
            "\n[yellow]Note: Safe commands (ls, cat, etc.) will still work without Docker[/yellow]"
        )

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
- I'll translate them to bash commands and execute them safely
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
- `clear` - Clear conversation history
- `!!` - Repeat last command

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
            user_input = pt_prompt(
                f"{config.prompt_symbol}",
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
                context.clear_history()
                llm.clear_context()
                console.print("[green]Conversation history and context cleared[/green]")
                continue
            
            # Quick shortcuts - bypass LLM for common commands
            quick_commands = {
                "ls": "ls -la",
                "dir": "ls -la", 
                "pwd": "pwd",
                "..": "cd ..",
                "!!": context.last_command if context.last_command else None,
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
                        context.working_directory = new_dir
                        console.print(f"[cyan]Working directory set to: {context.working_directory}[/cyan]\n")
                    else:
                        console.print(f"[yellow]Note: Path '{path_token}' not found; using current directory.[/yellow]")
                except Exception:
                    console.print(f"[yellow]Note: Couldn't resolve path '{path_token}'; using current directory.[/yellow]")
            
            # Prepare recent context for LLM
            recent_context = context.get_recent_context()

            # Auto-composition: if the previous assistant asked a clarifying question
            # and the user's reply is a short path-like answer (e.g. "current folder", ".", "here", "output"),
            # combine the original user intent with this short reply to form a full instruction.
            previous_assistant = context.get_last_assistant_message()

            composed_input = None
            if previous_assistant and previous_assistant.strip().endswith('?'):
                # Heuristic: short replies (<=4 words) or common path tokens
                short_tokens = ['.', 'here', 'current', 'this', 'output', 'cwd', 'folder', 'directory']
                words = user_input.strip().split()
                lower = user_input.lower()
                looks_like_path = any(tok in lower for tok in short_tokens) or lower.startswith('/') or lower.startswith('~')
                if len(words) <= 4 and looks_like_path:
                    # Find the user's previous message (the intent that prompted the question)
                    prior_user = None
                    for msg in reversed(context.get_full_history()):
                        if msg.get('role') == 'user':
                            prior_user = msg.get('content')
                            break
                    if prior_user:
                        # Compose a new user input combining prior intent + clarified path
                        composed_input = f"{prior_user} in {user_input.strip()}"

            # If we composed a new input, call the LLM with that; otherwise use the raw user input
            call_input = composed_input if composed_input else user_input

            # Record the raw user message in conversation history (we store the user's reply)
            context.add_user_message(user_input)

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

            # Capture the previous assistant message BEFORE recording the new response
            previous_assistant = context.get_last_assistant_message()

            # Defensive sanitization: strip any echoed RECENT CONVERSATION HISTORY
            if isinstance(response, str) and "RECENT CONVERSATION HISTORY:" in response:
                # Try remove bounded block ending with '---', else remove until end
                response = re.sub(r'RECENT CONVERSATION HISTORY:.*?---\s*', '', response, flags=re.S).strip()
                if "RECENT CONVERSATION HISTORY:" in response:
                    response = re.sub(r'RECENT CONVERSATION HISTORY:.*$', '', response, flags=re.S).strip()

            # Record current assistant response and LLM context
            context.add_assistant_message(response)

            # Track in LLM context window for conversation continuity
            llm.add_to_context(user_input, response)

            if not is_command:
                console.print(f"[yellow]{config.assistant_symbol}[/yellow] {response}")
                continue

            # Extract the actual command (remove markdown, backticks, explanations, etc.)
            # BEFORE analyzing for safety or executing
            command = llm._extract_command(response)
            
            if not command:
                console.print(f"[yellow]{config.assistant_symbol}[/yellow] {response}")
                continue

            # Analyze the EXTRACTED command (not the raw response with markdown/explanation)
            analyzer = CommandAnalyzer()
            safety, reason = analyzer.analyze(command)
            uses_docker = analyzer.should_use_docker(safety)

            # Print the extracted command before any confirmation prompt
            console.print(f"[green]{config.assistant_symbol}[/green] {command}")

            # If the PREVIOUS assistant message was a clarifying question, require explicit run confirmation
            # only for non-SAFE commands. Safe commands skip this extra prompt.
            if previous_assistant and previous_assistant.strip().endswith('?') and safety != SafetyLevel.SAFE:
                confirm_run = Prompt.ask("Run this command?", choices=["yes", "no"], default="no")
                if confirm_run != "yes":
                    console.print("[yellow]Command cancelled.[/yellow]")
                    continue
            
            if safety == SafetyLevel.DANGEROUS:
                console.print(f"\n[bold red]⚠️  WARNING: Dangerous command![/bold red]")
                console.print(f"[yellow]Reason: {reason}[/yellow]")
                if uses_docker:
                    console.print(f"[dim]Will run in isolated Docker container.[/dim]")
                else:
                    console.print(f"[dim]Docker not available — this would run on host. Proceed with caution.[/dim]")
                confirm = Prompt.ask("Proceed?", choices=["yes", "no"], default="no")
                if confirm != "yes":
                    console.print("[yellow]Command cancelled.[/yellow]")
                    continue
            
            # Show where command will run
            if uses_docker:
                console.print(f"[dim]🐳 Running in Docker sandbox...[/dim]")
            else:
                console.print(f"[dim]💻 Running on host...[/dim]")

            # Show spinner during command execution
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
            else:
                console.print("\n[bold]Output:[/bold]")
                console.print("nothing")

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
