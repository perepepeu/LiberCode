# Detailed Flows

## Installed Startup Flow

Current installed console script:

```text
pyproject.toml
  -> libercode = "libercode.__main__:main"
  -> libercode/__main__.py main()
  -> if arguments are present: libercode.cli.main()
  -> else: ensure_config()
  -> LiberAgent(cfg)
  -> LibercodeUI(...)
  -> app.set_agent(agent)
  -> app.run()
```

The argparse CLI path:

```text
libercode/cli.py main()
  -> parse args
  -> command handler
  -> ensure_config()
  -> LiberAgent(cfg)
  -> run_interactive() or run_one_shot() or config/show action
```

## TUI Message Flow

```text
LibercodeUI.on_input_submitted()
  -> if slash command: dispatch command
  -> else render user message
  -> run worker
  -> agent.handle_tui_message(text, tui)
  -> build conversation history and system prompt
  -> provider.chat_stream(...)
  -> render chunks
  -> process tool calls when present
  -> persist history and update status
```

Key files:

- `libercode/tui.py`
- `libercode/agent.py`
- `libercode/providers/*`
- `libercode/storage/sqlite_store.py`

Known gaps:

- Many broad `except Exception: pass` blocks in the TUI can hide failures.
- Some async worker paths update UI and provider state without a single shared command contract.

## TUI Slash Command Flow

```text
User enters "/command args"
  -> LibercodeUI._dispatch_command_with_args()
  -> agent.handle_tui_command(cmd, args, tui)
  -> one of _tui_cmd_* handlers
```

Current command list lives in `libercode/tui.py` as `COMMANDS`.

Important command notes:

- `/memory`: has an async handler and focused dispatch test.
- `/provider`: opens a modal for empty/list/setup; direct switching uses `_tui_provider_direct_switch`.
- `/config`: reads and writes the same YAML config loaded by `LiberConfig`.
- `/pr`: uses a dedicated external command helper for `gh pr create`.
- `/restore` and legacy `/undo`: share path-contained snapshot restore logic.

## Legacy Interactive Slash Command Flow

```text
agent.run_interactive()
  -> prompt-toolkit input
  -> if input starts with "/": _handle_slash_command()
  -> else provider chat flow
```

This surface supports a smaller and different command set than the TUI. It handles `/memory`, `/tasks`, `/checkpoints`, `/scratch`, `/status`, `/undo`, `/context`, `/export`, `/import`, `/exit`, and `/quit`.

Known drift:

- Legacy `/mode` only prints the current mode, while TUI `/mode` changes modes.

## Model Tool Call Flow

The model can request tools in two forms.

XML-like form:

```text
<tool name="shell">...</tool>
<tool name="file:read">...</tool>
<tool name="file:write">path
content</tool>
```

Legacy line form:

```text
!command
file:read path
file:write path content
file:edit path ||| old ||| new
task:create title ||| description
git status
mode build
agent:spawn task
```

Flow:

```text
agent._process_tool_call(response)
  -> parse first matching tool call
  -> _dispatch_tool(...) or direct branch
  -> shell/file/git/task/checkpoint/memory/scratch/subagent method
```

Mode restrictions:

- `_exec_shell()` blocks plan mode.
- `_edit_file()` blocks plan mode.
- `_write_file()` blocks plan mode.
- Tool `mode` accepts every mode in `VALID_MODES`.

## File and Shell Flow

Shell:

```text
agent._exec_shell(cmd)
  -> ShellExecutor.run(cmd)
  -> is_forbidden(cmd)
  -> subprocess.run(..., shell=True)
```

Files:

```text
agent._read_file(path)
  -> ShellExecutor.read_file(path)
  -> ShellExecutor validates path containment before reading
  -> agent performs a second containment check
```

```text
agent._write_file(path, content)
  -> agent blocks plan mode
  -> agent validates path
  -> compute diff
  -> optional TUI confirmation
  -> write file
  -> memory auto-store
  -> optional checkpoint
```

Security note: file containment is enforced in `ShellExecutor`; arbitrary shell commands still use `shell=True` with a denylist and need further policy work.

## Config Flow

Main load:

```text
LiberConfig.load()
  -> read ~/.config/libercode/config.yaml if present
  -> overlay project .libercoderc if present
  -> resolve data_dir
```

CLI config:

```text
cli.py cmd_config()
  -> LiberConfig.load()
  -> mutate cfg
  -> cfg.save_global()
  -> writes YAML
```

TUI provider/config paths:

```text
agent._tui_cmd_config()
  -> path ~/.config/libercode/config.yaml
  -> YAML parsing
```

```text
LiberConfig.save_provider_config()
  -> update provider and providers entries
  -> save ~/.config/libercode/config.yaml
```

## Provider Flow

```text
agent._init_provider()
  -> build_provider(
       name=config.provider.name,
       model=config.provider.model,
       api_key=config.provider.api_key,
       api_base=config.provider.api_base,
       max_tokens=config.provider.max_tokens,
       temperature=config.provider.temperature
     )
  -> provider.validate()
  -> fallback to BuiltinProvider on ProviderError
```

Runtime switching:

```text
agent.swap_provider()
  -> build_provider(...)
  -> assign provider
  -> stop_checker.set_provider()
  -> save provider config
```

TUI also has provider switching logic in `LibercodeUI`, including API key modal and model modal. Consolidate these paths if possible.

## Persistence Flow

```text
LiberAgent.__init__()
  -> data_dir
  -> SqliteStore(data_dir/libercode.db)
  -> ProjectMemory(store)
  -> TaskTracker(store)
  -> ScratchNotes(store)
  -> Checkpointer(store, project_root, git)
```

Session start:

```text
agent._init_session(project_root)
  -> store.session_get_active(project_root)
  -> resume active session if present
  -> else store.session_start(project_root, mode)
```

History:

```text
store.history_append(session_id, role, content, mode)
store.history_get(session_id, limit)
```

## Checkpoint Flow

```text
Checkpointer.save(summary)
  -> _take_snapshot()
  -> _git_snapshot()
  -> store.checkpoint_save(...)
```

Snapshot limits:

- Up to 50 `*.py` files.
- Per-file limit: 50 KB.
- Total limit: 2 MB.

Restore paths:

- TUI `/restore` and legacy `/undo` both use `LiberAgent._restore_snapshot_files()`.
- Restore blocks paths that escape `self.shell.workdir`.

## Test and Lint Flow

TUI `/test`:

```text
_detect_project_type()
  -> command map
  -> _run_cmd(...)
  -> if failure keywords are present, ask provider to summarize
```

TUI `/lint`:

```text
_detect_project_type()
  -> command map
  -> _run_cmd(...)
  -> if output is non-empty, ask provider for fixes
```

For this repo:

- Test command: `python -m pytest --tb=short -q`
- Lint command: `ruff check .`
