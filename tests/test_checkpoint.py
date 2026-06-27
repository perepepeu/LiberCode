import os
import tempfile
from unittest.mock import MagicMock
from libercode.checkpoint import Checkpointer


class TestCheckpointer:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MagicMock()
        self.git = MagicMock()
        self.git.is_repo.return_value = False
        self.checkpointer = Checkpointer(self.store, self.tmpdir, self.git)

    def test_save_calls_store(self):
        self.store.checkpoint_list.return_value = []
        cid = self.checkpointer.save(summary="test checkpoint")
        self.store.checkpoint_save.assert_called_once()
        assert cid.startswith("cp_")

    def test_restore_calls_store(self):
        self.store.checkpoint_get.return_value = {"id": "cp_1", "files": {}}
        result = self.checkpointer.restore("cp_1")
        self.store.checkpoint_get.assert_called_once_with("cp_1")

    def test_take_snapshot_limits_file_size(self):
        big_file = os.path.join(self.tmpdir, "big.py")
        with open(big_file, "w") as f:
            f.write("x" * 100000)
        small_file = os.path.join(self.tmpdir, "small.py")
        with open(small_file, "w") as f:
            f.write("print('hello')")
        snapshot = self.checkpointer._take_snapshot()
        assert len(snapshot["files"]["small.py"]) == len("print('hello')")
        assert len(snapshot["files"]["big.py"]) < 100000

    def test_take_snapshot_total_limit(self):
        for i in range(60):
            path = os.path.join(self.tmpdir, f"file{i}.py")
            with open(path, "w") as f:
                f.write("x" * 50000)
        snapshot = self.checkpointer._take_snapshot()
        assert len(snapshot["files"]) <= 50

    def test_git_snapshot_uses_helper(self):
        self.git.is_repo.return_value = True
        self.git.diff.return_value = {"stdout": "diff output"}
        result = self.checkpointer._git_snapshot()
        assert result == "diff output"
        self.git.diff.assert_called_once()
