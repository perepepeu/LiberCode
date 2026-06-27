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
Cycles through the available themes: dracula → tokyonight → catppuccin → kanagawa → nord → dracula.

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
Displays instructions for importing a previously exported session.
Lists any `libercode_export_*.json` files found in the current directory.

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
