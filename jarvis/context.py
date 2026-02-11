"""
Context manager for conversation history and environment state
"""
import os
from typing import List, Dict, Optional, Any
from datetime import datetime


class ConversationContext:
    """Manages conversation history and environment state"""
    
    def __init__(self):
        """Initialize conversation context"""
        self.history: List[Dict[str, str]] = []
        self.working_directory = os.getcwd()
        self.last_command: Optional[str] = None
        self.last_output: Optional[str] = None
    
    def add_user_message(self, message: str):
        """
        Add a user message to the conversation history
        
        Args:
            message: The user's input
        """
        self.history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        MAX_HISTORY = 50
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
    
    def add_assistant_message(self, message: str):
        """
        Add an assistant message to the conversation history
        
        Args:
            message: The assistant's response
        """
        self.history.append({
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_command_execution(self, command: str, output: Any, exit_code: int):
        """
        Record a command execution
        
        Args:
            command: The command that was executed
            output: The command output
            exit_code: The exit code (0 = success)
        """
        self.last_command = command
        self.last_output = output
        
        self.history.append({
            "role": "system",
            "content": f"Executed: {command}",
            "output": output,
            "exit_code": exit_code,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_recent_context(self, num_messages: int = 3) -> str:
        """
        Get recent conversation context for the LLM
        
        Args:
            num_messages: Number of recent messages to include
            
        Returns:
            Formatted context string
        """
        if not self.history:
            return ""

        recent = [
            msg for msg in self.history[-num_messages * 2:]
            if msg["role"] in ["user", "assistant"]
        ]

        context_parts = []

        # Include working directory
        context_parts.append(f"Current directory: {self.working_directory}")

        if self.last_command:
            context_parts.append(f"Last command: {self.last_command}")

        for msg in recent:
            role = msg["role"].capitalize()
            context_parts.append(f"{role}: {msg['content']}")

        return "\n".join(context_parts)

    
    def get_last_assistant_message(self) -> Optional[str]:
        """
        Get the last assistant message
        
        Returns:
            The last assistant message, or None if there isn't one
        """
        for msg in reversed(self.history):
            if msg["role"] == "assistant":
                return msg["content"]
        return None
    
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
    
    def clear_history(self):
        """Clear the conversation history"""
        self.history = []
        self.last_command = None
        self.last_output = None
    
    def get_full_history(self) -> List[Dict[str, str]]:
        """
        Get the complete conversation history
        
        Returns:
            List of all messages
        """
        return self.history.copy()
    
    def export_history(self, filepath: str):
        """
        Export conversation history to a file
        
        Args:
            filepath: Path to save the history
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not filepath or not isinstance(filepath, str):
                raise ValueError("Filepath must be a non-empty string")
            
            expanded_path = os.path.expanduser(filepath)
            
            with open(expanded_path, 'w', encoding='utf-8') as f:
                f.write("# Jarvis Jr Conversation History\n\n")
                
                for msg in self.history:
                    timestamp = msg.get("timestamp", "")
                    role = msg.get("role", "").upper()
                    content = msg.get("content", "")
                    
                    f.write(f"[{timestamp}] {role}: {content}\n")
                    
                    if role == "SYSTEM" and "output" in msg:
                        output = msg.get("output", "")
                        exit_code = msg.get("exit_code", "")
                        f.write(f"  Exit Code: {exit_code}\n")
                        f.write(f"  Output: {output}\n")
                    
                    f.write("\n")
            
            return True
        except ValueError as e:
            print(f"Invalid input: {e}")
            return False
        except IOError as e:
            print(f"Error writing to file: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error exporting history: {e}")
            return False
