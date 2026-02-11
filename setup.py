from setuptools import setup, find_packages

setup(
    name="jarvis-jr",
    version="0.1.0",
    description="Natural language command line interface powered by local LLM",
    author="Rakesh",
    packages=find_packages(),
    install_requires=[
        "ollama>=0.1.0",
        "docker>=7.0.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "prompt-toolkit>=3.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "jarvis=jarvis.main:app",
        ],
    },
    python_requires=">=3.8",
)
