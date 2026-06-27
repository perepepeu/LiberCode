import os
import sys
import tempfile
from libercode.shell import ShellExecutor


class TestShellExecutor:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.shell = ShellExecutor(workdir=self.tmpdir)

    def test_run_success(self):
        result = self.shell.run("echo hello")
        assert result["success"] is True
        assert "hello" in result["stdout"]

    def test_run_failure(self):
        result = self.shell.run("exit 1")
        assert result["success"] is False
        assert result["exit_code"] == 1

    def test_run_timeout(self):
        cmd = "ping -n 10 127.0.0.1" if sys.platform == "win32" else "sleep 10"
        result = self.shell.run(cmd, timeout=1)
        assert result["success"] is False
        assert "timed out" in result["stderr"].lower()

    def test_read_file(self):
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w") as f:
            f.write("content here")
        result = self.shell.read_file("test.txt")
        assert result["success"] is True
        assert result["content"] == "content here"

    def test_read_file_not_found(self):
        result = self.shell.read_file("nonexistent.txt")
        assert result["success"] is False

    def test_write_file(self):
        result = self.shell.write_file("new.txt", "hello world")
        assert result["success"] is True
        path = os.path.join(self.tmpdir, "new.txt")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "hello world"

    def test_edit_file(self):
        path = os.path.join(self.tmpdir, "edit.txt")
        with open(path, "w") as f:
            f.write("foo bar baz")
        result = self.shell.edit_file("edit.txt", "bar", "qux")
        assert result["success"] is True
        with open(path) as f:
            assert f.read() == "foo qux baz"

    def test_edit_file_not_found(self):
        result = self.shell.edit_file("missing.txt", "a", "b")
        assert result["success"] is False

    def test_edit_file_old_not_found(self):
        path = os.path.join(self.tmpdir, "noedit.txt")
        with open(path, "w") as f:
            f.write("something")
        result = self.shell.edit_file("noedit.txt", "not_there", "new")
        assert result["success"] is False

    def test_list_files(self):
        os.makedirs(os.path.join(self.tmpdir, "subdir"))
        with open(os.path.join(self.tmpdir, "a.txt"), "w") as f:
            f.write("")
        result = self.shell.list_files()
        assert result["success"] is True
        assert "a.txt" in result["entries"]
        assert "subdir/" in result["entries"]
