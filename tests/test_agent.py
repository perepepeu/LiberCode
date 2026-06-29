import os
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
    agent.shell.read_file.return_value = {"success": True, "content": "file content"}
    agent.shell.write_file.return_value = {"success": True}
    agent.shell.edit_file.return_value = {"success": True}
    agent.shell.run.return_value = {"success": True, "stdout": "ok", "stderr": ""}
    agent.git = MagicMock()
    agent.memory = MagicMock()
    agent.tasks = MagicMock()
    agent.scratch = MagicMock()
    agent.checkpointer = MagicMock()
    agent.stop_checker = MagicMock()
    agent.console = MagicMock()
    agent.tui_ui = None
    agent.VALID_MODES = ["build", "plan", "spec", "debug"]
    return agent


class TestToolCallParser:
    def test_xml_shell(self):
        agent = make_agent(tempfile.mkdtemp())
        text = '<tool name="shell">echo test</tool>'
        result = agent._process_tool_call(text)
        agent.shell.run.assert_called_once_with("echo test")

    def test_xml_file_read(self):
        agent = make_agent(tempfile.mkdtemp())
        text = '<tool name="file:read">test.txt</tool>'
        result = agent._process_tool_call(text)
        agent.shell.read_file.assert_called_once_with("test.txt")

    def test_xml_file_write(self):
        agent = make_agent(tempfile.mkdtemp())
        text = '<tool name="file:write">output.txt\nhello world</tool>'
        result = agent._process_tool_call(text)
        # New _write_file writes directly, not through shell.write_file
        # Just verify it returns a success-like string
        assert result is not None
        assert "output.txt" in result

    def test_xml_file_edit(self):
        agent = make_agent(tempfile.mkdtemp())
        text = '<tool name="file:edit">test.txt ||| old ||| new</tool>'
        result = agent._process_tool_call(text)
        agent.shell.edit_file.assert_called_once_with("test.txt", "old", "new")

    def test_legacy_shell(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._process_tool_call("!ls -la")
        agent.shell.run.assert_called_once_with("ls -la")

    def test_legacy_file_read(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._process_tool_call("file:read test.txt")
        agent.shell.read_file.assert_called_once_with("test.txt")

    def test_no_tool_call(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._process_tool_call("just some text with no tool")
        assert result is None

    def test_mode_tool_accepts_debug(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._process_tool_call("mode debug")
        assert result is None
        assert agent.mode == "debug"
        agent.store.session_update_mode.assert_called_once_with(1, "debug")

    def test_path_traversal_read_blocked(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._read_file("../../../etc/passwd")
        assert "traversal blocked" in result.lower()

    def test_path_traversal_write_blocked(self):
        agent = make_agent(tempfile.mkdtemp())
        result = agent._write_file("../../../tmp/evil.txt", "payload")
        assert "traversal blocked" in result.lower()

    def test_path_traversal_read_safe(self):
        agent = make_agent(tempfile.mkdtemp())
        agent.shell.read_file.return_value = {
            "success": True,
            "content": "safe",
            "path": str(Path(tempfile.mkdtemp()) / "safe.txt"),
        }
        agent.shell.workdir = Path(tempfile.mkdtemp())
        result = agent._read_file("safe.txt")
        assert "safe" in result

    def test_extract_xml_tool_call(self):
        agent = make_agent(tempfile.mkdtemp())
        response = "Let me check that.\n<tool name=\"shell\">ls</tool>\nDone."
        result = agent._extract_next_tool_call(response)
        assert result is not None
        assert "shell" in result

    def test_extract_legacy_tool_call(self):
        agent = make_agent(tempfile.mkdtemp())
        response = "!echo hello"
        result = agent._extract_next_tool_call(response)
        assert result == "!echo hello"


class TestBuildMessages:
    def test_truncation_warning(self):
        agent = make_agent(tempfile.mkdtemp())
        history = [{"role": "user", "content": f"msg {i}"} for i in range(25)]
        messages = agent._build_messages("final", history)
        assert any("truncated" in m["content"].lower() for m in messages if m["role"] == "system")

    def test_no_truncation_small_history(self):
        agent = make_agent(tempfile.mkdtemp())
        history = [{"role": "user", "content": "hello"}]
        messages = agent._build_messages("final", history)
        assert not any(m.get("role") == "system" and "truncated" in m.get("content", "").lower() for m in messages)
