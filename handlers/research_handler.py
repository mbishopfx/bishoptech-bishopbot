from agents.research_agents import create_research_crew

def handle_research_command(input_text):
    try:
        crew = create_research_crew(input_text)
        result = crew.kickoff()
        return {"success": True, "output": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}
