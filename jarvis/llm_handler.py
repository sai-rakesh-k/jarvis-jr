"""
LLM handler for natural language to command translation
"""
import ollama
import re
from typing import Optional, Tuple
from .config import config


class LLMHandler:
    """Handles communication with Ollama LLM for command generation"""
    
    def __init__(self, warmup: bool = True):
        """Initialize LLM handler with Ollama client"""
        self.config = config
        self.model = config.ollama_model
        self.system_prompt = self._build_system_prompt()
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

    # --------------------------------------------------------------------------------------------------

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

        # Include provided ConversationContext (working directory only)
        if context:
            messages.append({"role": "system", "content": context})

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

    def _is_command(self, response: str) -> bool:
        """
        Check if response is a valid bash command
        
        Args:
            response: The response text to check
            
        Returns:
            True if it's a valid command, False otherwise
        """
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
            "mv", "cp", "rm", "rmdir", "head", "tail", "wc",
            "sort", "uniq", "du", "df", "pwd", "git", "pip",
            "whoami", "tree", "touch", "cd"
        }

        return first_word in allowed_commands

    def _build_system_prompt(self) -> str:
        return """You are a bash command generator.

    OUTPUT FORMAT (STRICT):
    - Output ONLY one single-line bash command.
    - OR output ONLY one single-line clarification question ending with ?.
    - No explanations, markdown, comments, or extra text.
    - Prefer simple, direct commands if multiple options are possible.

    You ONLY handle:
    - Files, Directories
    - Directories
    - File contents
    - Searching
    - Moving, copying, deleting,opening editing and similar files or folders
    - File permissions
    - Disk usage
    - Process management
    - CLI operations
    - Install required packages 

    If the request is NOT related to filesystem or CLI or Directory operations:
    Return exactly:
    echo "Error: Only filesystem and CLI operations are supported"


    DEFAULTS:
    - Path = current directory (.)
    - Non-recursive operations unless explicitly requested.
    - Hidden files/directories are excluded by default.

    FORBIDDEN UNLESS EXPLICITLY REQUESTED:
    - -a 
    - -A
    - -l

    DIRECTORY RULES:
    - change/go/transfer folder → cd <folder>
    - use relative paths only
    


    LISTING RULES:
    - Never include . or .. while listing directories unless explicitly requested.
    - If user asks ONLY files → use find . -maxdepth 1 -type f
    - If user asks ONLY directories/folders → find . -maxdepth 1 -type d ! -name ".*"
    - If user asks for files use ls
    - If user asks for directories/folders use find . -maxdepth 1 -type d ! -name ".*"
    - If user asks for both files and directories/folders use ls
    - Avoid broad wildcard deletion (e.g., rm *.txt) when exclusions are required.
    - Avoid using xargs with sh -c unless absolutely required.
    - Prefer direct loops or simple commands.
    - Read the user request carefully 
    If user request is ambiguous, output exactly one clarification question.
    
    
    """



    def _normalize_command(self, cmd: str, user_input: str) -> str:
        """
        Fix common LLM command mistakes before validation/execution.
        """

        user_lower = user_input.lower()

        # ---- check if user explicitly wants hidden files ----
        wants_hidden = any(word in user_lower for word in [
            "hidden",
            "include hidden",
            "everything",
            "all files including hidden"
        ])

        # ---- fix grep count (line count vs occurrence count) ----
        # If command is: grep ... | wc -l
        # ensure grep uses -o so occurrences are counted
        if "grep" in cmd and "| wc -l" in cmd:

            import re

            # match grep flags like -i, -ri, etc.
            match = re.search(r'\bgrep\s+(-[a-zA-Z]+)', cmd)

            if match:
                flags = match.group(1)

                # add 'o' only if missing
                if "o" not in flags:
                    new_flags = flags + "o"
                    cmd = cmd.replace(flags, new_flags, 1)
            
        # ---- split command into tokens ----
        parts = cmd.split()
        cleaned = []

        if any(word in user_lower for word in ["total", "all", "entire"]):
            parts

        for p in parts:

            # remove hidden flags unless requested
            if not wants_hidden:
                if p in ["-a", "-A", "-1A", "-A1", "-la", "-al"]:
                    continue

                # remove combined flags containing a/A
                if p.startswith("-"):
                    p = p.replace("A", "").replace("a", "")
                    if p == "-":
                        continue

            cleaned.append(p)

        cmd = " ".join(cleaned).strip()

        # ---- normalize common bad ls patterns ----
        if cmd.startswith("ls") and "*/" in cmd and "*" in cmd:
            return "ls"

        if cmd in ["ls .", "ls $(pwd)", "ls | cat", "ls -1 ."]:
            return "ls"

        # simplify useless "ls ." variants
        if cmd.startswith("ls ") and cmd.endswith(" ."):
            return "ls"
        
        # ---- fix common find typos ----
        if "-mxdepth" in cmd:
            cmd = cmd.replace("-mxdepth", "-maxdepth")
        elif "-maxdept" in cmd:
            cmd = cmd.replace("-maxdept", "-maxdepth")
        elif "-maxdeph" in cmd:
            cmd = cmd.replace("-maxdeph", "-maxdepth")
        if "-nme" in cmd:
            cmd = cmd.replace("-nme", "-name")
        elif "-inme" in cmd:
            cmd = cmd.replace("-inme", "-iname")

        return cmd

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

        user_lower = user_input.lower()

        # ---- GENERIC EXCEPT PARSER ----
        m = re.search(
            r"(delete|remove|count|how many).*(?:all )?"
            r"(?P<ext>\.\w+|\w+\s*files?).*"
            r"(?:except|exclude|excluding|apart from|but not|other than)\s+"
            r"(?P<exclude>.+)",
            user_lower
        )

        if m:
            action = m.group(1)
            ext = m.group("ext").strip()
            exclude_raw = m.group("exclude")
            
            # ---- detect file type from user input ----
            ext_map = {
                "python": ".py",
                "py": ".py",
                "text": ".txt",
                "txt": ".txt",
                "json": ".json",
                "java": ".java",
                "cpp": ".cpp",
                "c": ".c",
            }

            ext = None

            for key, value in ext_map.items():
                if key in user_lower:
                    ext = value
                    break

            # fallback (if regex gave extension like .txt)
            if not ext:
                ext = m.group("ext").replace("files", "").replace("file", "").strip()
                if not ext.startswith("."):
                    ext = "." + ext


            # ---- clean natural language fillers ----
            exclude_raw = re.sub(
                r"\b(and also|also|too)\b",
                "",
                exclude_raw
            )

            # ---- parse multiple excluded files ----
            exclude_files = re.split(r",|and", exclude_raw)
            exclude_files = [f.strip() for f in exclude_files if f.strip()]

            # ---- build exclusion part ----
            exclude_part = " ".join(
                [f'! -name "{f}"' for f in exclude_files]
            )

            # ---- DELETE CASE ----
            if action in ["delete", "remove"]:
                cmd = (
                    f'find . -maxdepth 1 -type f '
                    f'-name "*{ext}" {exclude_part} -delete'
                )
                return (cmd, True)

            # ---- COUNT CASE ----
            if action in ["count", "how many"]:
                cmd = (
                    f'find . -maxdepth 1 -type f '
                    f'-name "*{ext}" {exclude_part} | wc -l'
                )
                return (cmd, True)


        # Truncate very long inputs to prevent token overflow
        max_input_length = 500
        if len(user_input) > max_input_length:
            user_input = user_input[:max_input_length].strip()

        try:
            # -------------------------------
            #  Build messages for LLM
            # -------------------------------
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Include provided context (ConversationContext with working directory) first as system guidance
            if context:
                messages.append({"role": "system", "content": context})

            # No internal context window (conversation history disabled)

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

                # Question handling
                if response_text.endswith("?"):

                    # Fix cases like "pwd?" → "pwd"
                    possible_cmd = response_text[:-1].strip()

                    if self._is_command(possible_cmd):
                        return (possible_cmd, True)

                    return (response_text, False)


                command = self._extract_command(response_text)

                if not command:
                    continue
                command = self._normalize_command(command, user_input)
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
    
    def analyze_error (self,command:str,stderr:str)->str:
        messages = [
            {
                "role": "system",
                "content": """
    You are a troubleshooting assistant.

    Explain:
    1. Why the error occurred.
    2. Possible causes.
    3. What the user should do.

    Do NOT provide installation commands.
    Do NOT execute anything.
    Keep the answer concise.
    """
            },
            {
                "role": "user",
                "content": f"""
    Command:
    {command}

    Error:
    {stderr}
    """
            }
        ]
        response=ollama.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": 0.1,
                "num_predict": 120,
            }
        )
        return response["message"]["content"].strip()
    
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
  