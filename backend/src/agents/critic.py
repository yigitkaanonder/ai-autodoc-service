import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def critique_documentation(code: str, documentation: str) -> dict:
    prompt = f"""You are a documentation quality reviewer. Review the documentation for the given code.

Score the documentation from 0-10 based on these criteria:
- Are all functions documented? (2 points)
- Are all parameters explained with types? (2 points)
- Are return values specified with types? (2 points)
- Are edge cases mentioned? (2 points)
- Is the explanation clear and understandable? (2 points)

Formatting penalties (deduct points if violated):
- Documentation must start directly with content. Deduct 2 points if it has intro phrases like "Here is the documentation" or "I have updated...".
- Documentation must NOT repeat or rewrite the full source code. Deduct 2 points if the source code is reproduced.


Respond ONLY with a JSON object, no extra text:
{{"approved": true, "score": 9, "issues": []}}
or
{{"approved": false, "score": 5, "issues": ["issue 1", "issue 2"]}}

Rules:
- approved is true ONLY if score is 8 or above
- Be strict, find real issues
- If there is a formatting violation, mention it explicitly in issues

Code:
{code}

Documentation:
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