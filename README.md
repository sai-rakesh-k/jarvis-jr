# Jarvis Jr

A small CLI that translates natural-language instructions to shell commands and executes them with safety checks. Intended to be used with a local LLM (optional) and can be extended, but this repository does not include Docker-based sandboxing.

## Features

- **Natural Language CLI**: Convert plain-English requests to shell commands.
- **Safety Analysis**: Classifies commands before execution (safe/moderate/dangerous).
- **Pluggable LLM Backend**: Integration points for local LLMs (e.g., Ollama).
- **Conversation Context**: Maintains session state across interactions.

## Prerequisites

1. Python 3.8+
2. (Optional) Ollama and a local model if you want fully offline LLM inference

## Installation

Install dependencies and the package in editable mode:

```bash
pip install -r requirements.txt
pip install -e .
```

The package exposes a console script called `jarvis` via `setup.py`.

## Usage

After installation run:

```bash
jarvis
```

Or run the app directly with Python:

```bash
python -m jarvis.main
```

Follow the interactive prompts and type requests in plain English.

## Repository Layout

Top-level files and important modules:

- `setup.py` — package metadata and `jarvis` console entry point
- `requirements.txt` — Python dependencies
- `README.md` — this file
- `jarvis/` — main package
	- `main.py` — CLI entry point (exports `app`)
	- `llm_handler.py` — LLM integration helper
	- `command_analyzer.py` — command classification / safety logic
	- `executor.py` — executes commands
	- `context.py` — conversation/session state
	- `config.py` — configuration and defaults
	- `warning_system.py` — user warnings and confirmations
- `tests/` — test package (minimal)

## Notes & Next Steps

- Configure environment variables via `.env` or `config.py` before running an LLM backend.
- To enable offline LLM usage, install and configure Ollama and pull a supported model.
- Write additional tests under `tests/` to cover critical flows.

