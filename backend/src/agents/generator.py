import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def generate_documentation(code: str) -> str:
    prompt = f"""Analyze the following code and write documentation that includes:
- The general purpose of the code
- For each function: what it does, its parameters and return value
- Important edge cases if any

IMPORTANT RULES:
- Output ONLY the documentation itself
- Do NOT include any introductory phrases like "Here is the documentation" or "I have updated..."
- Do NOT repeat or rewrite the source code
- Start directly with the documentation content

Code:
{code}"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
    )

    return response.json()["message"]["content"]