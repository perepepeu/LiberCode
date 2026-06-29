# Testing and Verification Guide

## Baseline Commands

Run from the repository root.

```bash
python -m pytest -q
```

Expected current result:

```text
57 passed
```

```bash
python -m compileall -q libercode tests
```

Expected current result: no output and exit code 0.

```bash
ruff check .
```

Expected current result: failing lint until cleanup is done.

## Current Test Coverage Shape

| Test File | Covers | Notable Gaps |
| --- | --- | --- |
| `tests/test_shell.py` | Basic shell execution, timeout, read/write/edit/list, simple forbidden command patterns | Path traversal in `ShellExecutor`, shell injection policy, direct file containment. |
| `tests/test_agent.py` | Tool-call parsing, basic path traversal checks through mocked shell, message truncation | Real file path behavior, plan-mode write blocking, TUI command handlers. |
| `tests/test_slash_commands.py` | Legacy slash commands using mocked agent dependencies | TUI slash commands, missing `_tui_cmd_memory`, `/provider`, `/pr`, `/restore`. |
| `tests/test_checkpoint.py` | Snapshot save/list shape, file limits, git diff snapshot | Restore behavior, non-Python files, path validation, corrupted snapshot data. |
| `tests/test_git_utils.py` | Non-repo behavior, simple branch regex checks | Validating real Git ref rules inside an initialized repo. |
| `tests/test_providers.py` | Retry helper behavior | Provider payload shapes, streaming parsing, provider config save/load. |

## High-Value Tests to Add

1. Entry point smoke tests:
   - `python -m libercode --version` or equivalent console entry simulation.
   - Installed script target resolves to the intended main.
   - Default startup attaches a `LiberAgent` when TUI is used.

2. CLI tests:
   - `libercode exec` reaches `LiberAgent.run_one_shot`.
   - `libercode config --show` reads YAML.
   - `libercode show --summary` uses the store safely.

3. Config/provider tests:
   - Provider switch persists to the same format that `LiberConfig.load()` reads.
   - Missing optional TOML packages do not silently drop provider settings.
   - Saved provider keys are masked in UI output.

4. TUI command dispatch tests:
   - Every command in `tui.py` `COMMANDS` has a handler or UI action.
   - `/memory` does not raise.
   - `/mode debug` works consistently.

5. File safety tests:
   - Direct `ShellExecutor.read_file("../outside.txt")` is blocked.
   - Direct `ShellExecutor.write_file("../outside.txt", ...)` is blocked.
   - Symlink/junction escape behavior is blocked where supported.

6. Git/PR tests:
   - Branch validation rejects invalid refs inside a real temporary Git repo.
   - `/pr` invokes `gh` without prefixing `git`.
   - PR body quoting preserves spaces, quotes, and newlines.

7. Checkpoint tests:
   - Shared restore function blocks traversal paths.
   - Restore handles malformed snapshots gracefully.

## Lint Cleanup Strategy

1. Run `ruff check . --fix` after reviewing the diff.
2. Manually handle unresolved issues:
   - `F821` unresolved names.
   - `F811` redefinitions caused by duplicated imports.
   - `E701` multiple statements on one line.
   - `F841` unused locals that may signal incomplete logic.
3. Re-run tests after every batch.
4. Add lint to CI only after the baseline is clean.

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

