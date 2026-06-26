# LiberCode

An open-source terminal coding assistant that feels like a real pair programmer, not just a chat box.

```
pip install libercode
libercode
```

## Features

- **Terminal-native** — runs in your terminal, reads/edits files, executes shell commands, works with Git
- **Cross-session memory** — remembers your project context between sessions
- **Three working modes** — `build` for active development, `plan` for read-only analysis, `spec` for coordinating multi-step specs
- **Automatic checkpoints** — snapshots project state at configurable intervals
- **Task tracking** — create, update, pause, resume tasks with status tracking
- **Scratch notes** — quick notes that persist across sessions
- **Sub-agent spawning** — spins up helper agents for parallel work
- **Stop condition checking** — verifies whether a job is truly done before stopping
- **Built-in free provider** — works out of the box with HuggingFace Inference API (no API key needed)
- **Custom providers** — OpenAI, Anthropic, or any OpenAI-compatible API
- **Project-level config** — `.libercoderc` file for per-project settings

## Quick start

```bash
# Install
pip install libercode

# Run (first launch will walk you through setup)
libercode

# Or run in a specific mode
libercode --mode plan
libercode exec "explain the architecture of this project" --mode plan
```

The first run wizard will ask which provider to use. Choose **builtin** for zero-setup
(free HuggingFace models) or **custom** to use your own API key.

## Usage

### Interactive session

```bash
libercode
libercode --mode plan
libercode --mode spec
```

### One-shot commands

```bash
libercode exec "add error handling to the main function"
libercode exec "list all TODO comments in the codebase" --mode plan
```

### Commands inside the session

| Command | Description |
|---------|-------------|
| `!<command>` | Run a shell command (`!ls`, `!python test.py`) |
| `file:read <path>` | Read a file |
| `file:write <path> <content>` | Write/create a file |
| `file:edit <path> \|\|\| <old> \|\|\| <new>` | Edit a file |
| `git <command>` | Run any git command |
| `task:create <title> \|\|\| <desc>` | Create a tracked task |
| `task:update <id> status=completed` | Update task status |
| `checkpoint [summary]` | Save a checkpoint |
| `scratch <content>` | Write a quick note |
| `memory <key> = <value>` | Store in project memory |
| `mode <build\|plan\|spec>` | Switch working mode |
| `agent:spawn <task description>` | Spawn a sub-agent |

### Slash commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/tasks` | List all tasks |
| `/memory` | Show project memory |
| `/checkpoints` | List checkpoints |
| `/scratch` | List scratch notes |
| `/mode` | Show current mode |
| `/status` | Git status + session info |
| `/exit` | End session |

### Managing data

```bash
libercode config --show              # Show current configuration
libercode config --set mode=plan     # Change default mode
libercode config --set provider.model=gpt-4o  # Change model
libercode show --sessions            # List past sessions
libercode show --tasks               # List all tasks
libercode show --memory              # Show project memory
libercode show --summary             # Project summary
```

## Configuration

Global config is stored at `~/.config/libercode/config.yaml`.

Project-level config: create a `.libercoderc` file in your project root:

```yaml
mode: build
provider:
  name: openai
  api_key: sk-...
  model: gpt-4o
  temperature: 0.3
enable_checkpoints: true
checkpoint_interval: 10
```

### Custom providers

```bash
libercode config --set provider.name=openai
libercode config --set provider.api_key=sk-...
libercode config --set provider.model=gpt-4o

libercode config --set provider.name=anthropic
libercode config --set provider.api_key=sk-ant-...
libercode config --set provider.model=claude-sonnet-4-20250514
```

## Modes

| Mode | Description |
|------|-------------|
| **build** | Active development. Can read/edit files, run commands, commit code. |
| **plan** | Read-only analysis. Explores code, researches, produces plans but never writes. |
| **spec** | Spec-following coordinator. Takes a specification, breaks it into tasks, coordinates execution across sub-agents, verifies completion. |

## Architecture

```
libercode/
  cli.py          — Entry point and command dispatch
  config.py       — Configuration, first-run wizard, project-level .libercoderc
  agent.py        — Main agent orchestrator and interactive loop
  modes.py        — System prompts for build/plan/spec modes
  providers/      — LLM providers (builtin HuggingFace, custom OpenAI/Anthropic)
  shell.py        — Shell + file read/write/edit/search operations
  git_utils.py    — Git integration
  memory.py       — Cross-session project memory
  checkpoint.py   — Automatic project snapshots
  task.py         — Task tracking with pause/resume
  scratch.py      — Persistent scratch notes
  stop_condition.py — Verifies job completion
  storage/        — SQLite and file-based persistence
```

## Development

```bash
git clone https://github.com/libercode/libercode
cd libercode
pip install -e .
libercode
```

## License

MIT
