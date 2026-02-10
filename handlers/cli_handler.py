import time
from services import openai_service, shell_service, git_service, reply_service
from services.task_planner import TaskPlanner
from services.terminal_session_manager import TerminalSessionManager
from utils import logger

def handle_cli_command(input_text, response_url=None, user_id=None, mode="gemini"):
    log_id = logger.get_new_id()
    try:
        # 1. Use OpenAI GPT-4o to process the message
        refined_input = openai_service.process_message(input_text)
        try:
            plan_text, tasks = TaskPlanner.plan_tasks(refined_input, mode=mode)
        except Exception as exc:
            print(f"⚠️ Task planner failed: {exc}")
            plan_text = refined_input
            tasks = [refined_input]
        
        # 2. Inform Slack Gemini is starting
        if response_url:
            summary = TaskPlanner.build_plan_summary(tasks, mode=mode)
            who = f"<@{user_id}>" if not reply_service.is_whatsapp_target(response_url) else str(user_id)
            reply_service.send(
                response_url, 
                f"🚀 *{mode.capitalize()} automation starting for {who}...*\n{summary}"
            )

        initial_command = TaskPlanner.build_cli_prompt(refined_input, tasks, mode=mode)

        # 3. Start Terminal Session via Manager
        session_id = TerminalSessionManager.start_session(
            user_id=user_id,
            response_url=response_url,
            initial_command=initial_command,
            plan_text=plan_text,
            tasks=tasks,
            agent_mode=mode
        )
        
        if session_id:
            exec_output = f"Session `{session_id}` started (mode={mode}). Monitoring thread active (40s interval)."
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
