import time
from services import openai_service, shell_service, git_service, slack_service
from utils import logger

def handle_cli_command(input_text, response_url=None):
    log_id = logger.get_new_id()
    try:
        # 1. Use OpenAI GPT-4o to process the message
        refined_input = openai_service.process_message(input_text)
        
        # 2. Inform Slack Gemini is starting
        if response_url:
            slack_service.send_delayed_message(response_url, "🚀 *Gemini is starting, please hold...* (Connecting to skills and MCP)")

        # 3. Start Terminal and Gemini
        window_id = shell_service.start_terminal_session()
        
        if window_id:
            # 4. Wait 10 seconds for Gemini to connect
            time.sleep(10)
            
            # 5. Send the refined input through to that SPECIFIC window
            shell_service.send_input_to_terminal(refined_input, window_id=window_id)
            exec_output = f"Command sent to Gemini CLI (Window {window_id}): {refined_input}"
        else:
            exec_output = "FAILED to start terminal session"
        
        # 6. Git Management (Sync changes - optional here since Gemini CLI handles its own)
        # git_service.sync_changes(input_text)
        
        # 7. Log the result
        logger.log_verbose(log_id, refined_input, exec_output)
        
        return {
            "success": True, 
            "output": exec_output, 
            "code": refined_input,
            "log_id": log_id
        }
        
    except Exception as e:
        logger.log_error(log_id, str(e))
        return {
            "success": False, 
            "error": str(e), 
            "log_id": log_id
        }
