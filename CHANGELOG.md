# Changelog

## [Unreleased]

### Added
- Slash command palette: type `/` to open a filterable OptionList of all
  16 commands. Supports keyboard navigation (↑↓ Enter Esc) and mouse click.
- Model picker: `/model` opens an interactive OptionList to switch AI model.
  Current model is marked with ✓. Clicking updates the header badge live.
- Mode picker: `/mode` opens a picker for build/plan/spec/debug modes.
- Clickable hint bar: all 5 shortcut buttons (^C ^T ^N ^L Esc) respond to
  mouse clicks in addition to keyboard shortcuts.
- Backend command handlers in agent.py:
  - `/undo`    — removes last user+assistant message pair from history
  - `/context` — displays current system prompt in chat
  - `/export`  — saves full session to libercode_export_<timestamp>.json
  - `/import`  — shows import instructions and lists available .json files
  - `/tasks`   — displays task list with done/pending status
  - `/memory`  — displays stored memory entries
  - `/git`     — runs git status --short with syntax coloring
  - `/stash`   — runs git stash and displays output
  - `/pop`     — runs git stash pop and displays output
- Thread-safe write bridge: `write_output()`, `write_error()`,
  `write_info()`, `show_picker_from_thread()`, `update_model_badge_from_thread()`
  allow agent (running in worker thread) to safely write to TUI chat log.
- Agent wired to TUI via `set_agent()` — slash commands now work end-to-end
  through `handle_tui_command` / `handle_tui_message` / `handle_picker_selected`.
- TUI launched with agent connected: `python -m libercode.tui` creates both
  LiberAgent and LibercodeUI, wiring them together on startup.

### Fixed
- Prompt icon `>` alignment: added `height: 1` and `content-align: left middle`
  to `#prompt-icon`, replaced `align-vertical: middle` with `align: left middle`
  on `#prompt-row` for correct vertical centering with the input field.
- Scrollbar appearance: added `scrollbar-gutter: stable` to `#chat-area` and
  CSS rules `ScrollableContainer > .scrollbar` / `.scrollbar--vertical` with
  `width: 1` to force a thin 1-cell-wide scrollbar matching theme border color.
- Slash commands now work in TUI mode: replaced broken `self.ui.query_one()`
  calls with thread-safe `tui.write_output()` pattern via `run_worker()`.
