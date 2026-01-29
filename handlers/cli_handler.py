import time
from services import openai_service, shell_service, git_service, slack_service
from services.terminal_session_manager import TerminalSessionManager
from utils import logger

def handle_cli_command(input_text, response_url=None, user_id=None):
    log_id = logger.get_new_id()
    try:
        # 1. Use OpenAI GPT-4o to process the message
        refined_input = openai_service.process_message(input_text)
        
        # 2. Inform Slack Gemini is starting
        if response_url:
            slack_service.send_delayed_message(
                response_url, 
                f"🚀 *Gemini is starting for <@{user_id}>...*\nConnecting to skills and MCP with refined prompt: `{refined_input}`"
            )

        # 3. Start Terminal Session via Manager
        session_id = TerminalSessionManager.start_session(
            user_id=user_id,
            response_url=response_url,
            initial_command=refined_input
        )
        
        if session_id:
            exec_output = f"Session `{session_id}` started. Monitoring thread active (40s interval)."
        else:
            exec_output = "FAILED to start terminal session"
        
        # 4. Log the result
        logger.log_verbose(log_id, refined_input, exec_output)
        
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
