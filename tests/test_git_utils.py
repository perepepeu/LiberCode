import subprocess
import tempfile
from libercode.git_utils import GitHelper, VALID_BRANCH_RE


class TestGitHelper:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.git = GitHelper(workdir=self.tmpdir)

    def test_is_repo_false(self):
        assert self.git.is_repo() is False

    def test_checkout_invalid_branch(self):
        result = self.git.checkout("branch with spaces")
        assert result["success"] is False
        assert "Invalid branch name" in result["stderr"]

    def test_create_branch_invalid(self):
        result = self.git.create_branch("bad..branch")
        assert result["success"] is False
        assert "Invalid branch name" in result["stderr"]

    def test_summary_not_repo(self):
        summary = self.git.summary()
        assert "Not a git repository" in summary


class TestBranchValidation:
    def test_valid_branch_names(self):
        assert VALID_BRANCH_RE.match("main") is not None
        assert VALID_BRANCH_RE.match("feature/my-feature") is not None
        assert VALID_BRANCH_RE.match("fix-123") is not None
        assert VALID_BRANCH_RE.match("release/v1.0") is not None

    def test_invalid_branch_names(self):
        assert VALID_BRANCH_RE.match("branch with spaces") is None
        assert VALID_BRANCH_RE.match("") is None
        assert VALID_BRANCH_RE.match("~branch") is None
        assert VALID_BRANCH_RE.match("branch\0null") is None

    def test_git_ref_validation_rejects_bad_dot_branch(self):
        tmpdir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, text=True)
        git = GitHelper(workdir=tmpdir)
        assert git.is_valid_branch_name("feature/good") is True
        assert git.is_valid_branch_name("bad..branch") is False
