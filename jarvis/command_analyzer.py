"""
Command analyzer for safety classification
"""
import re
from enum import Enum
from typing import Tuple
from .config import config


class SafetyLevel(Enum):
    """Safety classification levels"""
    SAFE = "safe"           # Read-only, always run on host
    MODERATE = "moderate"   # File modifications, run in Docker by default
    DANGEROUS = "dangerous" # Destructive operations, require confirmation + Docker


class CommandAnalyzer:
    """Analyzes bash commands for safety and determines execution mode"""
    
    def __init__(self):
        self.config = config
    
    def analyze(self, command: str) -> Tuple[SafetyLevel, str]:
        """
        Analyze a command and return its safety level with explanation
        """
        command = command.strip()

        # =========================
        # 1 Detect dangerous compound commands FIRST
        # =========================
        # Block: && || ; ` $() (command chaining/execution)
        dangerous_operators = [
            r'&&',
            r'\|\|',
            r';',
            r'\$\(',
            r'`',
            r'\n'
        ]

        for op in dangerous_operators:
            if re.search(op, command):
                return (
                    SafetyLevel.DANGEROUS,
                    f"Compound or chained command detected: {op}"
                )

        # Block dangerous pipes: |sh, |bash, |python, |nc, |curl, etc (pipe to shell/interpreters)
        dangerous_pipes = [
            r'\|\s*sh\b',
            r'\|\s*bash\b',
            r'\|\s*zsh\b',
            r'\|\s*python\b',
            r'\|\s*perl\b',
            r'\|\s*ruby\b',
            r'\|\s*nc\b',
            r'\|\s*curl\b',
            r'\|\s*wget\b',
            r'\|\s*telnet\b'
        ]

        for pipe in dangerous_pipes:
            if re.search(pipe, command):
                return (
                    SafetyLevel.DANGEROUS,
                    f"Dangerous pipe to shell/interpreter detected"
                )

        # Safe pipes (| wc, | head, | tail, | sort, | uniq, | grep, etc.) are allowed

        # =========================
        # 2 Dangerous patterns
        # =========================
        for pattern in self.config.dangerous_patterns:
            if re.search(pattern, command):
                return (
                    SafetyLevel.DANGEROUS,
                    f"Contains dangerous pattern: {pattern}"
                )

        # =========================
        # 3 Extract base command
        # =========================
        base_command = self._extract_base_command(command)

        # =========================
        # 4 Safe commands (read-only)
        # =========================
        if base_command in self.config.safe_commands:
            return (
                SafetyLevel.SAFE,
                "Read-only command, safe to execute on host"
            )

        # =========================
        # 5 Moderate commands
        # =========================
        if base_command in self.config.moderate_commands:
            return (
                SafetyLevel.MODERATE,
                "File modification command, will run in Docker sandbox"
            )

        # =========================
        # 6️⃣ Default
        # =========================
        return (
            SafetyLevel.MODERATE,
            "Unknown command, will run in Docker sandbox for safety"
        )

    
    def _extract_base_command(self, command: str) -> str:
        """
        Extract the base command from a full command string
        
        Examples:
            "ls -la /home" -> "ls"
            "sudo apt-get install" -> "apt-get"
            "  grep pattern file.txt  " -> "grep"
        """
        command = command.strip()
        
        # Handle sudo
        if command.startswith('sudo '):
            command = command[5:].strip()
        
        # Get first word
        parts = command.split()
        if not parts:
            return ""
        
        return parts[0]
    
    def should_use_docker(self, safety_level: SafetyLevel) -> bool:
        """
        Determine if command should run in Docker based on safety level
        
        Args:
            safety_level: The safety level of the command
            
        Returns:
            True if should run in Docker, False if can run on host
        """
        # Safe commands never use Docker
        if safety_level == SafetyLevel.SAFE:
            return False
        # Optionally allow moderate commands on host for speed
        if safety_level == SafetyLevel.MODERATE and self.config.run_moderate_on_host:
            return False
        # Default: Moderate and Dangerous use Docker
        return True
    
    def requires_confirmation(self, safety_level: SafetyLevel) -> bool:
        """
        Determine if command requires user confirmation before execution
        
        Args:
            safety_level: The safety level of the command
            
        Returns:
            True if requires confirmation, False otherwise
        """
        return safety_level == SafetyLevel.DANGEROUS
