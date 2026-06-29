# Testing and Verification Guide

## Baseline Commands

Run from the repository root.

```bash
python -m pytest -q
```

Expected current result:

```text
69 passed
```

```bash
python -m compileall -q libercode tests
```

Expected current result: no output and exit code 0.

```bash
ruff check .
```

Expected current result: no output other than `All checks passed!`.

## Current Test Coverage Shape

| Test File | Covers | Notable Gaps |
| --- | --- | --- |
| `tests/test_shell.py` | Basic shell execution, timeout, read/write/edit/list, simple forbidden command patterns, direct path containment | Shell injection policy and richer command authorization. |
| `tests/test_agent.py` | Tool-call parsing, path traversal checks, plan-mode write blocking, safe restore helper, message truncation | Broader real-provider and real-session behavior. |
| `tests/test_slash_commands.py` | Legacy slash commands, TUI `/memory`, TUI `/pr` external `gh` invocation | TUI provider modal flows, `/restore` end-to-end rendering. |
| `tests/test_checkpoint.py` | Snapshot save/list shape, file limits, git diff snapshot | Restore behavior, non-Python files, path validation, corrupted snapshot data. |
| `tests/test_git_utils.py` | Non-repo behavior, branch regex checks, `git check-ref-format` validation | More branch edge cases and worktree scenarios. |
| `tests/test_providers.py` | Retry helper behavior | Provider payload shapes, streaming parsing, provider config save/load. |
| `tests/test_config.py` | Provider YAML save/load round-trip | Project-level `.libercoderc` overlay edge cases. |
| `tests/test_entrypoint.py` | Installed entry point routing and agent-backed TUI startup | Console script invocation in a packaged environment. |

## High-Value Tests to Add

1. CLI tests:
   - `libercode exec` reaches `LiberAgent.run_one_shot`.
   - `libercode config --show` reads YAML.
   - `libercode show --summary` uses the store safely.

2. Config/provider tests:
   - Saved provider keys are masked in UI output.
   - Project-level `.libercoderc` overlays provider fields without corrupting saved global provider entries.

3. TUI command dispatch tests:
   - Every command in `tui.py` `COMMANDS` has a handler or UI action.
   - Provider modal setup flow saves and reloads API keys.

4. File safety tests:
   - Symlink/junction escape behavior is blocked where supported.

5. Git/PR tests:
   - PR body quoting preserves spaces, quotes, and newlines.

6. Checkpoint tests:
   - Restore handles malformed snapshots gracefully.

## Lint Maintenance Strategy

1. Run `ruff check .` before commits that touch Python code.
2. Use `ruff check . --fix` for safe mechanical cleanup when the diff is reviewed.
3. Re-run tests after any lint cleanup.
4. Add lint to CI to keep the baseline clean.

## Manual Smoke Checklist

After startup/config fixes, verify:

- `libercode --version`
- `libercode`
- `libercode exec "say hello"`
- `libercode config --show`
- TUI `/help`
- TUI `/memory`
- TUI `/mode debug`
- TUI `/test`
- TUI `/lint`
- TUI provider picker opens
