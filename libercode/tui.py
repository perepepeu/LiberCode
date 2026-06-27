import re
from datetime import datetime
from rich.align import Align
from rich.markdown import Markdown as RichMarkdown
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Static, Input, RichLog

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

LOGO = (
    "██╗     ██╗██████╗ ███████╗██████╗  ██████╗ ██████╗ ██████╗ ███████╗\n"
    "██║     ██║██╔══██╗██╔════╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝\n"
    "██║     ██║██████╔╝█████╗  ██████╔╝██║     ██║   ██║██║  ██║█████╗  \n"
    "██║     ██║██╔══██╗██╔══╝  ██╔══██╗██║     ██║   ██║██║  ██║██╔══╝  \n"
    "███████╗██║██████╔╝███████╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗\n"
    "╚══════╝╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝"
)

DEFAULT_MODEL = "Qwen2.5-Coder-7B-Instruct"

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def _detect_lang(code: str) -> str:
    if "def " in code or "import " in code:
        return "python"
    if "function " in code or "const " in code or "=>" in code:
        return "javascript"
    if "fn " in code or "let mut" in code:
        return "rust"
    return "text"


class LibercodeUI(App):
    CSS = """
    Screen { background: $bg; }

    #header-bar {
        height: 3; background: $bg_panel;
        border-bottom: solid $border; padding: 0 2;
        align: left middle;
    }
    #logo-text { color: $primary; text-style: bold; }
    #model-badge { color: $muted; margin-left: 2; }
    #theme-badge { color: $accent; margin-left: 1; }
    #token-counter { dock: right; color: $muted; margin-right: 2; }

    #chat-area {
        height: 1fr; overflow-y: auto; padding: 1 2;
        background: $bg;
        scrollbar-size: 1 1;
        scrollbar-color: $border;
        scrollbar-color-hover: $primary;
    }

    #input-area {
        height: auto; min-height: 5; max-height: 10;
        background: $bg_panel;
        border-top: solid $border; padding: 1 2;
    }
    #prompt-row { height: auto; align: left middle; }
    #prompt-icon { color: $primary; width: 3; margin-right: 1; }
    #prompt-input {
        height: auto; min-height: 1; width: 1fr;
        border: solid $border;
        background: $bg_input; color: $text; padding: 0 1;
    }
    #prompt-input:focus { border: solid $border_act; }
    #hint-bar { height: 1; color: $muted; margin-top: 1; }
    """

    THEME_NAMES = list(THEMES.keys())

    is_thinking = reactive(False)
    token_count = reactive(0)
    current_model = reactive(DEFAULT_MODEL)
    spinner_frame = reactive(0)

    def __init__(self, theme_name: str = "dracula", model: str = DEFAULT_MODEL):
        super().__init__()
        self.theme_data_name = theme_name
        self.theme_data = THEMES[theme_name]
        self.current_model = model
        self._spinner_interval = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Static("◆", id="logo-text")
            yield Static(" libercode", id="logo-text")
            yield Static(f" {self.current_model}", id="model-badge")
            yield Static(f" {self.theme_data_name}", id="theme-badge")
            yield Static("0 tokens", id="token-counter")
        with ScrollableContainer(id="chat-area"):
            yield RichLog(id="chat-log", markup=True, highlight=True)
        with Vertical(id="input-area"):
            with Horizontal(id="prompt-row"):
                yield Static("›", id="prompt-icon")
                yield Input(placeholder="Type a message...", id="prompt-input")
            yield Static("^C quit  ^T theme  ^N session  ^L clear  Esc cancel", id="hint-bar")

    def on_mount(self) -> None:
        self._apply_theme(self.theme_data_name)
        self._write_logo()

    def _apply_theme(self, name: str) -> None:
        self.theme_data_name = name
        self.theme_data = THEMES[name]
        t = self.theme_data
        self.screen.styles.background = t["bg"]
        for var, key in [
            ("bg", "bg"), ("bg_panel", "bg_panel"), ("bg_input", "bg_input"),
            ("border", "border"), ("border_act", "border_act"),
            ("primary", "primary"), ("secondary", "secondary"), ("accent", "accent"),
            ("text", "text"), ("muted", "muted"),
            ("error", "error"), ("warning", "warning"), ("success", "success"), ("info", "info"),
        ]:
            self.screen.styles.set_variation(var, t[key])
        try:
            self.query_one("#theme-badge").update(f" {name}")
        except Exception:
            pass

    def _write_logo(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
        logo_text = Text(LOGO, style=Style(color=t["primary"], bold=True))
        log.write(Align.center(logo_text))

        welcome = Text()
        welcome.append("  Welcome to ", Style(color=t["muted"]))
        welcome.append("libercode", Style(color=t["primary"], bold=True))
        welcome.append(" — AI in your terminal\n", Style(color=t["muted"]))
        welcome.append("  Model: ", Style(color=t["muted"]))
        welcome.append(self.current_model, Style(color=t["accent"]))
        welcome.append("  |  Theme: ", Style(color=t["muted"]))
        welcome.append(self.theme_data_name, Style(color=t["secondary"]))
        welcome.append("  |  ", Style(color=t["muted"]))
        welcome.append(datetime.now().strftime("%H:%M %d/%m/%Y"), Style(color=t["muted"]))
        welcome.append("\n")
        log.write(welcome)

        log.write(Text("  " + "─" * 60, Style(color=t["border"])))
        log.write(Text(""))

    def _tick_spinner(self) -> None:
        try:
            icon = self.query_one("#prompt-icon", Static)
            frame = SPINNER_FRAMES[self.spinner_frame % len(SPINNER_FRAMES)]
            icon.update(Text(frame, style=Style(color=self.theme_data["warning"])))
            self.spinner_frame = self.spinner_frame + 1
        except Exception:
            pass

    def watch_is_thinking(self, value: bool) -> None:
        try:
            inp = self.query_one("#prompt-input", Input)
            inp.disabled = value
        except Exception:
            pass
        if value:
            self._spinner_interval = self.set_interval(0.1, self._tick_spinner)
        else:
            if self._spinner_interval:
                self._spinner_interval.cancel()
                self._spinner_interval = None
            try:
                icon = self.query_one("#prompt-icon", Static)
                icon.update(Text("›", style=Style(color=self.theme_data["primary"])))
            except Exception:
                pass

    def watch_token_count(self, value: int) -> None:
        try:
            counter = self.query_one("#token-counter", Static)
            counter.update(f" {value:,} tokens")
        except Exception:
            pass

    def watch_current_model(self, value: str) -> None:
        try:
            badge = self.query_one("#model-badge", Static)
            badge.update(f" {value}")
        except Exception:
            pass

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
        header = Text()
        header.append(f"  {t['user_icon']} you ", Style(color=t["secondary"], bold=True))
        header.append(f"  {datetime.now().strftime('%H:%M')}", Style(color=t["muted"]))
        log.write(header)
        log.write(Text(f"  {text}", Style(color=t["text"])))
        log.write(Text(""))

    def render_ai_header(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        t = self.theme_data
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
            header = Text(f"  ╭── {lang} ", Style(color=t["accent"], bold=True))
            header.append(f"({len(lines)} lines)", Style(color=t["muted"]))
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
        try:
            badge = self.query_one("#theme-badge", Static)
            badge.update(f" {name}")
        except Exception:
            pass

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


if __name__ == "__main__":
    LibercodeUI().run()
