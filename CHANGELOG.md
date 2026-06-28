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

### Fixed
- Eliminate chat response delay by streaming provider chunks in a thread pool
  via asyncio.Queue, keeping the event loop responsive between chunks.
- Command palette no longer steals keyboard focus from the Input field —
  OptionList is purely visual, navigation handled in on_key() with event.stop().
- Picker (model/mode selection) also keeps focus on Input, with keyboard nav
  handled in on_key().

### Added
- Tab key cycles agent mode (build → plan → spec → debug → build) with
  a mode badge in the header bar and a "⇄ Mode → ..." message in chat log.
- AI responses rendered with full Markdown and syntax-highlighted code blocks
  after streaming completes (bold, inline code, fenced code with line numbers).
- Mode pill next to input shows active mode (build/plan/spec/debug) with
  distinct colors that update instantly on Tab and /mode.
- `/sessions` command lists past sessions and `/sessions <id>` restores
  history into the current chat.
- `/import` now fully restores messages, memory, tasks, and mode from
  exported JSON files (not just instructions).
- Improved language detection for syntax-highlighted code blocks with
  fallback panel for unknown languages and horizontal Rule divider after
  each AI response.
- Real-time status bar showing mode · provider · session · tokens · tasks · git branch.
- `/checkpoint` saves manual project snapshots; `/restore` lists and restores
  file snapshots from checkpoints with path traversal protection.
- `/scratch` command exposed in TUI for viewing scratch notes.
- Tool call results (shell, file, git, task) rendered as styled bordered
  panels with icons and colors for instant visual feedback.
