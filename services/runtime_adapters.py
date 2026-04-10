import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TASK_PROGRESS_RE = re.compile(r"(?:^|\n)\s*TASK\s+(\d+)\s+COMPLETE\b", re.IGNORECASE)
SESSION_COMPLETE_RE = re.compile(r"SESSION COMPLETE\s*(.*)", re.IGNORECASE | re.DOTALL)
SESSION_COMPLETE_LINE_RE = re.compile(r"^\s*SESSION COMPLETE\s*(.*)$", re.IGNORECASE)

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
SUMMARY_STOP_TOKENS = (
    "tokens used",
    "context window",
    "provider:",
    "model:",
    "workdir:",
    "approval:",
    "sandbox:",
    "reasoning effort:",
    "reasoning summaries:",
    "session id:",
    "--------",
)

from config import CONFIG


@dataclass(frozen=True)
class RuntimeLaunchMode:
    key: str
    label: str
    cli_args_config_key: Optional[str] = None
    default_cli_args: Optional[str] = None
    prompt_transport: Optional[str] = None
    prompt_style: Optional[str] = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuntimeAdapter:
    key: str
    label: str
    binary: str
    cli_args_config_key: str
    default_cli_args: str
    boot_delay_config_key: str
    default_boot_delay_seconds: int
    prompt_style: str
    prompt_preamble: str
    prompt_transport_config_key: Optional[str] = None
    default_prompt_transport: str = "stdin"
    default_launch_mode: Optional[str] = None
    launch_modes: tuple[RuntimeLaunchMode, ...] = field(default_factory=tuple)
    supports_freeform_prompt: bool = True
    default_yes_input: str = "y"
    default_no_input: str = "n"
    attention_tokens: tuple[str, ...] = field(default_factory=tuple)
    completion_tokens: tuple[str, ...] = field(default_factory=tuple)
    error_tokens: tuple[str, ...] = field(default_factory=tuple)
    ignored_error_patterns: tuple[str, ...] = field(default_factory=tuple)
    enter_button_label: str = "✅ Yes / Enter"
    no_button_label: str = "❌ No"
    exit_marker_prefix: str = "__BISHOPBOT_RUNTIME_EXIT__"
    ready_tokens: tuple[str, ...] = field(default_factory=tuple)
    not_ready_tokens: tuple[str, ...] = field(default_factory=tuple)

    def available_launch_modes(self) -> dict[str, RuntimeLaunchMode]:
        modes = {}
        for mode in self.launch_modes:
            modes[mode.key] = mode
            for alias in mode.aliases:
                modes[alias.lower()] = mode
        return modes

    def resolve_launch_mode(self, requested_mode: Optional[str] = None) -> Optional[RuntimeLaunchMode]:
        modes = self.available_launch_modes()
        if requested_mode:
            normalized = requested_mode.strip().lower()
            if normalized in modes:
                return modes[normalized]
        if self.default_launch_mode:
            return modes.get(self.default_launch_mode)
        return None

    def cli_args(self, launch_mode: Optional[str] = None) -> str:
        resolved_mode = self.resolve_launch_mode(launch_mode)
        config_key = self.cli_args_config_key
        default_value = self.default_cli_args
        if resolved_mode:
            config_key = resolved_mode.cli_args_config_key or config_key
            default_value = resolved_mode.default_cli_args or default_value
        value = str(CONFIG.get(config_key, default_value) or "").strip()
        return value or default_value

    def command_parts(self, launch_mode: Optional[str] = None) -> list[str]:
        args = self.cli_args(launch_mode=launch_mode)
        return [self.binary, *shlex.split(args)] if args else [self.binary]

    def launch_command(self, launch_mode: Optional[str] = None) -> str:
        return shlex.join(self.command_parts(launch_mode=launch_mode))

    def is_available(self) -> bool:
        return shutil.which(self.binary) is not None

    def prompt_transport(self, launch_mode: Optional[str] = None) -> str:
        resolved_mode = self.resolve_launch_mode(launch_mode)
        if resolved_mode and resolved_mode.prompt_transport in {"stdin", "argv"}:
            return resolved_mode.prompt_transport

        if self.prompt_transport_config_key:
            configured = str(CONFIG.get(self.prompt_transport_config_key, "") or "").strip().lower()
            if configured in {"stdin", "argv"}:
                return configured

        command_parts = self.command_parts(launch_mode=launch_mode)
        if len(command_parts) > 1 and command_parts[1] == "exec":
            return "argv"
        return self.default_prompt_transport

    def prompt_style_label(self, launch_mode: Optional[str] = None) -> str:
        resolved_mode = self.resolve_launch_mode(launch_mode)
        if resolved_mode and resolved_mode.prompt_style:
            return resolved_mode.prompt_style
        return self.prompt_style

    def supports_interactive_controls(self, launch_mode: Optional[str] = None) -> bool:
        return self.prompt_transport(launch_mode=launch_mode) == "stdin"

    def launch_bootstrap_command(
        self,
        cwd: str,
        initial_prompt: Optional[str] = None,
        launch_mode: Optional[str] = None,
        state_file: Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> str:
        quoted_cwd = shlex.quote(cwd)
        label = f"[{self.label}] starting in {self.prompt_style_label(launch_mode)}..."
        command_parts = self.command_parts(launch_mode=launch_mode)
        prompt_transport = self.prompt_transport(launch_mode=launch_mode)
        
        # If transport is 'argv', we include the prompt as an argument.
        if initial_prompt and prompt_transport == "argv":
            if self.key == "gemini":
                command_parts.extend(["--prompt", initial_prompt])
            else:
                command_parts.append(initial_prompt)
        
        launch_cmd = shlex.join(command_parts)

        # Build segments
        segments = [f"cd {quoted_cwd}"]
        
        if output_file:
            segments.append(f"mkdir -p {shlex.quote(str(Path(output_file).parent))}")
            segments.append(f": > {shlex.quote(output_file)}")

        if state_file:
            q_state = shlex.quote(state_file)
            segments.append(f"mkdir -p {shlex.quote(str(Path(state_file).parent))}")
            resolved_mode = launch_mode or self.default_launch_mode or "default"
            
            # Use echo instead of printf to avoid %Y issues
            initial_state = (
                f"echo 'status=running' > {q_state} ; "
                f"echo 'runtime={self.key}' >> {q_state} ; "
                f"echo 'launch_mode={resolved_mode}' >> {q_state} ; "
                f"echo \"started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)\" >> {q_state} ; "
                f"echo \"heartbeat_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)\" >> {q_state}"
            )
            segments.append(initial_state)
            
            # Heartbeat background loop using echo
            heartbeat_seconds = max(1, int(str(CONFIG.get("TERMINAL_STATE_HEARTBEAT_SECONDS", "3") or "3")))
            hb_loop = (
                f"while true; do "
                f"echo 'status=running' > {q_state} ; "
                f"echo 'runtime={self.key}' >> {q_state} ; "
                f"echo 'launch_mode={resolved_mode}' >> {q_state} ; "
                f"echo \"heartbeat_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)\" >> {q_state} ; "
                f"sleep {heartbeat_seconds} ; "
                f"done"
            )
            segments.append(f"({hb_loop}) & HEARTBEAT_PID=$!")

            # Trap for unexpected shell exit while the runtime is still active.
            trap_body = (
                f"if [ -n \"$HEARTBEAT_PID\" ]; then "
                f"EXIT_CODE=$?; "
                f"kill \"$HEARTBEAT_PID\" 2>/dev/null; "
                f"echo 'status=exited' > {q_state} ; "
                f"echo \"exit_code=$EXIT_CODE\" >> {q_state} ; "
                f"echo 'runtime={self.key}' >> {q_state} ; "
                f"echo 'launch_mode={resolved_mode}' >> {q_state} ; "
                f"echo \"exited_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)\" >> {q_state} ; "
            )
            if output_file:
                trap_body += f"printf '{self.exit_marker_prefix}:{self.key}:%s\\n' \"$EXIT_CODE\" | tee -a {shlex.quote(output_file)}; "
            else:
                trap_body += f"printf '{self.exit_marker_prefix}:{self.key}:%s\\n' \"$EXIT_CODE\"; "
            trap_body += "fi; "
            segments.append(f"trap {shlex.quote(trap_body.strip())} EXIT")

        segments.append(f"echo {shlex.quote(label)}")

        # Interactive runtimes such as Gemini need a TTY-preserving capture path.
        if output_file and prompt_transport == "stdin":
            segments.append(
                f"script -q -F {shlex.quote(output_file)} {launch_cmd}"
            )
            segments.append("RUNTIME_EXIT_CODE=$?")
        elif output_file:
            segments.append(f"{{ {launch_cmd}; }} 2>&1 | tee -a {shlex.quote(output_file)}")
            segments.append("RUNTIME_EXIT_CODE=${pipestatus[1]}")
        else:
            segments.append(launch_cmd)
            segments.append("RUNTIME_EXIT_CODE=$?")

        if state_file:
            q_state = shlex.quote(state_file)
            resolved_mode = launch_mode or self.default_launch_mode or "default"
            segments.append("[ -n \"$HEARTBEAT_PID\" ] && kill \"$HEARTBEAT_PID\" 2>/dev/null")
            segments.append("unset HEARTBEAT_PID")
            segments.append(f"echo 'status=exited' > {q_state}")
            segments.append(f"echo \"exit_code=$RUNTIME_EXIT_CODE\" >> {q_state}")
            segments.append(f"echo 'runtime={self.key}' >> {q_state}")
            segments.append(f"echo 'launch_mode={resolved_mode}' >> {q_state}")
            segments.append(f"echo \"exited_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)\" >> {q_state}")
            if output_file:
                segments.append(f"printf '{self.exit_marker_prefix}:{self.key}:%s\\n' \"$RUNTIME_EXIT_CODE\" | tee -a {shlex.quote(output_file)}")
            else:
                segments.append(f"printf '{self.exit_marker_prefix}:{self.key}:%s\\n' \"$RUNTIME_EXIT_CODE\"")

        return " ; ".join(segments)

    def build_initial_prompt(
        self,
        refined_instruction: str,
        tasks: Optional[List[str]] = None,
        context_block: Optional[str] = None,
        original_request: Optional[str] = None,
    ) -> str:
        task_lines = "\n".join(f"{idx + 1}. {task}" for idx, task in enumerate(tasks or []))
        sections = [self.prompt_preamble.strip()]
        if context_block:
            sections.extend(["", f"Persistent context:\n{context_block.strip()}"])
        if original_request and original_request.strip() and original_request.strip() != refined_instruction.strip():
            sections.extend(["", f"Original user request:\n{original_request.strip()}"])
        sections.extend(["", f"Refined request:\n{refined_instruction.strip()}"])
        if task_lines:
            sections.extend(["", f"Execution plan:\n{task_lines}"])
        return "\n".join(section for section in sections if section is not None).strip()

    def terminal_input_for_control(self, control: str) -> str:
        normalized = (control or "").strip().upper()
        if normalized == "ENTER":
            return ""
        if normalized == "Y":
            return self.default_yes_input
        if normalized == "N":
            return self.default_no_input
        return control

    def boot_delay_seconds(self) -> int:
        raw = CONFIG.get(self.boot_delay_config_key, self.default_boot_delay_seconds)
        try:
            return max(0, int(str(raw)))
        except Exception:
            return self.default_boot_delay_seconds

    def sanitize_output(self, output: Optional[str]) -> str:
        cleaned = ANSI_ESCAPE_RE.sub("", output or "")
        cleaned = cleaned.replace("\r", "")
        return CONTROL_CHAR_RE.sub("", cleaned)

    def _normalized_output(self, output: Optional[str]) -> str:
        return self.sanitize_output(output).lower()

    def _filtered_error_lines(self, output: Optional[str]) -> list[str]:
        cleaned = self.sanitize_output(output)
        lines = []
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lower_line = line.lower()
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.ignored_error_patterns):
                continue
            if any(token.lower() in lower_line for token in self.error_tokens):
                lines.append(line)
        return lines

    def detect_attention_required(self, output: str, launch_mode: Optional[str] = None) -> bool:
        if self.prompt_transport(launch_mode=launch_mode) == "argv" and self.extract_exit_code(output) is not None:
            return False
        haystack = self._normalized_output(output)
        return any(token.lower() in haystack for token in self.attention_tokens)

    def detect_completion(self, output: str) -> bool:
        exit_code = self.extract_exit_code(output)
        if exit_code is not None:
            return exit_code == 0
        haystack = self._normalized_output(output)
        return any(token.lower() in haystack for token in self.completion_tokens)

    def detect_ready(self, output: Optional[str], launch_mode: Optional[str] = None) -> bool:
        if self.prompt_transport(launch_mode=launch_mode) != "stdin":
            return True
        haystack = self._normalized_output(output)
        if not haystack:
            return False
        if any(token.lower() in haystack for token in self.not_ready_tokens):
            return False
        return any(token.lower() in haystack for token in self.ready_tokens)

    def detect_error(self, output: str) -> bool:
        exit_code = self.extract_exit_code(output)
        if exit_code is not None:
            return exit_code != 0
        return bool(self._filtered_error_lines(output))

    def extract_task_progress(self, output: Optional[str]) -> int:
        if not output:
            return 0
        matches = TASK_PROGRESS_RE.findall(self.sanitize_output(output))
        if not matches:
            return 0
        try:
            return max(int(match) for match in matches)
        except Exception:
            return 0

    def extract_final_summary(self, output: Optional[str]) -> Optional[str]:
        if not output:
            return None
        cleaned = self.sanitize_output(output)
        match = SESSION_COMPLETE_RE.search(cleaned)
        if not match:
            return None

        summary_lines: list[str] = []
        capture_started = False
        for raw_line in cleaned[match.start():].splitlines():
            line = raw_line.strip()
            if not line:
                if capture_started and summary_lines:
                    break
                continue

            line_match = SESSION_COMPLETE_LINE_RE.match(line)
            if line_match:
                capture_started = True
                inline_summary = (line_match.group(1) or "").strip()
                if inline_summary:
                    summary_lines.append(inline_summary)
                continue

            if not capture_started:
                continue

            lower_line = line.lower()
            if line.startswith(self.exit_marker_prefix):
                break
            if any(token in lower_line for token in SUMMARY_STOP_TOKENS):
                break
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.ignored_error_patterns):
                continue
            if lower_line.startswith("error"):
                break

            summary_lines.append(line)

        if not summary_lines:
            return None
        return " ".join(summary_lines).strip() or None

    def extract_exit_code(self, output: Optional[str]) -> Optional[int]:
        if not output:
            return None
        pattern = rf"{re.escape(self.exit_marker_prefix)}:{re.escape(self.key)}:(-?\d+)"
        match = re.search(pattern, output)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    def controls(self, launch_mode: Optional[str] = None) -> dict:
        return {
            "enter_button_label": self.enter_button_label,
            "no_button_label": self.no_button_label,
            "supports_interactive_controls": self.supports_interactive_controls(launch_mode=launch_mode),
        }

    def metadata(self, launch_mode: Optional[str] = None) -> dict:
        resolved_mode = self.resolve_launch_mode(launch_mode)
        return {
            "runtime": self.key,
            "runtime_label": self.label,
            "launch_mode": resolved_mode.key if resolved_mode else None,
            "launch_mode_label": resolved_mode.label if resolved_mode else self.prompt_style_label(launch_mode),
            "binary": self.binary,
            "cli_args": self.cli_args(launch_mode=launch_mode),
            "launch_command": self.launch_command(launch_mode=launch_mode),
            "prompt_style": self.prompt_style_label(launch_mode),
            "prompt_transport": self.prompt_transport(launch_mode=launch_mode),
            "supports_freeform_prompt": self.supports_freeform_prompt,
            "supports_interactive_controls": self.supports_interactive_controls(launch_mode=launch_mode),
            "boot_delay_seconds": self.boot_delay_seconds(),
            "is_available": self.is_available(),
            "controls": self.controls(launch_mode=launch_mode),
        }


def parse_runtime_invocation(runtime: Optional[str], input_text: str) -> Tuple[str, Optional[str], str]:
    default_runtime = get_runtime_adapter(runtime).key
    resolved_runtime = default_runtime
    resolved_mode: Optional[str] = None
    remaining_tokens: list[str] = []

    for token in (input_text or "").strip().split():
        normalized = token.strip().lower()
        bare = normalized[2:] if normalized.startswith("--") else normalized

        runtime_candidate = None
        if bare in RUNTIME_ADAPTERS:
            runtime_candidate = bare
        elif bare.startswith("runtime:"):
            explicit_runtime = bare.split(":", 1)[1].strip().lower()
            if explicit_runtime in RUNTIME_ADAPTERS:
                runtime_candidate = explicit_runtime

        if runtime_candidate:
            resolved_runtime = runtime_candidate
            continue

        adapter = get_runtime_adapter(resolved_runtime)
        available_modes = adapter.available_launch_modes()
        mode = available_modes.get(bare)
        if mode:
            resolved_mode = mode.key
            continue

        if bare.startswith("mode:"):
            explicit_mode = bare.split(":", 1)[1].strip().lower()
            mode = available_modes.get(explicit_mode)
            if mode:
                resolved_mode = mode.key
                continue

        remaining_tokens.append(token)

    remaining = " ".join(remaining_tokens).strip()
    return resolved_runtime, resolved_mode, remaining


RUNTIME_ADAPTERS: Dict[str, RuntimeAdapter] = {
    "gemini": RuntimeAdapter(
        key="gemini",
        label="Gemini",
        binary="/opt/homebrew/bin/gemini",
        cli_args_config_key="GEMINI_CLI_ARGS",
        default_cli_args="--yolo",
        boot_delay_config_key="GEMINI_BOOT_DELAY_SECONDS",
        default_boot_delay_seconds=10,
        prompt_style="YOLO automation mode",
        default_launch_mode="yolo",
        launch_modes=(
            RuntimeLaunchMode(
                key="yolo",
                label="YOLO",
                cli_args_config_key="GEMINI_CLI_ARGS_YOLO",
                default_cli_args="--yolo",
                prompt_transport="stdin",
                prompt_style="YOLO automation mode",
                aliases=("shell",),
            ),
        ),
        prompt_preamble=(
            "You are operating inside the Gemini CLI in YOLO automation mode. "
            "Execute the plan sequentially, narrate progress briefly, and do not stop for confirmation unless the terminal itself blocks."
        ),
        prompt_transport_config_key="GEMINI_PROMPT_TRANSPORT",
        default_prompt_transport="stdin",
        attention_tokens=("proceed?", "continue?", "y/n", "confirm", "press enter", "allow"),
        completion_tokens=("session complete",),
        error_tokens=("error", "failed", "traceback", "permission denied"),
        ready_tokens=("type your message or @path/to/file",),
        not_ready_tokens=("waiting for authentication",),
        enter_button_label="✅ Confirm / Enter",
    ),
    "codex": RuntimeAdapter(
        key="codex",
        label="Codex",
        binary="codex",
        cli_args_config_key="CODEX_CLI_ARGS",
        default_cli_args="exec --full-auto",
        boot_delay_config_key="CODEX_BOOT_DELAY_SECONDS",
        default_boot_delay_seconds=5,
        prompt_style="full-auto / yolo mode",
        default_launch_mode="full-auto",
        launch_modes=(
            RuntimeLaunchMode(
                key="full-auto",
                label="Full Auto",
                cli_args_config_key="CODEX_CLI_ARGS_FULL_AUTO",
                default_cli_args="exec --full-auto",
                prompt_transport="argv",
                prompt_style="full-auto execution mode",
                aliases=("fullauto", "exec",),
            ),
            RuntimeLaunchMode(
                key="yolo",
                label="YOLO",
                cli_args_config_key="CODEX_CLI_ARGS_YOLO",
                default_cli_args="--yolo",
                prompt_transport="stdin",
                prompt_style="YOLO shell mode",
                aliases=("shell", "interactive"),
            ),
        ),
        prompt_preamble=(
            "You are operating inside the real Codex CLI in high-autonomy terminal mode. "
            "Execute the plan sequentially, keep progress terse but visible, and do not ask for confirmation unless the CLI blocks on an unavoidable prompt."
        ),
        prompt_transport_config_key="CODEX_PROMPT_TRANSPORT",
        default_prompt_transport="argv",
        attention_tokens=("proceed?", "continue?", "y/n", "confirm", "press enter", "approval", "allow"),
        completion_tokens=("session complete",),
        error_tokens=("error", "failed", "traceback", "permission denied"),
        ready_tokens=("session id:", "approval:", "sandbox:", "reasoning effort:"),
        ignored_error_patterns=(
            r"failed to stat skills entry",
            r"failed to load skill",
            r"worker quit with fatal: transport channel closed",
            r"fail to delete session:",
        ),
        enter_button_label="✅ Continue / Enter",
    ),
}


def get_runtime_adapter(runtime: Optional[str]) -> RuntimeAdapter:
    normalized = (runtime or "gemini").strip().lower()
    return RUNTIME_ADAPTERS.get(normalized, RUNTIME_ADAPTERS["gemini"])
