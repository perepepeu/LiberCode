import asyncio
import re
from datetime import datetime

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
from textual.widgets import Button, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

THEMES = {
    "dracula": {
        "bg": "#282a36", "bg_panel": "#1e1f29", "bg_input": "#21222c",
        "border": "#6272a4", "border_act": "#bd93f9",
        "primary": "#bd93f9", "secondary": "#ff79c6", "accent": "#50fa7b",
        "text": "#f8f8f2", "muted": "#6272a4",
        "error": "#ff5555", "warning": "#ffb86c", "success": "#50fa7b", "info": "#8be9fd",
        "user_icon": "◈", "ai_icon": "◆", "syntax": "dracula",
    },
    "tokyonight": {
        "bg": "#1a1b26", "bg_panel": "#16161e", "bg_input": "#1f2335",
        "border": "#3b4261", "border_act": "#7aa2f7",
        "primary": "#7aa2f7", "secondary": "#bb9af7", "accent": "#9ece6a",
        "text": "#c0caf5", "muted": "#565f89",
        "error": "#f7768e", "warning": "#e0af68", "success": "#9ece6a", "info": "#2ac3de",
        "user_icon": "›", "ai_icon": "✦", "syntax": "monokai",
    },
    "catppuccin": {
        "bg": "#1e1e2e", "bg_panel": "#181825", "bg_input": "#1e1e2e",
        "border": "#45475a", "border_act": "#cba6f7",
        "primary": "#cba6f7", "secondary": "#f38ba8", "accent": "#a6e3a1",
        "text": "#cdd6f4", "muted": "#585b70",
        "error": "#f38ba8", "warning": "#fab387", "success": "#a6e3a1", "info": "#89dceb",
        "user_icon": "⦿", "ai_icon": "⬡", "syntax": "monokai",
    },
    "kanagawa": {
        "bg": "#1f1f28", "bg_panel": "#16161d", "bg_input": "#1a1a22",
        "border": "#363646", "border_act": "#7e9cd8",
        "primary": "#7e9cd8", "secondary": "#957fb8", "accent": "#76946a",
        "text": "#dcd7ba", "muted": "#727169",
        "error": "#c34043", "warning": "#dca561", "success": "#76946a", "info": "#7fb4ca",
        "user_icon": "▸", "ai_icon": "⬧", "syntax": "monokai",
    },
    "nord": {
        "bg": "#2e3440", "bg_panel": "#242933", "bg_input": "#2e3440",
        "border": "#3b4252", "border_act": "#88c0d0",
        "primary": "#88c0d0", "secondary": "#b48ead", "accent": "#a3be8c",
        "text": "#eceff4", "muted": "#616e88",
        "error": "#bf616a", "warning": "#ebcb8b", "success": "#a3be8c", "info": "#5e81ac",
        "user_icon": "›", "ai_icon": "◇", "syntax": "nord",
    },
}

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

COMMANDS = [
    ("/help",    "Show all available commands",          "info"),
    ("/clear",   "Clear current session history",        "warning"),
    ("/undo",    "Restore last checkpoint",              "warning"),
    ("/context", "Show current system prompt",           "muted"),
    ("/export",  "Export session to file",               "success"),
    ("/import",  "Import memory from file",              "success"),
    ("/model",   "Switch AI model",                      "accent"),
    ("/theme",   "Cycle to next theme",                  "accent"),
    ("/mode",    "Switch mode (build/plan/spec/debug)",  "primary"),
    ("/tasks",   "List current tasks",                   "muted"),
    ("/memory",  "Show stored memory entries",           "muted"),
    ("/git",     "Show git status summary",              "muted"),
    ("/stash",   "Git stash current changes",            "muted"),
    ("/pop",     "Git stash pop",                        "muted"),
    ("/session", "Start a new session",                  "warning"),
    ("/quit",    "Exit libercode",                       "error"),
]

DEFAULT_MODEL = "Qwen2.5-Coder-7B-Instruct"

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

LOGO_LINES = [
    "██╗     ██╗██████╗ ███████╗██████╗  ██████╗ ██████╗ ██████╗ ███████╗",
    "██║     ██║██╔══██╗██╔════╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "██║     ██║██████╔╝█████╗  ██████╔╝██║     ██║   ██║██║  ██║█████╗  ",
    "██║     ██║██╔══██╗██╔══╝  ██╔══██╗██║     ██║   ██║██║  ██║██╔══╝  ",
    "███████╗██║██████╔╝███████╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗",
    "╚══════╝╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
]


def _detect_lang(code: str) -> str:
    if "def " in code or "import " in code:
        return "python"
    if "function " in code or "const " in code or "=>" in code:
        return "javascript"
    if "fn " in code or "let mut" in code:
        return "rust"
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
    #spacer      { width: 1fr; }
    #token-counter {
        color: $muted;
        width: auto;
        margin-right: 2;
        text-align: right;
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
        scrollbar-color: $border;
        scrollbar-color-hover: $primary;
        scrollbar-background: $bg;
    }
    #chat-log {
        height: auto;
        background: $bg;
        padding: 1 0;
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
    #prompt-row   { height: auto; align-vertical: middle; }
    #prompt-icon  { color: $primary; width: 3; margin-right: 1; }
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
        Binding("ctrl+c", "quit",          "quit",    priority=True, show=False),
        Binding("ctrl+t", "cycle_theme",   "theme",   priority=True, show=False),
        Binding("ctrl+n", "new_session",   "session", priority=True, show=False),
        Binding("ctrl+l", "clear_chat",    "clear",   priority=True, show=False),
        Binding("escape", "cancel_action", "cancel",  priority=True, show=False),
        Binding("up",     "palette_up",    "up",      priority=True, show=False),
        Binding("down",   "palette_down",  "down",    priority=True, show=False),
    ]

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
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Static("◆ libercode", id="logo-text")
            yield Static("", id="model-badge")
            yield Static("", id="theme-badge")
            yield Static("", id="spacer")
            yield Static("0 tokens", id="token-counter")
        yield Static("", id="logo-area")
        with ScrollableContainer(id="chat-area"):
            yield RichLog(id="chat-log", markup=True, highlight=True, wrap=True)
        with Vertical(id="input-area"):
            with Horizontal(id="prompt-row"):
                yield Static("›", id="prompt-icon")
                yield Input(placeholder="Type a message...", id="prompt-input")
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

        self._palette_index = 0
        self._palette_visible = True

        palette = self.query_one("#command-palette", OptionList)
        self._fill_palette_options(palette)
        palette.display = True
        palette.focus()

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
        if not self._palette_items:
            return
        try:
            palette = self.query_one("#command-palette", OptionList)
            idx = palette.highlighted or 0
            cmd, _, _ = self._palette_items[idx]
        except Exception:
            return
        self._hide_command_palette()
        try:
            self.query_one("#prompt-input", Input).value = ""
        except Exception:
            pass
        self._dispatch_command(cmd.lstrip("/"))

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
        picker.focus()

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

    def _dispatch_command(self, cmd: str) -> None:
        if cmd == "quit":
            self.action_quit()
        elif cmd == "theme":
            self.action_cycle_theme()
        elif cmd == "session":
            self.action_new_session()
        elif cmd == "clear":
            self.action_clear_chat()
        elif cmd == "help":
            self._show_help()
        else:
            self.post_message(CommandEvent(command=cmd))

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
        val = event.value
        if val.startswith("/"):
            query = val[1:]
            self._palette_index = 0
            self._show_command_palette(query)
        else:
            if self._palette_visible:
                self._hide_command_palette()

    def on_key(self, event) -> None:
        try:
            picker = self.query_one("#picker", OptionList)
            if picker.display and event.key == "escape":
                self._hide_picker()
                event.stop()
                return
        except Exception:
            pass

        if not self._palette_visible:
            return
        if event.key == "enter":
            self._palette_confirm()
            event.stop()
        elif event.key == "escape":
            self._hide_command_palette()
            event.stop()

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
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        log.write(Text("  " + "╌" * 58, Style(color=t["border"])))
        header = Text()
        header.append(f"  {t['user_icon']} you ", Style(color=t["secondary"], bold=True))
        header.append(f"  {datetime.now().strftime('%H:%M')}", Style(color=t["muted"]))
        log.write(header)
        panel = Panel(
            Text(text, style=Style(color=t["text"])),
            border_style=Style(color=t["secondary"]),
            padding=(0, 2),
            expand=False,
        )
        log.write(Align(panel, align="right", width=70))
        log.write(Text(""))

    def render_ai_header(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        log.write(Text(""))
        header = Text()
        header.append(f"  {t['ai_icon']} libercode ", Style(color=t["primary"], bold=True))
        header.append(f"  {self.current_model}", Style(color=t["muted"]))
        log.write(header)

    def render_ai_response(self, full_text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        last_end = 0
        for match in CODE_BLOCK_RE.finditer(full_text):
            start = match.start()
            if start > last_end:
                segment = full_text[last_end:start]
                if segment.strip():
                    log.write(RichMarkdown(segment))
            lang = match.group(1) or _detect_lang(match.group(2))
            code = match.group(2).rstrip("\n")
            lines = code.split("\n")
            header = Text()
            header.append("  ╭─ ", Style(color=t["border"]))
            header.append(
                f" {lang.upper()} ",
                Style(color=t["bg"], bold=True, bgcolor=t["accent"]),
            )
            header.append(f" ─ {len(lines)} lines", Style(color=t["muted"]))
            log.write(header)
            syntax = Syntax(
                code, lang,
                theme=t["syntax"],
                line_numbers=len(lines) > 5,
                word_wrap=True,
                background_color=t["bg_input"],
                indent_guides=True,
            )
            log.write(syntax)
            log.write(Text(f"  ╰{'─' * 62}", Style(color=t["border"])))
            last_end = match.end()
        remaining = full_text[last_end:]
        if remaining.strip():
            log.write(RichMarkdown(remaining))

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

    def cycle_theme(self) -> None:
        idx = self.THEME_NAMES.index(self.theme_data_name)
        next_name = self.THEME_NAMES[(idx + 1) % len(self.THEME_NAMES)]
        self._apply_theme(next_name)
        self.show_theme_changed(next_name)

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


if __name__ == "__main__":
    LibercodeUI().run()
