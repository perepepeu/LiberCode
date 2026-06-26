import subprocess
import os
import shlex
from pathlib import Path


class ShellExecutor:
    def __init__(self, workdir: str = "."):
        self.workdir = Path(workdir).resolve()

    def run(self, command: str, timeout: int = 120) -> dict:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workdir),
                env={**os.environ, "PWD": str(self.workdir)},
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "success": False,
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }

    def run_interactive(self, command: str) -> int:
        return subprocess.call(command, shell=True, cwd=str(self.workdir))

    def read_file(self, path: str) -> dict:
        full_path = self.workdir / path
        if not full_path.exists():
            return {"success": False, "error": f"File not found: {path}"}
        if not full_path.is_file():
            return {"success": False, "error": f"Not a file: {path}"}
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            return {"success": True, "content": content, "path": str(full_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        full_path = self.workdir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            full_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(full_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def edit_file(self, path: str, old_string: str, new_string: str) -> dict:
        result = self.read_file(path)
        if not result["success"]:
            return result
        content = result["content"]
        if old_string not in content:
            return {
                "success": False,
                "error": f"Could not find text to replace in {path}",
            }
        new_content = content.replace(old_string, new_string, 1)
        return self.write_file(path, new_content)

    def list_files(self, path: str = ".") -> dict:
        full_path = (self.workdir / path).resolve()
        if not full_path.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        try:
            entries = []
            for entry in sorted(full_path.iterdir()):
                suffix = "/" if entry.is_dir() else ""
                entries.append(f"{entry.name}{suffix}")
            return {"success": True, "entries": entries, "path": str(full_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def grep(self, pattern: str, path: str = ".", include: str = "") -> dict:
        full_path = (self.workdir / path).resolve()
        cmd = ["rg", "-n", pattern, str(full_path)]
        if include:
            cmd.extend(["-g", include])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode in (0, 1):
                lines = [l for l in result.stdout.split("\n") if l.strip()]
                return {"success": True, "matches": lines}
            return {"success": False, "error": result.stderr}
        except FileNotFoundError:
            return self._grep_fallback(pattern, path, include)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _grep_fallback(self, pattern: str, path: str, include: str) -> dict:
        cmd = ["grep", "-rn", pattern, str(self.workdir / path)]
        if include:
            cmd.extend(["--include", include])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            lines = [l for l in result.stdout.split("\n") if l.strip()]
            return {"success": True, "matches": lines}
        except Exception as e:
            return {"success": False, "error": str(e)}
