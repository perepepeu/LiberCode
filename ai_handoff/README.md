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

Current result: 69 passed.

```bash
python -m compileall -q libercode tests
```

Current result: passed.

```bash
ruff check .
```

Current result: passed.

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

- The installed `libercode` entry point now routes argument-based usage to `cli.main()` and starts a TUI with `LiberAgent` attached when no arguments are passed.
- Config persistence is YAML-only through `~/.config/libercode/config.yaml`; provider save/load now round-trips through `LiberConfig`.
- TUI `/memory` has an async handler in `LiberAgent`.
- TUI `/pr` now invokes `gh pr create` through an external command helper instead of the Git helper.
- `ShellExecutor` now blocks path traversal for file read/write/list/search before touching the filesystem.
- The shell sandbox is still denylist-based and uses `shell=True`; this remains a security improvement area.
- `MagicMock/` is ignored test/workspace debris. Do not treat it as product source.

## Suggested Next Repair Sequence

1. Reduce `shell=True` exposure or add explicit confirmation/policy controls for arbitrary shell execution.
2. Split `agent.py` and `tui.py` into smaller command/provider/session modules.
3. Replace broad silent exception handling with debug logging or UI-visible warnings.
4. Run safe lint auto-fixes, then manually resolve remaining lint errors.
5. Add broader integration tests for TUI provider modal flows and session import/export.
