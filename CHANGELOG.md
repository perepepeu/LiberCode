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
