from services import openai_service, reply_service
from services.runtime_adapters import get_runtime_adapter, parse_runtime_invocation
from services.task_planner import TaskPlanner
from services.terminal_session_manager import TerminalSessionManager
from utils import logger

def handle_cli_command(input_text, response_url=None, user_id=None, mode="gemini"):
    log_id = logger.get_new_id()
    try:
        resolved_runtime, launch_mode, normalized_input = parse_runtime_invocation(mode, input_text)
        adapter = get_runtime_adapter(resolved_runtime)
        selected_mode = adapter.resolve_launch_mode(launch_mode)
        effective_input = normalized_input or input_text

        # 1. Use OpenAI GPT-4o to process the message
        refined_input = openai_service.process_message(effective_input)
        try:
            plan_text, tasks = TaskPlanner.plan_tasks(refined_input, mode=resolved_runtime)
        except Exception as exc:
            print(f"⚠️ Task planner failed: {exc}")
            plan_text = refined_input
            tasks = [refined_input]
        
        # 2. Inform Slack runtime is starting
        if response_url:
            summary = TaskPlanner.build_plan_summary(tasks, mode=resolved_runtime)
            who = f"<@{user_id}>" if not reply_service.is_whatsapp_target(response_url) else str(user_id)
            mode_line = ""
            if selected_mode:
                mode_line = f"\nLaunch mode: *{selected_mode.label}* (`{adapter.launch_command(launch_mode=selected_mode.key)}`)"
            if resolved_runtime != mode:
                mode_line += f"\nRuntime override: *{adapter.label}*"
            reply_service.send(
                response_url, 
                f"🚀 *{adapter.label} automation starting for {who}...*{mode_line}\n{summary}"
            )

        initial_command = TaskPlanner.build_cli_prompt(refined_input, tasks, mode=resolved_runtime)

        # 3. Start Terminal Session via Manager
        session_id = TerminalSessionManager.start_session(
            user_id=user_id,
            response_url=response_url,
            initial_command=initial_command,
            plan_text=plan_text,
            tasks=tasks,
            agent_mode=resolved_runtime,
            launch_mode=selected_mode.key if selected_mode else None,
        )
        
        if session_id:
            exec_output = f"Session `{session_id}` started (runtime={resolved_runtime}, mode={selected_mode.key if selected_mode else 'default'}). Monitoring thread active (40s interval)."
        else:
            exec_output = "FAILED to start terminal session"
        
        # 4. Log the result
        log_output = f"{exec_output}\n\nPlan:\n{plan_text}"
        logger.log_verbose(log_id, refined_input, log_output)
        
        return {
            "success": True, 
            "output": exec_output, 
            "code": refined_input,
            "log_id": log_id,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.log_error(log_id, str(e))
        return {
            "success": False, 
            "error": str(e), 
            "log_id": log_id
        }
