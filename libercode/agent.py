import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import tiktoken
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich import box
from prompt_toolkit import PromptSession as PTSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.input import create_input

from libercode.config import LiberConfig, VALID_MODES as CONFIG_VALID_MODES
from libercode.providers import BuiltinProvider, build_provider
from libercode.providers.base import BaseProvider, ProviderError
from libercode.storage.sqlite_store import SqliteStore
from libercode.shell import ShellExecutor
from libercode.git_utils import GitHelper
from libercode.memory import ProjectMemory
from libercode.checkpoint import Checkpointer
from libercode.task import TaskTracker
from libercode.scratch import ScratchNotes
from libercode.stop_condition import StopConditionChecker
from libercode.modes import get_system_prompt
from libercode.ui import Renderer


class LiberAgent:
    def __init__(self, config: LiberConfig):
        self.config = config
        self.console = Console()
        self.ui = Renderer(self.console)

        data_dir = Path(config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        project_root = Path.cwd().resolve()
        db_path = str(data_dir / "libercode.db")

        self.store = SqliteStore(db_path)
        self.shell = ShellExecutor(workdir=str(project_root))
        self.git = GitHelper(workdir=str(project_root))
        self.memory = ProjectMemory(self.store)
        self.checkpointer = Checkpointer(self.store, str(project_root), self.git)
        self.tasks = TaskTracker(self.store)
        self.scratch = ScratchNotes(self.store)
        self.stop_checker = StopConditionChecker(
            self.store, self.shell, self.git, self.memory
        )

        self.mode = config.mode
        self.provider = self._init_provider()
        self.stop_checker.set_provider(self.provider)
        self.session_id = self._init_session(project_root)
        self.turn_count = 0
        self.total_tokens = 0
        self._spawn_depth = 0
        self.tui_ui = None
        try:
            self._enc = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def _init_provider(self) -> BaseProvider:
        pc = self.config.provider
        try:
            return build_provider(
                name=pc.name,
                model=pc.model or "",
                api_key=pc.api_key or "",
                api_base=pc.api_base or "",
                max_tokens=getattr(pc, "max_tokens", 4096),
                temperature=getattr(pc, "temperature", 0.2),
            )
        except ProviderError as e:
            self.console.print(f"[dim yellow]Provider warning: {e}[/]")
            self.console.print("[dim]Falling back to builtin provider.[/]")
            return BuiltinProvider(
                model=self.config.builtin_model,
                api_base=self.config.builtin_api_base,
            )

    @property
    def available_models(self) -> list[str]:
        try:
            return self.provider.list_models()
        except Exception:
            return getattr(self.provider, "available_models", [])

    def swap_provider(
        self,
        name:    str,
        model:   str = "",
        api_key: str = "",
    ) -> None:
        from libercode.providers.registry import build_provider, PROVIDER_REGISTRY
        cls, _ = PROVIDER_REGISTRY.get(name, (None, ""))
        resolved_model = model or (cls.default_model if cls else "")

        new_provider = build_provider(
            name=name,
            model=resolved_model,
            api_key=api_key,
        )
        self.provider = new_provider
        self.stop_checker.set_provider(new_provider)

        try:
            self.config.save_provider_config(
                provider_name=name,
                api_key=api_key,
                model=resolved_model,
                set_active=True,
            )
        except Exception:
            pass

    def _init_session(self, project_root: Path) -> int:
        active = self.store.session_get_active(str(project_root))
        if active:
            self.console.print(
                f"[dim]Resuming session #{active['id']} ({active['mode']})[/]"
            )
            self.mode = active["mode"]
            return active["id"]
        sid = self.store.session_start(str(project_root), self.mode)
        self.console.print(f"[dim]New session #{sid} started ({self.mode} mode)[/]")
        return sid

    def _build_context(self) -> dict:
        ctx = {"mode": self.mode}

        git_summary = self.git.summary()
        if git_summary:
            ctx["git_summary"] = git_summary

        pending = self.tasks.pending_tasks()
        if pending:
            ctx["pending_tasks"] = pending[:5]

        memory_items = self.memory.all() if self.config.enable_memory else []
        if memory_items:
            ctx["memory"] = memory_items[:10]

        return ctx

    def _system_prompt(self) -> str:
        ctx = self._build_context()
        base = get_system_prompt(self.mode, ctx)

        extras = []
        if self.git.is_repo():
            extras.append(f"\n## Git Status\n{ctx.get('git_summary', '')}")

        pending = ctx.get("pending_tasks", [])
        if pending:
            extras.append("\n## Pending Tasks")
            for t in pending[:5]:
                extras.append(f"- [{t['status']}] #{t['id']} {t['title']}")

        memories = ctx.get("memory", [])
        if memories:
            extras.append("\n## Project Memory (recent)")
            for m in memories[:5]:
                extras.append(f"- {m['key']}: {m.get('value', '')[:150]}")

        return base + "\n" + "\n".join(extras)

    def _build_messages(self, user_input: str, history: list) -> list:
        messages = []
        limit = 20
        if len(history) > limit:
            dropped = len(history) - limit
            messages.append({
                "role": "system",
                "content": f"[Note: {dropped} earlier messages were truncated to fit context window.]"
            })
        for h in history[-limit:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_input})
        return messages

    def _process_tool_call(self, text: str) -> Optional[str]:
        import re
        tool_pattern = re.compile(r"<tool\s+name=\"([^\"]+)\"[^>]*>(.*?)</tool>", re.DOTALL)
        for match in tool_pattern.finditer(text):
            tool_name = match.group(1).strip()
            tool_body = match.group(2).strip()
            return self._dispatch_tool(tool_name, tool_body)

        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                continue

            if stripped.startswith("!") and len(stripped) > 1:
                cmd = stripped[1:].strip()
                return self._exec_shell(cmd)

            if stripped.startswith("file:read "):
                path = stripped[len("file:read ") :].strip().strip("`'\"")
                return self._read_file(path)

            if stripped.startswith("file:write "):
                rest = "\n".join(lines[i + 1 :])
                restripped = stripped[len("file:write ") :].strip()
                path_end = restripped.find(" ")
                if path_end == -1:
                    path = restripped.strip("`'\"")
                    content = rest
                else:
                    path = restripped[:path_end].strip("`'\"")
                    content = restripped[path_end + 1 :] + "\n" + rest
                content = content.strip()
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                return self._write_file(path, content)

            if stripped.startswith("file:edit "):
                parts = stripped[len("file:edit ") :].strip().split(" ||| ")
                if len(parts) == 3:
                    return self._edit_file(
                        parts[0].strip(), parts[1].strip(), parts[2].strip()
                    )

            if stripped.startswith("task:create "):
                parts = stripped[len("task:create ") :].strip().split(" ||| ")
                title = parts[0]
                desc = parts[1] if len(parts) > 1 else ""
                return self._task_create(title, desc)

            if stripped.startswith("task:update "):
                parts = stripped[len("task:update ") :].strip().split(" ", 2)
                if len(parts) >= 2:
                    tid = int(parts[0])
                    kwargs = {}
                    if len(parts) >= 3:
                        for kv in parts[2].split(","):
                            if "=" in kv:
                                k, v = kv.split("=", 1)
                                kwargs[k.strip()] = v.strip()
                    return self._task_update(tid, **kwargs)

            if stripped.startswith("checkpoint"):
                summary = stripped[len("checkpoint") :].strip() or "manual checkpoint"
                return self._save_checkpoint(summary)

            if stripped.startswith("scratch "):
                content = stripped[len("scratch ") :].strip()
                return self._scratch_note(content)

            if stripped.startswith("memory "):
                content = stripped[len("memory ") :].strip()
                if "=" in content:
                    key, val = content.split("=", 1)
                    self.memory.remember(key.strip(), val.strip())
                    return f"[Memory] Stored: {key.strip()}"
                return "[Memory] Key not found. Use `memory key = value`"

            if stripped.startswith("git "):
                cmd = stripped[len("git ") :].strip()
                return self._exec_shell(f"git {cmd}")

            if stripped.startswith("mode "):
                new_mode = stripped[len("mode ") :].strip()
                if new_mode in CONFIG_VALID_MODES:
                    self.mode = new_mode
                    self.store.session_update_mode(self.session_id, new_mode)
                    return None
                return f"[Mode] Invalid mode. Use {', '.join(CONFIG_VALID_MODES)}."

            if stripped.startswith("agent:spawn "):
                task_desc = stripped[len("agent:spawn ") :].strip()
                return self._spawn_subagent(task_desc)

        return None

    def _dispatch_tool(self, name: str, body: str) -> Optional[str]:
        if name == "shell":
            return self._exec_shell(body)
        if name == "file:read":
            return self._read_file(body.strip().strip("`'\""))
        if name == "file:write":
            parts = body.split("\n", 1)
            path = parts[0].strip().strip("`'\"")
            content = parts[1].strip() if len(parts) > 1 else ""
            return self._write_file(path, content)
        if name == "file:edit":
            parts = body.split("|||")
            if len(parts) == 3:
                return self._edit_file(
                    parts[0].strip(), parts[1].strip(), parts[2].strip()
                )
            return "[Error] file:edit requires <tool name=\"file:edit\">path ||| old ||| new</tool>"
        if name == "task:create":
            parts = body.split("|||", 1)
            title = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            return self._task_create(title, desc)
        if name == "task:update":
            parts = body.strip().split(" ", 2)
            if len(parts) >= 2:
                tid = int(parts[0])
                kwargs = {}
                if len(parts) >= 3:
                    for kv in parts[2].split(","):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            kwargs[k.strip()] = v.strip()
                return self._task_update(tid, **kwargs)
        if name == "checkpoint":
            return self._save_checkpoint(body.strip() or "manual checkpoint")
        if name == "scratch":
            return self._scratch_note(body.strip())
        if name == "memory":
            content = body.strip()
            if "=" in content:
                key, val = content.split("=", 1)
                self.memory.remember(key.strip(), val.strip())
                return f"[Memory] Stored: {key.strip()}"
            return "[Memory] Key not found. Use `memory key = value`"
        if name == "git":
            return self._exec_shell(f"git {body.strip()}")
        if name == "mode":
            new_mode = body.strip()
            if new_mode in CONFIG_VALID_MODES:
                self.mode = new_mode
                self.store.session_update_mode(self.session_id, new_mode)
                return None
            return f"[Mode] Invalid mode. Use {', '.join(CONFIG_VALID_MODES)}."
        if name == "agent:spawn":
            return self._spawn_subagent(body.strip())
        return None

    def _exec_shell(self, cmd: str) -> str:
        if self.mode == "plan":
            return "[Error] Cannot execute shell commands in plan mode."
        result = self.shell.run(cmd)
        if result["success"]:
            output = result["stdout"][:2000] if result["stdout"] else "(no output)"
            if result["stderr"]:
                output += f"\n[stderr]\n{result['stderr'][:500]}"
            return f"[Shell] Exit 0\n{output}"
        else:
            error = (
                result["stderr"][:1000] or result["stdout"][:1000] or "Unknown error"
            )
            return f"[Shell] Exit {result['exit_code']}\n{error}"

    def _read_file(self, path: str) -> str:
        result = self.shell.read_file(path)
        if result["success"]:
            real_path = Path(result.get("path", "")).resolve()
            workdir = Path(self.shell.workdir).resolve()
            if not real_path.is_relative_to(workdir):
                return f"[Error] Path traversal blocked: {path}"
            content = result["content"]
            if len(content) > 4000:
                content = content[:2000] + "\n... [truncated] ...\n" + content[-2000:]
            return f"[File] {path}\n```\n{content}\n```"
        return f"[Error] {result.get('error', 'Read failed')}"

    def _write_file(self, path: str, content: str) -> str:
        from pathlib import Path
        from libercode.differ import compute_diff

        if self.mode == "plan":
            return "[Error] Cannot write files in plan mode."

        full_path = Path(self.shell.workdir) / path
        if not full_path.resolve().is_relative_to(Path(self.shell.workdir).resolve()):
            return f"[Error] Path traversal blocked: {path}"

        diff_lines = compute_diff(str(full_path), content)

        if self.tui_ui is not None:
            self.tui_ui._render_diff_panel(path, diff_lines)
            import asyncio
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self.tui_ui.ask_confirm(f"Apply changes to {path}?"),
                loop
            )
            confirmed = future.result(timeout=300)
            if not confirmed:
                return f"[File] Skipped: {path}"

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            self.memory.auto_store_context(
                f"file:{path}", f"Created/updated with {len(content)} chars"
            )
            if (
                self.config.enable_checkpoints
                and self.turn_count % self.config.checkpoint_interval == 0
            ):
                self.checkpointer.save(summary=f"wrote {path}")
            return f"[File] Written: {path}"
        except Exception as e:
            return f"[File] Error writing {path}: {e}"

    def _edit_file(self, path: str, old: str, new: str) -> str:
        if self.mode == "plan":
            return "[Error] Cannot edit files in plan mode."
        result = self.shell.edit_file(path, old, new)
        if result["success"]:
            self.memory.auto_store_context(f"edit:{path}", "Edited (replaced text)")
            return f"[File] Edited {path}"
        return f"[Error] {result.get('error', 'Edit failed')}"

    def _task_create(self, title: str, description: str = "") -> str:
        tid = self.tasks.create(title, description, mode=self.mode)
        return f"[Task] Created #{tid}: {title}"

    def _task_update(self, task_id: int, **kwargs) -> str:
        self.tasks.update(task_id, **kwargs)
        return f"[Task] Updated #{task_id}: {kwargs}"

    def _save_checkpoint(self, summary: str) -> str:
        cid = self.checkpointer.save(summary=summary)
        return f"[Checkpoint] Saved: {cid}"

    def _scratch_note(self, content: str) -> str:
        if "=" in content:
            title, text = content.split("=", 1)
            nid = self.scratch.write(title.strip(), text.strip())
            return f"[Scratch] Note #{nid}: {title.strip()}"
        nid = self.scratch.write(f"note_{int(time.time())}", content)
        return f"[Scratch] Note #{nid}"

    def _restore_snapshot_files(self, files: dict) -> tuple[int, list[str]]:
        restored = 0
        errors = []
        workdir = Path(self.shell.workdir).resolve()
        for rel_path, content in files.items():
            try:
                full_path = (workdir / rel_path).resolve()
                if not full_path.is_relative_to(workdir):
                    errors.append(f"Blocked: {rel_path}")
                    continue
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                restored += 1
            except Exception as e:
                errors.append(f"{rel_path}: {e}")
        return restored, errors

    def _spawn_subagent(self, task_desc: str) -> str:
        if self.mode == "plan":
            return "[Error] Cannot spawn agents in plan mode."
        if self._spawn_depth >= 2:
            return "[Error] Maximum sub-agent nesting depth (2) reached."
        tid = self.tasks.create(
            f"Sub-agent: {task_desc[:50]}", task_desc, mode=self.mode
        )
        self.tasks.start(tid)

        prompt = (
            f"You are a LiberCode sub-agent. Complete this task:\n\n"
            f"{task_desc}\n\n"
            f"Current directory: {Path.cwd()}\n"
            f"Mode: {self.mode}\n\n"
            f"Report back what you did and the results."
        )

        messages = [{"role": "user", "content": prompt}]
        self._spawn_depth += 1
        try:
            response = self.provider.chat(
                messages,
                system="You are a helpful coding sub-agent. Be concise and focused.",
            )
        finally:
            self._spawn_depth -= 1

        self.tasks.complete(tid)
        self.memory.auto_store_context(f"subagent:{tid}", response[:300])
        return f"[Sub-agent #{tid}] Complete.\n{response[:1500]}"

    def _check_stop_condition(self, task_id: int) -> dict:
        return self.stop_checker.auto_check(task_id, self.mode)

    def _print_hero(self):
        self.ui.hero()

    def _print_context_bar(self):
        self.ui.context_bar(self.mode, self.provider.name, self.session_id)

    def _print_quick_actions(self):
        self.ui.quick_actions()

    def _print_help(self):
        self.ui.help()

    def _handle_slash_command(self, cmd: str) -> bool:
        cmd = cmd.strip().lower()

        if cmd == "/help":
            self._print_help()
            return True

        if cmd == "/tasks":
            tasks = self.tasks.list()
            if not tasks:
                self.console.print("[dim]No tasks yet[/]")
                return True
            table = Table(box=box.SIMPLE)
            table.add_column("ID")
            table.add_column("Status")
            table.add_column("Priority")
            table.add_column("Title")
            for t in tasks[:15]:
                table.add_row(
                    str(t["id"]), t["status"], t.get("priority", "med"), t["title"][:60]
                )
            self.console.print(table)
            return True

        if cmd == "/memory":
            items = self.memory.all()
            if not items:
                self.console.print("[dim]No memory stored[/]")
                return True
            for m in items[:15]:
                self.console.print(f"  [cyan]{m['key']}[/]: {m.get('value', '')[:120]}")
            return True

        if cmd == "/checkpoints":
            cps = self.checkpointer.list()
            if not cps:
                self.console.print("[dim]No checkpoints[/]")
                return True
            for cp in cps[:10]:
                self.console.print(
                    f"  [{cp['created_at'][:19]}] {cp['id']} — {cp.get('summary', '')[:60]}"
                )
            return True

        if cmd == "/scratch":
            notes = self.scratch.list()
            if not notes:
                self.console.print("[dim]No scratch notes[/]")
                return True
            for n in notes[:10]:
                self.console.print(
                    f"  #{n['id']} [bold]{n['title']}[/] — {n.get('content', '')[:80]}"
                )
            return True

        if cmd == "/mode":
            self.console.print(f"Current mode: [bold]{self.mode.upper()}[/]")
            return True

        if cmd == "/status":
            self.console.print(f"Session: #{self.session_id} | Mode: {self.mode}")
            self.console.print(f"Provider: {self.provider.name}")
            if self.git.is_repo():
                self.console.print(self.git.summary())
            self.console.print(f"Tasks: {len(self.tasks.list())} total")
            return True

        if cmd == "/undo":
            cps = self.checkpointer.list()
            if not cps:
                self.console.print("[dim]No checkpoints to undo[/]")
                return True
            latest = cps[0]
            snapshot = latest.get("snapshot", {})
            files = snapshot.get("files", {})
            restored, errors = self._restore_snapshot_files(files)
            self.console.print(
                f"[green]Restored {restored} files from checkpoint {latest['id']}[/]"
            )
            for err in errors:
                self.console.print(f"[red]{err}[/]")
            return True

        if cmd == "/context":
            system = self._system_prompt()
            self.console.print(Panel(system, title="System Prompt", border_style="dim"))
            return True

        if cmd.startswith("/export"):
            import json as _json
            parts = cmd.split(maxsplit=1)
            export_path = parts[1].strip() if len(parts) > 1 else "libercode_export.json"
            data = {
                "memory": self.memory.all(),
                "tasks": self.tasks.list(),
                "mode": self.mode,
            }
            Path(export_path).write_text(_json.dumps(data, indent=2, default=str))
            self.console.print(f"[green]Exported to {export_path}[/]")
            return True

        if cmd.startswith("/import"):
            import json as _json
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                self.console.print("[red]Usage: /import <path>[/]")
                return True
            import_path = parts[1].strip()
            if not Path(import_path).exists():
                self.console.print(f"[red]File not found: {import_path}[/]")
                return True
            data = _json.loads(Path(import_path).read_text())
            for item in data.get("memory", []):
                self.memory.remember(item["key"], item.get("value", ""), item.get("category", "general"))
            self.console.print(f"[green]Imported memory from {import_path}[/]")
            return True

        if cmd in ("/exit", "/quit"):
            self.console.print("[yellow]Ending session...[/]")
            summary = f"Last mode: {self.mode}, turns: {self.turn_count}"
            self.store.session_end(self.session_id, summary)
            return False

        return False

    def _extract_next_tool_call(self, response: str) -> Optional[str]:
        import re
        tool_match = re.search(r"<tool\s+name=\"([^\"]+)\"[^>]*>.*?</tool>", response, re.DOTALL)
        if tool_match:
            return tool_match.group(0)
        for line in response.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("```"):
                continue
            if (
                stripped.startswith("file:")
                or (stripped.startswith("!") and len(stripped) > 1)
                or stripped.startswith("task:")
                or stripped.startswith("checkpoint")
                or stripped.startswith("scratch ")
                or stripped.startswith("memory ")
                or stripped.startswith("git ")
                or stripped.startswith("mode ")
                or stripped.startswith("agent:")
            ):
                return stripped
        return None

    def _process_response(self, response: str) -> str:
        result = self._process_tool_call(response)
        if result:
            return result
        return ""

    def _make_pt_session(self):
        kb = KeyBindings()
        modes = list(CONFIG_VALID_MODES)

        @kb.add("tab")
        def _(event):
            cur = modes.index(self.mode) if self.mode in modes else 0
            new = modes[(cur + 1) % len(modes)]
            self.mode = new
            self.store.session_update_mode(self.session_id, new)
            event.app.current_buffer.text = ""
            event.app.invalidate()

        @kb.add("s-tab")
        def _(event):
            cur = modes.index(self.mode) if self.mode in modes else 0
            new = modes[(cur - 1) % len(modes)]
            self.mode = new
            self.store.session_update_mode(self.session_id, new)
            event.app.current_buffer.text = ""
            event.app.invalidate()

        @kb.add("enter")
        def _(event):
            buf = event.app.current_buffer
            text = buf.text
            if text.strip().endswith(";;"):
                buf.text = text[:-2].rstrip()
                event.app.exit(result=text[:-2].rstrip())
            else:
                buf.insert_text("\n")

        @kb.add("escape", "enter")
        def _(event):
            event.app.exit(result=event.app.current_buffer.text)

        try:
            _input = create_input()
        except Exception:
            _input = None

        try:
            return PTSession(key_bindings=kb, input=_input)
        except Exception:
            return None

    def _pt_prompt_text(self):
        mc = self._mode_color_code()
        ctx = (
            f"\x1b[2m"
            f"{self.mode.capitalize()} \x1b[0m\x1b[2m· \x1b[0m"
            f"\x1b[2m{self.provider.name} \x1b[0m\x1b[2m· \x1b[0m"
            f"\x1b[2mSession #{self.session_id} \x1b[0m\x1b[2m· \x1b[0m"
            f"\x1b[32mConnected\x1b[0m"
            f"\x1b[0m"
        )
        prompt = f"\x1b[1;{mc}m{self.mode}\x1b[0m "
        return ANSI(f"{ctx}\n{prompt}")

    def _mode_color_code(self):
        return {"build": "32", "plan": "33", "spec": "34", "debug": "31"}.get(
            self.mode, "37"
        )

    def run_interactive(self):
        with self.console.status("[dim]Starting session...[/]", spinner="dots"):
            time.sleep(0.4)
        self._print_hero()
        self._print_context_bar()
        self._print_quick_actions()
        self.console.print()

        history = self.store.history_get(self.session_id, limit=30)
        pt_session = self._make_pt_session()

        while True:
            try:
                if pt_session is not None:
                    user_input = pt_session.prompt(
                        lambda: self._pt_prompt_text(),
                        refresh_interval=0.1,
                    )
                else:
                    user_input = Prompt.ask(
                        f"[bold {self._mode_color()}]{self.mode}[/]"
                    )
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                break

            if pt_session is not None and user_input is None:
                break

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                should_continue = self._handle_slash_command(user_input)
                if should_continue is False:
                    break
                continue

            self.turn_count += 1
            self.store.history_append(self.session_id, "user", user_input, self.mode)

            if (
                self.config.enable_checkpoints
                and self.turn_count % self.config.checkpoint_interval == 0
            ):
                self.checkpointer.save(summary=f"auto-turn-{self.turn_count}")

            messages = self._build_messages(user_input, history)
            system = self._system_prompt()

            self.console.print(f"[dim]{self.provider.name} thinking...[/]")

            full_response = ""
            try:
                for chunk in self.provider.chat_stream(messages, system=system):
                    full_response += chunk
                    print(chunk, end="", flush=True)
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/]")
                continue
            print()
            self.console.print(Markdown(full_response))

            if not full_response.strip():
                self.console.print("[yellow]Empty response. Retrying...[/]")
                continue

            self.store.history_append(
                self.session_id, "assistant", full_response, self.mode
            )
            self.total_tokens += len(self._enc.encode(user_input + full_response))

            tool_result = self._process_response(full_response)
            if tool_result:
                self.console.print(Panel(tool_result, border_style="dim"))

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": full_response})

            if self.turn_count >= self.config.max_turns:
                self.console.print(
                    f"[yellow]Reached max turns ({self.config.max_turns}). Ending session.[/]"
                )
                break

        summary = f"Completed {self.turn_count} turns in {self.mode} mode"
        self.store.session_end(self.session_id, summary)
        self.console.print(f"[dim]Session #{self.session_id} ended. {summary}[/]")

    def run_one_shot(self, instruction: str):
        self.turn_count += 1
        self.store.history_append(self.session_id, "user", instruction, self.mode)

        messages = self._build_messages(instruction, [])
        system = self._system_prompt()

        response = self.provider.chat(messages, system=system)
        self.store.history_append(self.session_id, "assistant", response, self.mode)

        self.console.print(Markdown(response))

        tool_result = self._process_response(response)
        if tool_result:
            self.console.print(Panel(tool_result, border_style="dim"))

        self.store.session_end(self.session_id, f"One-shot: {instruction[:50]}")

    def _mode_color(self):
        return {"build": "green", "plan": "yellow", "spec": "blue", "debug": "red"}.get(
            self.mode, "white"
        )

    # ── TUI Command Handlers (thread-safe via tui callbacks) ──

    async def handle_tui_command(self, cmd: str, args: str, tui) -> None:
        self.tui_ui = tui

        if cmd == "undo":
            await self._tui_cmd_undo(tui)
        elif cmd == "context":
            await self._tui_cmd_context(tui)
        elif cmd == "export":
            await self._tui_cmd_export(tui)
        elif cmd == "import":
            await self._tui_cmd_import(tui, args)
        elif cmd == "model":
            if not args.strip():
                tui.open_model_modal()
            else:
                await self._tui_cmd_model(args, tui)
        elif cmd == "mode":
            await self._tui_cmd_mode(args, tui)
        elif cmd == "tasks":
            await self._tui_cmd_tasks(tui)
        elif cmd == "memory":
            await self._tui_cmd_memory(tui)
        elif cmd == "git":
            output = await self._run_git_async("status", "--short")
            self._tui_write_git_output("git status", output, tui)
        elif cmd == "stash":
            output = await self._run_git_async("stash")
            self._tui_write_git_output("git stash", output, tui)
        elif cmd == "pop":
            output = await self._run_git_async("stash", "pop")
            self._tui_write_git_output("git stash pop", output, tui)
        elif cmd == "sessions":
            await self._tui_cmd_sessions(args, tui)
        elif cmd == "checkpoint":
            await self._tui_cmd_checkpoint(args, tui)
        elif cmd == "restore":
            await self._tui_cmd_restore(args, tui)
        elif cmd == "scratch":
            await self._tui_cmd_scratch(tui)
        elif cmd == "search":
            await self._tui_cmd_search(args, tui)
        elif cmd == "pr":
            await self._tui_cmd_pr(args, tui)
        elif cmd == "review":
            await self._tui_cmd_review(tui)
        elif cmd == "test":
            await self._tui_cmd_test(args, tui)
        elif cmd == "lint":
            await self._tui_cmd_lint(args, tui)
        elif cmd == "config":
            await self._tui_cmd_config(args, tui)
        elif cmd == "provider":
            parts = args.strip().split(maxsplit=1)
            if not args.strip() or args.strip() in ("list", "setup"):
                tui.open_provider_modal()
            else:
                name  = parts[0].lower()
                model = parts[1].strip() if len(parts) > 1 else ""
                await self._tui_provider_direct_switch(name, model, tui)
        else:
            tui.write_error(f"Unknown command: /{cmd}")

    async def handle_tui_message(self, user_input: str, tui) -> None:
        import asyncio

        self.tui_ui = tui
        self.turn_count += 1
        self.store.history_append(
            self.session_id, "user", user_input, self.mode
        )

        history  = self.store.history_get(self.session_id, limit=30)
        messages = self._build_messages(user_input, history)
        system   = self._system_prompt()

        # Show AI header immediately
        tui.render_ai_header(self.provider.name)

        full_response = ""
        queue: asyncio.Queue = asyncio.Queue()

        def _stream_worker():
            try:
                for chunk in self.provider.chat_stream(
                    messages, system=system
                ):
                    queue.put_nowait(chunk)
            except Exception as e:
                queue.put_nowait(e)
            finally:
                queue.put_nowait(None)

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _stream_worker)

        # Stream chunks into buffer — event loop free between awaits
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                tui.write_error(f"Provider error: {chunk}")
                return
            full_response += chunk

        if not full_response.strip():
            tui.write_error("Empty response from provider.")
            return

        # Render with full Markdown + syntax highlighting
        tui.render_ai_response(full_response)

        self.store.history_append(
            self.session_id, "assistant", full_response, self.mode
        )
        self.total_tokens += len(
            self._enc.encode(user_input + full_response)
        )

        # Detect and render tool calls with visual panels
        import re as _re
        tool_pattern = _re.compile(
            r"<tool\s+name=\"([^\"]+)\"[^>]*>(.*?)</tool>",
            _re.DOTALL
        )
        tool_matches = list(tool_pattern.finditer(full_response))
        if tool_matches:
            for match in tool_matches:
                tool_name = match.group(1).strip()
                tool_body = match.group(2).strip()
                result = self._dispatch_tool(tool_name, tool_body)
                if result:
                    tui._render_tool_result(tool_name, result)
        else:
            tool_result = self._process_response(full_response)
            if tool_result:
                tool_name = "shell"
                if tool_result.startswith("[File]"):
                    tool_name = "file:write"
                elif tool_result.startswith("[Task]"):
                    tool_name = "task:create"
                elif tool_result.startswith("[Checkpoint]"):
                    tool_name = "checkpoint"
                elif tool_result.startswith("[Memory]"):
                    tool_name = "memory"
                elif tool_result.startswith("[Scratch]"):
                    tool_name = "scratch"
                elif tool_result.startswith("[Sub-agent"):
                    tool_name = "agent:spawn"
                tui._render_tool_result(tool_name, tool_result)

        tui.refresh_status_bar()
        tui.refresh_token_bar()

    async def handle_picker_selected(self, kind: str, value: str, tui) -> None:
        if kind == "model":
            self.provider.model = value
            tui.update_model_badge_from_thread(value)
            tui.write_info(f"Model switched to {value}")

        elif kind == "mode":
            self.mode = value
            self.store.session_update_mode(self.session_id, value)
            tui.write_info(f"Mode switched to {value}")
            tui._update_mode_pill(value)

        elif kind == "provider_wizard":
            await self._tui_wizard_step2(value, tui)

        elif kind == "provider_model":
            state    = getattr(self, "_wizard_state", {})
            provider = state.get("provider", "")
            api_key  = state.get("api_key", "")
            if provider:
                old = self.provider
                try:
                    self.swap_provider(name=provider, model=value, api_key=api_key)
                    from rich.text import Text
                    from rich.style import Style
                    tui.write_output(Text(
                        f"\n  ✓ Setup complete!\n"
                        f"  Provider: {provider}\n"
                        f"  Model:    {value}\n"
                        f"  Config saved to config.yaml\n",
                        Style(color=tui.theme_data["success"], bold=True)
                    ))
                    tui.update_model_badge_from_thread(
                        f"{provider} / {value}"
                    )
                    tui.refresh_status_bar()
                except ProviderError as e:
                    self.provider = old
                    tui.write_error(f"Setup failed: {e}")
                self._wizard_state = {}

        tui.refresh_status_bar()

    def _tui_write(self, tui, content) -> None:
        tui.write_output(content)

    def _tui_sep(self, tui) -> None:
        t = tui.theme_data
        tui.write_output(Text("  " + "─" * 58, Style(color=t["border"])))

    async def _tui_cmd_undo(self, tui) -> None:
        t = tui.theme_data
        history = self.store.history_get(self.session_id, limit=100)
        removed = 0
        for role in ["assistant", "user"]:
            for i in range(len(history) - 1, -1, -1):
                if history[i].get("role") == role:
                    history.pop(i)
                    removed += 1
                    break
        if removed == 0:
            tui.write_error("Nothing to undo.")
        else:
            tui.write_output(Text(
                "  ↩ Last message pair removed from history\n",
                Style(color=t.get("warning", "#f1fa8c"))
            ))

    async def _tui_cmd_context(self, tui) -> None:
        t = tui.theme_data
        prompt = self._system_prompt()
        tui.write_output(Text("\n  System Prompt\n", Style(color=t["primary"], bold=True)))
        self._tui_sep(tui)
        for line in prompt.splitlines():
            tui.write_output(Text(f"  {line}", Style(color=t["text"])))
        self._tui_sep(tui)
        tui.write_output("\n")

    async def _tui_cmd_export(self, tui) -> None:
        t    = tui.theme_data
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(f"libercode_export_{ts}.json")
        try:
            history = self.store.history_get(self.session_id, limit=1000)
            payload = {
                "exported_at": datetime.now().isoformat(),
                "mode":        self.mode,
                "messages":    history,
                "memory":      self.memory.all(),
                "tasks":       self.tasks.list(),
            }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
            tui.write_output(Text(
                f"\n  ✓ Exported to {path}\n",
                Style(color=t["success"], bold=True)
            ))
        except Exception as e:
            tui.write_error(f"Export failed: {e}")

    async def _tui_cmd_import(self, tui, args: str = "") -> None:
        from rich.text import Text
        from rich.style import Style
        import json
        t = tui.theme_data

        # If no filename given → show instructions + list files
        if not args:
            tui.write_output(Text(
                "\n  Import\n", Style(color=t["primary"], bold=True)
            ))
            self._tui_sep(tui)
            tui.write_output(Text(
                "  Usage: /import <filename>\n",
                Style(color=t["muted"])
            ))
            exports = sorted(Path(".").glob("libercode_export_*.json"))
            if exports:
                tui.write_output(Text(
                    "  Available exports:", Style(color=t["text"])
                ))
                for f in exports:
                    size = f.stat().st_size // 1024
                    tui.write_output(Text(
                        f"    {f.name}  ({size}kb)",
                        Style(color=t.get("info", t["accent"]))
                    ))
            else:
                tui.write_output(Text(
                    "  No libercode_export_*.json files found in current directory.\n",
                    Style(color=t["muted"])
                ))
            self._tui_sep(tui)
            return

        # Filename was given → load and import
        path = Path(args.strip())

        if not path.exists():
            path = Path.cwd() / args.strip()

        if not path.exists():
            tui.write_error(f"File not found: {args.strip()}")
            return

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            tui.write_error(f"Failed to read file: {e}")
            return

        imported = {"messages": 0, "memory": 0, "tasks": 0}

        messages = payload.get("messages", [])
        for msg in messages:
            role    = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                self.store.history_append(
                    self.session_id, role, content,
                    payload.get("mode", self.mode)
                )
                imported["messages"] += 1

        for entry in payload.get("memory", []):
            key = entry.get("key", "")
            val = entry.get("value", "")
            cat = entry.get("category", "general")
            if key:
                self.memory.remember(key, val, cat)
                imported["memory"] += 1

        for task in payload.get("tasks", []):
            title = task.get("title", "") or task.get("text", "")
            desc  = task.get("description", "")
            if title:
                self.tasks.create(title, desc, mode=self.mode)
                imported["tasks"] += 1

        if "mode" in payload and payload["mode"] in self.VALID_MODES:
            self.mode = payload["mode"]
            self.store.session_update_mode(self.session_id, self.mode)
            tui._update_mode_pill(self.mode)

        tui.write_output(Text(
            f"\n  ✓ Import complete from {path.name}\n",
            Style(color=t["success"], bold=True)
        ))
        self._tui_sep(tui)
        tui.write_output(Text(
            f"  Messages: {imported['messages']}\n"
            f"  Memory:   {imported['memory']}\n"
            f"  Tasks:    {imported['tasks']}\n",
            Style(color=t["text"])
        ))
        self._tui_sep(tui)

    async def _tui_cmd_model(self, args: str, tui) -> None:
        if not args:
            current = getattr(self.provider, "model", "")
            tui.show_picker_from_thread("model", self.available_models, current)
        else:
            match = next(
                (m for m in self.available_models if args.lower() in m.lower()),
                None
            )
            if match:
                self.provider.model = match
                tui.update_model_badge_from_thread(match)
                tui.write_info(f"Model switched to {match}")
            else:
                tui.write_error(
                    f"Model '{args}' not found. "
                    f"Available: {', '.join(self.available_models)}"
                )

    VALID_MODES = list(CONFIG_VALID_MODES)

    async def _tui_cmd_mode(self, args: str, tui) -> None:
        if not args:
            tui.show_picker_from_thread("mode", self.VALID_MODES, self.mode)
        elif args in self.VALID_MODES:
            self.mode = args
            self.store.session_update_mode(self.session_id, args)
            tui.write_info(f"Mode switched to {args}")
            tui.refresh_status_bar()
        else:
            tui.write_error(
                f"Invalid mode '{args}'. "
                f"Valid: {', '.join(self.VALID_MODES)}"
            )

    async def _tui_cmd_tasks(self, tui) -> None:
        t = tui.theme_data
        tui.write_output(Text("\n  Tasks\n", Style(color=t["primary"], bold=True)))
        self._tui_sep(tui)
        tasks = self.tasks.list()
        if not tasks:
            tui.write_output(Text(
                "  No tasks yet. Start a conversation.\n",
                Style(color=t["muted"])
            ))
        else:
            for i, task in enumerate(tasks[:20]):
                done  = task.get("status", "") in ("done", "completed")
                icon  = "✓" if done else "○"
                color = t["success"] if done else t["text"]
                tui.write_output(Text(
                    f"  {icon} [{task.get('id','?')}] {task.get('title','')[:70]}",
                    Style(color=color)
                ))
        self._tui_sep(tui)
        tui.write_output("\n")
        tui.refresh_status_bar()

    async def _tui_cmd_memory(self, tui) -> None:
        t = tui.theme_data
        tui.write_output(Text("\n  Memory\n", Style(color=t["primary"], bold=True)))
        self._tui_sep(tui)
        items = self.memory.all()
        if not items:
            tui.write_output(Text(
                "  No memory stored yet.\n",
                Style(color=t["muted"])
            ))
        else:
            for item in items[:20]:
                key = item.get("key", "")
                category = item.get("category", "general")
                value = item.get("value", "")
                line = Text()
                line.append(f"  {key}", Style(color=t["accent"], bold=True))
                line.append(f"  ({category})", Style(color=t["muted"]))
                line.append(f": {value[:140]}", Style(color=t["text"]))
                tui.write_output(line)
        self._tui_sep(tui)
        tui.write_output("\n")

    async def _tui_cmd_checkpoint(self, args: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t       = tui.theme_data
        summary = args.strip() if args.strip() else f"manual checkpoint — turn {self.turn_count}"
        try:
            cid = self.checkpointer.save(summary=summary)
            tui.write_output(Text(
                f"\n  ✓ Checkpoint saved: {cid}\n"
                f"  Summary: {summary}\n",
                Style(color=t["success"], bold=True)
            ))
        except Exception as e:
            tui.write_error(f"Checkpoint failed: {e}")

    async def _tui_cmd_restore(self, args: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t = tui.theme_data
        try:
            cps = self.checkpointer.list()
        except Exception as e:
            tui.write_error(f"Could not load checkpoints: {e}")
            return
        if not args.strip():
            tui.write_output(Text(
                "\n  Checkpoints\n", Style(color=t["primary"], bold=True)
            ))
            self._tui_sep(tui)
            if not cps:
                tui.write_output(Text(
                    "  No checkpoints saved yet.\n",
                    Style(color=t["muted"])
                ))
            else:
                for cp in cps[:15]:
                    cid     = cp.get("id", "?")
                    created = str(cp.get("created_at", ""))[:16]
                    summ    = cp.get("summary", "")[:60]
                    nfiles  = len(cp.get("snapshot", {}).get("files", {}))
                    line    = Text()
                    line.append(f"  {cid}", Style(color=t["accent"], bold=True))
                    line.append(f"  {created}", Style(color=t["muted"]))
                    line.append(f"  {nfiles} files", Style(color=t["text"]))
                    line.append(f"  {summ}", Style(color=t["muted"]))
                    tui.write_output(line)
            self._tui_sep(tui)
            tui.write_output(Text(
                "  Use /restore <checkpoint_id> to restore files.\n",
                Style(color=t["muted"])
            ))
            return
        target_id = args.strip()
        cp = next((c for c in cps if str(c.get("id", "")) == target_id), None)
        if cp is None:
            tui.write_error(f"Checkpoint '{target_id}' not found.")
            return
        snapshot = cp.get("snapshot", {})
        files    = snapshot.get("files", {})
        if not files:
            tui.write_error(f"Checkpoint {target_id} has no file snapshot.")
            return
        restored, errors = self._restore_snapshot_files(files)
        tui.write_output(Text(
            f"\n  ✓ Restored {restored} files from checkpoint {target_id}\n",
            Style(color=t["success"], bold=True)
        ))
        if errors:
            for err in errors:
                tui.write_error(err)

    async def _tui_cmd_scratch(self, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t = tui.theme_data
        tui.write_output(Text(
            "\n  Scratch Notes\n", Style(color=t["primary"], bold=True)
        ))
        self._tui_sep(tui)
        try:
            notes = self.scratch.list()
        except Exception as e:
            tui.write_error(f"Could not load notes: {e}")
            return
        if not notes:
            tui.write_output(Text(
                "  No scratch notes yet.\n", Style(color=t["muted"])
            ))
        else:
            for n in notes[:20]:
                nid     = n.get("id", "?")
                title   = n.get("title", "")
                content = n.get("content", "")[:80]
                line    = Text()
                line.append(f"  #{nid} ", Style(color=t["accent"], bold=True))
                line.append(f"{title}  ", Style(color=t["text"], bold=True))
                line.append(content,      Style(color=t["muted"]))
                tui.write_output(line)
        self._tui_sep(tui)

    async def _tui_cmd_sessions(self, args: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t = tui.theme_data

        # If an ID was passed → restore that session
        if args.strip().isdigit():
            await self._tui_restore_session(int(args.strip()), tui)
            return

        # Otherwise → list all sessions for this project
        try:
            sessions = self.store.session_list(str(Path.cwd().resolve()))
        except Exception as e:
            tui.write_error(f"Could not load sessions: {e}")
            return

        tui.write_output(Text(
            "\n  Sessions\n", Style(color=t["primary"], bold=True)
        ))
        self._tui_sep(tui)

        if not sessions:
            tui.write_output(Text(
                "  No past sessions found.\n", Style(color=t["muted"])
            ))
        else:
            for s in sessions[:20]:
                sid     = s.get("id", "?")
                mode    = s.get("mode", "?")
                started = str(s.get("started_at", ""))[:16]
                ended   = str(s.get("ended_at", ""))[:16] or "active"
                summary = s.get("summary", "")[:50]
                is_cur  = (sid == self.session_id)

                line = Text()
                line.append(
                    "  ▶ " if is_cur else "    ",
                    Style(color=t["accent"], bold=True)
                )
                line.append(f"#{sid}", Style(
                    color=t["accent"] if is_cur else t["primary"],
                    bold=is_cur
                ))
                line.append(f"  {mode:<6}", Style(color=t["secondary"]))
                line.append(f"  {started}", Style(color=t["muted"]))
                line.append(f"  → {ended}", Style(color=t["muted"]))
                if summary:
                    line.append(f"  {summary}", Style(color=t["text"]))
                tui.write_output(line)

        self._tui_sep(tui)
        tui.write_output(Text(
            "  Use /sessions <id> to restore a session.\n",
            Style(color=t["muted"])
        ))

    async def _tui_restore_session(self, session_id: int, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t = tui.theme_data

        try:
            history = self.store.history_get(session_id, limit=50)
        except Exception as e:
            tui.write_error(f"Could not load session #{session_id}: {e}")
            return

        if not history:
            tui.write_error(f"Session #{session_id} has no messages.")
            return

        self.session_id = session_id

        tui.write_output(Text(
            f"\n  ◈ Restored session #{session_id}\n",
            Style(color=t["accent"], bold=True)
        ))
        self._tui_sep(tui)

        for msg in history[-20:]:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                tui.render_user_message(content[:300])
            elif role == "assistant":
                tui.render_ai_response(content[:1000])

        self._tui_sep(tui)
        tui.write_output(Text(
            f"  Session #{session_id} loaded. Continue where you left off.\n",
            Style(color=t["muted"])
        ))

    async def _run_git_async(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out = (stdout or b"").decode().strip()
        err = (stderr or b"").decode().strip()
        return (out + "\n" + err).strip() or "(no output)"

    async def _run_git(self, *args: str) -> str:
        return await self._run_git_async(*args)

    async def _run_external_cmd(self, *args: str) -> str:
        import asyncio
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.shell.workdir,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode("utf-8", errors="replace").strip() or "(no output)"
        except FileNotFoundError:
            return f"Command not found: {args[0]}"
        except Exception as e:
            return f"Error running {args[0]}: {e}"

    def _tui_write_git_output(self, title: str, output: str, tui) -> None:
        t = tui.theme_data
        tui.write_output(Text(f"\n  {title}\n", Style(color=t["primary"], bold=True)))
        self._tui_sep(tui)
        for line in output.splitlines():
            if line.startswith(("M ", " M")):
                color = t.get("warning", "#f1fa8c")
            elif line.startswith(("A ", " A")):
                color = t["success"]
            elif line.startswith(("D ", " D")):
                color = t["error"]
            elif line.startswith("??"):
                color = t["muted"]
            else:
                color = t["text"]
            tui.write_output(Text(f"  {line}", Style(color=color)))
        self._tui_sep(tui)
        tui.write_output("\n")

    # ── Feature 10: /search ──

    async def _tui_cmd_search(self, query: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t = tui.theme_data

        if not query.strip():
            tui.write_error("Usage: /search <term>")
            return

        q = query.strip().lower()

        try:
            history = self.store.history_get(self.session_id, limit=1000)
        except Exception as e:
            tui.write_error(f"Could not search history: {e}")
            return

        matches = [
            msg for msg in history
            if q in msg.get("content", "").lower()
        ]

        tui.write_output(Text(
            f'\n  Search: "{query}"\n',
            Style(color=t["primary"], bold=True)
        ))
        self._tui_sep(tui)

        if not matches:
            tui.write_output(Text(
                f'  No results for "{query}"\n',
                Style(color=t["muted"])
            ))
        else:
            tui.write_output(Text(
                f"  {len(matches)} result(s) found\n",
                Style(color=t["accent"])
            ))
            for msg in matches[:10]:
                role    = msg.get("role", "?")
                content = msg.get("content", "")
                ts      = str(msg.get("created_at", ""))[:16]

                idx   = content.lower().find(q)
                start = max(0, idx - 60)
                end   = min(len(content), idx + len(q) + 60)
                excerpt = ("…" if start > 0 else "") + \
                          content[start:end] + \
                          ("…" if end < len(content) else "")

                line = Text()
                line.append(f"  [{role}]", Style(
                    color=t["secondary"] if role == "user" else t["primary"],
                    bold=True
                ))
                line.append(f"  {ts}  ", Style(color=t["muted"]))

                lo = excerpt.lower()
                qi = lo.find(q)
                if qi >= 0:
                    line.append(excerpt[:qi],        Style(color=t["text"]))
                    line.append(excerpt[qi:qi+len(q)], Style(
                        color=t["bg"], bgcolor=t["accent"], bold=True
                    ))
                    line.append(excerpt[qi+len(q):], Style(color=t["text"]))
                else:
                    line.append(excerpt, Style(color=t["text"]))

                tui.write_output(line)
                tui.write_output(Text(""))

        self._tui_sep(tui)

    # ── Feature 16: /pr and /review ──

    async def _tui_cmd_pr(self, args: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        t = tui.theme_data

        if not self.git.is_repo():
            tui.write_error("Not a git repository.")
            return

        branch = (await self._run_git("rev-parse", "--abbrev-ref", "HEAD")).strip()
        if branch in ("main", "master", "HEAD"):
            tui.write_error(
                f"Current branch is '{branch}'. "
                "Create a feature branch first."
            )
            return

        base = "main"
        base_check = (await self._run_git("rev-parse", "--verify", "main")).strip()
        if base_check.startswith("fatal"):
            base = "master"

        log_raw = await self._run_git(
            "log", f"{base}..HEAD", "--oneline", "--no-decorate"
        )
        diff_raw = await self._run_git("diff", f"{base}...HEAD", "--stat")

        tui.write_info("Generating PR description…")
        pr_prompt = (
            f"Generate a GitHub pull request title and description for "
            f"branch '{branch}' based on these commits:\n\n"
            f"{log_raw}\n\nFiles changed:\n{diff_raw}\n\n"
            "Format:\nTITLE: <title>\n\nBODY:\n<markdown body>"
        )

        import asyncio
        q: asyncio.Queue = asyncio.Queue()

        def _gen():
            try:
                for chunk in self.provider.chat_stream(
                    [{"role": "user", "content": pr_prompt}],
                    system="You are a helpful git assistant."
                ):
                    q.put_nowait(chunk)
            except Exception as e:
                q.put_nowait(e)
            finally:
                q.put_nowait(None)

        asyncio.get_event_loop().run_in_executor(None, _gen)
        full = ""
        while True:
            chunk = await q.get()
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                tui.write_error(str(chunk))
                return
            full += chunk

        title, body = branch, ""
        if "TITLE:" in full:
            parts = full.split("TITLE:", 1)[1]
            lines = parts.strip().splitlines()
            title = lines[0].strip()
            if "BODY:" in full:
                body = full.split("BODY:", 1)[1].strip()

        tui.write_output(Text(f"\n  PR Title:  {title}\n",
                              Style(color=t["primary"], bold=True)))
        if body:
            tui.write_output(Text(f"  Body preview:\n  {body[:200]}\n",
                                  Style(color=t["muted"])))

        confirmed = await tui.ask_confirm("Push branch and open PR?")
        if not confirmed:
            tui.write_info("PR cancelled.")
            return

        push_out = await self._run_git("push", "-u", "origin", branch)
        tui.write_output(Text(f"  {push_out}\n", Style(color=t["muted"])))

        gh_args = [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body[:4000],
            "--base",
            base,
        ]
        gh_preview = f'gh pr create --title "{title}" --body <generated> --base {base}'
        tui._render_tool_result("shell", gh_preview)

        push_result = await self._run_external_cmd(*gh_args)
        if "https://github.com" in push_result:
            url = [w for w in push_result.split() if w.startswith("https://")][0]
            tui.write_output(Text(
                f"\n  ✓ PR created: {url}\n",
                Style(color=t["success"], bold=True)
            ))
        else:
            tui.write_output(Text(
                f"\n  Pushed. Run:\n  {gh_preview}\n",
                Style(color=t["accent"])
            ))

    async def _tui_cmd_review(self, tui) -> None:
        if not self.git.is_repo():
            tui.write_error("Not a git repository.")
            return

        diff = await self._run_git("diff", "HEAD")
        if not diff.strip():
            diff = await self._run_git("diff", "--cached")
        if not diff.strip():
            tui.write_error("No uncommitted changes to review.")
            return

        tui.write_info("Reviewing current diff…")
        review_prompt = (
            "Review the following git diff. List:\n"
            "1. Potential bugs or issues\n"
            "2. Code quality suggestions\n"
            "3. Security concerns (if any)\n"
            "4. What looks good\n\n"
            f"```diff\n{diff[:6000]}\n```"
        )
        await self.handle_tui_message(review_prompt, tui)

    # ── Feature 17: /test and /lint ──

    def _detect_project_type(self) -> str:
        root = Path(self.shell.workdir)
        if (root / "Cargo.toml").exists():
            return "rust"
        if (root / "package.json").exists():
            return "node"
        if (root / "pyproject.toml").exists():
            return "python"
        if (root / "setup.py").exists():
            return "python"
        if (root / "requirements.txt").exists():
            return "python"
        if (root / "go.mod").exists():
            return "go"
        if (root / "pom.xml").exists():
            return "java"
        return "unknown"

    async def _run_cmd(self, *args: str) -> str:
        import asyncio
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.shell.workdir,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode("utf-8", errors="replace").strip() or "(no output)"
        except FileNotFoundError:
            return f"Command not found: {args[0]}"
        except Exception as e:
            return f"Error running {args[0]}: {e}"

    async def _tui_cmd_test(self, args: str, tui) -> None:
        project = self._detect_project_type()
        cmd_map = {
            "python": ["python", "-m", "pytest", "--tb=short", "-q"],
            "node":   ["npx", "jest", "--no-coverage"],
            "rust":   ["cargo", "test"],
            "go":     ["go", "test", "./..."],
            "java":   ["mvn", "test", "-q"],
        }

        cmd_args = cmd_map.get(project)
        if args.strip():
            cmd_args = args.strip().split()
        if not cmd_args:
            tui.write_error(
                f"Unknown project type '{project}'. "
                "Provide a command: /test pytest tests/"
            )
            return

        tui.write_info(f"Running: {' '.join(cmd_args)}")
        output = await self._run_cmd(*cmd_args)
        tui._render_tool_result("shell", output)

        if any(kw in output.lower() for kw in ["error", "failed", "failure", "assert"]):
            tui.write_info("Summarising failures…")
            summary_prompt = (
                "Summarise only the test failures from this test output. "
                "For each failure, state what failed and suggest a fix.\n\n"
                f"```\n{output[:4000]}\n```"
            )
            await self.handle_tui_message(summary_prompt, tui)

    async def _tui_cmd_lint(self, args: str, tui) -> None:
        project = self._detect_project_type()
        cmd_map = {
            "python": ["ruff", "check", "."],
            "node":   ["npx", "eslint", ".", "--max-warnings=0"],
            "rust":   ["cargo", "clippy", "--", "-D", "warnings"],
            "go":     ["golangci-lint", "run"],
        }

        cmd_args = cmd_map.get(project)
        if args.strip():
            cmd_args = args.strip().split()
        if not cmd_args:
            tui.write_error(
                f"Unknown project type '{project}'. "
                "Provide a command: /lint ruff check ."
            )
            return

        tui.write_info(f"Running: {' '.join(cmd_args)}")
        output = await self._run_cmd(*cmd_args)
        tui._render_tool_result("shell", output)

        if output.strip() and "no issues" not in output.lower():
            tui.write_info("Asking agent to fix lint issues…")
            fix_prompt = (
                "Here are the linter warnings. "
                "For each issue, explain what the problem is and how to fix it. "
                "Show the corrected code snippet for the top 5 issues.\n\n"
                f"```\n{output[:4000]}\n```"
            )
            await self.handle_tui_message(fix_prompt, tui)

    # ── Feature 18: /config ──

    async def _tui_cmd_config(self, args: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        from libercode.config import GLOBAL_CONFIG_PATH
        t = tui.theme_data

        config_path = GLOBAL_CONFIG_PATH

        if "=" in args:
            key, val = args.split("=", 1)
            key = key.strip()
            val = val.strip()
            await self._tui_config_set(config_path, key, val, tui)
            return

        tui.write_output(Text(
            "\n  Configuration\n", Style(color=t["primary"], bold=True)
        ))
        self._tui_sep(tui)
        tui.write_output(Text(
            f"  File: {config_path}\n", Style(color=t["muted"])
        ))
        self._tui_sep(tui)

        if not config_path.exists():
            tui.write_output(Text(
                "  Config file not found. Using defaults.\n",
                Style(color=t["muted"])
            ))
        else:
            try:
                raw = config_path.read_text(encoding="utf-8")
                from rich.syntax import Syntax
                tui.write_output(Syntax(
                    raw, "yaml",
                    theme="dracula",
                    line_numbers=True,
                    background_color=t["bg_panel"],
                ))
            except Exception as e:
                tui.write_error(f"Could not read config: {e}")

        self._tui_sep(tui)
        tui.write_output(Text(
            "  Usage: /config key = value\n"
            "  Example: /config provider.model = deepseek-coder-v2\n",
            Style(color=t["muted"])
        ))

    async def _tui_config_set(
        self, config_path, key: str, val: str, tui
    ) -> None:
        from rich.text import Text
        from rich.style import Style
        import yaml
        t = tui.theme_data

        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        parts = key.split(".")
        node  = data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = val

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

            tui.write_output(Text(
                f"\n  ✓ {key} = {val}\n"
                "  Restart libercode for changes to take effect.\n",
                Style(color=t["success"], bold=True)
            ))
        except Exception as e:
            tui.write_error(f"Could not write config: {e}")

    # ── Provider management ──

    async def _tui_cmd_provider(self, args: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        from libercode.providers.registry import (
            PROVIDER_REGISTRY
        )
        from libercode.providers.base import ProviderError
        t = tui.theme_data

        if args.strip() == "setup":
            await self._tui_provider_wizard(tui)
            return

        if not args.strip() or args.strip() == "list":
            await self._tui_provider_list(tui)
            return

        parts = args.strip().split(maxsplit=1)
        name  = parts[0].lower()
        model = parts[1].strip() if len(parts) > 1 else ""

        if name not in PROVIDER_REGISTRY:
            tui.write_error(
                f"Unknown provider '{name}'. "
                f"Available: {', '.join(PROVIDER_REGISTRY)}"
            )
            return

        old_provider = self.provider
        try:
            self.swap_provider(name=name, model=model)
            tui.write_output(Text(
                f"\n  ✓ Provider → {name}"
                f"  model: {self.provider.model}\n",
                Style(color=t["success"], bold=True)
            ))
            tui.update_model_badge_from_thread(
                f"{name} / {self.provider.model}"
            )
            tui.refresh_status_bar()
        except ProviderError as e:
            self.provider = old_provider
            tui.write_error(f"Provider switch failed: {e}")

    async def _tui_provider_direct_switch(self, name: str, model: str, tui) -> None:
        """Switch provider directly by name, optionally setting model."""
        from rich.text import Text
        from rich.style import Style
        from libercode.providers.registry import PROVIDER_REGISTRY
        from libercode.providers.base import ProviderError
        t = tui.theme_data

        if name not in PROVIDER_REGISTRY:
            tui.write_error(
                f"Unknown provider '{name}'. "
                f"Available: {', '.join(PROVIDER_REGISTRY)}"
            )
            return

        old_provider = self.provider
        try:
            self.swap_provider(name=name, model=model)
            tui.write_output(Text(
                f"\n  ✓ Provider → {name}"
                f"  model: {self.provider.model}\n",
                Style(color=t["success"], bold=True)
            ))
            tui.update_model_badge_from_thread(
                f"{name} / {self.provider.model}"
            )
            tui.refresh_status_bar()
        except ProviderError as e:
            self.provider = old_provider
            tui.write_error(f"Provider switch failed: {e}")

    async def _tui_provider_list(self, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        from libercode.providers.registry import (
            PROVIDER_REGISTRY, detect_available_from_env
        )
        t    = tui.theme_data
        envs = detect_available_from_env()

        tui.write_output(Text(
            "\n  Providers\n", Style(color=t["primary"], bold=True)
        ))
        self._tui_sep(tui)

        for name, (cls, env_var) in PROVIDER_REGISTRY.items():
            is_active   = (name == self.provider.display_name)
            has_env_key = name in envs
            no_key_needed = not env_var

            if is_active:
                status_icon  = "▶"
                status_color = t["accent"]
            elif has_env_key or no_key_needed:
                status_icon  = "✓"
                status_color = t["success"]
            else:
                status_icon  = "○"
                status_color = t["muted"]

            line = Text()
            line.append(f"  {status_icon} ", Style(color=status_color, bold=True))
            line.append(f"{name:<12}", Style(
                color=t["primary"] if is_active else t["text"],
                bold=is_active
            ))
            line.append(f"  {cls.default_model:<35}", Style(color=t["muted"]))
            if is_active:
                line.append(f"  ← active ({self.provider.model})",
                            Style(color=t["accent"]))
            elif has_env_key:
                line.append(f"  key: {envs[name]}", Style(color=t["muted"]))
            elif not no_key_needed:
                line.append(f"  {env_var}", Style(color=t["muted"]))
            tui.write_output(line)

        self._tui_sep(tui)
        tui.write_output(Text(
            "  /provider <name>       — switch provider\n"
            "  /provider <name> <model> — switch provider and model\n"
            "  /provider setup        — interactive wizard\n",
            Style(color=t["muted"])
        ))

    async def _tui_provider_wizard(self, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        from libercode.providers.registry import PROVIDER_REGISTRY
        t = tui.theme_data

        tui.write_output(Text(
            "\n  Provider Setup Wizard\n",
            Style(color=t["primary"], bold=True)
        ))
        self._tui_sep(tui)
        tui.write_output(Text(
            "  Step 1: choose a provider — "
            "type the name and press Enter\n",
            Style(color=t["muted"])
        ))

        provider_names = list(PROVIDER_REGISTRY.keys())
        tui.show_picker_from_thread("provider_wizard", provider_names)
        self._wizard_state = {"step": 1}

    async def _tui_wizard_step2(self, provider_name: str, tui) -> None:
        from rich.text import Text
        from rich.style import Style
        from libercode.providers.registry import PROVIDER_REGISTRY
        import os
        t = tui.theme_data

        cls, env_var = PROVIDER_REGISTRY.get(provider_name, (None, ""))
        self._wizard_state = {
            "step":     2,
            "provider": provider_name,
            "env_var":  env_var,
            "cls":      cls,
        }

        if not env_var:
            await self._tui_wizard_finish(provider_name, "", tui)
            return

        existing_key = os.environ.get(env_var, "")
        if existing_key:
            tui.write_output(Text(
                f"\n  Found {env_var} in environment.\n"
                f"  Key: {existing_key[:4]}…{existing_key[-4:]}\n",
                Style(color=t["success"])
            ))
            confirmed = await tui.ask_confirm(
                f"Use existing {env_var}?"
            )
            if confirmed:
                await self._tui_wizard_finish(
                    provider_name, existing_key, tui
                )
                return

        tui.write_output(Text(
            f"\n  Enter your {provider_name} API key\n"
            "  (type key and press Enter — it will not be shown):\n",
            Style(color=t["muted"])
        ))
        self._wizard_state["step"] = 3

    async def _tui_wizard_finish(
        self, provider_name: str, api_key: str, tui
    ) -> None:
        from rich.text import Text
        from rich.style import Style
        from libercode.providers.registry import PROVIDER_REGISTRY, build_provider
        t = tui.theme_data

        cls = PROVIDER_REGISTRY.get(provider_name, (None, ""))[0]

        try:
            tmp = build_provider(provider_name, api_key=api_key)
            models = tmp.list_models()
        except Exception:
            models = cls.available_models if cls else []

        tui.write_output(Text(
            f"\n  Step 2: choose a model for {provider_name}\n",
            Style(color=t["muted"])
        ))
        tui.show_picker_from_thread(
            "provider_model", models,
            cls.default_model if cls else ""
        )
        self._wizard_state = {
            "step":     4,
            "provider": provider_name,
            "api_key":  api_key,
        }
