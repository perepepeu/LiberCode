# Risk Register

This file lists current risks first, then recently fixed risks so future agents do not rediscover stale problems.

## Current Risks

| Priority | Area | Evidence | Why It Matters | Recommended Fix |
| --- | --- | --- | --- | --- |
| P1 | Shell safety | `libercode/shell.py` uses `shell=True` for arbitrary commands | File containment is stronger now, but shell execution still relies on a denylist and can miss dangerous variants. | Prefer argument-list execution for known commands. For arbitrary shell mode, require explicit user confirmation and document policy boundaries. |
| P2 | Giant modules | `libercode/agent.py`, `libercode/tui.py` | These files still mix orchestration, command handling, provider setup, rendering, and workflow logic. | Extract command handlers, provider management, TUI modals, shell/file tools, and session operations into smaller modules. |
| P2 | Lint debt | `ruff check .` | Lint debt creates noise and can hide real defects. | Run safe auto-fixes, then manually fix remaining issues. Add lint to CI once baseline is clean. |
| P2 | Silent exceptions | Many `except Exception: pass` in `agent.py`, `tui.py`, `checkpoint.py`, and `stop_condition.py` | Failures can disappear, especially in provider switching, TUI UI updates, and checkpoint capture. | Log debug details behind a verbose flag or route warnings to the UI/status area. |
| P3 | Workspace debris | `MagicMock/` ignored by `.gitignore` | This is not product code, but it can confuse agents scanning the filesystem. | Keep ignored, or clean periodically outside product changes. |

## Recently Fixed

| Area | Fix |
| --- | --- |
| Installed startup | `libercode.__main__` now delegates to CLI when arguments are present and starts an agent-backed TUI otherwise. |
| CLI contract | `--version`, `exec`, `config`, `show`, and other argument-based commands are reachable through the installed entry point. |
| Config persistence | Provider settings now save and load through YAML at `~/.config/libercode/config.yaml`; TOML writer dependencies are no longer needed for config. |
| Missing TUI command | `/memory` now has `_tui_cmd_memory` coverage. |
| PR creation | `/pr` now invokes `gh pr create` through an external command helper instead of the Git helper. |
| File containment | `ShellExecutor` blocks traversal for read/write/list/search before touching the filesystem. |
| Mode drift | `VALID_MODES` is centralized and includes `debug` across CLI, TUI, wizard, renderer help, and tool-call mode switching. |
| Checkpoint restore asymmetry | TUI `/restore` and legacy `/undo` share the same path-contained restore helper. |
| Branch validation | Branch creation/checkout uses regex prefiltering plus `git check-ref-format --branch`. |

