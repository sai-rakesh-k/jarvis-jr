# Jarvis Jr - Explanation Features

How to get human-readable explanations of command outputs.

---

## **Two Ways to Get Explanations**

### **Method 1: Ask for Explanation in Your Question**

Include trigger words in your request:

```
You: explain all directories
You: what files are here?
You: tell me about disk usage
You: show me what's in this folder
```

**Trigger words:**
- explain
- what does/is
- tell me
- show me
- mean
- understand
- describe

---

### **Method 2: Use the `explain` Command**

Run any command first, then type `explain`:

```
You: list directories
Jarvis: ls -d */ | grep -v 'venv\|node_modules'

Output:
jarvis/
tests/
docs/

You: explain
💬 You have 3 main directories in your project: jarvis (source code), tests (test files), and docs (documentation).
```

---

## **Examples**

### **Example 1: Automatic Explanation**

```
You: explain all directories here
Jarvis: ls -d */ | grep -v 'venv\|node_modules\|__pycache__\|\.git'

🟢 Execution: Success

Output:
jarvis/
tests/

💬 Your project has 2 main directories: jarvis contains the source code, and tests contains test files. System folders like venv are hidden.
```

### **Example 2: Manual Explanation**

```
You: list python files
Jarvis: find . -name "*.py" -not -path "*/venv/*"

🟢 Execution: Success

Output:
./jarvis/main.py
./jarvis/config.py
./jarvis/executor.py
...

You: explain
💬 You have 7 Python files in your project, mostly in the jarvis folder which contains the main application code.
```

### **Example 3: No Explanation (Default)**

```
You: list directories
Jarvis: ls -d */ | grep -v 'venv\|node_modules'

🟢 Execution: Success

Output:
jarvis/
tests/

[No automatic explanation - you didn't ask for one!]
```

---

## **Benefits**

✅ **Cleaner output by default** - No clutter unless you want it  
✅ **Understand results** - AI explains what the output means  
✅ **Perfect for beginners** - No need to understand bash output  
✅ **On-demand** - Use `explain` whenever you need clarification  

---

## **Special Commands**

| Command | What It Does |
|---------|-------------|
| `help` | Show help menu |
| `explain` | Explain last command output |
| `clear` | Clear conversation history |
| `history` | Show past commands |
| `exit` | Quit Jarvis |

---

## **Configuration**

Explanations are **smart and automatic**:
- If you ask for explanation → You get it
- If you don't → Clean output only
- Always available via `explain` command

No configuration needed!

---

## **Pro Tips**

1. **For quick tasks**: Just run commands normally
   ```
   You: list files
   → Shows output, no explanation
   ```

2. **When learning**: Add "explain" or "what is"
   ```
   You: explain the files here
   → Shows output + explanation
   ```

3. **After running something**: Type `explain`
   ```
   You: [command runs]
   You: explain
   → Get explanation of last output
   ```

---

**Enjoy cleaner, smarter command outputs!** 🎯
