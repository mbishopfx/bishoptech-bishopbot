import time
import uuid
import threading
from datetime import datetime, timezone
from services import shell_service, reply_service, session_link_service, session_log_service, session_output_service, session_state_service
from services.runtime_adapters import get_runtime_adapter
from config import CONFIG

# Global dictionary to track active sessions
# session_id -> {window_id, thread, response_url, user_id, last_output, active}
SESSIONS = {}

class TerminalSessionManager:
    SESSIONS = SESSIONS

    @staticmethod
    def start_session(user_id, response_url, initial_command, plan_text="", tasks=None, agent_mode="gemini", launch_mode=None):
        """Starts a runtime-aware terminal session and kicks off monitoring."""
        session_id = str(uuid.uuid4())[:8]
        adapter = get_runtime_adapter(agent_mode)
        resolved_launch_mode = adapter.resolve_launch_mode(launch_mode)
        adapter_meta = adapter.metadata(launch_mode=resolved_launch_mode.key if resolved_launch_mode else None)

        if not adapter_meta.get("is_available"):
            print(f"❌ Failed to start {adapter.label} terminal for session {session_id}: binary missing")
            return None

        effective_launch_mode = resolved_launch_mode.key if resolved_launch_mode else None
        state_path = session_state_service.initialize_session_state(
            session_id,
            runtime=adapter.key,
            launch_mode=effective_launch_mode,
            prompt_transport=adapter.prompt_transport(launch_mode=effective_launch_mode),
        )
        output_path = session_output_service.initialize_session_output(session_id)

        # 1. Start the actual terminal window for the requested runtime.
        # Some runtimes (for example `codex exec --full-auto`) want the prompt on argv at launch time
        # instead of waiting for keystroke injection after boot.
        launch_prompt = initial_command if adapter.prompt_transport(launch_mode=effective_launch_mode) == "argv" else None
        window_id = shell_service.start_terminal_session(
            runtime=adapter.key,
            initial_prompt=launch_prompt,
            launch_mode=effective_launch_mode,
            state_file=state_path,
            output_file=output_path,
        )

        if not window_id:
            print(f"❌ Failed to start {adapter.label} terminal for session {session_id}")
            return None

        prompt_transport = adapter.prompt_transport(launch_mode=effective_launch_mode)
        boot_delay = adapter.boot_delay_seconds()

        # 2. For interactive stdin-driven shells, give the runtime time to become ready
        # before typing the initial prompt. For argv-native launches (for example
        # `codex exec --full-auto`), do not sleep here: the process may finish quickly,
        # and delaying polling risks missing the real terminal lifecycle entirely.
        if prompt_transport == "stdin":
            time.sleep(max(0, boot_delay))
            shell_service.send_input_to_terminal(initial_command, window_id=window_id)

        # 3. Store session info
        SESSIONS[session_id] = {
            "window_id": window_id,
            "response_url": response_url,
            "user_id": user_id,
            "last_output": "",
            "last_raw_output": "",
            "last_summary_output": "",
            "active": True,
            "start_time": time.time(),
            "last_poll_time": time.time(),
            "status": "booting",
            "needs_input": False,
            "completed_at": None,
            "runtime": adapter.key,
            "runtime_label": adapter.label,
            "launch_mode": effective_launch_mode,
            "launch_mode_label": adapter_meta.get("launch_mode_label"),
            "launch_command": adapter.launch_command(launch_mode=effective_launch_mode),
            "prompt_transport": prompt_transport,
            "boot_delay_seconds": boot_delay,
            "runtime_metadata": adapter_meta,
            "state_path": state_path,
            "output_path": output_path,
            "terminal_exists": True,
            "terminal_busy": False,
            "completed_task_count": 0,
            "final_summary": None,
        }
        SESSIONS[session_id]["plan_text"] = plan_text
        SESSIONS[session_id]["tasks"] = tasks or []
        SESSIONS[session_id]["agent_mode"] = adapter.key
        SESSIONS[session_id]["current_task_index"] = 0
        SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])

        # Keep a per-user "last session" pointer (used by WhatsApp controls like !enter).
        if user_id and session_id:
            session_link_service.set_last_session(str(user_id), session_id)
        
        # 5. Start background polling thread
        thread = threading.Thread(
            target=TerminalSessionManager._poll_loop, 
            args=(session_id,), 
            daemon=True
        )
        SESSIONS[session_id]["thread"] = thread
        thread.start()
        
        if plan_text:
            plan_header = f"🧭 {adapter.label} plan for session `{session_id}`"
            runtime_context = (
                f"Runtime: {adapter.label}\n"
                f"Launch mode: {adapter_meta.get('launch_mode_label', adapter.prompt_style_label(launch_mode))}\n"
                f"Launch: {adapter.launch_command(launch_mode=launch_mode)}\n"
                f"Boot delay: {boot_delay}s\n\n"
                f"{plan_text}"
            )
            TerminalSessionManager.send_status_to_slack(session_id, runtime_context, header_override=plan_header)
        
        return session_id

    @staticmethod
    def _poll_loop(session_id):
        """Background thread that polls terminal output and posts to Slack."""
        print(f"🧵 Polling thread started for session {session_id}")
        
        timeout = 1800  # 30 minutes
        try:
            poll_interval = int(str(CONFIG.get("TERMINAL_POLL_INTERVAL_SECONDS", "40")))
        except Exception:
            poll_interval = 40
        
        while session_id in SESSIONS and SESSIONS[session_id]["active"]:
            session = SESSIONS[session_id]
            adapter = get_runtime_adapter(session.get("runtime"))
            try:
                close_recovery_grace = max(0, int(str(CONFIG.get("TERMINAL_CLOSE_RECOVERY_GRACE_SECONDS", "20"))))
            except Exception:
                close_recovery_grace = 20

            # Check for timeout
            if time.time() - session["start_time"] > timeout:
                session["status"] = "timed_out"
                timeout_note = "⏰ *Session Timeout:* Closing terminal session after 30 minutes."
                TerminalSessionManager.send_status_to_slack(session_id, timeout_note)
                session_log_service.append_event(session_id, "Timeout", timeout_note)
                TerminalSessionManager.close_session(session_id)
                break

            # Capture output + terminal state
            snapshot = shell_service.get_terminal_snapshot(session["window_id"])
            full_output = TerminalSessionManager._sanitize_snapshot_output(snapshot.contents)
            capture_output = TerminalSessionManager._sanitize_snapshot_output(
                session_output_service.read_output_file(session.get("output_path"))
            )
            parse_output = TerminalSessionManager._best_runtime_parse_output(full_output, capture_output)
            current_output = TerminalSessionManager._format_snapshot_output(
                snapshot.contents,
                tail_lines=TerminalSessionManager._tail_lines_for_target(session.get("response_url")),
            )
            previous_exists = session.get("terminal_exists", True)
            session["terminal_exists"] = snapshot.exists
            session["terminal_busy"] = snapshot.busy
            runtime_state = session_state_service.parse_session_state(session_id)
            if snapshot.exists:
                session["terminal_missing_since"] = None
            elif previous_exists and not snapshot.exists and not session.get("terminal_missing_since"):
                session["terminal_missing_since"] = time.time()
            session["runtime_state"] = runtime_state

            # Detect runtime state from the full terminal buffer so completion / error / progress
            # markers are not lost when Slack/WhatsApp tails only the latest lines.
            needs_input = adapter.detect_attention_required(parse_output, launch_mode=session.get("launch_mode"))
            is_complete = adapter.detect_completion(parse_output)
            has_error = adapter.detect_error(parse_output)
            exit_code = adapter.extract_exit_code(parse_output)
            state_exit_code = runtime_state.get("exit_code")
            if exit_code is None and state_exit_code not in {None, ""}:
                try:
                    exit_code = int(state_exit_code)
                except Exception:
                    pass
            state_status = (runtime_state.get("status") or "").strip().lower()
            if state_status == "exited" and exit_code == 0:
                is_complete = True
            elif state_status == "exited" and exit_code not in {None, 0}:
                has_error = True
            completed_task_count = adapter.extract_task_progress(parse_output)
            final_summary = adapter.extract_final_summary(parse_output)

            session["needs_input"] = needs_input
            session["exit_code"] = exit_code
            session["completed_task_count"] = completed_task_count
            session["current_task_index"] = completed_task_count
            if final_summary:
                session["final_summary"] = final_summary
            if is_complete:
                session["status"] = "completed"
                session["completed_at"] = time.time()
            elif has_error:
                session["status"] = "attention_needed"
            elif needs_input:
                session["status"] = "waiting_for_input"
            elif snapshot.exists and snapshot.busy:
                session["status"] = "running"
            elif snapshot.exists and not snapshot.busy and session.get("prompt_transport") == "argv":
                session["status"] = "settled"
            else:
                session["status"] = "running"

            if current_output and current_output != session["last_output"]:
                TerminalSessionManager.send_status_to_slack(session_id, current_output, needs_input=needs_input)
                session_log_service.append_snapshot(
                    session_id,
                    status=session.get("status", "running"),
                    exists=snapshot.exists,
                    busy=snapshot.busy,
                    visible_tail=current_output,
                    full_output=parse_output,
                )
                session["last_output"] = current_output
                session["last_raw_output"] = snapshot.contents or ""
                session["last_poll_time"] = time.time()

            if is_complete:
                completion_note = (
                    f"✅ *{session.get('runtime_label', 'Agent')} session `{session_id}` marked complete.*\n"
                    f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                    f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                    f"Launch: {session.get('launch_command', '(unknown)')}\n"
                    f"Progress: {TerminalSessionManager._progress_label(session)}\n"
                    f"Exit code: {session.get('exit_code', 0)}"
                )
                if session.get("final_summary"):
                    completion_note += f"\nSummary: {session.get('final_summary')}"
                if completion_note != session.get("last_summary_output"):
                    TerminalSessionManager.send_status_to_slack(session_id, completion_note, header_override=f"✅ {session.get('runtime_label', 'Agent')} session `{session_id}` complete")
                    session_log_service.append_event(session_id, "Completed", completion_note)
                    session["last_summary_output"] = completion_note
                TerminalSessionManager.close_session(session_id)
                break

            if has_error and exit_code is not None:
                failure_note = (
                    f"❌ *{session.get('runtime_label', 'Agent')} session `{session_id}` exited with an error.*\n"
                    f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                    f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                    f"Launch: {session.get('launch_command', '(unknown)')}\n"
                    f"Exit code: {exit_code}"
                )
                if failure_note != session.get("last_summary_output"):
                    TerminalSessionManager.send_status_to_slack(session_id, failure_note, header_override=f"❌ {session.get('runtime_label', 'Agent')} session `{session_id}` failed")
                    session_log_service.append_event(session_id, "Failed", failure_note)
                    session["last_summary_output"] = failure_note
                TerminalSessionManager.close_session(session_id)
                break

            if not snapshot.exists and session.get("terminal_missing_since") and state_status == "exited" and exit_code == 0:
                recovered_note = (
                    f"✅ *{session.get('runtime_label', 'Agent')} session `{session_id}` exited cleanly after its terminal closed.*\n"
                    f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                    f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                    f"Launch: {session.get('launch_command', '(unknown)')}\n"
                    f"Progress: {TerminalSessionManager._progress_label(session)}\n"
                    f"Exit code: {exit_code}\n"
                    "Recovered completion from the runtime state sidecar after the terminal window disappeared."
                )
                if session.get("final_summary"):
                    recovered_note += f"\nSummary: {session.get('final_summary')}"
                if recovered_note != session.get("last_summary_output"):
                    TerminalSessionManager.send_status_to_slack(session_id, recovered_note, header_override=f"✅ {session.get('runtime_label', 'Agent')} session `{session_id}` recovered after terminal close")
                    session_log_service.append_event(session_id, "Recovered completion", recovered_note)
                    session["last_summary_output"] = recovered_note
                TerminalSessionManager.close_session(session_id)
                break

            if not snapshot.exists and session.get("terminal_missing_since") and state_status == "exited" and exit_code not in {None, 0}:
                recovered_failure_note = (
                    f"❌ *{session.get('runtime_label', 'Agent')} session `{session_id}` exited after its terminal closed.*\n"
                    f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                    f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                    f"Launch: {session.get('launch_command', '(unknown)')}\n"
                    f"Exit code: {exit_code}\n"
                    "Recovered failure from the runtime state sidecar after the terminal window disappeared."
                )
                if recovered_failure_note != session.get("last_summary_output"):
                    TerminalSessionManager.send_status_to_slack(session_id, recovered_failure_note, header_override=f"❌ {session.get('runtime_label', 'Agent')} session `{session_id}` failed after terminal close")
                    session_log_service.append_event(session_id, "Recovered failure", recovered_failure_note)
                    session["last_summary_output"] = recovered_failure_note
                TerminalSessionManager.close_session(session_id)
                break

            if not snapshot.exists and session.get("terminal_missing_since") and state_status in {"running", "launching"} and TerminalSessionManager._runtime_state_heartbeat_is_fresh(runtime_state):
                heartbeat_note = (
                    f"🫀 *{session.get('runtime_label', 'Agent')} session `{session_id}` heartbeat still looks alive after the terminal closed.*\n"
                    f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                    f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                    f"Launch: {session.get('launch_command', '(unknown)')}\n"
                    f"Last heartbeat: {runtime_state.get('heartbeat_at', '(unknown)')}\n"
                    "BishopBot is keeping the session open because the runtime sidecar still reports a fresh heartbeat even though Terminal is not currently visible."
                )
                if heartbeat_note != session.get("last_summary_output"):
                    TerminalSessionManager.send_status_to_slack(session_id, heartbeat_note, header_override=f"🫀 {session.get('runtime_label', 'Agent')} session `{session_id}` heartbeat recovered")
                    session_log_service.append_event(session_id, "Heartbeat recovery", heartbeat_note)
                    session["last_summary_output"] = heartbeat_note
                time.sleep(5)
                continue

            if not snapshot.exists and session.get("terminal_missing_since"):
                missing_since = session.get("terminal_missing_since") or time.time()
                missing_for_seconds = max(0, int(time.time() - missing_since))
                if missing_for_seconds < close_recovery_grace:
                    recovery_note = (
                        f"🕵️ *{session.get('runtime_label', 'Agent')} session `{session_id}` terminal closed; waiting for runtime-state reconciliation.*\n"
                        f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                        f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                        f"Launch: {session.get('launch_command', '(unknown)')}\n"
                        f"Grace window: {close_recovery_grace}s\n"
                        "The terminal disappeared before an explicit completion marker was captured, so BishopBot is checking the runtime sidecar before marking this as lost."
                    )
                    if recovery_note != session.get("last_summary_output"):
                        TerminalSessionManager.send_status_to_slack(session_id, recovery_note, header_override=f"🕵️ {session.get('runtime_label', 'Agent')} session `{session_id}` reconciling terminal close")
                        session_log_service.append_event(session_id, "Terminal close recovery", recovery_note)
                        session["last_summary_output"] = recovery_note
                    time.sleep(5)
                    continue

                closed_note = (
                    f"⚠️ *{session.get('runtime_label', 'Agent')} session `{session_id}` lost its terminal window.*\n"
                    f"Runtime: {session.get('runtime_label', 'Agent')}\n"
                    f"Launch mode: {session.get('launch_mode_label', 'default')}\n"
                    f"Launch: {session.get('launch_command', '(unknown)')}\n"
                    f"Recovery grace elapsed: {close_recovery_grace}s\n"
                    "The runtime window disappeared before an explicit completion marker was captured or the sidecar confirmed a clean exit."
                )
                if closed_note != session.get("last_summary_output"):
                    TerminalSessionManager.send_status_to_slack(session_id, closed_note, header_override=f"⚠️ {session.get('runtime_label', 'Agent')} session `{session_id}` lost terminal")
                    session_log_service.append_event(session_id, "Lost terminal", closed_note)
                    session["last_summary_output"] = closed_note
                TerminalSessionManager.close_session(session_id)
                break

            time.sleep(max(5, poll_interval))
        
        print(f"🧵 Polling thread exiting for session {session_id}")

    @staticmethod
    def _tail_lines_for_target(target):
        try:
            if reply_service.is_whatsapp_target(target):
                return int(str(CONFIG.get("TERMINAL_TAIL_LINES_WHATSAPP", "40")))
            return int(str(CONFIG.get("TERMINAL_TAIL_LINES_SLACK", "15")))
        except Exception:
            return 15

    @staticmethod
    def get_terminal_contents(window_id, tail_lines=15):
        """Uses AppleScript to get the current visible text in the terminal window."""
        snapshot = shell_service.get_terminal_snapshot(window_id)
        return TerminalSessionManager._format_snapshot_output(snapshot.contents, tail_lines=tail_lines)

    @staticmethod
    def _sanitize_snapshot_output(full_text):
        return get_runtime_adapter(None).sanitize_output(full_text or "").strip()

    @staticmethod
    def _format_snapshot_output(full_text, tail_lines=15):
        cleaned = TerminalSessionManager._sanitize_snapshot_output(full_text)
        lines = cleaned.splitlines()
        if tail_lines and len(lines) > tail_lines:
            last_lines = [line for line in lines[-tail_lines:] if line.strip()]
            return "\n".join(last_lines)
        return cleaned

    @staticmethod
    def _best_runtime_parse_output(snapshot_output, capture_output):
        snapshot_clean = TerminalSessionManager._sanitize_snapshot_output(snapshot_output)
        capture_clean = TerminalSessionManager._sanitize_snapshot_output(capture_output)
        if not capture_clean:
            return snapshot_clean
        if not snapshot_clean:
            return capture_clean

        preferred_markers = ("SESSION COMPLETE", "TASK ", "__BISHOPBOT_RUNTIME_EXIT__")
        capture_has_preferred = any(marker in capture_clean for marker in preferred_markers)
        snapshot_has_preferred = any(marker in snapshot_clean for marker in preferred_markers)

        if capture_has_preferred and not snapshot_has_preferred:
            return capture_clean
        if len(capture_clean) > len(snapshot_clean):
            return capture_clean
        return snapshot_clean

    @staticmethod
    def _progress_label(session):
        total = len(session.get("tasks") or [])
        completed = int(session.get("completed_task_count") or 0)
        if total > 0:
            completed = min(completed, total)
            return f"{completed}/{total} tasks"
        if completed > 0:
            return f"{completed} task{'s' if completed != 1 else ''} completed"
        return "No progress markers yet"

    @staticmethod
    def _parse_runtime_timestamp(value):
        if not value:
            return None
        try:
            normalized = str(value).strip().replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except Exception:
            return None

    @staticmethod
    def _runtime_state_heartbeat_is_fresh(runtime_state):
        heartbeat = TerminalSessionManager._parse_runtime_timestamp(runtime_state.get("heartbeat_at"))
        if not heartbeat:
            return False
        try:
            stale_after = max(1, int(str(CONFIG.get("TERMINAL_STATE_HEARTBEAT_STALE_SECONDS", "15"))))
        except Exception:
            stale_after = 15
        age_seconds = (datetime.now(timezone.utc) - heartbeat.astimezone(timezone.utc)).total_seconds()
        return age_seconds <= stale_after

    @staticmethod
    def send_status_to_slack(session_id, output, needs_input=False, header_override=None):
        """Sends a status update to Slack (response_url) or WhatsApp (whatsapp:<wa_id>)."""
        session = SESSIONS.get(session_id)
        if not session:
            return
            
        runtime_label = session.get("runtime_label", session.get("agent_mode", "Gemini").capitalize())
        runtime_meta = session.get("runtime_metadata") or {}
        controls = runtime_meta.get("controls") or {}
        session_status = session.get("status", "running").replace("_", " ").title()
        header = header_override or f"🤖 *{runtime_label} Session `{session_id}` Status Update*"
        if needs_input:
            header += " ⚠️ *ACTION REQUIRED*"

        prompt_transport = session.get("prompt_transport") or runtime_meta.get("prompt_transport") or "stdin"
        launch_mode_label = session.get("launch_mode_label") or runtime_meta.get("launch_mode_label") or runtime_meta.get("prompt_style") or "default"
        context_line = (
            f"_Runtime:_ {runtime_label}  •  _Mode:_ {launch_mode_label}  •  _Status:_ {session_status}  •  _Progress:_ {TerminalSessionManager._progress_label(session)}  •  _Launch:_ `{session.get('launch_command', '(unknown)')}`  •  _Prompt:_ `{prompt_transport}`"
        )

        summary_line = session.get("final_summary")
        if summary_line:
            context_line += f"  •  _Summary:_ {summary_line[:180]}"

        # Format the output in a code block
        formatted_output = f"```\n{output}\n```"

        target = session.get("response_url")
        if reply_service.is_whatsapp_target(target):
            msg = f"{header}\n{context_line}\n{formatted_output}"
            if needs_input:
                msg += f"\n\nControls: !enter {session_id} | !n {session_id} | !y {session_id} | !stop {session_id}"
            else:
                msg += f"\n\nControls: !status {session_id} | !stop {session_id}"
            reply_service.send(target, msg)
            return

        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header}
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": context_line}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": formatted_output}
            }
        ]

        action_elements = []
        if controls.get("supports_interactive_controls", True):
            action_elements.extend([
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": controls.get("enter_button_label", "✅ Yes / Enter")},
                    "value": f"{session_id}:ENTER",
                    "action_id": "cli_input_enter"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": controls.get("no_button_label", "❌ No")},
                    "value": f"{session_id}:N",
                    "action_id": "cli_input_no"
                },
            ])

        action_elements.extend([
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📟 Status"},
                "value": f"{session_id}:STATUS",
                "action_id": "cli_status"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🛑 Stop Session"},
                "style": "danger",
                "value": f"{session_id}:STOP",
                "action_id": "cli_stop"
            }
        ])

        blocks.append({
            "type": "actions",
            "elements": action_elements
        })

        reply_service.send(target, header, blocks=blocks)

    @staticmethod
    def send_input(session_id, input_text):
        """Sends input to the active terminal session."""
        session = SESSIONS.get(session_id)
        if not session or not session["active"]:
            return False

        adapter = get_runtime_adapter(session.get("runtime"))
        translated_input = adapter.terminal_input_for_control(input_text)
        return shell_service.send_input_to_terminal(translated_input, window_id=session["window_id"])

    @staticmethod
    def snapshot(session_id):
        """Capture current tailed output for a session (useful for manual status requests)."""
        session = SESSIONS.get(session_id)
        if not session or not session.get("active"):
            return None
        return TerminalSessionManager.get_terminal_contents(
            session["window_id"],
            tail_lines=TerminalSessionManager._tail_lines_for_target(session.get("response_url")),
        )

    @staticmethod
    def close_session(session_id):
        """Closes a session and flags it as inactive."""
        session = SESSIONS.get(session_id)
        if session:
            session["active"] = False
            if session.get("status") not in {"completed", "timed_out"}:
                session["status"] = "closed"
            session_log_service.append_event(
                session_id,
                "Session closed",
                f"Final status: {session.get('status', 'closed')}\nLog path: {session.get('log_path', '(default)')}"
            )
            # We don't necessarily want to hard-kill the terminal window automatically
            # but we could if needed. For now just stop polling.
            print(f"✅ Session {session_id} closed.")
            return True
        return False
