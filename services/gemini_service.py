from openai import OpenAI
from config import CONFIG
import re

client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])

def generate_code(prompt):
    """
    GPT-4o replacement for the previous Gemini-based code generation.
    """
    system_instruction = f"""
You are an expert software engineer. 
Translate the natural language request into executable code (Bash or Python).
Context: The project is located at {CONFIG['PROJECT_ROOT_DIR']}.

Guidelines:
1. Only return the code block.
2. Ensure code is safe.
3. Use Bash for shell tasks, Python for logic/file manipulation.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    code = response.choices[0].message.content
    
    # Parse code out of markdown blocks if present
    code_blocks = re.findall(r'```(?:python|bash|sh|)?\n(.*?)\n```', code, re.DOTALL)
    if code_blocks:
        return code_blocks[0]
    
    return code.strip()