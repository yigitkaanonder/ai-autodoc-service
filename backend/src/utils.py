import os
from datetime import datetime

def save_documentation(content: str, filename: str = "documentation") -> str:
    docs_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs")
    )
    os.makedirs(docs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(docs_dir, f"{filename}_{timestamp}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Documentation\n\n")
        f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(content)

    print(f"Documentation saved: {filepath}")
    return filepath