# Jarvis Jr - Complete Setup Guide for WSL

This guide will walk you through installing and running Jarvis Jr on Windows with WSL.

## Prerequisites

- Windows 10/11 with WSL installed
- VS Code (optional, for editing)

---

## Step 1: Open WSL Terminal

### Option A: From Windows Terminal
1. Open Windows Terminal
2. Click dropdown arrow next to `+`
3. Select your WSL distribution (Ubuntu, etc.)

### Option B: From VS Code
1. Open VS Code
2. Press `` Ctrl+` `` to open terminal
3. Click dropdown and select WSL (Ubuntu)

### Option C: Direct WSL Command
Open PowerShell and type:
```powershell
wsl
```

---

## Step 2: Navigate to Project

```bash
cd /mnt/c/Users/Rakesh/jarvis-jr
```

**Explanation:** 
- `/mnt/c` is how WSL accesses your C: drive
- Your Windows path `C:\Users\Rakesh\jarvis-jr` becomes `/mnt/c/Users/Rakesh/jarvis-jr`

---

## Step 3: Install Python and pip (if not already installed)

Check if Python is installed:
```bash
python3 --version
```

If not installed:
```bash
sudo apt update
sudo apt install python3 python3-pip -y
```

---

## Step 4: Install Ollama

### Install Ollama:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Start Ollama service:
```bash
# Start Ollama in background
ollama serve &
```

**Note:** Ollama needs to be running before using Jarvis. You can also start it in a separate terminal.

### Download Qwen 2.5 Coder model:
```bash
ollama pull qwen2.5-coder:7b
```

**This will take a few minutes** (model is ~4.7GB)

### Verify installation:
```bash
ollama list
```

You should see `qwen2.5-coder:7b` in the list.

---

## Step 5: Install Docker

### Check if Docker is installed:
```bash
docker --version
```

### If not installed, install Docker:

**Option A: Docker Desktop (Recommended for WSL)**
1. Download from: https://www.docker.com/products/docker-desktop/
2. Install Docker Desktop on Windows
3. In Docker Desktop settings: Enable "Use WSL 2 based engine"
4. In WSL, Docker will be automatically available

**Option B: Docker in WSL directly**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Start Docker
sudo service docker start

# Add your user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Log out and back in for group change to take effect
exit
# Then reopen WSL
```

### Verify Docker:
```bash
docker run hello-world
```

---

## Step 6: Install Jarvis Jr

### Navigate to project:
```bash
cd /mnt/c/Users/Rakesh/jarvis-jr
```

### Install in development mode:
```bash
pip install -e .
```

**What this does:**
- Installs all dependencies from `requirements.txt`
- Makes `jarvis` command available globally
- Changes to code are immediately reflected (no need to reinstall)

### Verify installation:
```bash
jarvis --help
```

You should see:
```
Usage: jarvis [OPTIONS] COMMAND [ARGS]...

  Jarvis Jr - Natural Language Command Line Interface

Commands:
  interactive  Start interactive Jarvis Jr session
  run          Run a single natural language command and exit
  version      Show version information
```

---

## Step 7: Run Jarvis Jr!

### Start interactive mode:
```bash
jarvis interactive
```

### Or run a single command:
```bash
jarvis run "list all python files"
```

---

## Daily Usage

### Every time you want to use Jarvis:

1. **Open WSL terminal**
2. **Start Ollama (if not running):**
   ```bash
   ollama serve &
   ```
3. **Start Docker (if not running):**
   ```bash
   # If using Docker Desktop: Make sure it's running in Windows
   
   # If using Docker in WSL directly:
   sudo service docker start
   ```
4. **Run Jarvis:**
   ```bash
   jarvis interactive
   ```

---

## Quick Start Script

Create a script to start everything automatically:

```bash
# Create startup script
cat > ~/start-jarvis.sh << 'EOF'
#!/bin/bash

echo "Starting Ollama..."
ollama serve > /dev/null 2>&1 &
sleep 2

echo "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "Starting Docker..."
    sudo service docker start
fi

echo "Starting Jarvis Jr..."
cd /mnt/c/Users/Rakesh/jarvis-jr
jarvis interactive
EOF

# Make it executable
chmod +x ~/start-jarvis.sh
```

**Now you can just run:**
```bash
~/start-jarvis.sh
```

---

## Using Jarvis

### Interactive Mode:

```bash
$ jarvis interactive

╭──────────────────────────────────────────╮
│ 🤖 Jarvis Jr                             │
│                                          │
│ Welcome! I'm your natural language       │
│ command line assistant.                  │
╰──────────────────────────────────────────╯

You: list all python files
Jarvis: find . -name '*.py'

🟢 Execution: Success

Output:
./main.py
./test.py

You: create a backup of test.py
Jarvis: cp test.py test.py.bak

🟡 Execution: Success

You: exit
Goodbye! 👋
```

### Special Commands:
- `help` - Show help
- `exit` or `quit` - Exit Jarvis
- `clear` - Clear conversation history
- `history` - Show conversation history
- `export output.txt` - Save conversation to file

---

## Troubleshooting

### Issue: "Ollama not available"

**Solution:**
```bash
# Check if Ollama is running
pgrep ollama

# If not running, start it:
ollama serve &

# Check if model is downloaded:
ollama list

# If model not found:
ollama pull qwen2.5-coder:7b
```

### Issue: "Docker not available"

**Solution:**
```bash
# Check Docker status
docker info

# Start Docker (if using Docker in WSL)
sudo service docker start

# If using Docker Desktop: Make sure it's running in Windows
```

### Issue: "jarvis: command not found"

**Solution:**
```bash
# Reinstall
cd /mnt/c/Users/Rakesh/jarvis-jr
pip install -e .

# Or use full path
python3 -m jarvis.main interactive
```

### Issue: Permission denied for Docker

**Solution:**
```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in
exit
# Reopen WSL
```

### Issue: Can't find project directory

**Solution:**
```bash
# Verify path in Windows
# If project is at C:\Users\Rakesh\jarvis-jr

# In WSL, use:
cd /mnt/c/Users/Rakesh/jarvis-jr

# Check if you're in the right place:
ls
# Should see: jarvis/ tests/ setup.py requirements.txt etc.
```

---

## Tips

1. **Keep Ollama running:** Start it once and leave it running in the background
2. **Use Tab completion:** Jarvis commands support tab completion
3. **Be specific:** "delete test.txt" is better than "delete a file"
4. **Check safety indicators:** 
   - 🟢 Safe commands run directly
   - 🟡 Moderate commands run in Docker
   - 🔴 Dangerous commands ask for confirmation

---

## Updating Jarvis

If you make changes to the code:

```bash
cd /mnt/c/Users/Rakesh/jarvis-jr
# Changes are automatically reflected (no need to reinstall)
# Just restart Jarvis
```

---

## Uninstall

```bash
pip uninstall jarvis-jr
```

---

## Getting Help

- Type `help` inside Jarvis
- Check README.md for features
- View code in VS Code for customization

---

**You're all set! Enjoy using Jarvis Jr! 🚀**
