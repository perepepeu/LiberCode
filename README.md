# LiberCode

An open-source terminal coding assistant that feels like a real pair programmer, not just a chat box.

```
pip install libercode
libercode
```

## Features

- **Terminal-native** — runs in your terminal, reads/edits files, executes shell commands, works with Git
- **Cross-session memory** — remembers your project context between sessions
- **Four working modes** — `build`, `plan`, `spec`, and `debug`
- **Automatic checkpoints** — snapshots project state at configurable intervals
- **Undo support** — revert to the last checkpoint with `/undo`
- **Task tracking** — create, update, pause, resume tasks with status tracking
- **Scratch notes** — quick notes that persist across sessions
- **Sub-agent spawning** — spins up helper agents for parallel work (max depth: 2)
- **Stop condition checking** — verifies whether a job is truly done before stopping
- **Built-in free provider** — works out of the box with HuggingFace Inference API (no API key needed)
- **Custom providers** — OpenAI, Anthropic, or any OpenAI-compatible API
- **Project-level config** — `.libercoderc` file for per-project settings
- **Multiline input** — press Enter for new lines, `;;` or Alt+Enter to submit
- **Export/import** — port memory and tasks between projects

## Quick start

```bash
# Install
pip install libercode

# Run (first launch will walk you through setup)
libercode

# Or run in a specific mode
libercode --mode plan
libercode --mode debug
libercode exec "explain the architecture of this project" --mode plan
```

The first run wizard will ask which provider to use. Choose **builtin** for zero-setup
(free HuggingFace models) or **custom** to use your own API key.

Set `HF_TOKEN` in your environment for authenticated HuggingFace requests (optional).

## Usage

### Interactive session

```bash
libercode
libercode --mode plan
libercode --mode spec
libercode --mode debug
```

### One-shot commands

```bash
libercode exec "add error handling to the main function"
libercode exec "list all TODO comments in the codebase" --mode plan
```

### Multiline input

Press **Enter** to add new lines. Submit with **;;** at the end of a line or **Alt+Enter**.

### Tool commands

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
| `mode <build\|plan\|spec\|debug>` | Switch working mode |
| `agent:spawn <task>` | Spawn a sub-agent |

### Slash Commands

Type `/` in the input field to open the command palette. Filter by typing after the `/` (e.g. `/git` shows only git-related commands). Navigate with ↑↓, confirm with Enter, cancel with Esc. You can also click any command with the mouse.

| Command    | Description                          | Handled by |
|------------|--------------------------------------|------------|
| /help      | Show all available commands          | UI         |
| /clear     | Clear current session history        | UI         |
| /session   | Start a new session                  | UI         |
| /theme     | Cycle to next color theme            | UI         |
| /quit      | Exit libercode                       | UI         |
| /undo      | Remove last message pair             | Agent      |
| /context   | Show current system prompt           | Agent      |
| /export    | Export session to JSON file          | Agent      |
| /import    | Show import instructions             | Agent      |
| /model     | Switch AI model (opens picker)       | Agent      |
| /mode      | Switch mode: build/plan/spec/debug   | Agent      |
| /tasks     | List current tasks                   | Agent      |
| /memory    | Show stored memory entries           | Agent      |
| /git       | Show git status --short              | Agent      |
| /stash     | Run git stash                        | Agent      |
| /pop       | Run git stash pop                    | Agent      |

### Keyboard Shortcuts

| Key       | Action         |
|-----------|----------------|
| Ctrl+C    | Quit           |
| Ctrl+T    | Cycle theme    |
| Ctrl+N    | New session    |
| Ctrl+L    | Clear chat     |
| Escape    | Cancel         |
| /         | Open command palette |
| ↑ ↓      | Navigate palette |
| Enter     | Confirm selection |

> **Tip:** The hint bar at the bottom is clickable — you can mouse-click any shortcut label to trigger the action.

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
max_turns: 30
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
| **spec** | Spec-following coordinator. Takes a specification, breaks it into tasks, coordinates execution. |
| **debug** | Diagnostic specialist. Analyzes errors, traces issues, diagnoses problems. |

## Architecture

```
libercode/
  cli.py            — Entry point and command dispatch
  config.py         — Configuration, first-run wizard, project-level .libercoderc
  agent.py          — Main agent orchestrator and command handlers
  tui.py            — Textual TUI with palette, pickers, and clickable hints
  ui.py             — Rich console UI rendering (hero, context bar, help)
  modes.py          — System prompt loader
  prompts/          — System prompts as .md files (build, plan, spec, debug)
  providers/        — LLM providers (builtin HuggingFace, custom OpenAI/Anthropic)
  shell.py          — Shell + file read/write/edit/search with forbidden command list
  git_utils.py      — Git integration with branch validation and stash support
  memory.py         — Cross-session project memory with versioned context
  checkpoint.py     — Automatic project snapshots with size limits
  task.py           — Task tracking with validation
  scratch.py        — Persistent scratch notes
  stop_condition.py — Verifies job completion via LLM
  storage/          — SQLite persistence with WAL mode and indexes
```

## Security

- **Forbidden commands** — destructive shell commands (rm -rf /, dd, format, etc.) are blocked
- **Path traversal protection** — file reads/writes are restricted to the project directory
- **Config file permissions** — API key config files are set to user-only read/write
- **Sub-agent depth limit** — recursive spawning is capped at depth 2

## Development

```bash
git clone https://github.com/perepepeu/LiberCode
cd libercode
pip install -e .
python -m pytest tests/  # Run 57 tests
libercode
```

## License

MIT
