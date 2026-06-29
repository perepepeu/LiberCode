# Architecture Notes

## High-Level Shape

LiberCode is organized as a terminal coding assistant with a central agent and multiple surfaces around it.

```text
User input
  -> CLI argparse or Textual TUI
  -> LiberAgent
  -> Provider chat or tool dispatch
  -> Shell, files, git, memory, tasks, checkpoints, scratch notes
  -> SQLite persistence and terminal rendering
```

## Main Modules

| Module | Responsibility | Notes |
| --- | --- | --- |
| `libercode/__main__.py` | Package entry script | Currently starts a TUI without setting an agent. |
| `libercode/cli.py` | Argparse CLI commands | Implements `interactive`, `exec`, `config`, `show`, `wizard`, and `mode`, but is not the installed entry point. |
| `libercode/agent.py` | Agent orchestration | Very large file: prompt context, tool parsing, slash commands, TUI command handlers, provider switching, checkpoint restore, PR/test/lint helpers. |
| `libercode/tui.py` | Textual UI | Very large file: layout, command palette, modals, rendering, input dispatch, provider/model modals. |
| `libercode/config.py` | Config dataclasses and first-run wizard | Main path is YAML at `~/.config/libercode/config.yaml`; some provider methods write TOML elsewhere. |
| `libercode/providers/` | Provider abstraction and concrete LLM adapters | Uses `BaseProvider`, `PROVIDER_REGISTRY`, and provider-specific stream implementations. |
| `libercode/shell.py` | Shell and file operations | Uses `shell=True` and a command denylist. Path containment belongs here but is only partial in the agent. |
| `libercode/git_utils.py` | Git helper | Uses argument lists, which is better than shell strings. Branch validation is regex-only and incomplete. |
| `libercode/storage/sqlite_store.py` | SQLite persistence | Sessions, history, memory, tasks, checkpoints, scratch notes. WAL mode is enabled. |
| `libercode/checkpoint.py` | Snapshot capture | Captures up to 50 Python files with per-file and total-size limits. |
| `libercode/memory.py` | Project memory facade | Stores key/value memory and auto-context entries. |
| `libercode/task.py` | Task facade | Validates status and priority before storing tasks. |
| `libercode/scratch.py` | Scratch note facade | Simple note create/update/search. |
| `libercode/stop_condition.py` | Completion verification | Checks task state, optionally asks the provider for a verdict. |

## Command Surfaces

There are four separate command surfaces. This is a major source of drift.

| Surface | Files | Example | Current Risk |
| --- | --- | --- | --- |
| Argparse CLI | `cli.py` | `libercode exec "..."` | Not wired by installed entry point. |
| Legacy slash commands | `agent.py` `_handle_slash_command` | `/memory`, `/undo` | Different behavior than TUI slash commands. |
| TUI slash commands | `tui.py` dispatch plus `agent.py` async handlers | `/provider`, `/pr`, `/restore` | Missing `_tui_cmd_memory`; `/pr` likely broken. |
| Model tool calls | `agent.py` `_process_tool_call` and `_dispatch_tool` | `file:write`, `<tool name="shell">` | Mode and safety rules differ by path. |

## Persistence Model

The active store is SQLite through `SqliteStore`.

Tables:

- `memory`
- `tasks`
- `checkpoints`
- `scratch_notes`
- `sessions`
- `conversation_history`

The main config is not in SQLite. It is loaded from global YAML plus optional project-level `.libercoderc`.

## Provider Model

`build_provider()` in `libercode/providers/registry.py`:

1. Looks up provider key in `PROVIDER_REGISTRY`.
2. Resolves the API key from explicit argument or environment variable.
3. Instantiates the provider.
4. Calls `validate()`.

Runtime switching happens in both `LiberAgent.swap_provider()` and TUI provider modal code. These paths are not fully aligned with config persistence.

## Mode Model

The intended modes are `build`, `plan`, `spec`, and `debug`.

Current drift:

- CLI choices include `debug`.
- TUI `VALID_MODES` includes `debug`.
- Legacy model tool command `mode <...>` only allows `build`, `plan`, and `spec`.
- First-run wizard only offers `build`, `plan`, and `spec`.
- Some renderer color maps omit `debug`.

