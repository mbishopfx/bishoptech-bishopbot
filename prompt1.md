## Updated Project Overview: Slack-Integrated CLI Shell with AI Enhancements

This updated project builds on the original Slack bot, adding AI-driven research teams using CrewAI (with configurable LLMs: OpenAI's GPT-4o or Google's Gemini Flash Preview, including fallback logic) and website auditing/real-time data fetching via Firecrawl integrated with OpenAI for parsing. These features are triggered via new slash commands (e.g., `/research`, `/audit`), maintaining local execution and scalability. The system now supports agentic workflows where AI agents can collaborate on tasks like research or data analysis.

## Key Additions
- **CrewAI Research Teams**: Modular AI agent crews for research tasks. Configurable with GPT-4o or Gemini Flash (fallback: try primary, switch on failure). Agents can handle "agentic needs" like multi-step reasoning, tool usage, or team collaboration.
- **Firecrawl + OpenAI Integration**: For website audits (e.g., SEO, content analysis) and real-time data fetching. Firecrawl crawls sites to markdown/structured data; OpenAI parses/analyzes it. Outputs fed back to Slack or used in CLI ops.
- **Model Fallback**: In config, set primary/secondary LLM; services handle switching on errors (e.g., API rate limits).
- **New Slash Commands**: `/research <topic>` for agentic research; `/audit <url>` for site audits.
- **Scalability Enhancements**: Added `agents/` for CrewAI definitions; expanded `services/` for new integrations. Easy to add more agents or tools.
- **Security/Local Notes**: All crawls/parsing run locally; Firecrawl uses local or API mode (assume API for simplicity). Limit scopes to prevent over-crawling.

## Updated Prerequisites
- Add API Keys: OpenAI, Firecrawl (if API), Gemini (already there).
- Update `.env`:
  ```
  OPENAI_API_KEY=sk-...
  FIRECRAWL_API_KEY=...  # If using Firecrawl API
  PRIMARY_LLM=openai  # or 'gemini'
  SECONDARY_LLM=gemini  # Fallback
  ```
- New Dependencies: See updated `requirements.txt`.

## Updated Setup Instructions
1. Pull updates or add new files as below.
2. Install new deps: `pip install -r requirements.txt`.
3. Run as before: `python app.py`.
4. Test: `/research Analyze quantum computing trends` → Agents research, reply with findings.
5. `/audit https://example.com` → Crawl, parse with OpenAI, reply with audit report.

## Updated Workflow for New Features
- **Research**: Slack `/research <query>` → Handler sets up CrewAI agents (e.g., researcher, analyzer) with chosen LLM → Execute task → Git if project-related → Slack reply.
- **Audit**: Slack `/audit <url> [instructions]` → Firecrawl fetches data → OpenAI parses/audits → Reply with verbose output/logs.
- **Fallback**: If primary LLM fails (e.g., exception), switch to secondary and retry.
- **Integration with Existing**: CLI commands can invoke these (e.g., `/cli research and edit file based on findings` → Parse via Gemini, call research handler).

# Updated Project Structure Template

Expanded for new features: Added `agents/` for CrewAI configs; new services/handlers. Structure remains modular.

```
slack-cli-gemini/
├── app.py                  # Main: Now registers new commands (/research, /audit)
├── config.py               # Updated: LLM configs, OpenAI/Firecrawl keys
├── requirements.txt        # Updated with new deps
├── .env.example
├── README.md               # Updated docs
├── logs/
├── agents/                 # CrewAI agent/crew definitions (scalable: add files for new teams)
│   ├── research_agents.py  # Defines agents/tasks for research crews
│   └── audit_agents.py     # Optional: If audits need agentic flow
├── handlers/               # Added new handlers
│   ├── cli_handler.py
│   ├── google_handler.py
│   ├── research_handler.py # Handles /research: Sets up/runs CrewAI
│   ├── audit_handler.py    # Handles /audit: Firecrawl + OpenAI
│   └── base_handler.py
├── services/               # Added new services
│   ├── gemini_service.py
│   ├── git_service.py
│   ├── google_service.py
│   ├── shell_service.py
│   ├── openai_service.py   # OpenAI client with fallback to Gemini
│   ├── crewai_service.py   # CrewAI wrapper: Configures LLMs, runs crews
│   └── firecrawl_service.py# Firecrawl client: Crawl/parse sites
├── utils/                  # Added fallback utils
│   ├── logger.py
│   ├── auth_utils.py
│   ├── command_parser.py
│   └── llm_fallback.py     # Helper for LLM switching
└── tests/                  # Added tests for new features
    ├── test_cli_handler.py
    ├── test_git_service.py
    ├── test_research_handler.py
    └── test_audit_handler.py
```

## Scalability Rationale Updates
- **Agents**: Separate dir for easy addition of new agent crews (e.g., `sales_agents.py`).
- **Handlers/Services**: One per feature; decouples for independent scaling.
- **Fallback**: Centralized in `utils/llm_fallback.py` for reuse across services.
- **Growth**: For more integrations (e.g., another crawler), add to `services/`.

## Updated requirements.txt
```
slack-bolt==1.18.0
google-generativeai==0.3.0  # Gemini
google-auth==2.23.0
google-auth-oauthlib==1.0.0
google-api-python-client==2.100.0
gitpython==3.1.40
python-dotenv==1.0.0
requests==2.31.0
pytest==7.4.0
openai==1.0.0  # New: OpenAI API
crewai==0.1.0  # New: CrewAI (check latest version)
firecrawl-py==0.0.1  # New: Firecrawl Python SDK (assuming; check PyPI)
langchain==0.0.300  # Optional: If CrewAI needs it for tools
```

## Updated Code Skeletons

### app.py (Updates)
```python
# ... existing imports ...

from handlers.research_handler import handle_research_command
from handlers.audit_handler import handle_audit_command

# Existing /cli ...

@app.command("/research")
def research_listener(ack, body, say):
    ack()
    say("Research command received, processing...")
    response = handle_research_command(body["text"])
    say(response["output"] if response["success"] else f"Failure: {response['error']}. See log.")

@app.command("/audit")
def audit_listener(ack, body, say):
    ack()
    say("Audit command received, processing...")
    response = handle_audit_command(body["text"])
    say(response["output"] if response["success"] else f"Failure: {response['error']}. See log.")

# ... existing main ...
```

### config.py (Updates)
```python
# ... existing ...

CONFIG.update({
    "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
    "FIRECRAWL_API_KEY": os.environ.get("FIRECRAWL_API_KEY"),
    "PRIMARY_LLM": os.environ.get("PRIMARY_LLM", "openai"),
    "SECONDARY_LLM": os.environ.get("SECONDARY_LLM", "gemini"),
})
```

### agents/research_agents.py
```python
from crewai import Agent, Task, Crew
from utils.llm_fallback import get_llm

def create_research_crew(query):
    llm = get_llm()  # With fallback
    
    researcher = Agent(
        role='Researcher',
        goal='Gather information on {query}',
        backstory='Expert in web research',
        llm=llm,
        tools=[]  # Add tools like web search if needed
    )
    
    analyzer = Agent(
        role='Analyzer',
        goal='Analyze and summarize findings',
        backstory='Data analysis specialist',
        llm=llm
    )
    
    task1 = Task(description=f'Research {query}', agent=researcher)
    task2 = Task(description='Summarize research', agent=analyzer)
    
    crew = Crew(agents=[researcher, analyzer], tasks=[task1, task2])
    return crew
```

### handlers/research_handler.py
```python
import services.crewai_service as crewai
import services.git_service as git
import utils.logger as logger
from agents.research_agents import create_research_crew

def handle_research_command(input_text):
    try:
        crew = create_research_crew(input_text)
        result = crewai.run_crew(crew)
        
        # Optional: Git if research outputs files
        # git.commit_and_push(some_dir, f"Research on {input_text}")
        
        logger.log_success(result)
        return {"success": True, "output": result}
    except Exception as e:
        log_path = logger.log_error(str(e))
        return {"success": False, "error": str(e), "log": log_path}
```

### handlers/audit_handler.py
```python
import services.firecrawl_service as firecrawl
import services.openai_service as openai
import utils.logger as logger

def handle_audit_command(input_text):
    try:
        # Assume input_text = "url [instructions]"
        url, instructions = input_text.split(maxsplit=1) if ' ' in input_text else (input_text, "Perform SEO audit")
        
        crawled_data = firecrawl.crawl_url(url)
        parsed_output = openai.parse_data(crawled_data, instructions)
        
        logger.log_success(parsed_output)
        return {"success": True, "output": parsed_output}
    except Exception as e:
        log_path = logger.log_error(str(e))
        return {"success": False, "error": str(e), "log": log_path}
```

### services/openai_service.py
```python
from openai import OpenAI
from config import CONFIG
from utils.llm_fallback import fallback_to_gemini

client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])

def parse_data(data, instructions):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": f"Parse and {instructions}: {data}"}]
        )
        return response.choices[0].message.content
    except Exception:
        # Fallback
        return fallback_to_gemini(data, instructions, model="gpt-4o")  # Adapt prompt

# Additional methods as needed
```

### services/crewai_service.py
```python
def run_crew(crew):
    return crew.kickoff()  # CrewAI execution
```

### services/firecrawl_service.py
```python
from firecrawl import FirecrawlApp
from config import CONFIG

app = FirecrawlApp(api_key=CONFIG["FIRECRAWL_API_KEY"])

def crawl_url(url):
    return app.crawl_url(url, params={'extractorOptions': {'mode': 'markdown'}})  # Or 'llm-extraction' for structured
```

### utils/llm_fallback.py
```python
import services.gemini_service as gemini
import services.openai_service as openai  # Circular? Use direct imports if needed
from config import CONFIG

def get_llm():
    if CONFIG["PRIMARY_LLM"] == "openai":
        return "gpt-4o"  # Return model string or client
    else:
        return "gemini-1.5-flash-preview"  # Adjust to actual

def fallback_to_gemini(data, instructions, original_model):
    # Switch to Gemini
    prompt = f"Using {original_model} style, parse and {instructions}: {data}"
    return gemini.generate_command(prompt)  # Reuse or adapt
```

This updated template integrates the new features seamlessly. Implement the skeletons, handle any specifics (e.g., exact Firecrawl params), and test incrementally. For more details on agents or configs, let me know!