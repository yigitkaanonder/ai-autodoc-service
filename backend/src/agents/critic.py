import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def critique_documentation(code: str, documentation: str) -> dict:
    prompt = f"""You are a strict documentation quality reviewer. You will receive a single function and its documentation. Score the documentation from 0 to 10.

Scoring criteria (2 points each):
1. Purpose: Does it clearly explain what the function does? (2 points)
2. Parameters: Are all parameters listed with types and descriptions? (2 points)
3. Return value: Is the return type and meaning documented? (2 points)
4. Edge cases: Are error conditions or boundary cases mentioned? (2 points)
5. Clarity: Is the writing concise, accurate, and well-structured? (2 points)

Formatting penalties (applied after scoring):
- DEDUCT 2 points if the documentation starts with any phrase addressing the reader such as "Here is", "This is the", "Below is", "I have", "The following", or any text before the ## heading.
- DEDUCT 2 points if the original source code is reproduced inside the documentation.

Respond with ONLY a JSON object, nothing else:
{{"approved": true, "score": 9, "issues": []}}
or
{{"approved": false, "score": 5, "issues": ["issue 1", "issue 2"]}}

Rules:
- approved = true ONLY if final score >= 8
- Be strict but fair — do not penalize section headings like "## Parameters" or "## Edge Cases", those are structural, not introductory.

Function code:
{code}

Documentation to review:
{documentation}"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
    )

    content = response.json()["message"]["content"]
    
    # Extract JSON from response
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # If model added extra text, find the JSON part
        start = content.find("{")
        end = content.rfind("}") + 1
        return json.loads(content[start:end])