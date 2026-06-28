# Libercode Command Reference

## Using Commands

Type `/` in the input field to open the command palette.
Filter by typing after the `/` (e.g. `/git` shows only git-related commands).
Navigate with ↑↓, confirm with Enter, cancel with Esc.
You can also click any command with the mouse.

## Command Details

### /help
Prints the full command reference table to the chat.

### /clear
Clears all messages from the chat log. Does not reset history sent to the model.

### /session
Starts a new session: clears the chat AND resets conversation history.

### /theme
Cycles through the available themes: dracula → tokyonight → catppuccin → kanagawa → nord → gruvbox → solarized → onedark → rosepine → dracula.

### /quit
Exits libercode immediately.

### /undo
Removes the last user message and the last assistant response from the
conversation history. Useful when the model gave a bad answer and you want
to retry without it influencing future responses.

### /context
Displays the current system prompt being sent to the model with every request.

### /export
Saves the current session (messages, memory, tasks, model, mode) to a JSON file
named `libercode_export_YYYYMMDD_HHMMSS.json` in the current working directory.

### /import
Without arguments: displays a list of available `libercode_export_*.json` files in the
current directory with their sizes.
With argument: imports messages, memory, and tasks from the specified JSON file.
Example: `/import libercode_export_20260627_120000.json`

### /model [name]
Without arguments: opens an interactive picker showing all available models.
The current model is marked with ✓. Click or press Enter to switch.
With argument: switches directly if the name matches (partial match ok).
Example: `/model qwen` switches to the first model containing "qwen".

### /mode [mode]
Without arguments: opens a picker for build / plan / spec / debug.
With argument: switches directly.
- **build** — default coding mode
- **plan**  — plan before coding, asks clarifying questions
- **spec**  — generates a spec document before any code
- **debug** — focuses on error analysis and fixes

### /tasks
Shows the current task list with ✓ for completed and ○ for pending tasks.

### /memory
Shows all stored memory entries (key: value pairs).

### /git
Runs `git status --short` and displays the output with color coding:
- Modified files → warning color
- Added files    → success color
- Deleted files  → error color
- Untracked      → muted color

### /stash
Runs `git stash` and displays the output.

### /pop
Runs `git stash pop` and displays the output.

### /checkpoint [summary]
Saves a manual project checkpoint. The snapshot captures the current state of
tracked files. Optionally provide a summary string.
Example: `/checkpoint before refactor`

### /restore [checkpoint_id]
Without arguments: lists all saved checkpoints with their IDs, creation dates,
file counts, and summaries.
With argument: restores all files captured in the specified checkpoint, writing
them back to disk. Path traversal is blocked for safety.
Example: `/restore cp_abc123`

### /scratch
Shows all scratch notes stored in the project, with IDs, titles, and content previews.

### /sessions [id]
Without arguments: lists all past sessions for the current project with IDs, modes,
dates, and summaries. The current session is marked with ▶.
With argument: restores the specified session by loading its conversation history
into the current chat log. Use `/sessions <id>` to resume where you left off.

### /search <term>
Searches the full conversation history for the given term. Displays matching
messages with the search term highlighted in yellow. Shows role (user/assistant)
and timestamp for each match. Example: `/search error handling`

### /pr [branch]
Creates a GitHub pull request for the current branch. Without arguments, generates
an AI-powered PR title and description based on the git log, then pushes the branch.
With argument: uses the given base branch. Requires `gh` CLI to be installed.

### /review
Sends the current uncommitted git diff to the AI for automated code review.
The AI analyzes the diff for bugs, code quality issues, security concerns,
and highlights what looks good.

### /test [command]
Runs the project's test suite with auto-detected runner:
- Python → pytest
- Node → jest
- Rust → cargo test
- Go → go test ./...

With argument: runs the custom command instead (e.g. `/test python -m unittest`).
If failures are detected, the AI summarizes them and suggests fixes.

### /lint [command]
Runs the project's linter with auto-detected runner:
- Python → ruff
- Node → eslint
- Rust → cargo clippy

With argument: runs the custom command instead (e.g. `/lint mypy .`).
If issues are found, the AI explains each one and shows corrected code.

### /config [key = value]
Without arguments: displays the current configuration file with syntax highlighting.
With key=value: sets a config value (supports nested keys like `provider.model`).
Example: `/config provider.model = deepseek-coder-v2`
