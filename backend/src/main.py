import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from agents.generator import generate_documentation

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

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
    from graph import build_graph

    test_code = """
def p(x, y, z=None):
    if z:
        return x * y + z
    return x * y

def f(data):
    result = []
    for i in data:
        if i % 2 == 0:
            result.append(i * 2)
        elif i < 0:
            result.append(abs(i))
    return result

def g(a, b, c, d=0):
    if b == 0:
        raise ValueError("err")
    if c < 0:
        return None
    return (a / b) + c - d
"""
    graph = build_graph()
    
    final_state = graph.invoke({
        "code": test_code,
        "documentation": "",
        "approved": False,
        "issues": [],
        "iteration": 0
    })
    
    print("\nFinal documentation:\n")
    print(final_state["documentation"])
    save_documentation(final_state["documentation"], "test")