import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# ---------------------------------------------------
# Length Budget:
# - Focal code length: 8000 characters
# - Dependency context length: 6000 characters 
# - Each documentation length: 1500 characters
# 
# Dependent function's codes are added if the context 
# length remains under the budget.
# ---------------------------------------------------

MAX_FOCAL_CODE_CHARS = 8000
MAX_CONTEXT_CHARS = 6000
MAX_CODE_DEP_CHARS = 1500

REQUIRED_SECTIONS = ["**Parameters:**", "**Returns:**", "**Edge Cases:**"]


def _truncate_code(code: str, limit: int) -> str:
    """Cuts the code to the limit, and tells to ai model."""
    if len(code) <= limit:
        return code
    cut = code[:limit]
    last_nl = cut.rfind("\n")
    if last_nl > 0:
        cut = cut[:last_nl]
    return cut + "\n# ... (truncated: function body continues beyond this point)"


def build_context_block(deps: list) -> str:
    """deps: [{"name": str, "kind": "doc" | "code", "text": str}, ...]
 
    Rules:
    - Adds the full "doc" of dependencies first, then "code".
    - If the total length doesn't exceed MAX_CONTEXT_CHARS, start adding "code".
    """

    if not deps:
        return ""
 
    ordered = sorted(deps, key=lambda d: 0 if d["kind"] == "doc" else 1)
 
    parts = []
    remaining = MAX_CONTEXT_CHARS
    skipped = []
 
    for dep in ordered:
        name, kind, text = dep["name"], dep["kind"], dep["text"]
 
        if kind == "code":
            text = _truncate_code(text, MAX_CODE_DEP_CHARS)
 
        block = (
            f"----- dependency: {name} ({'documentation' if kind == 'doc' else 'source code'}) "
            f"— you are NOT documenting this -----\n"
            f"{text}\n"
            f"----- end dependency: {name} -----\n"
        )
 
        if len(block) <= remaining:
            parts.append(block)
            remaining -= len(block)
        else:
            skipped.append(name)
 
    if skipped:
        parts.append(
            "NOTE: The following dependencies were omitted for length; assume they "
            "behave as their names suggest: " + ", ".join(skipped) + "\n"
        )
 
    return (
        "\nContext — the focal function calls the functions below. Use their "
        "documentation/source only to understand what those calls do. Do NOT "
        "document them and do NOT copy their text; document only the focal "
        "function.\n" + "".join(parts)
    )


def validate_format(doc: str) -> list:
    """Deterministic format checker. Reduces ai calls."""

    issues = []
    stripped = doc.lstrip()
 
    if not stripped.startswith("## "):
        issues.append(
            "Documentation must begin directly with the '## <function_name>' "
            "heading. Remove ALL text before it (no 'Here is', no preamble)."
        )
 
    if "```" in doc or "\ndef " in doc or doc.startswith("def "):
        issues.append(
            "Do not reproduce the source code inside the documentation. "
            "Remove all code blocks."
        )
 
    for section in REQUIRED_SECTIONS:
        if section not in doc:
            issues.append(f"Missing required section: {section}")
 
    return issues


def clean_output(doc: str) -> str:
    """If there is text behind "## ", then remove it. Don't iterate again."""
    idx = doc.find("## ")
    if idx > 0:
        return doc[idx:]
    return doc


def generate_documentation(code: str, deps: list = None,
                           function_name: str = "", feedback: list = None) -> str:

    code = _truncate_code(code, MAX_FOCAL_CODE_CHARS)
    context_block = build_context_block(deps or [])
 
    feedback_block = ""
    if feedback:
        feedback_block = (
            "\nYour previous attempt was rejected for these reasons. "
            "Fix ALL of them:\n"
            + "\n".join(f"- {issue}" for issue in feedback) + "\n"
        )
 
    focal_line = (
        f"The focal function you must document is named `{function_name}`. "
        "Everything inside the dependency blocks is a DIFFERENT function — "
        "never describe the focal function as a wrapper around itself.\n"
        if function_name else ""
    )
 
    prompt = f"""You are an expert technical documentation writer. Your task is to write clear, structured documentation for a single function extracted from a codebase.
 
{focal_line}Analyze the function below and produce documentation in this exact format:
 
## <function_name>
A clear 1-2 sentence description of what this function does and why it exists.
 
**Parameters:**
- `param_name` (type): What this parameter represents and any constraints.
 
**Returns:**
- (type): What the function returns and under what conditions.
 
**Edge Cases:**
- List any notable edge cases, error handling, or boundary conditions.
 
{context_block}
Function:
{code}
{feedback_block}
Rules (follow these EXACTLY):
- Begin directly with the ## heading. No preamble, no "Here is the documentation", no greeting.
- Do not reproduce the source code.
- If the function has no parameters, write "None" under Parameters.
- If the function has no return value, write "None (void/side-effect only)" under Returns.
- If there are no notable edge cases IN THE CODE ITSELF, write "None identified" under Edge Cases. Do not invent hypothetical edge cases the code does not handle."""
 
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "user", "content": prompt},
                # Prefill "## "
                {"role": "assistant", "content": "## "},
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }
    )
 
    doc = "## " + response.json()["message"]["content"]
    return clean_output(doc)