# DevMate - Terminal Pair Programmer

A powerful open-source terminal coding assistant that feels like a real pair programmer, not just a chat box.

## Features

### Core Capabilities
- **File Operations**: Read, edit, write, and search files in your project
- **Shell Commands**: Run any shell command directly from the assistant
- **Git Integration**: Full Git support (status, commits, branches, diffs, stash)
- **Persistent Memory**: Remembers context across sessions with automatic checkpoints

### Working Modes
- **Build Mode** (default): Full coding mode with read/write/execute capabilities
- **Plan Mode**: Read-only planning and analysis
- **Spec Mode**: Spec-driven coordination for larger tasks

### Productivity Features
- **Automatic Checkpoints**: Save progress every N actions (configurable)
- **Task Tracking**: Create, track, and complete multi-step tasks
- **Scratch Notes**: Persistent scratchpad for ideas and notes
- **Memory Search**: Query past actions and decisions
- **Stop Conditions**: Set conditions that automatically stop when met

### Helper Agents
Spawn specialized agents for specific tasks:
- **Code Review Agent**: Analyzes code quality and suggests improvements
- **Test Agent**: Plans and executes testing strategies
- **Docs Agent**: Updates documentation as you code

### Model Support
- **Built-in**: No setup required, uses heuristics for common operations
- **OpenAI**: GPT-4o, GPT-4 Turbo support
- **Anthropic**: Claude Sonnet and other models
- **Ollama**: Local model support (CodeLlama, DeepSeek Coder, etc.)
- **Custom**: Any OpenAI-compatible API endpoint

## Quick Start

### Installation

```bash
# Make executable
chmod +x devmate.py

# Optional: Add to PATH
sudo ln -s $(pwd)/devmate.py /usr/local/bin/devmate
```

### First Run

```bash
# Start in current directory
./devmate.py

# Or start in a specific project
./devmate.py /path/to/project

# Show setup guide
./devmate.py --setup
```

## Configuration

### Global Config (~/.devmate/config.json)

First run creates default config. Edit to customize:

```json
{
  "model": {
    "provider": "builtin",
    "api_key": "",
    "base_url": "",
    "model_name": "devmate-local",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "auto_checkpoint": true,
  "checkpoint_interval": 5,
  "verbose": false,
  "color_enabled": true,
  "default_mode": "build"
}
```

### Project Config (.devmate.json)

Create in your project root for project-specific settings:

```json
{
  "name": "my-project",
  "mode": "build",
  "memory_tags": ["python", "web", "api"],
  "ignored_dirs": [".git", "node_modules", "__pycache__"]
}
```

## Command Reference

| Category | Command | Description |
|----------|---------|-------------|
| Files | `/read <path>` | Read a file's contents |
| Files | `/write <path> <content>` | Write content to file |
| Files | `/list [path]` | List files (add `-r` for recursive) |
| Shell/Git | `/run <command>` | Execute a shell command |
| Shell/Git | `/git <subcommand>` | Git operations |
| Tasks | `/task new <title>` | Create a new task |
| Tasks | `/task list` | List active tasks |
| Memory | `/memory [query]` | View/search memory |
| Memory | `/checkpoint` | Manage checkpoints |
| Other | `/help` | Show all commands |
| Other | `/mode <build\|plan\|spec>` | Change working mode |
| Other | `/quit` | Exit DevMate |

## Examples

### Multi-step Task with Checkpoints

```
DevMate> /task new "Refactor authentication module"
Created task 'Refactor authentication module' (ID: a1b2c3d4)

DevMate> Let's start by reading the auth module
[DevMate reads and analyzes the code]

DevMate> /checkpoint new "Analyzed current auth implementation"
💾 Checkpoint created: xyz789
```

### Using Stop Conditions

```
DevMate> /stop "All tests pass and no linting errors"
[DevMate works on the task...]
🎉 Stop condition met! Task complete.
```

### Spawning Helper Agents

```
DevMate> /agent spawn code-review "Review the recent changes"
[CodeReviewAgent] Analyzing code changes...
```

## Advanced Usage

### Plan Mode
Use for safe exploration without making changes:
```bash
./devmate.py --mode plan
```

### Ollama Local Models
```bash
ollama pull codellama
# Configure provider: "ollama" in ~/.devmate/config.json
```

## License

MIT License

---

**DevMate** - Your intelligent pair programmer in the terminal.
