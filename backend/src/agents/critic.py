import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def critique_documentation(code: str, documentation: str) -> dict:
    """Critic#2: does the generated doc related with the code?
    Returns {"approved": true|false, "score": 1-10, "issues": [str,]}."""

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
    

def gate_documentation(code: str, existing_documentation: str) -> dict:
    """Critic#1: does the existing doc STILL describe the (now-changed) code?
    Returns {"decision": "keep"|"regenerate", "reason": str}."""

    prompt = f"""You are a documentation drift detector. A function's source code changed (variable renames, comments, refactors, or real behavior changes). Decide whether its EXISTING documentation is STILL accurate for the function as written below.

Method:
1. Read the NEW code and note its ACTUAL behavior: purpose, parameters, return value, error/edge-case handling.
2. Read the existing documentation's claims.
3. Compare. Judge ONLY from the code shown — do NOT assume the function changed in any particular way unless the NEW code clearly shows it.

Decision:
- "keep": every claim in the existing documentation is still true for the NEW code. Cosmetic changes (renamed locals, comments, formatting, internal refactors with identical behavior) → keep.
- "regenerate": you can point to a SPECIFIC claim in the documentation that the NEW code contradicts or that is now missing (changed purpose, parameters, return value, or edge cases).

Do NOT regenerate just because wording could be improved. Only regenerate on a real factual mismatch. If every claim still holds, return keep.

Examples:
- Doc says "raises ZeroDivisionError on empty list" and the NEW code starts with `if not numbers: return 0.0` -> regenerate (edge case changed).
- Doc says "raises ZeroDivisionError on empty list" and the NEW code still ends with `total / len(numbers)` with no empty-list guard, only locals were renamed -> keep (behavior identical).
- Doc lists parameters (a, b) and the NEW code is `def f(a, b, c)` -> regenerate (new parameter).
- Only a comment was added inside the body, logic unchanged -> keep.

Respond with ONLY a JSON object, nothing else:
{{"decision": "keep", "reason": "..."}}
or
{{"decision": "regenerate", "reason": "<the specific contradicting claim>"}}

New function code:
{code}

Existing documentation:
{existing_documentation}"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": OLLAMA_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "stream": False},
    )
    content = response.json()["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}") + 1
        return json.loads(content[start:end])
    