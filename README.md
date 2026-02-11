# Jarvis Jr

A natural language command line interface that lets you interact with your terminal using plain English instead of memorizing bash commands.

## Features

-  **Natural Language Interface**: Enter the task to be executed in plain English
-  **Local LLM**: Powered by Qwen 2.5 Coder 7B via Ollama (100% offline)
-  **Docker Sandbox**: Dangerous commands run in isolated containers
-  **Safety First**: Three-tier command classification (safe, moderate, dangerous)

## Prerequisites

1. **Python 3.8+**
2. **Docker** (for sandboxing)
3. **Ollama** with Qwen 2.5 Coder 7B model
4. **WSL** (if on Windows)

## Installation

### 1. Install Ollama and download the model

```bash
# Install Ollama (visit https://ollama.ai)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull Qwen 2.5 Coder 7B
ollama pull qwen2.5-coder:7b
```

### 2. Install Docker

Follow instructions at https://docs.docker.com/get-docker/

### 3. Install Jarvis Jr

```bash
cd jarvis-jr
pip install -e .
```

## Usage

Simply run:

```bash
jarvis
```

Then type your requests in plain English:

```
You: list all python files in current directory
You: create a backup of config.json
You: find all files larger than 100MB
You: delete all .tmp files
```

## How It Works

1. You type a command in natural language
2. Qwen 2.5 Coder translates it to bash command
3. Safety analyzer checks if command is dangerous
4. Safe commands run directly; risky ones run in Docker
5. You see the output and can continue the conversation

## Safety Features

- **Safe commands**: Run directly (ls, cat, grep, pwd, etc.)
- **Moderate commands**: Run in Docker with warning (mkdir, touch, wget, etc.)
- **Dangerous commands**: Require confirmation + Docker isolation (rm -rf, dd, etc.)

## Project Structure

```
jarvis-jr/
├── jarvis/              # Main package
│   ├── main.py          # CLI entry point
│   ├── llm_handler.py   # Ollama integration
│   ├── command_analyzer.py  # Safety classification
│   ├── docker_sandbox.py    # Docker container management
│   ├── executor.py      # Command execution
│   ├── context.py       # Conversation state
│   └── config.py        # Configuration
├── tests/               # Tests
├── Dockerfile           # Sandbox container
└── requirements.txt     # Dependencies
```

## License

