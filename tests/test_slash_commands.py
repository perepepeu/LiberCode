import json
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from libercode.agent import LiberAgent
from libercode.config import LiberConfig


def make_agent(tmpdir):
    config = LiberConfig()
    config.data_dir = tmpdir
    agent = LiberAgent.__new__(LiberAgent)
    agent.config = config
    agent.mode = "build"
    agent.turn_count = 0
    agent.total_tokens = 0
    agent.session_id = 1
    agent.provider = MagicMock()
    agent.provider.name = "test/model"
    agent.store = MagicMock()
    agent.store.session_start.return_value = 1
    agent.shell = MagicMock()
    agent.shell.workdir = Path(tmpdir)
    agent.shell.read_file.return_value = {"success": True, "content": "file content"}
    agent.shell.write_file.return_value = {"success": True}
    agent.shell.edit_file.return_value = {"success": True}
    agent.shell.run.return_value = {"success": True, "stdout": "ok", "stderr": ""}
    agent.git = MagicMock()
    agent.git.is_repo.return_value = False
    agent.memory = MagicMock()
    agent.memory.all.return_value = []
    agent.tasks = MagicMock()
    agent.tasks.list.return_value = []
    agent.scratch = MagicMock()
    agent.scratch.list.return_value = []
    agent.checkpointer = MagicMock()
    agent.checkpointer.list.return_value = []
    agent.stop_checker = MagicMock()
    agent.console = MagicMock()
    agent._spawn_depth = 0
    return agent


class TestSlashCommands:
    def test_mode_command(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._handle_slash_command("/mode")
        assert result is True
        agent.console.print.assert_called()

    def test_status_command(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._handle_slash_command("/status")
        assert result is True

    def test_undo_no_checkpoints(self):
        agent = make_agent(tempfile.mkdtemp())
        agent.checkpointer.list.return_value = []
        result = agent._handle_slash_command("/undo")
        assert result is True

    def test_context_command(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._handle_slash_command("/context")
        assert result is True

    def test_export_command(self):
        agent = make_agent(tempfile.mkdtemp())
        export_path = str(Path(tempfile.mkdtemp()) / "export.json")
        result = agent._handle_slash_command(f"/export {export_path}")
        assert result is True
        assert Path(export_path).exists()

    def test_import_command(self):
        agent = make_agent(tempfile.mkdtemp())
        import_path = str(Path(tempfile.mkdtemp()) / "import.json")
        data = {"memory": [{"key": "test", "value": "data", "category": "general"}]}
        Path(import_path).write_text(json.dumps(data))
        result = agent._handle_slash_command(f"/import {import_path}")
        assert result is True
        agent.memory.remember.assert_called()

    def test_import_no_file(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._handle_slash_command("/import nonexistent.json")
        assert result is True

    def test_unknown_slash_returns_false(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._handle_slash_command("/unknown")
        assert result is False

    def test_exit_command(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._handle_slash_command("/exit")
        assert result is False

    def test_shell_blocked_in_plan_mode(self):
        agent = make_agent(tempfile.mkdtemp())
        agent.mode = "plan"
        result = agent._exec_shell("ls")
        assert "plan mode" in result.lower()

    def test_tui_memory_command(self):
        agent = make_agent(tempfile.mkdtemp())
        agent.memory.all.return_value = [
            {"key": "stack", "value": "python", "category": "project"}
        ]
        tui = MagicMock()
        tui.theme_data = {
            "primary": "cyan",
            "accent": "blue",
            "muted": "bright_black",
            "text": "white",
            "border": "bright_black",
        }

        asyncio.run(agent.handle_tui_command("memory", "", tui))

        assert tui.write_output.called

    def test_tui_pr_uses_gh_external_command(self):
        agent = make_agent(tempfile.mkdtemp())
        agent.git.is_repo.return_value = True
        agent.provider.chat_stream.return_value = iter([
            "TITLE: Test PR\n\nBODY:\nBody text"
        ])
        tui = MagicMock()
        tui.theme_data = {
            "primary": "cyan",
            "muted": "bright_black",
            "success": "green",
            "accent": "blue",
        }
        git_calls = []
        external_calls = []

        async def confirm(_question):
            return True

        async def fake_run_git(*args):
            git_calls.append(args)
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return "feature/test"
            if args == ("rev-parse", "--verify", "main"):
                return "main"
            if args and args[0] == "push":
                return "pushed"
            return ""

        async def fake_external(*args):
            external_calls.append(args)
            return "https://github.com/example/repo/pull/1"

        agent._run_git = fake_run_git
        agent._run_external_cmd = fake_external
        tui.ask_confirm = confirm

        asyncio.run(agent._tui_cmd_pr("", tui))

        assert external_calls
        assert external_calls[0][:3] == ("gh", "pr", "create")
        assert not any(call and call[0] == "gh" for call in git_calls)
