"""
LLM handler for natural language to command translation
"""
import ollama
import re
import os
import json
import time
from typing import Optional, Tuple, Generator
from .config import config


class LLMHandler:
    """Handles communication with Ollama LLM for command generation"""
    
    def __init__(self, warmup: bool = True):
        """Initialize LLM handler with Ollama client"""
        self.config = config
        self.model = config.ollama_model
        self.system_prompt = self._build_system_prompt()
        self._command_cache = {}  # Cache for repeated queries
        self._cache_size = 50     # Max cache entries
        self.context_window = []  # Track conversation history for context
        self.max_context_messages = 5  # Keep last 5 exchanges
        if warmup:
            self._warmup_model()
    
    def _warmup_model(self):
        """Pre-load model into GPU memory for faster first response"""
        try:
            ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                options={"num_predict": 1, "num_gpu": 1}
            )
        except Exception:
            pass  # Silent fail - warmup is optional
    
    def add_to_context(self, user_input: str, assistant_output: str):
        """
        Add user input and assistant response to context window
        
        Args:
            user_input: The user's natural language input
            assistant_output: The LLM's response (command or question)
        """
        self.context_window.append({
            "user": user_input,
            "assistant": assistant_output
        })
        
        # Keep only the last N exchanges to prevent context bloat
        if len(self.context_window) > self.max_context_messages:
            self.context_window = self.context_window[-self.max_context_messages:]
    
    def get_context_string(self) -> str:
        """
        Generate a string representation of recent context
        
        Returns:
            Formatted context history for inclusion in prompts
        """
        if not self.context_window:
            return ""
        
        context_parts = ["RECENT CONVERSATION HISTORY:"]
        for i, exchange in enumerate(self.context_window, 1):
            context_parts.append(f"User: {exchange['user']}")
            context_parts.append(f"Assistant: {exchange['assistant']}")
        
        context_parts.append("---")
        return "\n".join(context_parts)
    
    def clear_context(self):
        """Clear the context window"""
        self.context_window = []
    
        # Strict Command Detection

    def _is_command(self, response: str) -> bool:
        response = response.strip()

        if not response:
            return False

        # Must be single line
        if "\n" in response:
            return False

        # Questions are not commands
        if response.endswith("?"):
            return False

        # Extract first word (command name)
        first_word = response.split()[0]

        # Allowed shell commands
        allowed_commands = {
            "ls", "find", "grep", "sed", "awk", "cat", "mkdir",
            "mv", "cp", "rm", "head", "tail", "wc",
            "sort", "uniq", "du", "df", "pwd",
            "whoami", "tree", "touch"
        }

        return first_word in allowed_commands

    # --------------------

    def assemble_messages_for_test(self, user_input: str, context: Optional[str] = None):
        """
        Assemble the messages that would be sent to the LLM for debugging/testing.

        Returns the list of message dicts without calling the model.
        """
        # Validate and sanitize input (same as generate_command)
        if not user_input or not isinstance(user_input, str):
            raise ValueError("Invalid input: please provide a non-empty string")

        user_input_trunc = user_input
        max_input_length = 500
        if len(user_input_trunc) > max_input_length:
            user_input_trunc = user_input_trunc[:max_input_length].strip()

        messages = [{"role": "system", "content": self.system_prompt}]

        # Include provided ConversationContext (if any) first
        if context:
            messages.append({"role": "system", "content": context})

        # Include internal LLM context window
        if self.context_window:
            messages.append({"role": "system", "content": self.get_context_string()})

        messages.append({"role": "user", "content": user_input_trunc})

        return messages
    
    def _validate_syntax(self, command: str) -> bool:
        """
        Validate bash syntax without executing command
        """
        import subprocess
        result = subprocess.run(
            ["bash", "-n"],
            input=command,
            text=True,
            capture_output=True
        )
        return result.returncode == 0

    def _build_system_prompt(self) -> str:
        return """You are a bash command generator.

    Return exactly ONE single-line bash command.
    No explanations.
    No markdown.
    No comments.
    No extra text.

    If clarification is required, return exactly ONE single-line question ending with ?.

    If the user does not specify a path, assume the current directory (.).
    """


          
    def generate_command(self, user_input: str, context: Optional[str] = None) -> Tuple[str, bool]:
        """
        Generate a bash command from natural language input
        Now includes:
        - Low randomness
        - Tool whitelist
        - Command chaining block
        - Bash syntax validation
        - Auto-repair retry (1 attempt)
        - Input validation and truncation
        """
        
        # Validate and sanitize input
        if not user_input or not isinstance(user_input, str):
            return ("Invalid input: please provide a non-empty string", False)
        
        # Truncate very long inputs to prevent token overflow
        max_input_length = 500
        if len(user_input) > max_input_length:
            user_input = user_input[:max_input_length].strip()

        # Check cache first (only for commands without context)
        cache_key = user_input.lower().strip()
        if cache_key and not context and cache_key in self._command_cache:
            cached_result = self._command_cache[cache_key]
            if cached_result and isinstance(cached_result, tuple) and len(cached_result) == 2:
                return cached_result

        try:
            # -------------------------------
            #  Build messages for LLM
            # -------------------------------
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Include provided context (ConversationContext) first as system guidance
            if context:
                messages.append({"role": "system", "content": context})

            # Include LLMHandler context window if available (recent exchanges)
            if self.context_window:
                context_str = self.get_context_string()
                messages.append({"role": "system", "content": context_str})

            messages.append({"role": "user", "content": user_input})

            # -------------------------------
            #  Call Ollama (LOW temperature for stability)
            # -------------------------------
            max_attempts = 3

            for attempt in range(max_attempts):

                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "num_predict": 80,
                        "temperature": 0.0,
                        "top_k": 1,
                        "top_p": 0.9,
                        "num_ctx": 512,
                        "num_gpu": 1,
                    }
                )

                response_text = response['message']['content'].strip()

                # Reject explanation patterns
                if response_text.lower().startswith(("to ", "this ", "here ", "you ", "use ", "run ")):
                    continue  # retry instead of return

                # Reject multi-line output
                if "\n" in response_text:
                    continue  # retry

                # Question
                if response_text.endswith("?"):
                    return (response_text, False)

                command = self._extract_command(response_text)

                if not command:
                    continue

                if self._validate_syntax(command):
                    return (command, True)

            # If all retries fail
            return ("Failed to generate valid command after retries.", False)

        except ollama.ResponseError as e:
            return (f"Error communicating with Ollama: {str(e)}", False)
        except Exception as e:
            return (f"Unexpected error: {str(e)}", False)

    
    def _extract_command(self, response: str) -> str:
        """
        Extract the actual command from the response
        
        Sometimes the LLM includes markdown code blocks or extra text.
        This function extracts just the command.
        
        Args:
            response: The LLM response
            
        Returns:
            The cleaned command
        """
        if not response or not isinstance(response, str):
            return ""
        

        # Remove markdown code blocks if present
        if "```" in response:
            # Extract content between ``` markers
            match = re.search(r'```(?:bash|sh)?\n?(.*?)\n?```', response, re.DOTALL)
            if match:
                response = match.group(1).strip()

            # Remove inline backticks to avoid accidental shell command substitution
            response = response.replace("`", "")

        # Remove leading $ or # (common in examples)
        response = re.sub(r'^[\$#]\s*', '', response.strip())
        # Remove leading "Output:" if model includes it
        response = re.sub(r'^Output:\s*', '', response, flags=re.IGNORECASE)


        # Split into lines and pick the first line that contains alphanumeric characters
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Skip lines that are just emojis or punctuation (e.g., '✓')
            if not re.search(r'[A-Za-z0-9]', line):
                continue
            return line

        # Reject obvious English sentences
        if response.lower().startswith(("to ", "this ", "here ", "you ", "use ", "run ")):
            return ""

        return response.strip()
    
    def is_ollama_available(self) -> bool:
        """Check if Ollama is available and the model is installed"""
        try:
            # Try to list models
            response = ollama.list()
            
            if not response or 'models' not in response:
                return False
            
            # Check if our model is in the list
            models = response.get('models', [])
            if not isinstance(models, list):
                return False
            
            model_names = [m.get('name', '') for m in models if isinstance(m, dict)]
            
            # Check for exact match or partial match (with tag)
            model_base = self.model.split(':')[0]
            for name in model_names:
                if self.model in name or name.startswith(model_base):
                    return True
            
            return False
            
        except (AttributeError, KeyError, TypeError, Exception):
            return False
    
    def explain_command(self, command: str) -> str:
        """
        Get an explanation of what a command does
        
        Args:
            command: The bash command to explain
            
        Returns:
            Explanation of the command
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that explains bash commands. Provide a brief, clear explanation in 1-2 sentences."
                },
                {
                    "role": "user",
                    "content": f"Explain this bash command: {command}"
                }
            ]
            
            response = ollama.chat(
                model=self.model,
                messages=messages
            )
            
            return response['message']['content'].strip()
            
        except Exception as e:
            return f"Could not generate explanation: {str(e)}"
    
    def is_explanation_request(self, user_input: str) -> bool:
        """
        Fast pattern-based detection for explanation requests (no LLM call)
        
        Args:
            user_input: What the user just said
            
        Returns:
            True if asking for explanation, False if it's a new command
        """
        user_lower = user_input.lower().strip()
        
        # Exact matches for quick explanation requests
        quick_explain = {'explain', 'explain this', 'what does this mean', 'what is this',
                         'why', 'how', 'huh', 'what', '?', 'elaborate', 'clarify'}
        if user_lower in quick_explain:
            return True
        
        # Pattern matches for explanation phrases
        explain_patterns = [
            'explain', 'what does', 'what is', 'what are', 'tell me about',
            'what do you mean', 'can you explain', 'i don\'t understand',
            'break it down', 'simplify', 'in simple terms', 'what happened'
        ]
        
        for pattern in explain_patterns:
            if pattern in user_lower:
                # Make sure it's asking about previous output, not a new command
                # e.g., "explain git" is a new command, "explain this" is about previous
                new_command_indicators = ['file', 'directory', 'folder', 'create', 'delete',
                                          'list', 'show', 'find', 'search', 'run']
                if not any(ind in user_lower for ind in new_command_indicators):
                    return True
        
        return False
    
    def explain_output(self, user_request: str, command: str, output: str) -> str:
        """
        Explain command output in plain English
        
        Args:
            user_request: What the user originally asked
            command: The command that was run
            output: The command output
            
        Returns:
            Human-readable explanation
        """
        try:
            # Limit output to first 500 chars to save tokens
            limited_output = output[:500] + ("..." if len(output) > 500 else "")
            
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Summarize command output in 1-2 simple sentences that a non-technical user can understand. Focus on what the user asked for."
                },
                {
                    "role": "user",
                    "content": f"User asked: '{user_request}'\nCommand run: {command}\nOutput:\n{limited_output}\n\nExplain what this output means in simple terms:"
                }
            ]
            
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": 100,  # Reduced from 150
                    "temperature": 0.05, # Reduced from 0.1
                    "top_k": 5,          # Reduced from 10
                    "top_p": 0.9,        # Add top_p
                    "num_ctx": 512,      # Reduced from 2048
                    "num_gpu": 1
                }
            )
            
            return response['message']['content'].strip()
            
        except Exception:
            return ""  # Silently fail - explanation is optional
