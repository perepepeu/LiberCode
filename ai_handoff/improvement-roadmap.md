# Improvement Roadmap

This roadmap is ordered for low rework and high confidence.

## Phase 1: Make Startup Honest

Goal: the documented commands should reach the code that implements them.

Tasks:

- Change the package entry point or `libercode/__main__.py` so installed `libercode` routes intentionally.
- If default behavior is TUI, create `LiberAgent(cfg)` and call `app.set_agent(agent)`.
- If argparse is the main entry, delegate to `libercode.cli.main()`.
- Add smoke tests for entry-point routing.

Acceptance:

- `libercode --version` prints the package version.
- `libercode exec "..."` calls the one-shot path.
- Default `libercode` starts an agent-connected UI.

## Phase 2: Unify Configuration

Goal: there is one source of truth for user config.

Tasks:

- Pick YAML or TOML.
- Make load/save/provider-switch paths use the same file.
- Remove undeclared dependencies or add them to `pyproject.toml`.
- Stop swallowing provider config save failures silently.

Acceptance:

- Switching provider persists and survives process restart.
- `config --show`, TUI `/config`, and provider modal show the same state.
- Tests cover missing optional config writer packages.

## Phase 3: Align Commands

Goal: one command registry, multiple renderers.

Tasks:

- Define commands and metadata once.
- Implement shared command services for memory/tasks/checkpoints/mode/provider.
- Make CLI, legacy interactive, and TUI call the same behavior where possible.
- Implement missing `_tui_cmd_memory`.

Acceptance:

- Every advertised command has a tested handler.
- `debug` mode works across CLI, TUI, wizard, model tools, and UI colors.

## Phase 4: Harden Tool Safety

Goal: security boundaries are enforced in the lowest practical layer.

Tasks:

- Add path containment checks inside `ShellExecutor` file methods.
- Replace string-prefix checks with `Path.resolve().is_relative_to(...)`.
- Consider a safer command execution API for non-arbitrary commands.
- Add explicit confirmation or policy controls for arbitrary shell execution.

Acceptance:

- Direct `ShellExecutor` traversal tests fail closed.
- Plan mode cannot write files through any tool path unless explicitly designed.
- Shell command policy is documented and tested.

## Phase 5: Split Large Files

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

## Phase 6: Improve Observability

Goal: failures should be visible without overwhelming users.

Tasks:

- Replace broad silent exceptions with debug logging or UI warnings.
- Add a verbose mode for provider/config/TUI failures.
- Store diagnostic context for failed commands and provider switches.

Acceptance:

- Provider switch failure explains whether it was validation, missing API key, config save, or model fetch.
- TUI worker exceptions are visible in a controlled way.

