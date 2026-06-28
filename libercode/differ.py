# libercode/differ.py
"""Utilities for computing and rendering unified diffs."""
import difflib
from pathlib import Path
from rich.text import Text
from rich.style import Style


def compute_diff(path: str, new_content: str) -> list[tuple[str, str]]:
    """
    Return a list of (line, kind) tuples where kind is one of:
    'add', 'del', 'ctx', 'hdr'.
    If the file does not exist yet, every line is 'add'.
    """
    try:
        old = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        old = []

    new = new_content.splitlines(keepends=True)

    lines = []
    diff  = difflib.unified_diff(
        old, new,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            lines.append((line, "hdr"))
        elif line.startswith("@@"):
            lines.append((line, "hdr"))
        elif line.startswith("+"):
            lines.append((line, "add"))
        elif line.startswith("-"):
            lines.append((line, "del"))
        else:
            lines.append((line, "ctx"))
    return lines


def render_diff(diff_lines: list[tuple[str, str]], theme: dict) -> Text:
    """
    Render a list of (line, kind) tuples as a Rich Text object.
    theme must contain keys: success, error, muted, text.
    """
    out = Text()
    for line, kind in diff_lines:
        if kind == "add":
            out.append(line.rstrip("\n") + "\n",
                       Style(color=theme["success"]))
        elif kind == "del":
            out.append(line.rstrip("\n") + "\n",
                       Style(color=theme["error"]))
        elif kind == "hdr":
            out.append(line.rstrip("\n") + "\n",
                       Style(color=theme["muted"], bold=True))
        else:
            out.append(line.rstrip("\n") + "\n",
                       Style(color=theme["text"]))
    return out
