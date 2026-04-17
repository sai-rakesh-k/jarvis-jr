"""
Context manager for environment state
"""
import os
from typing import Dict


class ConversationContext:
    """Manages working directory state only"""
    
    def __init__(self):
        """Initialize conversation context"""
        # Default working directory set to /home/rakesh (WSL Ubuntu)
        self.working_directory = "/home/rakesh"
    
    def get_recent_context(self) -> str:
        """
        Get current context for the LLM (working directory only)
        
        Returns:
            Formatted context string with current directory
        """
        return f"Current directory: {self.working_directory}"
    
    def update_working_directory(self, new_dir: str):
        """
        Update the current working directory
        
        Args:
            new_dir: The new working directory path
            
        Raises:
            ValueError: If the directory does not exist
        """
        if not new_dir or not isinstance(new_dir, str):
            raise ValueError("Directory path must be a non-empty string")
        
        abs_path = os.path.abspath(new_dir)
        
        if not os.path.isdir(abs_path):
            raise ValueError(f"Directory does not exist: {abs_path}")
        
        self.working_directory = abs_path
    
    def get_environment_info(self) -> Dict[str, str]:
        """
        Get current environment information
        
        Returns:
            Dictionary with environment details
        """
        return {
            "working_directory": self.working_directory,
            "user": os.environ.get("USER", "unknown"),
            "home": os.environ.get("HOME", "~"),
            "shell": os.environ.get("SHELL", "/bin/bash")
        }