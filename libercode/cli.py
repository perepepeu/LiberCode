import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from libercode.config import (
    ensure_config,
    first_run_wizard,
    LiberConfig,
    GLOBAL_CONFIG_PATH,
)
from libercode.agent import LiberAgent

console = Console()


def cmd_interactive(args):
    cfg = ensure_config()
    if args.mode:
        cfg.mode = args.mode
    if args.verbose:
        cfg.verbose = True
    agent = LiberAgent(cfg)
    agent.run_interactive()


def cmd_exec(args):
    cfg = ensure_config()
    if args.mode:
        cfg.mode = args.mode
    agent = LiberAgent(cfg)
    instruction = " ".join(args.instruction) if args.instruction else ""
    if not instruction and not sys.stdin.isatty():
        instruction = sys.stdin.read().strip()
    if not instruction:
        console.print(
            '[red]No instruction provided. Use: libercode exec "your instruction"[/]'
        )
        return
    agent.run_one_shot(instruction)


def cmd_config(args):
    cfg = LiberConfig.load()
    if args.set:
        for kv in args.set:
            if "=" not in kv:
                console.print(f"[red]Invalid format: {kv}. Use key=value[/]")
                continue
            key, value = kv.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key.startswith("provider."):
                pkey = key[len("provider.") :]
                if hasattr(cfg.provider, pkey):
                    setattr(cfg.provider, pkey, value)
                    console.print(f"[green]Set provider.{pkey} = {value}[/]")
            elif hasattr(cfg, key):
                if value.lower() in ("true", "false"):
                    setattr(cfg, key, value.lower() == "true")
                elif value.isdigit():
                    setattr(cfg, key, int(value))
                else:
                    setattr(cfg, key, value)
                console.print(f"[green]Set {key} = {value}[/]")
            else:
                console.print(f"[red]Unknown config key: {key}[/]")
        cfg.save_global()
    elif args.reset:
        GLOBAL_CONFIG_PATH.unlink(missing_ok=True)
        console.print("[yellow]Config reset. Run libercode to set up again.[/]")
    elif args.show:
        import yaml

        console.print(
            Markdown(
                f"```yaml\n{yaml.dump(cfg.to_dict(), default_flow_style=False)}\n```"
            )
        )
    else:
        GLOBAL_CONFIG_PATH.unlink(missing_ok=True)
        console.print("[yellow]Config file removed. Run first-run setup again.[/]")
        first_run_wizard()


def cmd_show(args):
    cfg = ensure_config()
    agent = LiberAgent(cfg)

    if args.memory:
        items = agent.memory.all()
        if not items:
            console.print("[dim]No project memory[/]")
            return
        for m in items[:20]:
            console.print(
                f"  [cyan]{m['key']}[/] ({m.get('category', 'general')}): {m.get('value', '')[:150]}"
            )
        return

    if args.tasks:
        status_filter = args.filter
        items = agent.tasks.list(status=status_filter)
        if not items:
            console.print("[dim]No tasks[/]")
            return
        from rich.table import Table
        from rich import box

        table = Table(box=box.SIMPLE)
        table.add_column("ID")
        table.add_column("Status")
        table.add_column("Priority")
        table.add_column("Title")
        for t in items[:20]:
            table.add_row(
                str(t["id"]), t["status"], t.get("priority", "med"), t["title"][:70]
            )
        console.print(table)
        if args.filter:
            console.print(f"[dim]Filtered by status: {args.filter}[/]")
        return

    if args.checkpoints:
        cps = agent.checkpointer.list()
        if not cps:
            console.print("[dim]No checkpoints[/]")
            return
        for cp in cps[:10]:
            console.print(
                f"  [{cp['created_at'][:19]}] {cp['id']} — {cp.get('summary', '')[:80]}"
            )
        return

    if args.scratch:
        notes = agent.scratch.list()
        if not notes:
            console.print("[dim]No scratch notes[/]")
            return
        for n in notes[:10]:
            console.print(f"  #{n['id']} [bold]{n['title']}[/]")
            if n.get("content"):
                console.print(f"      {n['content'][:120]}")
        return

    if args.sessions:
        sessions = agent.store.session_list()
        if not sessions:
            console.print("[dim]No sessions[/]")
            return
        for s in sessions[:10]:
            status = "active" if s.get("is_active") else "ended"
            console.print(
                f"  #{s['id']} {s.get('mode', '?')} {status} — {s.get('started_at', '')[:19]}"
            )
        return

    if args.summary:
        items = agent.memory.all()
        tasks = agent.tasks.list()
        sessions = agent.store.session_list()
        console.print(
            Panel.fit(
                f"[bold]LiberCode Project Summary[/]\n\n"
                f"[cyan]Sessions:[/] {len(sessions)}\n"
                f"[cyan]Memory items:[/] {len(items)}\n"
                f"[cyan]Tasks:[/] {len(tasks)}\n"
                f"[cyan]Provider:[/] {agent.provider.name}\n"
                f"[cyan]Data dir:[/] {agent.config.data_dir}",
                border_style="green",
            )
        )
        return

    console.print(
        "[yellow]Use --memory, --tasks, --checkpoints, --scratch, --sessions, or --summary[/]"
    )


def cmd_wizard(args):
    first_run_wizard()


def cmd_mode(args):
    if args.mode not in ("build", "plan", "spec"):
        console.print("[red]Mode must be build, plan, or spec[/]")
        return
    cfg = ensure_config()
    cfg.mode = args.mode
    cfg.save_global()
    console.print(f"[green]Default mode set to: {args.mode}[/]")


def cmd_version(args):
    from libercode import __version__

    console.print(f"LiberCode v{__version__}")


def main():
    parser = argparse.ArgumentParser(
        prog="libercode",
        description="LiberCode — open-source terminal pair programmer",
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument(
        "--mode", choices=["build", "plan", "spec"], help="Working mode"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_interactive = sub.add_parser(
        "interactive", aliases=["i", "shell"], help="Start interactive session"
    )
    p_interactive.add_argument(
        "--mode", choices=["build", "plan", "spec"], help="Working mode"
    )
    p_interactive.add_argument("--verbose", action="store_true", help="Verbose output")

    p_exec = sub.add_parser(
        "exec", aliases=["e", "run"], help="Execute one-shot instruction"
    )
    p_exec.add_argument(
        "instruction", nargs="*", help="Instruction (or pipe from stdin)"
    )
    p_exec.add_argument(
        "--mode", choices=["build", "plan", "spec"], help="Working mode"
    )

    p_config = sub.add_parser("config", help="Configure LiberCode")
    p_config.add_argument(
        "--set", action="append", help="Set config key=value (e.g. provider.model=...)"
    )
    p_config.add_argument("--show", action="store_true", help="Show current config")
    p_config.add_argument("--reset", action="store_true", help="Reset configuration")

    p_show = sub.add_parser("show", help="Show stored data")
    p_show.add_argument("--memory", action="store_true", help="Show project memory")
    p_show.add_argument("--tasks", action="store_true", help="Show tasks")
    p_show.add_argument(
        "--filter",
        help="Filter tasks by status (pending, in_progress, completed, failed, paused)",
    )
    p_show.add_argument("--checkpoints", action="store_true", help="Show checkpoints")
    p_show.add_argument("--scratch", action="store_true", help="Show scratch notes")
    p_show.add_argument("--sessions", action="store_true", help="Show past sessions")
    p_show.add_argument("--summary", action="store_true", help="Show project summary")

    p_wizard = sub.add_parser("wizard", help="Run first-time setup wizard")

    p_mode = sub.add_parser("mode", help="Set default working mode")
    p_mode.add_argument("mode", choices=["build", "plan", "spec"], help="Working mode")

    args = parser.parse_args()

    if args.version:
        cmd_version(args)
        return

    if args.command is None:
        cmd_interactive(args)
        return

    cmds = {
        "interactive": cmd_interactive,
        "i": cmd_interactive,
        "shell": cmd_interactive,
        "exec": cmd_exec,
        "e": cmd_exec,
        "run": cmd_exec,
        "config": cmd_config,
        "show": cmd_show,
        "wizard": cmd_wizard,
        "mode": cmd_mode,
    }

    handler = cmds.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
