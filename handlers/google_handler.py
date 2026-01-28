from services import google_service, rag_service
from utils import auth_utils

def handle_google_command(input_text, command="/google"):
    """
    Handles Gmail, Drive, Calendar, and Meet commands using the RAG knowledge base.
    """
    try:
        # Map command to context type
        context_map = {
            "/gmail": "gmail",
            "/drive": "drive",
            "/calendar": "calendar",
            "/meet": "calendar" # Meet is usually in calendar events
        }
        context_type = context_map.get(command)
        
        # Query the RAG knowledge base
        answer = rag_service.query_knowledge_base(input_text, context_type=context_type)
        
        return {"success": True, "output": answer}
        
    except Exception as e:
        return {"success": False, "error": str(e)}