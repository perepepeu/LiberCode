class StopConditionChecker:
    def __init__(self, store, shell, git_helper, memory):
        self._store = store
        self._shell = shell
        self._git = git_helper
        self._memory = memory

    def check(self, task_id: int) -> dict:
        task = self._store.task_get(task_id)
        if not task:
            return {"done": True, "reason": "Task not found"}

        if task.get("status") == "completed":
            return {"done": True, "reason": "Task marked complete"}

        if task.get("progress", 0) >= 1.0:
            return {"done": True, "reason": "Progress is 100%"}

        if task.get("status") in ("failed", "paused"):
            return {"done": False, "reason": f"Task is {task['status']}", "task": task}

        return {"done": False, "reason": "In progress", "task": task}

    def auto_check(self, task_id: int, mode: str) -> dict:
        result = self.check(task_id)
        if result["done"]:
            return result

        task = result.get("task", {})
        title = task.get("title", "")
        description = task.get("description", "")

        verification_prompt = (
            f"[Stop Condition Check] Task: {title}\n"
            f"Description: {description}\n\n"
            f"Has this task been fully completed? Check:\n"
            f"1. Are all code changes done?\n"
            f"2. Have all acceptance criteria been met?\n"
            f"3. Have tests been run and pass?\n"
            f"4. Is the code committed if needed?\n\n"
            f"Reply with YES and a brief summary if done, or NO with what's remaining."
        )

        return {
            "done": False,
            "reason": "Needs verification",
            "verification_prompt": verification_prompt,
            "task": task,
        }
