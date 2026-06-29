# AI Handoff for LiberCode

Last reviewed: 2026-06-28

This folder is a project-specific handoff for AI coding agents. It is not user-facing product documentation. Use it to understand the current architecture, flows, risks, and verification state before making surgical changes.

## Project Snapshot

LiberCode is a Python terminal coding assistant. It has two major interaction layers:

- A Rich/prompt-toolkit CLI flow in `libercode/cli.py` and parts of `libercode/agent.py`.
- A Textual TUI flow in `libercode/tui.py` plus async handlers in `libercode/agent.py`.

The core domain object is `LiberAgent`. It wires configuration, provider access, shell/file tools, git, memory, checkpoints, tasks, scratch notes, sessions, and stop-condition verification.

## Current Verification

Run from the repository root:

```bash
python -m pytest -q
```

Current result: 57 passed.

```bash
python -m compileall -q libercode tests
```

Current result: passed.

```bash
ruff check .
```

Current result: failed with 91 lint findings, 50 auto-fixable. Most are cleanup, but there are meaningful static-quality signals such as an unresolved `BaseProvider` type annotation in `libercode/agent.py`.

## Read These First

1. `libercode/__main__.py`
2. `pyproject.toml`
3. `libercode/cli.py`
4. `libercode/agent.py`
5. `libercode/tui.py`
6. `libercode/config.py`
7. `libercode/shell.py`
8. `libercode/providers/registry.py`
9. `libercode/storage/sqlite_store.py`
10. `tests/`

## Important Gotchas

- The installed `libercode` entry point currently targets `libercode.__main__:main`, but `__main__.py` creates a TUI app without attaching a `LiberAgent`. The direct `libercode/tui.py` script path does attach an agent.
- `cli.py` implements `exec`, `config`, `show`, `wizard`, and `mode`, but the package entry point does not route to `cli.main`.
- Config is split between YAML and TOML paths. Main config uses `~/.config/libercode/config.yaml`; newer provider/config UI code references `config.toml`.
- `tomli_w` and `toml` are used in provider/config paths but are not installed dependencies in the current editable environment.
- TUI `/memory` dispatches to `_tui_cmd_memory`, but no such method exists in `libercode/agent.py`.
- The `/pr` implementation builds a `gh pr create` command and then sends it through a Git helper that prefixes `git`, so it is likely to execute as `git gh pr create ...`.
- The shell sandbox is denylist-based and uses `shell=True`. File path validation is inconsistent across `LiberAgent` and `ShellExecutor`.
- `MagicMock/` is ignored test/workspace debris. Do not treat it as product source.

## Suggested First Repair Sequence

1. Fix startup routing and agent attachment.
2. Normalize config persistence to one format.
3. Fix missing TUI command handlers and command-surface drift.
4. Harden file/shell safety boundaries.
5. Split `agent.py` and `tui.py` into smaller command/provider/session modules.
6. Add integration tests for installed entry point, TUI command dispatch, provider save/load, path traversal, and PR creation.

