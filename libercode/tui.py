import asyncio
import re
from datetime import datetime
from pathlib import Path

from rich.align import Align
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

THEMES = {

    # ── Dracula ────────────────────────────────────────────
    "dracula": {
        "bg":         "#282a36",
        "bg_panel":   "#21232f",
        "bg_input":   "#1e2029",
        "text":       "#e6e6e1",
        "muted":      "#6272a4",
        "border":     "#44475a",
        "border_act": "#bd93f9",
        "primary":    "#bd93f9",
        "secondary":  "#ff79c6",
        "accent":     "#8be9fd",
        "success":    "#50fa7b",
        "warning":    "#ffb86c",
        "error":      "#ff5555",
        "info":       "#8be9fd",
        "user_icon": "◈", "ai_icon": "◆", "syntax": "dracula",
    },

    # ── Gruvbox ────────────────────────────────────────────
    "gruvbox": {
        "bg":         "#1d2021",
        "bg_panel":   "#282828",
        "bg_input":   "#32302f",
        "text":       "#e0cfa0",
        "muted":      "#7c6f64",
        "border":     "#3c3836",
        "border_act": "#fabd2f",
        "primary":    "#d79921",
        "secondary":  "#83a598",
        "accent":     "#b8bb26",
        "success":    "#b8bb26",
        "warning":    "#fe8019",
        "error":      "#cc241d",
        "info":       "#83a598",
        "user_icon": "◈", "ai_icon": "◆", "syntax": "monokai",
    },

    # ── Nord ───────────────────────────────────────────────
    "nord": {
        "bg":         "#252a35",
        "bg_panel":   "#434c5e",
        "bg_input":   "#2e3440",
        "text":       "#eceff4",
        "muted":      "#5b6575",
        "border":     "#3b4252",
        "border_act": "#88c0d0",
        "primary":    "#88c0d0",
        "secondary":  "#81a1c1",
        "accent":     "#a3be8c",
        "success":    "#a3be8c",
        "warning":    "#ebcb8b",
        "error":      "#bf616a",
        "info":       "#5e81ac",
        "user_icon": "›", "ai_icon": "◇", "syntax": "nord",
    },

    # ── Solarized Dark ─────────────────────────────────────
    "solarized": {
        "bg":         "#002b36",
        "bg_panel":   "#073642",
        "bg_input":   "#002b36",
        "text":       "#eee8d5",
        "muted":      "#657b83",
        "border":     "#073642",
        "border_act": "#268bd2",
        "primary":    "#268bd2",
        "secondary":  "#2aa198",
        "accent":     "#b58900",
        "success":    "#859900",
        "warning":    "#cb4b16",
        "error":      "#dc322f",
        "info":       "#6c71c4",
        "user_icon": "›", "ai_icon": "◇", "syntax": "monokai",
    },

    # ── One Dark Pro ───────────────────────────────────────
    "onedark": {
        "bg":         "#1b1f27",
        "bg_panel":   "#282c34",
        "bg_input":   "#21252b",
        "text":       "#abb2bf",
        "muted":      "#5c6370",
        "border":     "#3e4452",
        "border_act": "#61afef",
        "primary":    "#61afef",
        "secondary":  "#c678dd",
        "accent":     "#98c379",
        "success":    "#89d07a",
        "warning":    "#e5c07b",
        "error":      "#e06c75",
        "info":       "#56b6c2",
        "user_icon": "›", "ai_icon": "✦", "syntax": "monokai",
    },

    # ── Rosé Pine ──────────────────────────────────────────
    "rosepine": {
        "bg":         "#191724",
        "bg_panel":   "#26233a",
        "bg_input":   "#1f1d2e",
        "text":       "#e0def4",
        "muted":      "#6e6a86",
        "border":     "#403d52",
        "border_act": "#c4a7e7",
        "primary":    "#c4a7e7",
        "secondary":  "#ebbcba",
        "accent":     "#f6c177",
        "success":    "#9ccfd8",
        "warning":    "#e3b167",
        "error":      "#eb6f92",
        "info":       "#9ccfd8",
        "user_icon": "•", "ai_icon": "◆", "syntax": "monokai",
    },

    # ── White (GitHub Light) ───────────────────────────────
    "white": {
        "bg":         "#ffffff",
        "bg_panel":   "#f6f8fa",
        "bg_input":   "#fdfefe",
        "text":       "#24292f",
        "muted":      "#8c959f",
        "border":     "#d0d7de",
        "border_act": "#0969da",
        "primary":    "#0969da",
        "secondary":  "#8250df",
        "accent":     "#0550ae",
        "success":    "#1a7f37",
        "warning":    "#9a6700",
        "error":      "#cf222e",
        "info":       "#57a0ff",
        "user_icon": "›", "ai_icon": "◆", "syntax": "monokai",
    },

}

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

COMMANDS = [
    ("/help",      "Show all available commands",          "info"),
    ("/clear",     "Clear current session history",        "warning"),
    ("/undo",      "Restore last checkpoint",              "warning"),
    ("/context",   "Show current system prompt",           "muted"),
    ("/export",    "Export session to file",               "success"),
    ("/import",    "Import memory from file",              "success"),
    ("/model",     "Switch AI model",                      "accent"),
    ("/theme",     "Cycle to next theme",                  "accent"),
    ("/mode",      "Switch mode (build/plan/spec/debug)",  "primary"),
    ("/tasks",     "List current tasks",                   "muted"),
    ("/memory",    "Show stored memory entries",           "muted"),
    ("/git",       "Show git status summary",              "muted"),
    ("/stash",     "Git stash current changes",            "muted"),
    ("/pop",       "Git stash pop",                        "muted"),
    ("/sessions",  "List and restore past sessions",       "info"),
    ("/session",   "Start a new session",                  "warning"),
    ("/checkpoint","Save a manual project checkpoint",     "success"),
    ("/restore",   "List and restore a past checkpoint",   "warning"),
    ("/scratch",   "View scratch notes",                   "muted"),
    ("/search",    "Search conversation history",          "info"),
    ("/pr",        "Create a GitHub pull request",         "success"),
    ("/review",    "Review the current git diff",          "warning"),
    ("/test",      "Run tests (auto-detected runner)",     "success"),
    ("/lint",      "Run linter (auto-detected runner)",    "warning"),
    ("/config",    "View and edit configuration",          "info"),
    ("/provider",  "Switch AI provider at runtime",         "primary"),
    ("/quit",      "Exit libercode",                       "error"),
]

DEFAULT_MODEL = "Qwen2.5-Coder-7B-Instruct"

COMMAND_ARGS: dict[str, list[str]] = {
    "mode":     ["build", "plan", "spec", "debug"],
    "model":    [],
    "sessions": [],
    "restore":  [],
    "theme":    ["dracula", "gruvbox", "nord", "solarized",
                 "onedark", "rosepine", "white"],
}

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

LOGO_LINES = [
    "██╗     ██╗██████╗ ███████╗██████╗  ██████╗ ██████╗ ██████╗ ███████╗",
    "██║     ██║██╔══██╗██╔════╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "██║     ██║██████╔╝█████╗  ██████╔╝██║     ██║   ██║██║  ██║█████╗  ",
    "██║     ██║██╔══██╗██╔══╝  ██╔══██╗██║     ██║   ██║██║  ██║██╔══╝  ",
    "███████╗██║██████╔╝███████╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗",
    "╚══════╝╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
]


def _detect_lang(filename: str, content: str = "") -> str:
    """
    Detect programming language for syntax highlighting.
    Checks filename extension first, then content heuristics.
    Returns a Pygments lexer alias string.
    """
    import os
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "tsx", ".jsx": "jsx", ".rs": "rust", ".go": "go",
        ".java": "java", ".c": "c", ".cpp": "cpp", ".cs": "csharp",
        ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin",
        ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".fish": "fish",
        ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
        ".md": "markdown", ".sql": "sql", ".xml": "xml",
    }
    if filename:
        _, ext = os.path.splitext(filename.lower())
        if ext in ext_map:
            return ext_map[ext]
        base = os.path.basename(filename.lower())
        if base in ("dockerfile", "makefile", "rakefile"):
            return base
    head = content[:300].lower() if content else ""
    if head.startswith("#!/usr/bin/env python") or "def " in head or "import " in head:
        return "python"
    if head.startswith("#!/bin/bash") or head.startswith("#!/bin/sh"):
        return "bash"
    if "function " in head and ("{" in head or "=>" in head):
        return "javascript"
    if head.startswith("package main") or "func " in head:
        return "go"
    if head.startswith("use strict") or "fn " in head:
        return "rust"
    if "<html" in head or "<!doctype" in head:
        return "html"
    if head.strip().startswith("{") or head.strip().startswith("["):
        return "json"
    if "select " in head and "from " in head:
        return "sql"
    return "text"


class CommandEvent(Message):
    """Posted when the user selects a slash command from the palette."""
    def __init__(self, command: str, args: str = "") -> None:
        self.command = command
        self.args = args
        super().__init__()


class ShowPickerEvent(Message):
    """Posted by agent to ask UI to show a selection picker."""
    def __init__(self, kind: str, items: list, current: str = "") -> None:
        self.kind = kind
        self.items = items
        self.current = current
        super().__init__()


class PickerSelectedEvent(Message):
    """Posted by UI when user picks an item from the picker."""
    def __init__(self, kind: str, value: str) -> None:
        self.kind = kind
        self.value = value
        super().__init__()


class ProviderModal(ModalScreen):
    """Centered floating provider picker with live search."""

    BINDINGS = [
        Binding("escape", "dismiss_none", "Close",  priority=True),
        Binding("up",     "cursor_up",   "Up",   show=False, priority=True),
        Binding("down",   "cursor_down", "Down", show=False, priority=True),
        Binding("enter",  "confirm",     "Select"),
    ]

    CSS = """
    ProviderModal {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }
    #provider-modal-container {
        width: 62;
        height: auto;
        max-height: 36;
        background: #1e1f29;
        border: round #bd93f9;
        padding: 0;
    }
    #provider-modal-title {
        width: 1fr;
        content-align: center middle;
        background: #bd93f9;
        color: #282a36;
        text-style: bold;
        height: 1;
        padding: 0 2;
    }
    #modal-search {
        width: 1fr;
        border: none;
        border-bottom: solid #6272a4;
        background: #21222c;
        color: #f8f8f2;
        padding: 0 2;
        height: 3;
    }
    #modal-search:focus {
        border-bottom: solid #50fa7b;
    }
    #provider-list {
        width: 1fr;
        height: auto;
        max-height: 24;
        background: #1e1f29;
    }
    #provider-modal-footer {
        width: 1fr;
        height: 1;
        background: #282a36;
        color: #6272a4;
        content-align: center middle;
        padding: 0 2;
    }
    """

    def __init__(self, providers: list[dict], current: str) -> None:
        """
        providers: list of dicts with keys:
            name, default_model, status ("active"|"ready"|"unconfigured"),
            detail (masked key or env var name or "local")
        current: name of the active provider
        """
        super().__init__()
        self._all_providers = providers
        self._filtered = list(providers)
        self._current = current
        self._cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-modal-container"):
            yield Static("  ⚡  Switch Provider", id="provider-modal-title")
            yield Input(placeholder="  Search providers…", id="modal-search")
            yield OptionList(id="provider-list")
            yield Static(
                "↑↓ navigate    Enter select    Esc close",
                id="provider-modal-footer"
            )

    def on_mount(self) -> None:
        t = self.app.theme_data
        try:
            container = self.query_one("#provider-modal-container")
            container.styles.background = t["bg_panel"]
            container.styles.border = ("round", t["primary"])
            title = self.query_one("#provider-modal-title")
            title.styles.background = t["primary"]
            title.styles.color = t["bg"]
            search = self.query_one("#modal-search", Input)
            search.styles.background = t["bg_input"]
            search.styles.color = t["text"]
            search.styles.border_bottom = ("solid", t["border"])
            footer = self.query_one("#provider-modal-footer")
            footer.styles.background = t["bg"]
            footer.styles.color = t["muted"]
        except Exception:
            pass
        self._rebuild_list()
        self.query_one("#modal-search", Input).focus()

    def _rebuild_list(self, query: str = "") -> None:
        from rich.text import Text
        from rich.style import Style
        from textual.widgets._option_list import Option

        q = query.lower().strip()
        self._filtered = [
            p for p in self._all_providers
            if not q
            or q in p["name"].lower()
            or q in p["default_model"].lower()
        ]

        ol = self.query_one("#provider-list", OptionList)
        ol.clear_options()

        for i, p in enumerate(self._filtered):
            name    = p["name"]
            model   = p["default_model"]
            status  = p["status"]
            detail  = p["detail"]

            if status == "active":
                icon  = "▶"
                color = "accent"
            elif status == "ready":
                icon  = "✓"
                color = "success"
            else:
                icon  = "○"
                color = "muted"

            line = Text()
            line.append(f"  {icon} ", Style(bold=True))
            line.append(f"{name:<12}", Style(bold=(status == "active")))
            line.append(f"  {model:<32}", Style(dim=True))
            line.append(f"  {detail}", Style(dim=True))

            ol.add_option(Option(line, id=name))

        self._cursor = min(self._cursor, max(0, len(self._filtered) - 1))
        if self._filtered:
            try:
                ol.highlighted = self._cursor
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "modal-search":
            self._cursor = 0
            self._rebuild_list(event.value)

    def on_option_list_option_highlighted(self, event) -> None:
        self._cursor = event.option_index

    def action_cursor_up(self) -> None:
        if self._cursor > 0:
            self._cursor -= 1
            self.query_one("#provider-list", OptionList).highlighted = self._cursor

    def action_cursor_down(self) -> None:
        if self._cursor < len(self._filtered) - 1:
            self._cursor += 1
            self.query_one("#provider-list", OptionList).highlighted = self._cursor

    def action_confirm(self) -> None:
        if self._filtered:
            selected = self._filtered[self._cursor]
            self.dismiss(selected["name"])

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event) -> None:
        if event.option.id:
            self.dismiss(event.option.id)


class ModelModal(ModalScreen):
    """Centered floating model picker with live search and lazy load."""

    BINDINGS = [
        Binding("escape", "dismiss_none", "Close",  priority=True),
        Binding("up",     "cursor_up",    "Up",   show=False, priority=True),
        Binding("down",   "cursor_down",  "Down", show=False, priority=True),
        Binding("enter",  "confirm",      "Select"),
    ]

    CSS = """
    ModelModal {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }
    #provider-modal-container {
        width: 62;
        height: auto;
        max-height: 36;
        background: #1e1f29;
        border: round #bd93f9;
        padding: 0;
    }
    #provider-modal-title {
        width: 1fr;
        content-align: center middle;
        background: #bd93f9;
        color: #282a36;
        text-style: bold;
        height: 1;
        padding: 0 2;
    }
    #modal-search, #model-search {
        width: 1fr;
        border: none;
        border-bottom: solid #6272a4;
        background: #21222c;
        color: #f8f8f2;
        padding: 0 2;
        height: 3;
    }
    #modal-search:focus, #model-search:focus {
        border-bottom: solid #50fa7b;
    }
    #model-list {
        width: 1fr;
        height: auto;
        max-height: 24;
        background: #1e1f29;
    }
    #provider-modal-footer {
        width: 1fr;
        height: 1;
        background: #282a36;
        color: #6272a4;
        content-align: center middle;
        padding: 0 2;
    }
    """

    def __init__(
        self,
        provider_name: str,
        current_model: str,
        models: list[str],
    ) -> None:
        super().__init__()
        self._provider_name = provider_name
        self._current_model = current_model
        self._all_models = list(models)
        self._filtered = list(models)
        self._cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-modal-container"):
            yield Static(
                f"  ⚡  Select Model  ·  {self._provider_name}",
                id="provider-modal-title"
            )
            yield Input(placeholder="  Search models…", id="model-search")
            yield OptionList(id="model-list")
            yield Static(
                "↑↓ navigate    Enter select    Esc close",
                id="provider-modal-footer"
            )

    def on_mount(self) -> None:
        t = self.app.theme_data
        try:
            container = self.query_one("#provider-modal-container")
            container.styles.background = t["bg_panel"]
            container.styles.border = ("round", t["primary"])
            title = self.query_one("#provider-modal-title")
            title.styles.background = t["primary"]
            title.styles.color = t["bg"]
            search = self.query_one("#model-search", Input)
            search.styles.background = t["bg_input"]
            search.styles.color = t["text"]
            search.styles.border_bottom = ("solid", t["border"])
            footer = self.query_one("#provider-modal-footer")
            footer.styles.background = t["bg"]
            footer.styles.color = t["muted"]
        except Exception:
            pass
        self._rebuild_list()
        self.query_one("#model-search", Input).focus()

    def set_models(self, models: list[str]) -> None:
        self._all_models = models
        query = ""
        try:
            query = self.query_one("#model-search", Input).value
        except Exception:
            pass
        self._rebuild_list(query)

    def _rebuild_list(self, query: str = "") -> None:
        from rich.text import Text
        from rich.style import Style
        from textual.widgets._option_list import Option

        q = query.lower().strip()
        self._filtered = [
            m for m in self._all_models
            if not q or q in m.lower()
        ]

        ol = self.query_one("#model-list", OptionList)
        ol.clear_options()

        for m in self._filtered:
            is_current = (m == self._current_model)
            line = Text()
            line.append("  ▶ " if is_current else "    ")
            line.append(m, Style(bold=is_current))
            ol.add_option(Option(line, id=m))

        self._cursor = min(self._cursor, max(0, len(self._filtered) - 1))
        if self._filtered:
            try:
                ol.highlighted = self._cursor
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-search":
            self._cursor = 0
            self._rebuild_list(event.value)

    def on_option_list_option_highlighted(self, event) -> None:
        self._cursor = event.option_index

    def action_cursor_up(self) -> None:
        if self._cursor > 0:
            self._cursor -= 1
            self.query_one("#model-list", OptionList).highlighted = self._cursor

    def action_cursor_down(self) -> None:
        if self._cursor < len(self._filtered) - 1:
            self._cursor += 1
            self.query_one("#model-list", OptionList).highlighted = self._cursor

    def action_confirm(self) -> None:
        if self._filtered:
            self.dismiss(self._filtered[self._cursor])

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event) -> None:
        if event.option.id:
            self.dismiss(event.option.id)


class APIKeyModal(ModalScreen):
    """Centered modal for entering an API key."""

    BINDINGS = [
        Binding("escape", "dismiss_none", "Close", priority=True),
        Binding("enter",  "confirm",      "Submit", priority=True),
    ]

    CSS = """
    APIKeyModal {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }
    #api-key-container {
        width: 50;
        height: auto;
        background: #1e1f29;
        border: round #bd93f9;
        padding: 1 2;
    }
    #api-key-title {
        width: 1fr;
        text-align: center;
        color: #bd93f9;
        text-style: bold;
        margin-bottom: 1;
    }
    #api-key-hint {
        width: 1fr;
        color: #6272a4;
        margin-bottom: 1;
    }
    #api-key-input {
        width: 1fr;
        background: #21222c;
        color: #f8f8f2;
        border: round #6272a4;
        padding: 0 1;
    }
    #api-key-input:focus {
        border: round #bd93f9;
    }
    #api-key-footer {
        width: 1fr;
        color: #6272a4;
        text-align: center;
        margin-top: 1;
    }
    #api-key-btn-row {
        width: 1fr;
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #api-key-confirm {
        min-width: 12;
    }
    #api-key-cancel {
        min-width: 12;
    }
    """

    def __init__(self, provider_name: str) -> None:
        super().__init__()
        self._provider_name = provider_name

    def compose(self) -> ComposeResult:
        with Vertical(id="api-key-container"):
            yield Static(
                f"  Enter API Key for {self._provider_name.upper()}",
                id="api-key-title"
            )
            yield Static(
                "  Your key is saved locally and never sent anywhere else.",
                id="api-key-hint"
            )
            yield Input(
                placeholder="  sk-... or nvapi-...",
                password=True,
                id="api-key-input"
            )
            with Horizontal(id="api-key-btn-row"):
                yield Button("  Confirm  ", id="api-key-confirm", variant="primary")
                yield Button("  Cancel   ", id="api-key-cancel")
            yield Static(
                "  Enter submit    Esc cancel",
                id="api-key-footer"
            )

    def on_mount(self) -> None:
        t = self.app.theme_data
        try:
            container = self.query_one("#api-key-container")
            container.styles.background = t["bg_panel"]
            container.styles.border = ("round", t["primary"])
            title = self.query_one("#api-key-title")
            title.styles.color = t["primary"]
            hint = self.query_one("#api-key-hint")
            hint.styles.color = t["muted"]
            inp = self.query_one("#api-key-input", Input)
            inp.styles.background = t["bg_input"]
            inp.styles.color = t["text"]
            inp.styles.border = ("round", t["border"])
            footer = self.query_one("#api-key-footer")
            footer.styles.color = t["muted"]
        except Exception:
            pass
        self.query_one("#api-key-input", Input).focus()

    def action_confirm(self) -> None:
        val = self.query_one("#api-key-input", Input).value.strip()
        if val:
            self.dismiss(val)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "api-key-confirm":
            self.action_confirm()
        elif event.button.id == "api-key-cancel":
            self.action_dismiss_none()

    def on_key(self, event) -> None:
        key = event.key
        if key == "enter":
            self.action_confirm()
            event.stop()
        elif key == "escape":
            self.action_dismiss_none()
            event.stop()


class LibercodeUI(App):
    CSS = """
    $bg:         #282a36;
    $bg_panel:   #1e1f29;
    $bg_input:   #21222c;
    $border:     #6272a4;
    $border_act: #bd93f9;
    $primary:    #bd93f9;
    $secondary:  #ff79c6;
    $accent:     #50fa7b;
    $text:       #f8f8f2;
    $muted:      #6272a4;
    $warning:    #ffb86c;
    $error:      #ff5555;
    $success:    #50fa7b;

    Screen {
        background: $bg;
        layers: base overlay;
    }

    /* ── HEADER ── */
    #header-bar {
        height: 3;
        background: $bg_panel;
        border-bottom: tall $border;
        padding: 0 2;
        align-vertical: middle;
    }
    #logo-text   { color: $primary; text-style: bold; width: auto; }
    #model-badge { color: $muted;   width: auto; margin-left: 2; }
    #theme-badge { color: $accent;  width: auto; margin-left: 1; }
    #mode-badge  { color: $secondary; width: auto; margin-left: 1; }
    #spacer      { width: 1fr; }
    #mode-pill {
        width: auto;
        height: 1;
        padding: 0 1;
        margin-right: 1;
        content-align: center middle;
        text-style: bold;
    }
    #token-counter {
        color: $muted;
        width: auto;
        margin-right: 2;
        text-align: right;
    }
    #token-bar {
        width: 12;
        height: 1;
        margin-left: 2;
    }

    /* ── LOGO ── */
    #logo-area {
        height: auto;
        background: $bg;
        padding: 1 0;
        text-align: center;
        color: $primary;
        text-style: bold;
    }

    /* ── CHAT ── */
    #chat-area {
        height: 1fr;
        background: $bg;
        padding: 0 2;
        scrollbar-size: 1 1;
        scrollbar-gutter: stable;
        scrollbar-color: $border;
        scrollbar-color-hover: $primary;
        scrollbar-background: $bg;
    }
    ScrollableContainer > .scrollbar {
        width: 1;
    }
    ScrollableContainer > .scrollbar--vertical {
        width: 1;
    }
    #chat-log {
        height: auto;
        background: $bg;
        padding: 1 0;
    }

    /* ── STATUS BAR ── */
    #status-bar {
        height: 1;
        background: $bg_panel;
        border-top: tall $border;
        border-bottom: tall $border;
        padding: 0 2;
        color: $muted;
    }

    /* ── INPUT ── */
    #input-area {
        height: auto;
        min-height: 5;
        max-height: 12;
        background: $bg_panel;
        border-top: tall $border;
        padding: 1 2;
    }
    #prompt-row {
        height: auto;
        align: left middle;
    }
    #prompt-icon {
        color: $primary;
        width: 3;
        height: 1;
        content-align: left middle;
        margin-right: 1;
        padding-top: 0;
    }
    #prompt-input {
        height: auto;
        min-height: 1;
        width: 1fr;
        background: $bg_input;
        color: $text;
        border: round $border;
        padding: 0 1;
    }
    #prompt-input:focus { border: round $border_act; }
    #prompt-input.thinking {
        border: round $primary;
        background: $bg_panel;
    }

    /* ── THINKING ANIMATION ── */
    #mode-pill.thinking {
        text-style: bold blink;
    }

    /* ── HINT BAR ── */
    #hint-bar {
        height: 1;
        margin-top: 1;
        background: $bg_panel;
        padding-left: 2;
    }
    .hint-btn {
        background: $bg_panel;
        color: $muted;
        border: none;
        height: 1;
        min-width: 0;
        width: auto;
        padding: 0 1;
        margin: 0 1 0 0;
    }
    .hint-btn:hover  { background: $bg_input; color: $accent; }
    .hint-btn:focus  { background: $bg_panel; border: none; }

    /* ── COMMAND PALETTE ── */
    #command-palette {
        display: none;
        layer: overlay;
        dock: bottom;
        margin-bottom: 8;
        margin-left: 4;
        width: 62;
        height: auto;
        max-height: 22;
        background: $bg_panel;
        border: round $border_act;
    }

    /* ── MODEL / MODE PICKER ── */
    #picker {
        display: none;
        layer: overlay;
        dock: bottom;
        margin-bottom: 8;
        margin-left: 68;
        width: 36;
        height: auto;
        max-height: 14;
        background: $bg_panel;
        border: round $primary;
    }
    """

    CTRL_C_QUIT = False

    BINDINGS = [
        Binding("ctrl+c",  "quit",          "quit",    priority=True, show=False),
        Binding("ctrl+t",  "cycle_theme",   "theme",   priority=True, show=False),
        Binding("ctrl+n",  "new_session",   "session", priority=True, show=False),
        Binding("ctrl+l",  "clear_chat",    "clear",   priority=True, show=False),
        Binding("escape",  "cancel_action", "cancel",  priority=False, show=False),
        Binding("tab",     "cycle_mode",    "mode",    priority=True, show=False),
        Binding("up",      "palette_up",    "up",      priority=True, show=False),
        Binding("down",    "palette_down",  "down",    priority=True, show=False),
    ]

    AGENT_MODES = ["build", "plan", "spec", "debug"]

    THEME_NAMES = list(THEMES.keys())

    is_thinking = reactive(False)
    token_count = reactive(0)
    current_model = reactive(DEFAULT_MODEL)
    spinner_frame = reactive(0)

    def __init__(self, theme_name="dracula", model=DEFAULT_MODEL):
        self._init_theme = theme_name
        self._init_model = model
        self.theme_data = THEMES[theme_name]
        self.theme_data_name = theme_name
        self._spinner_interval = None
        self._palette_visible = False
        self._palette_index = 0
        self._palette_items = []
        self._picker_kind = ""
        self._agent = None
        self._is_processing = False
        self._confirm_event: asyncio.Event | None = None
        self._confirm_result: bool = False
        self._spinner_handle = None
        self._awaiting_api_key_for: str | None = None
        self.TOKEN_BUDGET = 8000
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Static("◆ libercode", id="logo-text")
            yield Static("", id="model-badge")
            yield Static("", id="theme-badge")
            yield Static("", id="mode-badge")
            yield Static("", id="spacer")
            yield Static("0 tokens", id="token-counter")
            yield Static("░░░░░░░░░░░░", id="token-bar")
        yield Static("", id="logo-area")
        with ScrollableContainer(id="chat-area"):
            yield RichLog(id="chat-log", markup=True, highlight=True, wrap=True)
        yield Static("", id="status-bar")
        with Vertical(id="input-area"):
            with Horizontal(id="prompt-row"):
                yield Static("", id="mode-pill")
                yield Static("›", id="prompt-icon")
                yield Input(placeholder="Type a message or /command…", id="prompt-input")
            with Horizontal(id="hint-bar"):
                yield Button("^C quit",    id="hint-quit",    classes="hint-btn")
                yield Button("^T theme",   id="hint-theme",   classes="hint-btn")
                yield Button("^N session", id="hint-session", classes="hint-btn")
                yield Button("^L clear",   id="hint-clear",   classes="hint-btn")
                yield Button("Esc cancel", id="hint-cancel",  classes="hint-btn")
        yield OptionList(id="command-palette")
        yield OptionList(id="picker")

    def on_mount(self) -> None:
        self.current_model = self._init_model
        self.call_later(self._post_mount)

    async def _post_mount(self) -> None:
        self._apply_theme(self._init_theme)
        self._build_hint_bar()
        await self._animate_logo()
        if self._agent is not None:
            self._update_mode_badge(self._agent.mode)
            self._update_mode_pill(self._agent.mode)
            self.refresh_token_bar()
        else:
            self._update_mode_pill("build")
        self.refresh_status_bar()
        self._show_welcome()

    def _apply_theme(self, name: str) -> None:
        self.theme_data_name = name
        self.theme_data = THEMES[name]
        t = self.theme_data

        self.screen.styles.background = t["bg"]

        w = self.query_one("#header-bar")
        w.styles.background = t["bg_panel"]
        w.styles.border_bottom = ("tall", t["border"])

        self.query_one("#logo-text").styles.color = t["primary"]

        self.query_one("#model-badge").update(
            Text(f" {self.current_model}", style=Style(color=t["muted"]))
        )
        self.query_one("#theme-badge").update(
            Text(f" {name}", style=Style(color=t["accent"]))
        )

        self._refresh_token_color()

        w = self.query_one("#logo-area")
        w.styles.background = t["bg"]
        w.styles.color = t["primary"]

        w = self.query_one("#chat-area")
        w.styles.background = t["bg"]
        w.styles.scrollbar_color = t["border"]
        w.styles.scrollbar_color_hover = t["primary"]
        w.styles.scrollbar_background = t["bg"]

        self.query_one("#chat-log").styles.background = t["bg"]

        w = self.query_one("#input-area")
        w.styles.background = t["bg_panel"]
        w.styles.border_top = ("tall", t["border"])

        w = self.query_one("#prompt-input")
        w.styles.background = t["bg_input"]
        w.styles.color = t["text"]
        w.styles.border = ("round", t["border"])

        self.query_one("#prompt-icon").styles.color = t["primary"]

        self.query_one("#hint-bar").styles.background = t["bg_panel"]

        self._build_hint_bar()

        try:
            p = self.query_one("#command-palette", OptionList)
            p.styles.background = t["bg_panel"]
            p.styles.border = ("round", t["border_act"])
            if self._palette_visible:
                self._refresh_palette()
        except Exception:
            pass

        try:
            p = self.query_one("#picker", OptionList)
            p.styles.background = t["bg_panel"]
            p.styles.border = ("round", t["primary"])
        except Exception:
            pass

        if self._agent is not None:
            self._update_mode_badge(self._agent.mode)
            self._update_mode_pill(self._agent.mode)
        else:
            self._update_mode_pill("build")

    async def _animate_logo(self) -> None:
        t = self.theme_data
        logo_widget = self.query_one("#logo-area", Static)

        logo_text = Text()
        for i, line in enumerate(LOGO_LINES):
            logo_text.append(line + "\n", Style(color=t["primary"], bold=True))
        logo_widget.update(logo_text)

        log = self.query_one("#chat-log", RichLog)
        await asyncio.sleep(0.05)

        welcome = Text()
        welcome.append("  Welcome to ", Style(color=t["muted"]))
        welcome.append("libercode", Style(color=t["primary"], bold=True))
        welcome.append(" — AI in your terminal\n", Style(color=t["muted"]))
        log.write(welcome)
        await asyncio.sleep(0.05)

        info = Text()
        info.append("  Model: ", Style(color=t["muted"]))
        info.append(self.current_model, Style(color=t["accent"]))
        info.append("  |  Theme: ", Style(color=t["muted"]))
        info.append(self.theme_data_name, Style(color=t["secondary"]))
        info.append("  |  ", Style(color=t["muted"]))
        info.append(datetime.now().strftime("%H:%M %d/%m/%Y"), Style(color=t["muted"]))
        log.write(info)
        await asyncio.sleep(0.05)

        log.write(Text("  " + "─" * 58, Style(color=t["border"])))
        log.write(Text(""))

    def _build_hint_bar(self) -> None:
        t = self.theme_data
        mapping = {
            "hint-quit":    ("^C", "quit"),
            "hint-theme":   ("^T", "theme"),
            "hint-session": ("^N", "session"),
            "hint-clear":   ("^L", "clear"),
            "hint-cancel":  ("Esc", "cancel"),
        }
        for btn_id, (key, label) in mapping.items():
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                rich_label = Text()
                rich_label.append(key,       Style(color=t["accent"], bold=True))
                rich_label.append(f" {label}", Style(color=t["muted"]))
                btn.label              = rich_label
                btn.styles.background  = t["bg_panel"]
                btn.styles.color       = t["muted"]
            except Exception:
                pass

    def _refresh_token_color(self) -> None:
        t = self.theme_data
        v = self.token_count
        color = t["muted"] if v < 2000 else t["warning"] if v < 6000 else t["error"]
        try:
            self.query_one("#token-counter", Static).update(
                Text(f"{v:,} tokens", style=Style(color=color))
            )
        except Exception:
            pass

    def _show_command_palette(self, query: str) -> None:
        q = query.lower().strip()
        self._palette_items = [
            (cmd, desc, color)
            for cmd, desc, color in COMMANDS
            if (not q) or q in cmd or q in desc.lower()
        ]

        if not self._palette_items:
            self._hide_command_palette()
            return

        self._palette_index   = 0
        self._palette_visible = True

        palette = self.query_one("#command-palette", OptionList)
        self._fill_palette_options(palette)
        palette.display = True
        # DO NOT call palette.focus() here — Input keeps focus.

        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def _fill_palette_options(self, palette: OptionList) -> None:
        t = self.theme_data
        palette.clear_options()
        for cmd, desc, color_key in self._palette_items:
            color = t.get(color_key, t["primary"])
            label = Text()
            label.append(cmd.ljust(14), Style(color=color, bold=True))
            label.append(desc,          Style(color=t["muted"]))
            palette.add_option(Option(label, id=cmd.lstrip("/")))
        palette.highlighted = self._palette_index

    def _refresh_palette(self) -> None:
        try:
            palette = self.query_one("#command-palette", OptionList)
            self._fill_palette_options(palette)
        except Exception:
            pass

    def _hide_command_palette(self) -> None:
        self._palette_visible = False
        self._palette_index   = 0
        self._palette_items   = []
        try:
            p = self.query_one("#command-palette", OptionList)
            p.display = False
            p.clear_options()
        except Exception:
            pass
        # Return focus to input (not strictly needed since we never
        # moved it, but keeps behaviour consistent)
        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def _palette_select_next(self) -> None:
        if not self._palette_items:
            return
        try:
            palette = self.query_one("#command-palette", OptionList)
            n = len(self._palette_items)
            cur = palette.highlighted or 0
            palette.highlighted = (cur + 1) % n
            self._palette_index = palette.highlighted
        except Exception:
            pass

    def _palette_select_prev(self) -> None:
        if not self._palette_items:
            return
        try:
            palette = self.query_one("#command-palette", OptionList)
            n = len(self._palette_items)
            cur = palette.highlighted or 0
            palette.highlighted = (cur - 1) % n
            self._palette_index = palette.highlighted
        except Exception:
            pass

    def _palette_confirm(self) -> None:
        """Execute the currently highlighted palette item."""
        if not self._palette_items:
            return
        idx = min(self._palette_index, len(self._palette_items) - 1)
        cmd_full, _, _ = self._palette_items[idx]

        self._hide_command_palette()

        if " " in cmd_full[1:]:
            try:
                self.query_one("#prompt-input", Input).value = cmd_full
            except Exception:
                pass
        else:
            cmd = cmd_full.lstrip("/")
            try:
                self.query_one("#prompt-input", Input).value = ""
            except Exception:
                pass
            self._dispatch_command(cmd)

    def show_picker(self, kind: str, items: list, current: str = "") -> None:
        self._picker_kind = kind
        t = self.theme_data
        picker = self.query_one("#picker", OptionList)
        picker.clear_options()
        for item in items:
            is_cur = (item == current)
            label  = Text()
            label.append(
                ("✓ " if is_cur else "  ") + item,
                Style(
                    color=t["accent"] if is_cur else t["text"],
                    bold=is_cur,
                )
            )
            picker.add_option(Option(label, id=item))
        picker.highlighted = 0
        picker.display     = True
        # DO NOT call picker.focus() — input keeps focus
        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def _hide_picker(self) -> None:
        try:
            self.query_one("#picker", OptionList).display = False
            self.query_one("#picker", OptionList).clear_options()
        except Exception:
            pass
        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def _show_help(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        log.write(Text(""))
        log.write(Text("  Available commands\n", Style(color=t["primary"], bold=True)))
        log.write(Text("  " + "─" * 50, Style(color=t["border"])))
        for cmd, desc, color_key in COMMANDS:
            color = t[color_key] if color_key in t else t["muted"]
            line = Text()
            line.append(f"  {cmd:<14}", Style(color=color, bold=True))
            line.append(desc, Style(color=t["muted"]))
            log.write(line)
        log.write(Text("  " + "─" * 50 + "\n", Style(color=t["border"])))

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value

        if not value.startswith("/"):
            self._hide_command_palette()
            return

        rest = value[1:]
        if " " in rest:
            cmd, arg_prefix = rest.split(" ", 1)
            cmd = cmd.lower()
            self._show_arg_palette(cmd, arg_prefix.strip())
        else:
            self._palette_index = 0
            self._show_command_palette(rest.lower())

    def on_key(self, event) -> None:
        key = event.key

        # ── Modal screens — intercept keys before Input steals them ──
        active_modal = None
        for screen in self.screen_stack:
            if isinstance(screen, ProviderModal):
                active_modal = screen
                break
            if isinstance(screen, ModelModal):
                active_modal = screen
                break
            if isinstance(screen, APIKeyModal):
                active_modal = screen
                break

        if active_modal is not None:
            if key == "up":
                active_modal.action_cursor_up()
                event.stop()
            elif key == "down":
                active_modal.action_cursor_down()
                event.stop()
            elif key == "enter":
                active_modal.action_confirm()
                event.stop()
            elif key == "escape":
                active_modal.action_dismiss_none()
                event.stop()
            return

        # ── Picker (model/mode overlay) ──
        try:
            picker = self.query_one("#picker", OptionList)
            if picker.display:
                if key == "escape":
                    self._hide_picker()
                    event.stop()
                elif key == "up":
                    n = picker.option_count
                    cur = picker.highlighted or 0
                    picker.highlighted = (cur - 1) % n
                    event.stop()
                elif key == "down":
                    n = picker.option_count
                    cur = picker.highlighted or 0
                    picker.highlighted = (cur + 1) % n
                    event.stop()
                elif key == "enter":
                    idx = picker.highlighted or 0
                    opt = picker.get_option_at_index(idx)
                    if opt is not None:
                        self._hide_picker()
                        self.post_message(
                            PickerSelectedEvent(
                                kind=self._picker_kind,
                                value=opt.id
                            )
                        )
                    event.stop()
                return   # all other keys pass through to input while picker is open
        except Exception:
            pass

        # ── Command palette ──
        if not self._palette_visible:
            return

        if key == "enter":
            self._palette_confirm()
            event.stop()
        elif key == "escape":
            self._hide_command_palette()
            event.stop()
        elif key == "up":
            self._palette_select_prev()
            event.stop()
        elif key == "down":
            self._palette_select_next()
            event.stop()
        # All other keys (letters, backspace, etc.) fall through to Input
        # so the user can keep typing to filter the palette

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "hint-quit":    self.action_quit,
            "hint-theme":   self.action_cycle_theme,
            "hint-session": self.action_new_session,
            "hint-clear":   self.action_clear_chat,
            "hint-cancel":  self.action_cancel_action,
        }
        fn = actions.get(event.button.id)
        if fn:
            fn()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()

        if event.option_list.id == "command-palette":
            cmd = event.option.id
            self._hide_command_palette()
            try:
                self.query_one("#prompt-input", Input).value = ""
            except Exception:
                pass
            self._dispatch_command(cmd)

        elif event.option_list.id == "picker":
            value = event.option.id
            self._hide_picker()
            self.post_message(PickerSelectedEvent(kind=self._picker_kind, value=value))

        # Always return focus to input
        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def on_show_picker_event(self, event: ShowPickerEvent) -> None:
        self.show_picker(event.kind, event.items, event.current)

    def watch_token_count(self, value: int) -> None:
        self._refresh_token_color()

    def watch_current_model(self, value: str) -> None:
        try:
            t = self.theme_data
            self.query_one("#model-badge", Static).update(
                Text(f" {value}", style=Style(color=t["muted"]))
            )
        except Exception:
            pass

    def watch_is_thinking(self, value: bool) -> None:
        try:
            self.query_one("#prompt-input", Input).disabled = value
        except Exception:
            pass
        if value:
            self._spinner_interval = self.set_interval(0.1, self._tick_spinner)
        else:
            if self._spinner_interval:
                self._spinner_interval.cancel()
                self._spinner_interval = None
            try:
                self.query_one("#prompt-icon", Static).update(
                    Text("›", style=Style(color=self.theme_data["primary"]))
                )
            except Exception:
                pass

    def watch_spinner_frame(self, value: int) -> None:
        if not self.is_thinking:
            return
        try:
            frame = SPINNER_FRAMES[value % len(SPINNER_FRAMES)]
            self.query_one("#prompt-icon", Static).update(
                Text(frame, style=Style(color=self.theme_data["warning"]))
            )
        except Exception:
            pass

    def _tick_spinner(self) -> None:
        self.spinner_frame = self.spinner_frame + 1

    def show_thinking(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        line = Text("  ◌ ", Style(color=t["warning"]))
        line.append("thinking...", Style(color=t["muted"], italic=True))
        log.write(line)

    def show_response_footer(self, word_count: int, elapsed: float) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        line = Text("\n  ", Style(color=t["muted"]))
        line.append("✓ ", Style(color=t["success"]))
        line.append(f"{word_count} words  {elapsed:.1f}s", Style(color=t["muted"]))
        line.append("  " + "─" * 50, Style(color=t["border"]))
        line.append("\n")
        log.write(line)

    def render_user_message(self, text: str) -> None:
        from rich.text import Text
        from rich.style import Style
        from datetime import datetime as _dt
        t   = self.theme_data
        log = self.query_one("#chat-log", RichLog)
        now = _dt.now().strftime("%H:%M:%S")
        msg = Text()
        msg.append("\n  › ", Style(color=t["secondary"], bold=True))
        msg.append(text,     Style(color=t["text"]))
        msg.append(f"  {now}", Style(color=t["muted"]))
        msg.append("\n")
        log.write(msg)
        log.scroll_end(animate=False)

    def render_ai_header(self, model_name: str = None) -> None:
        from rich.text import Text
        from rich.style import Style
        from datetime import datetime as _dt
        t   = self.theme_data
        log = self.query_one("#chat-log", RichLog)
        now = _dt.now().strftime("%H:%M:%S")
        name = model_name or self.current_model
        header = Text()
        header.append("\n  ◆ ", Style(color=t["primary"], bold=True))
        header.append(name, Style(color=t["primary"], bold=True))
        header.append(f"  {now}", Style(color=t["muted"]))
        header.append("\n")
        log.write(header)

    def render_ai_response(self, full_text: str) -> None:
        from rich.text import Text as RText
        from rich.style import Style
        from rich.syntax import Syntax
        from rich.markdown import Markdown as RichMarkdown
        from rich.panel import Panel
        from rich.rule import Rule
        import re

        log = self.query_one("#chat-log", RichLog)
        t   = self.theme_data

        if not full_text.strip():
            return

        CODE_BLOCK = re.compile(r"```([\w.+\-]*)\n?(.*?)```", re.DOTALL)

        last_end = 0
        for match in CODE_BLOCK.finditer(full_text):
            before = full_text[last_end : match.start()].strip()
            if before:
                try:
                    log.write(RichMarkdown(before))
                except Exception:
                    log.write(RText(before, Style(color=t["text"])))

            lang_tag = match.group(1).strip()
            code     = match.group(2)
            if not lang_tag or lang_tag == "text":
                lang_tag = _detect_lang("", code)

            alias = {
                "js": "javascript", "ts": "typescript", "py": "python",
                "sh": "bash", "rb": "ruby", "rs": "rust",
            }.get(lang_tag, lang_tag)

            try:
                log.write(Syntax(
                    code.rstrip(), alias,
                    theme=t.get("syntax", "dracula"),
                    line_numbers=True, word_wrap=True,
                    background_color=t["bg_panel"],
                    indent_guides=True,
                ))
            except Exception:
                log.write(Panel(
                    RText(code.rstrip(), Style(color=t["accent"])),
                    border_style=t["border"],
                    title=lang_tag or "code",
                    title_align="left",
                ))

            last_end = match.end()

        remaining = full_text[last_end:].strip()
        if remaining:
            try:
                log.write(RichMarkdown(remaining))
            except Exception:
                log.write(RText(remaining, Style(color=t["text"])))

        log.write(Rule(style=Style(color=t["border"])))
        log.scroll_end(animate=False)

    def show_theme_changed(self, name: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        line = Text("  ◈ Theme changed to ", Style(color=t["muted"]))
        line.append(name, Style(color=t["accent"], bold=True))
        line.append("\n")
        log.write(line)

    def show_session_cleared(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        t = self.theme_data
        log.write(Text("\n  ◈ New session started\n", Style(color=t["success"])))

    def show_cancelled(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        log.write(Text("\n  ✗ Cancelled\n", Style(color=t["warning"])))

    def show_error(self, msg: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        line = Text("\n  ✗ ", Style(color=t["error"]))
        line.append(msg, Style(color=t["error"]))
        line.append("\n")
        log.write(line)

    def _render_tool_result(self, tool_name: str, result: str) -> None:
        from rich.text import Text
        from rich.style import Style
        from rich.panel import Panel
        from rich.syntax import Syntax

        log = self.query_one("#chat-log", RichLog)
        t   = self.theme_data

        tool_meta = {
            "shell":       ("⚡", t["warning"],  "bash"),
            "file:write":  ("✎",  t["success"],  "text"),
            "file:read":   ("📄", t.get("info", t["accent"]), "text"),
            "file:edit":   ("✏",  t["accent"],   "diff"),
            "git":         ("⎇",  t["secondary"],"bash"),
            "task:create": ("☑",  t["success"],  "text"),
            "task:update": ("☑",  t["accent"],   "text"),
            "checkpoint":  ("◉",  t["primary"],  "text"),
            "memory":      ("🧠", t["primary"],  "text"),
            "scratch":     ("📝", t["muted"],    "text"),
        }
        icon, color, lang = tool_meta.get(tool_name, ("▸", t["muted"], "text"))
        display = result[:1500]
        if len(result) > 1500:
            display += f"\n… [{len(result)-1500} chars truncated]"
        if lang == "bash" and display.strip():
            inner = Syntax(
                display, "bash",
                theme=t.get("syntax", "dracula"),
                word_wrap=True,
                background_color=t["bg_panel"],
            )
        else:
            inner = Text(display, Style(color=t["text"]))
        log.write(Panel(
            inner,
            title=Text(f"{icon} {tool_name}", Style(color=color, bold=True)),
            title_align="left",
            border_style=color,
            padding=(0, 1),
        ))
        log.scroll_end(animate=False)

    def _render_diff_panel(self, path: str, diff_lines) -> None:
        """Render a diff panel in the chat log."""
        from rich.panel import Panel
        from libercode.differ import render_diff
        t = self.theme_data
        log = self.query_one("#chat-log", RichLog)
        body = render_diff(diff_lines, t)
        if not body.plain.strip():
            return
        log.write(Panel(
            body,
            title=Text(f"  diff  {path}", Style(color=t["primary"], bold=True)),
            title_align="left",
            border_style=t["border"],
            padding=(0, 1),
        ))
        log.scroll_end(animate=False)

    def _show_confirm(self, question: str) -> None:
        """Show a y/n prompt inline. Does not steal focus."""
        t = self.theme_data
        log = self.query_one("#chat-log", RichLog)
        msg = Text()
        msg.append(f"\n  ⚠  {question} ", Style(color=t["warning"], bold=True))
        msg.append("[y/N]", Style(color=t["accent"], bold=True))
        msg.append("  → type y or n and press Enter\n", Style(color=t["muted"]))
        log.write(msg)
        log.scroll_end(animate=False)

    async def ask_confirm(self, question: str) -> bool:
        """Show a y/n question and wait for the user's answer."""
        import asyncio
        self._confirm_event  = asyncio.Event()
        self._confirm_result = False
        self._show_confirm(question)
        await self._confirm_event.wait()
        self._confirm_event = None
        return self._confirm_result

    def _show_arg_palette(self, cmd: str, prefix: str) -> None:
        """Show argument suggestions for a command."""
        from textual.widgets._option_list import Option

        arg_list = list(COMMAND_ARGS.get(cmd, []))

        if cmd == "model" and self._agent:
            arg_list = self._agent.available_models
        elif cmd == "sessions" and self._agent:
            try:
                slist = self._agent.store.session_list(
                    str(Path.cwd().resolve())
                )
                arg_list = [str(s["id"]) for s in slist]
            except Exception:
                arg_list = []
        elif cmd == "restore" and self._agent:
            try:
                cps = self._agent.checkpointer.list()
                arg_list = [str(c["id"]) for c in cps]
            except Exception:
                arg_list = []

        if not arg_list:
            self._hide_command_palette()
            return

        filtered = [a for a in arg_list if a.lower().startswith(prefix.lower())]
        if not filtered:
            filtered = arg_list

        self._palette_items   = [(f"/{cmd} {a}", a, "accent") for a in filtered]
        self._palette_index   = 0
        self._palette_visible = True

        palette = self.query_one("#command-palette", OptionList)
        palette.clear_options()
        t = self.theme_data
        for full_cmd, label, _ in self._palette_items:
            display = Text()
            display.append(f"/{cmd} ", Style(color=t["muted"]))
            display.append(label, Style(color=t["accent"], bold=True))
            palette.add_option(Option(display, id=full_cmd))
        palette.display = True
        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def refresh_token_bar(self) -> None:
        """Update token progress bar. Safe from any thread."""
        import threading
        if threading.current_thread() is threading.main_thread():
            self._do_refresh_token_bar()
        else:
            self.call_from_thread(self._do_refresh_token_bar)

    def _do_refresh_token_bar(self) -> None:
        if self._agent is None:
            return
        used   = self._agent.total_tokens
        budget = self.TOKEN_BUDGET
        pct    = min(100, int(used / budget * 100))
        t      = self.theme_data

        filled = pct // 5
        empty  = 20 - filled
        bar_text = "█" * filled + "░" * empty

        color = t["success"]
        if pct >= 85:
            color = t["error"]
        elif pct >= 60:
            color = t["warning"]

        try:
            bar = self.query_one("#token-bar", Static)
            bar.update(Text(f" {bar_text} {pct}%", Style(color=color)))
        except Exception:
            pass

    _SPINNER_CHARS = ["◐", "◓", "◑", "◒"]
    _spinner_idx    = 0

    def start_thinking(self) -> None:
        """Animate the input border and mode pill while processing."""
        try:
            self.query_one("#prompt-input", Input).add_class("thinking")
            self.query_one("#mode-pill", Static).add_class("thinking")
        except Exception:
            pass
        self._spinner_idx = 0
        self._tick_thinking_spinner()

    def stop_thinking(self) -> None:
        """Remove the thinking animation."""
        try:
            self.query_one("#prompt-input", Input).remove_class("thinking")
            self.query_one("#mode-pill", Static).remove_class("thinking")
        except Exception:
            pass
        if self._spinner_handle is not None:
            self._spinner_handle.stop()
            self._spinner_handle = None

    def _tick_thinking_spinner(self) -> None:
        frame = self._SPINNER_CHARS[self._spinner_idx % len(self._SPINNER_CHARS)]
        self._spinner_idx += 1
        try:
            mode  = self._agent.mode if self._agent else "build"
            fg, _ = self.MODE_PILL_COLORS.get(mode, ("#bd93f9", "#1e1a2a"))
            self.query_one("#mode-pill", Static).update(
                Text(f" {frame} {mode.upper()} ",
                     Style(color=fg, bold=True))
            )
        except Exception:
            pass
        self._spinner_handle = self.set_timer(0.15, self._tick_thinking_spinner)

    def _show_welcome(self) -> None:
        """Show welcome panel on startup."""
        from rich.panel import Panel
        from datetime import datetime
        t   = self.theme_data
        log = self.query_one("#chat-log", RichLog)

        now     = datetime.now()
        hour    = now.hour
        greeting = (
            "Good morning" if 5  <= hour < 12
            else "Good afternoon" if 12 <= hour < 18
            else "Good evening"
        )

        agent = self._agent
        body  = Text()

        body.append(f"  {greeting}!\n", Style(color=t["primary"], bold=True))
        body.append(f"  {now.strftime('%A, %B %d %Y')}\n\n",
                    Style(color=t["muted"]))

        if agent:
            try:
                sessions = agent.store.session_list(
                    str(Path.cwd().resolve())
                )
                if len(sessions) > 1:
                    last = sessions[1]
                    body.append("  Last session  ", Style(color=t["text"]))
                    body.append(
                        str(last.get("started_at", ""))[:10],
                        Style(color=t["accent"])
                    )
                    body.append("\n")
            except Exception:
                pass

            try:
                pending = [
                    tk for tk in agent.tasks.list()
                    if tk.get("status", "") != "done"
                ]
                body.append(f"  Pending tasks  ", Style(color=t["text"]))
                body.append(str(len(pending)), Style(color=t["accent"], bold=True))
                body.append("\n")
            except Exception:
                pass

            try:
                if agent.git.is_repo():
                    status = agent.git.run("status", "--short")
                    n_files = len([
                        l for l in status.splitlines() if l.strip()
                    ])
                    body.append(f"  Modified files  ", Style(color=t["text"]))
                    body.append(str(n_files), Style(color=t["accent"], bold=True))
                    body.append("\n")
            except Exception:
                pass

            body.append(f"\n  Active mode  ", Style(color=t["text"]))
            body.append(agent.mode, Style(color=t["secondary"], bold=True))
            body.append("\n")

        body.append(
            "\n  Type a message or / for commands. Tab cycles mode.\n",
            Style(color=t["muted"])
        )

        log.write(Panel(
            body,
            title=Text("  LiberCode  ", Style(color=t["primary"], bold=True)),
            title_align="left",
            border_style=t["primary"],
            padding=(0, 1),
        ))
        log.write(Text(""))

    def cycle_theme(self) -> None:
        idx = self.THEME_NAMES.index(self.theme_data_name)
        next_name = self.THEME_NAMES[(idx + 1) % len(self.THEME_NAMES)]
        self._apply_theme(next_name)
        self.show_theme_changed(next_name)
        self._save_theme(next_name)

    def _save_theme(self, name: str) -> None:
        try:
            from libercode.config import LiberConfig, GLOBAL_CONFIG_PATH
            import yaml
            if GLOBAL_CONFIG_PATH.exists():
                with open(GLOBAL_CONFIG_PATH) as f:
                    raw = yaml.safe_load(f) or {}
            else:
                raw = {}
            raw["theme"] = name
            with open(GLOBAL_CONFIG_PATH, "w") as f:
                yaml.dump(raw, f, default_flow_style=False)
        except Exception:
            pass

    def action_quit(self)          -> None: self.exit()
    def action_cycle_theme(self)   -> None: self.cycle_theme()
    def action_new_session(self)   -> None: self.show_session_cleared()
    def action_clear_chat(self)    -> None: self.query_one("#chat-log", RichLog).clear()
    def action_cancel_action(self) -> None: self.show_cancelled()

    def action_palette_up(self) -> None:
        if self._palette_visible:
            self._palette_select_prev()

    def action_palette_down(self) -> None:
        if self._palette_visible:
            self._palette_select_next()

    def action_cycle_mode(self) -> None:
        if self._agent is None:
            return
        try:
            cur_idx = self.AGENT_MODES.index(self._agent.mode)
        except ValueError:
            cur_idx = 0
        new_mode = self.AGENT_MODES[(cur_idx + 1) % len(self.AGENT_MODES)]
        self._agent.mode = new_mode
        try:
            self._agent.store.session_update_mode(
                self._agent.session_id, new_mode
            )
        except Exception:
            pass
        self._update_mode_badge(new_mode)
        self._update_mode_pill(new_mode)
        from rich.text import Text as RText
        from rich.style import Style as RStyle
        t = self.theme_data
        self.query_one("#chat-log", RichLog).write(RText(
            f"  ⇄ Mode → {new_mode}\n",
            RStyle(color=t["accent"], bold=True)
        ))
        self.refresh_status_bar()

    def _update_mode_badge(self, mode: str) -> None:
        try:
            badge = self.query_one("#mode-badge", Static)
            badge.update(Text(f" {mode}", style=Style(color=self.theme_data["secondary"])))
        except Exception:
            pass

    MODE_PILL_COLORS = {
        "build": ("#50fa7b", "#1e2a23"),   # accent green on dark green
        "plan":  ("#f1fa8c", "#2a2a1a"),   # yellow on dark yellow
        "spec":  ("#8be9fd", "#1a2a2a"),   # cyan on dark cyan
        "debug": ("#ff5555", "#2a1a1a"),   # red on dark red
    }

    def _update_mode_pill(self, mode: str) -> None:
        fg, bg = self.MODE_PILL_COLORS.get(mode, ("#bd93f9", "#1e1a2a"))
        try:
            pill = self.query_one("#mode-pill", Static)
            pill.update(Text(f" {mode.upper()} ", Style(
                color=fg, bgcolor=bg, bold=True
            )))
            pill.styles.background = bg
        except Exception:
            pass

    def refresh_status_bar(self) -> None:
        import threading
        if threading.current_thread() is threading.main_thread():
            self._do_refresh_status_bar()
        else:
            self.call_from_thread(self._do_refresh_status_bar)

    def _do_refresh_status_bar(self) -> None:
        t = self.theme_data
        agent = self._agent
        bar   = Text()

        mode = agent.mode if agent else "build"
        mode_colors = {
            "build": t["success"],
            "plan":  t.get("warning", "#f1fa8c"),
            "spec":  t.get("info",    "#8be9fd"),
            "debug": t["error"],
        }
        bar.append(f" {mode.upper()} ", Style(
            color=mode_colors.get(mode, t["primary"]), bold=True
        ))
        bar.append(" · ", Style(color=t["border"]))

        provider = agent.provider.name if agent else "—"
        bar.append(provider, Style(color=t["muted"]))
        bar.append(" · ", Style(color=t["border"]))

        sid = agent.session_id if agent else "—"
        bar.append(f"#{sid}", Style(color=t["muted"]))
        bar.append(" · ", Style(color=t["border"]))

        tokens = agent.total_tokens if agent else 0
        tok_color = (
            t["error"]                       if tokens > 6000
            else t.get("warning", "#f1fa8c") if tokens > 3000
            else t["muted"]
        )
        bar.append(f"{tokens:,} tokens", Style(color=tok_color))
        bar.append(" · ", Style(color=t["border"]))

        try:
            task_count = len(agent.tasks.list()) if agent else 0
            pending    = sum(
                1 for t2 in agent.tasks.list()
                if t2.get("status", "") != "done"
            ) if agent else 0
            bar.append(
                f"{pending} tasks",
                Style(color=t["accent"] if pending else t["muted"])
            )
        except Exception:
            bar.append("— tasks", Style(color=t["muted"]))

        try:
            if agent and agent.git.is_repo():
                branch = agent.git.current_branch()
                bar.append(" · ", Style(color=t["border"]))
                bar.append(f"⎇ {branch}", Style(color=t["secondary"]))
        except Exception:
            pass

        bar.append(" ")
        try:
            self.query_one("#status-bar", Static).update(bar)
        except Exception:
            pass

    # ── Thread-safe bridge for agent communication ──

    def set_agent(self, agent) -> None:
        """Called by main() after constructing the agent."""
        self._agent = agent
        self.refresh_token_bar()

    def write_output(self, content) -> None:
        """Write Rich Text or str to the chat log. Safe when called from
        run_worker coroutines (which run on the event loop)."""
        try:
            log = self.query_one("#chat-log", RichLog)
            log.write(content)
            log.scroll_end(animate=False)
        except Exception:
            pass

    def write_error(self, message: str) -> None:
        """Thread-safe: write an error line to the chat log."""
        t = self.theme_data
        self.write_output(
            Text(f"\n  ✗ {message}\n", Style(color=t["error"], bold=True))
        )

    def write_info(self, message: str) -> None:
        """Thread-safe: write an info line to the chat log."""
        t = self.theme_data
        self.write_output(
            Text(f"\n  ◈ {message}\n", Style(color=t["accent"]))
        )

    def show_picker_from_thread(self, kind: str, items: list, current: str = "") -> None:
        """Open the picker overlay."""
        self.show_picker(kind, items, current)

    def update_model_badge_from_thread(self, model_name: str) -> None:
        """Update the model badge in the header."""
        try:
            t = self.theme_data
            self.query_one("#model-badge").update(
                Text(f" {model_name}", style=Style(color=t["muted"]))
            )
        except Exception:
            pass

    # ── Command dispatch ──

    def _dispatch_command(self, cmd: str) -> None:
        ui_cmds = {
            "quit":    self.action_quit,
            "theme":   self.action_cycle_theme,
            "session": self.action_new_session,
            "clear":   self.action_clear_chat,
            "help":    self._show_help,
        }
        if cmd in ui_cmds:
            ui_cmds[cmd]()
            return

        if self._agent is None:
            self.write_error("Agent not connected.")
            return

        agent = self._agent
        tui   = self

        async def _run():
            try:
                await agent.handle_tui_command(cmd, "", tui)
            except Exception as e:
                tui.write_error(str(e))

        self.run_worker(_run(), exclusive=False)

    def _dispatch_command_with_args(self, cmd: str, args: str) -> None:
        ui_cmds = {
            "quit":    self.action_quit,
            "theme":   self.action_cycle_theme,
            "session": self.action_new_session,
            "clear":   self.action_clear_chat,
            "help":    self._show_help,
        }
        if cmd in ui_cmds:
            ui_cmds[cmd]()
            return

        if self._agent is None:
            self.write_error("Agent not connected.")
            return

        agent = self._agent
        tui   = self

        async def _run():
            try:
                await agent.handle_tui_command(cmd, args, tui)
            except Exception as e:
                tui.write_error(str(e))

        self.run_worker(_run(), exclusive=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if self._confirm_event is not None and not self._confirm_event.is_set():
            val = text.lower().strip()
            self._confirm_result = val in ("y", "yes")
            self._confirm_event.set()
            self.query_one("#prompt-input", Input).value = ""
            return

        if (
            self._agent is not None
            and getattr(self._agent, "_wizard_state", {}).get("step") == 3
        ):
            api_key = text.strip()
            self.query_one("#prompt-input", Input).value = ""
            state    = self._agent._wizard_state
            provider = state.get("provider", "")
            agent    = self._agent
            tui      = self

            async def _wizard_finish():
                await agent._tui_wizard_finish(provider, api_key, tui)

            self.run_worker(_wizard_finish(), exclusive=False)
            return

        if self._is_processing and not text.startswith("/"):
            return

        self.query_one("#prompt-input", Input).value = ""

        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            cmd   = parts[0].lower().strip()
            args  = parts[1].strip() if len(parts) > 1 else ""
            self._hide_command_palette()
            self._dispatch_command_with_args(cmd, args)
            return

        if self._agent is None:
            self.write_error("Agent not connected.")
            return

        self._is_processing = True
        self.render_user_message(text)

        agent = self._agent
        tui   = self

        async def _chat():
            tui.start_thinking()
            try:
                await agent.handle_tui_message(text, tui)
            except Exception as e:
                tui.write_error(str(e))
            finally:
                tui._is_processing = False
                tui.stop_thinking()
                tui._update_mode_pill(
                    agent.mode if agent else "build"
                )

        self.run_worker(_chat(), exclusive=True)

    def open_provider_modal(self) -> None:
        """Build provider list from registry and push ProviderModal."""
        agent = self._agent
        if agent is None:
            return

        from libercode.providers.registry import (
            PROVIDER_REGISTRY, detect_available_from_env
        )
        env_keys = detect_available_from_env()
        current_provider_name = agent.provider.name
        current_model = getattr(agent.provider, 'model', '')
        providers = []
        for name, (cls, env_var) in PROVIDER_REGISTRY.items():
            display = getattr(cls, 'display_name', name)
            default_model = getattr(cls, 'default_model', '')
            if env_var and env_var in env_keys:
                detail = env_keys[env_var]
                status = "ready" if name != current_provider_name else "active"
            elif name == "builtin":
                detail = "(local)"
                status = "active" if name == current_provider_name else "ready"
            else:
                detail = env_var or ""
                status = "unconfigured"
            if name == current_provider_name:
                status = "active"
                detail = current_model
            providers.append({
                "name": display,
                "default_model": default_model,
                "status": status,
                "detail": detail,
            })
        providers.sort(key=lambda p: {"active": 0, "ready": 1, "unconfigured": 2}[p["status"]])

        def _on_dismiss(result):
            if result is not None:
                self._switch_provider_then_model(result)

        try:
            self.query_one("#prompt-input", Input).blur()
        except Exception:
            pass
        self.push_screen(
            ProviderModal(providers, current_provider_name),
            _on_dismiss
        )

    def _switch_provider_then_model(self, provider_display_name: str) -> None:
        """After selecting a provider, open ModelModal with lazy load."""
        agent = self._agent
        if agent is None:
            return

        from libercode.providers.registry import PROVIDER_REGISTRY
        import threading

        provider_key = None
        for key, (cls, _) in PROVIDER_REGISTRY.items():
            if getattr(cls, 'display_name', key) == provider_display_name:
                provider_key = key
                break
        if provider_key is None:
            provider_key = provider_display_name.lower()

        _, env_var = PROVIDER_REGISTRY.get(provider_key, (None, ""))

        if env_var:
            saved_key = ""
            try:
                from libercode.config import LiberConfig
                cfg = LiberConfig.load()
                if provider_key in cfg.providers:
                    saved_key = cfg.providers[provider_key].api_key
            except Exception:
                pass

            if not saved_key:
                def _on_key_modal(api_key):
                    if api_key is not None:
                        self._finish_provider_switch(provider_display_name, api_key)
                try:
                    self.query_one("#prompt-input", Input).blur()
                except Exception:
                    pass
                self.push_screen(
                    APIKeyModal(provider_display_name), _on_key_modal
                )
                return

        cls, _ = PROVIDER_REGISTRY[provider_key]
        default_model = getattr(cls, 'default_model', '')
        static_models = getattr(cls, 'available_models', []) or ([default_model] if default_model else [])
        current_model = getattr(agent.provider, 'model', '')

        modal = ModelModal(
            provider_name=provider_display_name,
            current_model=current_model,
            models=static_models,
        )

        def _fetch_models():
            try:
                provider = cls()
                models = provider.list_models()
                if models and self.is_running:
                    self.call_from_thread(modal.set_models, models)
            except Exception:
                pass

        t = threading.Thread(target=_fetch_models, daemon=True)
        t.start()

        def _on_model_dismiss(model_name):
            if model_name is None:
                return
            async def _do_swap():
                try:
                    from libercode.providers.registry import build_provider
                    from libercode.config import LiberConfig
                    saved_key = ""
                    try:
                        cfg = LiberConfig.load()
                        if provider_key in cfg.providers:
                            saved_key = cfg.providers[provider_key].api_key
                    except Exception:
                        pass
                    new_provider = build_provider(
                        provider_key, model=model_name, api_key=saved_key
                    )
                    agent.provider = new_provider
                    self.current_model = model_name
                    self.watch_current_model(model_name)
                    self.update_model_badge_from_thread(model_name)
                    self.refresh_status_bar()
                    self.write_info(f"Switched to {provider_display_name} / {model_name}")
                except Exception as e:
                    self.write_error(f"Provider swap failed: {e}")
            self.run_worker(_do_swap())

    def _finish_provider_switch(self, provider_display_name: str, api_key: str) -> None:
        """Save API key to config, then open model modal."""
        from libercode.providers.registry import PROVIDER_REGISTRY

        provider_key = None
        for key, (cls, _) in PROVIDER_REGISTRY.items():
            if getattr(cls, 'display_name', key) == provider_display_name:
                provider_key = key
                break
        if provider_key is None:
            provider_key = provider_display_name.lower()

        try:
            from libercode.config import LiberConfig, GLOBAL_CONFIG_PATH
            import yaml
            if GLOBAL_CONFIG_PATH.exists():
                with open(GLOBAL_CONFIG_PATH) as f:
                    raw = yaml.safe_load(f) or {}
            else:
                raw = {}
            raw.setdefault("providers", {})
            raw["providers"].setdefault(provider_key, {})
            raw["providers"][provider_key]["api_key"] = api_key
            with open(GLOBAL_CONFIG_PATH, "w") as f:
                yaml.dump(raw, f, default_flow_style=False)
            self.write_info(f"{provider_display_name.upper()} API key saved.")
        except Exception as e:
            self.write_error(f"Failed to save API key: {e}")
            return

        self._switch_provider_then_model(provider_display_name)

    def open_model_modal(self) -> None:
        """Open ModelModal for the current provider."""
        agent = self._agent
        if agent is None:
            return

        import threading

        current_provider = agent.provider
        provider_name = current_provider.display_name
        current_model = getattr(current_provider, 'model', '')

        try:
            available = current_provider.list_models()
        except Exception:
            available = list(getattr(current_provider, 'available_models', []))
        if not available:
            default = getattr(current_provider, 'default_model', '')
            if default:
                available = [default]

        modal = ModelModal(
            provider_name=provider_name,
            current_model=current_model,
            models=available,
        )

        def _fetch():
            try:
                models = current_provider.list_models()
                if models and self.is_running:
                    self.call_from_thread(modal.set_models, models)
            except Exception:
                pass

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

        def _on_dismiss(model_name):
            if model_name is None:
                return
            async def _do_set():
                try:
                    agent.provider.model = model_name
                    self.current_model = model_name
                    self.watch_current_model(model_name)
                    self.update_model_badge_from_thread(model_name)
                    self.refresh_status_bar()
                    self.write_info(f"Model → {model_name}")
                except Exception as e:
                    self.write_error(f"Model switch failed: {e}")
            self.run_worker(_do_set())

        try:
            self.query_one("#prompt-input", Input).blur()
        except Exception:
            pass
        self.push_screen(modal, _on_dismiss)

    def on_picker_selected_event(self, event: PickerSelectedEvent) -> None:
        if self._agent is None:
            return
        agent = self._agent
        tui   = self
        kind  = event.kind
        value = event.value

        async def _apply():
            await agent.handle_picker_selected(kind, value, tui)

        self.run_worker(_apply(), exclusive=False)


if __name__ == "__main__":
    from libercode.agent import LiberAgent
    from libercode.config import ensure_config

    cfg = ensure_config()
    agent = LiberAgent(cfg)

    app = LibercodeUI(theme_name="dracula", model=agent.provider.name)
    app.set_agent(agent)
    app.run()
