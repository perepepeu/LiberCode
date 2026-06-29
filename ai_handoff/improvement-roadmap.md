# Improvement Roadmap

This roadmap is ordered for low rework and high confidence.

## Completed: Startup, Config, Commands, and Core Safety

These items were addressed after the initial audit:

- Installed entry point routes intentionally and starts an agent-backed TUI by default.
- Provider and UI config persistence use YAML through `LiberConfig`.
- `VALID_MODES` is centralized and includes `debug` everywhere relevant.
- TUI `/memory` has an async handler.
- `ShellExecutor` blocks file path traversal before read/write/list/search.
- Plan mode blocks file writes.
- `/undo` and `/restore` share safe snapshot restore logic.
- `/pr` uses `gh pr create` through an external command helper.
- Branch validation uses `git check-ref-format --branch`.
- `ruff check .` passes.

## Phase 1: Split Large Files

Goal: reduce blast radius.

Suggested extractions from `agent.py`:

- `commands/legacy.py`
- `commands/tui.py`
- `tools/file_tools.py`
- `tools/shell_tools.py`
- `providers/runtime.py`
- `sessions.py`
- `checkpoints/restore.py`

Suggested extractions from `tui.py`:

- `tui/commands.py`
- `tui/modals/provider.py`
- `tui/modals/model.py`
- `tui/rendering.py`
- `tui/themes.py`

Acceptance:

- Existing tests still pass.
- New modules have focused unit tests.
- `agent.py` and `tui.py` stop being the default home for every new behavior.

## Phase 2: Improve Observability

Goal: failures should be visible without overwhelming users.

Tasks:

- Replace broad silent exceptions with debug logging or UI warnings.
- Add a verbose mode for provider/config/TUI failures.
- Store diagnostic context for failed commands and provider switches.

Acceptance:

- Provider switch failure explains whether it was validation, missing API key, config save, or model fetch.
- TUI worker exceptions are visible in a controlled way.

## Phase 3: Keep Lint in CI

Goal: keep the clean static-check baseline from regressing.

Tasks:

- Add a lint command to CI.
- Keep using `ruff check .` before Python commits.
- Review any `ruff --fix` diff before committing.

Acceptance:

- `ruff check .` exits 0.
- CI fails when lint regresses.

## Phase 4: Tighten Shell Policy

Goal: reduce risk from arbitrary shell commands.

Tasks:

- Prefer argument-list execution for known commands.
- Add user confirmation or policy gates for arbitrary shell execution.
- Document allowed, blocked, and confirmation-required command classes.

Acceptance:

- Shell execution behavior is predictable and tested beyond substring denylisting.
