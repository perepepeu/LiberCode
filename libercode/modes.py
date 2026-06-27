from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


SYSTEM_PROMPTS = {
    "build": _load_prompt("build"),
    "plan": _load_prompt("plan"),
    "spec": _load_prompt("spec"),
    "debug": _load_prompt("debug"),
}


def get_system_prompt(mode: str, context: dict = None) -> str:
    base = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["build"])
    ctx = context or {}
    extras = []
    if ctx.get("project_summary"):
        extras.append(f"Project context: {ctx['project_summary']}")
    if ctx.get("current_task"):
        extras.append(f"Current task: {ctx['current_task']}")
    if ctx.get("memory"):
        memory_items = ctx["memory"]
        if memory_items:
            extras.append("Project memory:")
            for item in memory_items[:10]:
                extras.append(f"  {item['key']}: {item['value'][:200]}")
    if extras:
        return base + "\n\n" + "\n".join(extras)
    return base
