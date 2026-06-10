import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def generate_documentation(code: str) -> str:
    prompt = f"""You are an expert technical documentation writer. Your task is to write clear, structured documentation for a single function extracted from a codebase.

Analyze the function below and produce documentation in this exact format:

## <function_name>
A clear 1-2 sentence description of what this function does and why it exists.

**Parameters:**
- `param_name` (type): What this parameter represents and any constraints.

**Returns:**
- (type): What the function returns and under what conditions.

**Edge Cases:**
- List any notable edge cases, error handling, or boundary conditions.

Rules:
- Begin directly with the ## heading. No preamble, no "Here is the documentation", no greeting.
- Do not reproduce the source code.
- If the function has no parameters, write "None" under Parameters.
- If the function has no return value, write "None (void/side-effect only)" under Returns.
- If there are no notable edge cases, write "None identified" under Edge Cases.

Function:
{code}"""