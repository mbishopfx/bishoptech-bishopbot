from openai import OpenAI
from config import CONFIG


def _client():
    return OpenAI(api_key=CONFIG["OPENAI_API_KEY"])

def process_message(input_text):
    """
    Uses GPT-4o to refine the user's message or generate code if needed.
    """
    response = _client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Refine the user's request into a clear, concise instruction for a Gemini CLI agent. Output ONLY the refined instruction text, no quotes or additional text."},
            {"role": "user", "content": input_text}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

def generate_response(prompt, system_prompt="You are an expert auditor.", model="gpt-4o"):
    """General OpenAI chat completion."""
    response = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4096
    )
    return response.choices[0].message.content
