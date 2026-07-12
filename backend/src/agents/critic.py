import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# (connect, read) timeout for Ollama calls. Read timeout is generous because a
# local LLM (stream=False) only responds after the full answer is generated.
OLLAMA_TIMEOUT = (5, 300)

APPROVAL_THRESHOLD = 8


CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "purpose":    {"type": "integer", "minimum": 0, "maximum": 2},
        "parameters": {"type": "integer", "minimum": 0, "maximum": 2},
        "returns":    {"type": "integer", "minimum": 0, "maximum": 2},
        "edge_cases": {"type": "integer", "minimum": 0, "maximum": 2},
        "clarity":    {"type": "integer", "minimum": 0, "maximum": 2},
        "issues":     {"type": "array", "items": {"type": "string"}},
    },
    "required": ["purpose", "parameters", "returns", "edge_cases",
                 "clarity", "issues"],
}

GATE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["keep", "regenerate"]},
        "reason":   {"type": "string"},
    },
    "required": ["decision", "reason"],
}


def critique_documentation(code: str, documentation: str) -> dict:
    """Critic#2: does the generated doc related with the code?
    Returns {"approved": true|false, "score": 0-10, "issues": [str,]}."""

    prompt = f"""You are a strict documentation quality reviewer. You will receive a single function and its documentation. Score EACH criterion from 0 to 2:
 
1. purpose: Does it clearly explain what the function does? Verify the description matches the ACTUAL code behavior (e.g. which function it really calls).
2. parameters: Are all parameters listed with correct types and descriptions matching the signature?
3. returns: Is the return type and meaning documented correctly?
4. edge_cases: Are error conditions or boundary cases IN THE CODE mentioned? "None identified" is an ACCEPTABLE answer worth full points if the code genuinely has no error handling or boundary conditions. Do NOT invent hypothetical edge cases the code does not handle, and do NOT penalize for omitting them.
5. clarity: Is the writing concise, accurate, and well-structured?
 
Do NOT judge formatting (headings, preamble, code reproduction) — that is checked elsewhere. A description sentence like "This function ..." inside the body is normal prose, not a violation.
 
For every criterion scored below 2, add one SPECIFIC issue string explaining exactly what is wrong and what the correct fact is, so the writer can fix it.
 
Function code:
{code}
 
Documentation to review:
{documentation}"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": CRITIQUE_SCHEMA,
            "options": {"temperature": 0},
        },
        timeout=OLLAMA_TIMEOUT,
    )

    result = json.loads(response.json()["message"]["content"])
 
    # Do aritmetic to get a 0-10 score from criterion.
    score = sum(result[k] for k in
                ["purpose", "parameters", "returns", "edge_cases", "clarity"])
    score = max(0, min(10, score))
 
    return {
        "approved": score >= APPROVAL_THRESHOLD,
        "score": score,
        "issues": result["issues"],
        "breakdown": {k: result[k] for k in
                      ["purpose", "parameters", "returns",
                       "edge_cases", "clarity"]},
    }
    

def gate_documentation(code: str, existing_documentation: str) -> dict:
    """Critic#1: does the existing doc STILL describe the (now-changed) code?
    Returns {"decision": "keep"|"regenerate", "reason": str}."""
 
    prompt = f"""You are a documentation drift detector. A function's source code changed (variable renames, comments, refactors, or real behavior changes). Decide whether its EXISTING documentation is STILL accurate for the function as written below.
 
Method:
1. Read the NEW code and note its ACTUAL behavior: purpose, parameters, return value, error/edge-case handling.
2. Read the existing documentation's claims.
3. Compare. Judge ONLY from the code shown — do NOT assume the function changed in any particular way unless the NEW code clearly shows it.
 
Decision:
- "keep": every claim in the existing documentation is still true for the NEW code. Cosmetic changes (renamed locals, comments, formatting, internal refactors with identical behavior) -> keep.
- "regenerate": you can point to a SPECIFIC claim in the documentation that the NEW code contradicts or that is now missing (changed purpose, parameters, return value, or edge cases).
 
Do NOT regenerate just because wording could be improved. Only regenerate on a real factual mismatch. If every claim still holds, return keep.
 
Examples:
- Doc says "raises ZeroDivisionError on empty list" and the NEW code starts with `if not numbers: return 0.0` -> regenerate (edge case changed).
- Doc says "raises ZeroDivisionError on empty list" and the NEW code still ends with `total / len(numbers)` with no empty-list guard, only locals were renamed -> keep (behavior identical).
- Doc lists parameters (a, b) and the NEW code is `def f(a, b, c)` -> regenerate (new parameter).
- Only a comment was added inside the body, logic unchanged -> keep.
 
New function code:
{code}
 
Existing documentation:
{existing_documentation}"""
 
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": GATE_SCHEMA,
            "options": {"temperature": 0},
        },
        timeout=OLLAMA_TIMEOUT,
    )
 
    return json.loads(response.json()["message"]["content"])
 