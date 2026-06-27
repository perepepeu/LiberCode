from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text


class Renderer:
    def __init__(self, console: Console):
        self.console = console

    def hero(self):
        gradient = ["bold cyan", "bold cyan", "bold green", "bold green", "bold green", "bold green"]
        lines = [
            "██╗     ██╗██████╗ ███████╗██████╗  ██████╗ ██████╗ ██████╗ ███████╗",
            "██║     ██║██╔══██╗██╔════╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝",
            "██║     ██║██████╔╝█████╗  ██████╔╝██║     ██║   ██║██║  ██║█████╗  ",
            "██║     ██║██╔══██╗██╔══╝  ██╔══██╗██║     ██║   ██║██║  ██║██╔══╝  ",
            "███████╗██║██████╔╝███████╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗",
            "╚══════╝╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
        ]
        banner = Text()
        for i, line in enumerate(lines):
            if i > 0:
                banner.append("\n")
            banner.append(line, style=gradient[min(i, len(gradient) - 1)])
        self.console.print(Panel(banner, border_style="dim cyan", padding=(0, 2)))
        self.console.print()

    def context_bar(self, mode: str, provider_name: str, session_id: int):
        mode_colors = {"build": "green", "plan": "yellow", "spec": "blue"}
        color = mode_colors.get(mode, "white")
        bar = Text()
        bar.append(f" {mode.capitalize()} ", style=f"bold {color}")
        bar.append("· ", style="dim")
        bar.append(provider_name, style="dim white")
        bar.append(" · ", style="dim")
        bar.append(f"Session #{session_id}", style="dim")
        bar.append(" · ", style="dim")
        bar.append("Connected", style="green")
        self.console.print(Panel(bar, border_style="dim", padding=(0, 1)))

    def quick_actions(self):
        actions = Text()
        actions.append("  /mode", style="bold cyan")
        actions.append("   ", style="dim")
        actions.append("@attach", style="bold cyan")
        actions.append("   ", style="dim")
        actions.append("$agent", style="bold cyan")
        actions.append("   ", style="dim")
        actions.append("/commands", style="bold cyan")
        self.console.print(actions)

    def help(self):
        table = Table(box=box.SIMPLE, padding=(0, 1))
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description")
        rows = [
            ("!<command>", "Run a shell command (e.g. !ls, !python test.py)"),
            ("file:read <path>", "Read a file"),
            ("file:write <path> <content>", "Write/create a file"),
            ("file:edit <path> ||| <old> ||| <new>", "Edit a file (replace text)"),
            ("git <command>", "Run any git command"),
            ("task:create <title> ||| <desc>", "Create a tracked task"),
            ("task:update <id> status=completed", "Update task status"),
            ("checkpoint [summary]", "Save a checkpoint"),
            ("scratch <content>", "Write a quick note"),
            ("memory <key> = <value>", "Store in project memory"),
            ("mode <build|plan|spec>", "Switch working mode"),
            ("agent:spawn <task>", "Spawn a sub-agent"),
        ]
        for cmd, desc in rows:
            table.add_row(cmd, desc)

        slash_table = Table(box=box.SIMPLE, padding=(0, 1))
        slash_table.add_column("Command", style="cyan", no_wrap=True)
        slash_table.add_column("Description")
        slash_rows = [
            ("/help", "Show this help"),
            ("/tasks", "List all tasks"),
            ("/memory", "Show project memory"),
            ("/checkpoints", "List checkpoints"),
            ("/scratch", "List scratch notes"),
            ("/mode", "Show current mode"),
            ("/status", "Git status + session info"),
            ("/exit", "End session"),
        ]
        for cmd, desc in slash_rows:
            slash_table.add_row(cmd, desc)

        self.console.print("[bold]Tool commands:[/]")
        self.console.print(table)
        self.console.print()
        self.console.print("[bold]Slash commands:[/]")
        self.console.print(slash_table)
        self.console.print(
            "[dim]Tip: Press Tab to cycle modes (build -> plan -> spec -> build)[/]"
        )
