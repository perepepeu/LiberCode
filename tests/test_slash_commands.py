import json
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
