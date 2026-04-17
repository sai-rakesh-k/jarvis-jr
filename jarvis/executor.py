"""
Command executor that routes commands with warning system
"""
import subprocess
import os
from typing import Tuple
from .command_analyzer import CommandAnalyzer, SafetyLevel
from .warning_system import WarningSystem
from .context import ConversationContext
import shlex
import sys


class CommandExecutor:
    """Executes commands with warning system for dangerous operations"""
    
    # Interactive commands that require TTY and stdin/stdout passthrough
    INTERACTIVE_COMMANDS = {"nano", "vim", "vi", "less", "more", "top", "htop", "man", "pico", "emacs"}
    
    def __init__(self, context: ConversationContext):
        """
        Initialize command executor
        
        Args:
            context: Conversation context for tracking state
        """
        self.context = context
        self.analyzer = CommandAnalyzer()
        self.warning_system = WarningSystem()
    
    def execute(self, command: str, auto_confirm: bool = False) -> Tuple[int, str, str, SafetyLevel]:
        """
        Execute a command with warning system for dangerous operations
        All commands execute on the host system.
        
        Args:
            command: The bash command to execute
            auto_confirm: If True, skip confirmation prompts (for testing)
            
        Returns:
            Tuple of (exit_code, stdout, stderr, safety_level)
        """
        # Check if this is an interactive command
        try:
            first_word = command.split()[0]
        except IndexError:
            first_word = ""
        
        is_interactive = first_word in self.INTERACTIVE_COMMANDS
        
        # Analyze command safety
        safety_level, reason = self.analyzer.analyze(command)
        
        # Show warning and get confirmation if needed
        if self.warning_system.should_warn(safety_level.value) and not auto_confirm:
            confirmed = self.warning_system.show_warning_and_confirm(command, reason, safety_level.value)
            if not confirmed:
                return (1, "", "Command execution cancelled by user", safety_level)
        else:
            # Show info for safe commands
            if safety_level == SafetyLevel.SAFE:
                self.warning_system.show_info_message(command, reason)
        
        # Execute on host - use interactive mode for TTY commands
        if is_interactive:
            exit_code = self._execute_interactive(command)
            stdout, stderr = "", ""
        else:
            exit_code, stdout, stderr = self._execute_on_host(command)
        
        # Update working directory if cd command was executed
        if exit_code == 0:
            self._update_working_directory_after_cd(command)
        
        return (exit_code, stdout, stderr, safety_level)
    
    def _execute_on_host(self, command: str) -> Tuple[int, str, str]:
        """
        Execute command directly on host system with output capture
        
        Args:
            command: The bash command to execute
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            # Run command in bash with 30 second timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.context.working_directory,
                timeout=30
            )
            
            return (result.returncode, result.stdout, result.stderr)
            
        except subprocess.TimeoutExpired:
            return (124, "", "Command timed out after 30 seconds")
        except FileNotFoundError:
            return (127, "", f"Command not found: {command.split()[0] if command else 'unknown'}")
        except Exception as e:
            return (1, "", f"Error executing command: {str(e)}")
    
    def _execute_interactive(self, command: str) -> int:
        """
        Execute interactive command with direct TTY passthrough
        User can interact with the command in real-time
        
        Args:
            command: The bash command to execute
            
        Returns:
            Exit code from the command
        """
        try:
            # Run command with direct stdin/stdout/stderr passthrough
            # No timeout for interactive commands
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.context.working_directory
            )
            return result.returncode
            
        except KeyboardInterrupt:
            # User pressed Ctrl+C
            return 130
        except FileNotFoundError:
            print(f"Error: Command not found: {command.split()[0] if command else 'unknown'}", file=sys.stderr)
            return 127
        except Exception as e:
            print(f"Error executing command: {str(e)}", file=sys.stderr)
            return 1
    
    

    def _update_working_directory_after_cd(self, command: str):
        """
        Update working directory if command was a cd command.
        Handles quoted paths and spaces correctly.
        """
        try:
            parts = shlex.split(command)
        except ValueError:
            # Malformed command (e.g., unclosed quotes)
            return

        if not parts:
            return

        # Handle sudo cd ...
        if parts[0] == "sudo":
            if len(parts) < 2:
                return
            base_cmd = parts[1]
            args = parts[2:]
        else:
            base_cmd = parts[0]
            args = parts[1:]

        if base_cmd != "cd":
            return

        # If no argument: go to home directory
        if not args:
            new_dir = os.path.expanduser("~")
        else:
            cd_dir = args[0]

            if cd_dir == "~":
                new_dir = os.path.expanduser("~")
            elif cd_dir == "-":
                # Optional: implement previous directory tracking later
                return
            elif os.path.isabs(cd_dir):
                new_dir = cd_dir
            else:
                new_dir = os.path.join(self.context.working_directory, cd_dir)

        new_dir = os.path.normpath(new_dir)

        # Update only if directory exists
        if os.path.isdir(new_dir):
            self.context.working_directory = new_dir

    def cleanup(self):
        """Cleanup resources (minimal cleanup needed)"""
        pass