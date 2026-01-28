from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from config import CONFIG

def create_research_crew(query):
    # Setup LLM with GPT-4o
    llm = ChatOpenAI(
        model="gpt-4o",
        openai_api_key=CONFIG["OPENAI_API_KEY"]
    )
    
    # Define Agents
    researcher = Agent(
        role='Senior Research Analyst',
        goal=f'Uncover cutting-edge developments in {query}',
        backstory="""You are an expert at identifying emerging trends and 
        gathering deep technical insights from various sources.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    writer = Agent(
        role='Technical Content Strategist',
        goal=f'Summarize research findings on {query} into a concise Slack report',
        backstory="""You excel at taking complex technical data and 
        making it digestible for developers and stakeholders.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Define Tasks
    task1 = Task(description=f'Deep dive research into {query}', agent=researcher, expected_output="A detailed report on the topic.")
    task2 = Task(description=f'Summarize the findings for a Slack message', agent=writer, expected_output="A 3-paragraph summary suitable for Slack.")
    
    # Instantiate Crew
    crew = Crew(
        agents=[researcher, writer],
        tasks=[task1, task2],
        process=Process.sequential
    )
    
    return crew