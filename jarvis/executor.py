"""
Command executor that routes commands to host or Docker
"""
import subprocess
import os
from typing import Tuple
from .command_analyzer import CommandAnalyzer, SafetyLevel
from .docker_sandbox import DockerSandbox
from .context import ConversationContext


class CommandExecutor:
    """Executes commands either on host or in Docker based on safety analysis"""
    
    def __init__(self, context: ConversationContext):
        """
        Initialize command executor
        
        Args:
            context: Conversation context for tracking state
        """
        self.context = context
        self.analyzer = CommandAnalyzer()
        self.sandbox = None  # Lazy initialization
    
    def _get_sandbox(self) -> DockerSandbox:
        """Get or create Docker sandbox instance"""
        if self.sandbox is None:
            self.sandbox = DockerSandbox()
        return self.sandbox
    
    def execute(self, command: str, auto_confirm: bool = False) -> Tuple[int, str, str, SafetyLevel]:
        """
        Execute a command with appropriate safety measures
        
        Args:
            command: The bash command to execute
            auto_confirm: If True, skip confirmation prompts (for testing)
            
        Returns:
            Tuple of (exit_code, stdout, stderr, safety_level)
        """
        # Analyze command safety
        safety_level, reason = self.analyzer.analyze(command)
        
        # Check if confirmation needed
        if self.analyzer.requires_confirmation(safety_level) and not auto_confirm:
            confirmed = self._get_user_confirmation(command, reason)
            if not confirmed:
                return (1, "", "Command execution cancelled by user", safety_level)
        
        # Execute based on safety level
        if self.analyzer.should_use_docker(safety_level):
            # Run in Docker
            exit_code, stdout, stderr = self._execute_in_docker(command)
        else:
            # Run on host
            exit_code, stdout, stderr = self._execute_on_host(command)
        
        # Record execution in context
        self.context.add_command_execution(command, stdout, exit_code)
        
        return (exit_code, stdout, stderr, safety_level)
    
    def _execute_on_host(self, command: str) -> Tuple[int, str, str]:
        """
        Execute command directly on host system
        
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
    
    def _execute_in_docker(self, command: str) -> Tuple[int, str, str]:
        """
        Execute command in Docker sandbox
        
        Args:
            command: The bash command to execute
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            sandbox = self._get_sandbox()
            
            # Execute in sandbox with current working directory mounted
            exit_code, stdout, stderr = sandbox.execute_command(
                command=command,
                working_dir=self.context.working_directory
            )
            
            return (exit_code, stdout, stderr)
            
        except Exception as e:
            return (1, "", f"Docker execution error: {str(e)}")
    
    def _get_user_confirmation(self, command: str, reason: str) -> bool:
        """
        Ask user to confirm execution of dangerous command
        
        Args:
            command: The command to confirm
            reason: Reason why it's dangerous
            
        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n⚠️ WARNING: This command is potentially dangerous!")
        print(f"Command: {command}")
        print(f"Reason: {reason}")
        print(f"It will run in an isolated Docker container.")
        
        while True:
            response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please answer 'yes' or 'no'")
    
    def is_docker_available(self) -> bool:
        """Check if Docker is available for sandbox execution"""
        try:
            sandbox = self._get_sandbox()
            return sandbox.is_docker_available()
        except Exception:
            return False
    
    def cleanup(self):
        """Cleanup resources (Docker containers, etc.)"""
        if self.sandbox:
            self.sandbox.cleanup()
