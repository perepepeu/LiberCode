import subprocess
import re
from pathlib import Path
from typing import Optional

VALID_BRANCH_RE = re.compile(r"^[a-zA-Z0-9_./-]+$")


class GitHelper:
    def __init__(self, workdir: str = "."):
        self.workdir = Path(workdir).resolve()

    def _run(self, args: list) -> dict:
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.workdir),
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "exit_code": -1}

    def is_valid_branch_name(self, branch: str) -> bool:
        if not branch or not VALID_BRANCH_RE.match(branch):
            return False
        result = self._run(["check-ref-format", "--branch", branch])
        return result["success"]

    def is_repo(self) -> bool:
        return self._run(["rev-parse", "--git-dir"])["success"]

    def status(self) -> dict:
        return self._run(["status", "--short"])

    def diff(self, staged: bool = False) -> dict:
        args = ["diff"]
        if staged:
            args.append("--cached")
        return self._run(args)

    def log(self, count: int = 10) -> dict:
        return self._run(
            [
                "log",
                f"-{count}",
                "--format=%h %s (%an, %ar)",
                "--no-decorate",
            ]
        )

    def branch(self) -> dict:
        return self._run(["branch", "--show-current"])

    def current_branch(self) -> str:
        try:
            result = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
            return result.get("stdout", "").strip() or "HEAD"
        except Exception:
            return "HEAD"

    def branches(self) -> dict:
        return self._run(["branch", "-a"])

    def commit(self, message: str) -> dict:
        return self._run(["commit", "-m", message])

    def add(self, paths: list) -> dict:
        return self._run(["add"] + paths)

    def diff_commits(self, base: str = "main...HEAD") -> dict:
        return self._run(["diff", base])

    def checkout(self, branch: str) -> dict:
        if not self.is_valid_branch_name(branch):
            return {"success": False, "stdout": "", "stderr": f"Invalid branch name: {branch}", "exit_code": -1}
        return self._run(["checkout", branch])

    def create_branch(self, name: str) -> dict:
        if not self.is_valid_branch_name(name):
            return {"success": False, "stdout": "", "stderr": f"Invalid branch name: {name}", "exit_code": -1}
        return self._run(["checkout", "-b", name])

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> dict:
        args = ["push", "-u", remote]
        if branch:
            args.append(branch)
        return self._run(args)

    def stash(self, message: str = "") -> dict:
        args = ["stash"]
        if message:
            args.extend(["push", "-m", message])
        return self._run(args)

    def stash_pop(self) -> dict:
        return self._run(["stash", "pop"])

    def stash_list(self) -> dict:
        return self._run(["stash", "list"])

    def summary(self) -> str:
        if not self.is_repo():
            return "Not a git repository."

        lines = []
        branch = self.branch()
        if branch["success"]:
            lines.append(f"Branch: {branch['stdout']}")

        status = self.status()
        if status["success"] and status["stdout"]:
            modified = [
                l
                for l in status["stdout"].split("\n")
                if l.startswith(" M") or (len(l) > 1 and l[0] == " " and l[1] == "M")
            ]
            staged = [
                l
                for l in status["stdout"].split("\n")
                if l.startswith("M ")
            ]
            untracked = [l for l in status["stdout"].split("\n") if l.startswith("?")]
            if modified:
                lines.append(f"Modified: {len(modified)} file(s)")
            if staged:
                lines.append(f"Staged: {len(staged)} file(s)")
            if untracked:
                lines.append(f"Untracked: {len(untracked)} file(s)")
        else:
            lines.append("Clean working tree")

        log = self.log(3)
        if log["success"] and log["stdout"]:
            lines.append("Recent commits:")
            for l in log["stdout"].split("\n"):
                lines.append(f"  {l}")

        return "\n".join(lines)
