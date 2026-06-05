import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def generate_documentation(code: str) -> str:
    prompt = f"""Analyze the following Python code and write documentation that includes:
- The general purpose of the code
- For each function: what it does, its parameters and return value
- Important edge cases if any

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


def save_documentation(content: str, filename: str = "documentation") -> str:
    os.makedirs("../docs", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"../docs/{filename}_{timestamp}.md"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Documentation\n\n")
        f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(content)

    print(f"Documentation saved: {filepath}")
    return filepath


if __name__ == "__main__":
    test_code = """
def add(a, b):
    return a + b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
"""
    print("Generating documentation...")
    result = generate_documentation(test_code)
    save_documentation(result, "test")
    print("\nPreview:\n")
    print(result)