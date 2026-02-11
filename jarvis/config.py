"""
Configuration settings for Jarvis Jr (Hardened Version)
"""
from pydantic import BaseModel
from typing import List, Set


class Config(BaseModel):
    """Application configuration"""

    # =========================
    # LLM Settings
    # =========================
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_host: str = "http://localhost:11434"

    # Recommended defaults for qwen2.5:3b (balanced accuracy and speed)
    llm_num_predict: int = 80
    llm_temperature: float = 0.1
    llm_top_k: int = 3
    llm_num_ctx: int = 512

    # =========================
    # Docker Settings
    # =========================
    docker_image: str = "jarvis-sandbox:latest"
    docker_timeout: int = 300
    docker_memory_limit: str = "1g"
    docker_cpu_limit: float = 2.0
    reuse_container: bool = True  # Reuse container for speed

    # =========================
    # Safety Classification
    # =========================

    # STRICTLY READ-ONLY COMMANDS
    safe_commands: Set[str] = {
        "ls", "pwd", "whoami", "date", "cal",
        "cat", "less", "more", "head", "tail",
        "grep", "find", "wc", "sort", "uniq",
        "diff", "file", "stat", "df", "du",
        "ps", "top", "htop",
        "which", "whereis", "man",
        "history", "env", "printenv",
        "basename", "dirname", "realpath",
    }

    # Commands that modify files/system (always sandboxed)
    moderate_commands: Set[str] = {
        "sed", "awk", "gawk", "mawk",  # Text processing (can modify)
        "touch", "mkdir", "rmdir",
        "cp", "mv", "ln",
        "wget", "curl",
        "git", "npm", "pip", "apt",
        "tar", "gzip", "unzip", "zip",
        "chmod", "chown",
        "tee", "xargs",
        "clear"
    }

    # Stronger dangerous detection
    dangerous_patterns: List[str] = [
        # Destructive file operations
        r"\brm\b",
        r"rm\s+-rf",
        r"rm\s+.*\*",

        # Disk operations
        r"\bdd\b",
        r"\bmkfs\b",
        r"\bfdisk\b",
        r"\bparted\b",
        r">\s*/dev/",

        # Permission escalation
        r"chmod\s+777",
        r"chmod\s+-R\s+777",
        r"chown\s+-R",

        # System control
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bpoweroff\b",

        # Process killing
        r"\bkill\b",
        r"\bpkill\b",
        r"\bkillall\b",

        # Fork bomb
        r":\(\)\{:\|:&\};:",

        # Pipe-to-shell attacks
        r"curl.*\|.*sh",
        r"wget.*\|.*sh",
        r"\|\s*sh",

        # Dev null abuse
        r"mv\s+.*\s+/dev/null",

        # Filesystem wipe tools
        r"\bshred\b",
        r"\bwipefs\b",
    ]

    # SECURITY: Never run modifying commands on host
    run_moderate_on_host: bool = False

    # Output formatting
    simplify_output: bool = True

    # UI
    prompt_symbol: str = "You: "
    assistant_symbol: str = "Jarvis: "
    command_color: str = "cyan"
    warning_color: str = "yellow"
    error_color: str = "red"
    success_color: str = "green"

    # Logging
    log_file: str = "~/.jarvis_history.log"
    enable_logging: bool = True

    class Config:
        frozen = False


# Global config instance
config = Config()
