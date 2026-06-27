import sys
import time
from pathlib import Path
from typing import Optional

import tiktoken
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from rich import box
import sys as _sys
from prompt_toolkit import PromptSession as PTSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.output import create_output
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.input import create_input

from libercode.config import LiberConfig
from libercode.providers import BuiltinProvider, CustomProvider
from libercode.storage.sqlite_store import SqliteStore
from libercode.storage.file_store import FileStore
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
        self.checkpointer = Checkpointer(self.store, str(project_root))
        self.tasks = TaskTracker(self.store)
        self.scratch = ScratchNotes(self.store)
        self.stop_checker = StopConditionChecker(
            self.store, self.shell, self.git, self.memory
        )
        self.stop_checker.set_provider(self.provider)

        self.mode = config.mode
        self.provider = self._init_provider()
        self.session_id = self._init_session(project_root)
        self.turn_count = 0
        self.total_tokens = 0
        try:
            self._enc = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def _init_provider(self):
        pc = self.config.provider
        if pc.name == "builtin":
            return BuiltinProvider(
                model=self.config.builtin_model,
                api_base=self.config.builtin_api_base,
            )
        else:
            return CustomProvider(
                name=pc.name,
                api_key=pc.api_key,
                api_base=pc.api_base,
                model=pc.model,
                max_tokens=pc.max_tokens,
                temperature=pc.temperature,
            )

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

        memory_items = self.memory.all()
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
                return f"[Memory] Key not found. Use `memory key = value`"

            if stripped.startswith("git "):
                cmd = stripped[len("git ") :].strip()
                return self._exec_shell(f"git {cmd}")

            if stripped.startswith("mode "):
                new_mode = stripped[len("mode ") :].strip()
                if new_mode in ("build", "plan", "spec"):
                    self.mode = new_mode
                    self.store.session_update_mode(self.session_id, new_mode)
                    return None
                return f"[Mode] Invalid mode. Use build, plan, or spec."

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
            return f"[Memory] Key not found. Use `memory key = value`"
        if name == "git":
            return self._exec_shell(f"git {body.strip()}")
        if name == "mode":
            new_mode = body.strip()
            if new_mode in ("build", "plan", "spec"):
                self.mode = new_mode
                self.store.session_update_mode(self.session_id, new_mode)
                return None
            return f"[Mode] Invalid mode. Use build, plan, or spec."
        if name == "agent:spawn":
            return self._spawn_subagent(body.strip())
        return None

    def _exec_shell(self, cmd: str) -> str:
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
            if not str(real_path).startswith(str(workdir)):
                return f"[Error] Path traversal blocked: {path}"
            content = result["content"]
            if len(content) > 4000:
                content = content[:2000] + "\n... [truncated] ...\n" + content[-2000:]
            return f"[File] {path}\n```\n{content}\n```"
        return f"[Error] {result.get('error', 'Read failed')}"

    def _write_file(self, path: str, content: str) -> str:
        if self.mode == "plan":
            return "[Error] Cannot write files in plan mode."
        target = Path(self.shell.workdir) / path
        if not target.resolve().is_relative_to(Path(self.shell.workdir).resolve()):
            return f"[Error] Path traversal blocked: {path}"
        result = self.shell.write_file(path, content)
        if result["success"]:
            self.memory.auto_store_context(
                f"file:{path}", f"Created/updated with {len(content)} chars"
            )
            if (
                self.config.enable_checkpoints
                and self.turn_count % self.config.checkpoint_interval == 0
            ):
                self.checkpointer.save(summary=f"wrote {path}")
            return f"[File] Written {len(content)} bytes to {path}"
        return f"[Error] {result.get('error', 'Write failed')}"

    def _edit_file(self, path: str, old: str, new: str) -> str:
        if self.mode == "plan":
            return "[Error] Cannot edit files in plan mode."
        result = self.shell.edit_file(path, old, new)
        if result["success"]:
            self.memory.auto_store_context(f"edit:{path}", f"Edited (replaced text)")
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

    def _spawn_subagent(self, task_desc: str) -> str:
        if self.mode == "plan":
            return "[Error] Cannot spawn agents in plan mode."
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
        response = self.provider.chat(
            messages,
            system="You are a helpful coding sub-agent. Be concise and focused.",
        )

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
        mode_cycle = {"build": "plan", "plan": "spec", "spec": "build"}

        @kb.add("tab")
        def _(event):
            new = mode_cycle[self.mode]
            self.mode = new
            self.store.session_update_mode(self.session_id, new)
            event.app.current_buffer.text = ""
            event.app.invalidate()

        @kb.add("s-tab")
        def _(event):
            rev = {"build": "spec", "plan": "build", "spec": "plan"}
            new = rev[self.mode]
            self.mode = new
            self.store.session_update_mode(self.session_id, new)
            event.app.current_buffer.text = ""
            event.app.invalidate()

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
        mode_color = {"build": "32", "plan": "33", "spec": "34"}.get(self.mode, "37")
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
        return {"build": "32", "plan": "33", "spec": "34"}.get(self.mode, "37")

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

            history.append({"role": "assistant", "content": full_response})
            if user_input.strip():
                history.append({"role": "user", "content": user_input})

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
        return {"build": "green", "plan": "yellow", "spec": "blue"}.get(
            self.mode, "white"
        )
