from __future__ import annotations

import re
from services import openai_service
from services.runtime_adapters import get_runtime_adapter


class TaskPlanner:
    MAX_TASKS = 8

    SYSTEM_PROMPTS = {
        "gemini": (
            "You are a Gemini CLI expert operating in YOLO automation mode. "
            "Translate the user's request into a concise, numbered plan of terminal-level tasks. "
            "Each task should be a standalone action that Gemini can reason about and execute sequentially."
        ),
        "codex": (
            "You are a Codex CLI expert operating in high-autonomy terminal mode. "
            "Break the request into a concise, numbered plan of terminal-level tasks that Codex can execute sequentially."
        ),
    }

    @staticmethod
    def plan_tasks(refined_instruction: str, mode: str = "gemini"):
        system_prompt = TaskPlanner.SYSTEM_PROMPTS.get(mode, TaskPlanner.SYSTEM_PROMPTS["gemini"])
        prompt = (
            "Build the most reliable terminal task plan for the request below. "
            "Return only a numbered list (1., 2., …) with each step on its own line.\n\n"
            f"Refined request:\n{refined_instruction}\n\nPlan:"
        )

        plan_text = openai_service.generate_response(prompt, system_prompt=system_prompt).strip()
        tasks = TaskPlanner._extract_tasks(plan_text)

        return plan_text, tasks

    @staticmethod
    def _extract_tasks(plan_text: str):
        tasks = []
        for line in plan_text.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(?:\d+[\.\)]\s*)?(.*\S.*)$', line)
            if match:
                tasks.append(match.group(1).strip())
            elif not tasks and line:
                tasks.append(line)

        if not tasks and plan_text:
            tasks = [plan_text.strip()]

        return tasks[: TaskPlanner.MAX_TASKS]

    @staticmethod
    def build_plan_summary(tasks: list[str], mode: str = "gemini"):
        header = f"🧭 *{mode.capitalize()} plan: {len(tasks)} step{'s' if len(tasks) != 1 else ''}*"
        if not tasks:
            return f"{header}\n_No discrete steps could be generated; running the refined request directly._"

        lines = "\n".join(f"{idx + 1}. {task}" for idx, task in enumerate(tasks))
        execution_mode = "YOLO mode" if mode == "gemini" else "full-auto / yolo mode"
        return f"{header}\n{lines}\n\nExecution will start immediately in {execution_mode}."

    @staticmethod
    def build_cli_prompt(
        refined_instruction: str,
        tasks: list[str],
        mode: str = "gemini",
        *,
        context_block: str | None = None,
        original_request: str | None = None,
    ):
        adapter = get_runtime_adapter(mode)
        base_prompt = adapter.build_initial_prompt(
            refined_instruction,
            tasks,
            context_block=context_block,
            original_request=original_request,
        )
        execution_suffix = (
            "\n\nWhen you finish each step, print \"TASK {step_number} COMPLETE\" and keep going. "
            "Only if you learn a durable, reusable fact, update `agent-context/vibes.md` and record it in the SQLite memory using `./scripts/agent_memory.py note ...` or direct sqlite. "
            "The session lifecycle is already tracked automatically, so do not spam the memory DB with routine progress. "
            "After all steps succeed, run `git status`, commit any changes with a descriptive message if there are staged files, and push to the current remote if appropriate. "
            "Then print \"SESSION COMPLETE\" on its own line followed by the final summary."
        )
        return f"{base_prompt}{execution_suffix}"
