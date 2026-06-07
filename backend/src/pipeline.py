from graph import build_graph
from utils import save_documentation

_graph = build_graph()


def process_file(file_path: str, code: str) -> str:
    print(f"\n[Pipeline] Processing {file_path}...")

    final_state = _graph.invoke({
        "code": code,
        "documentation": "",
        "approved": False,
        "issues": [],
        "iteration": 0,
        "score": 0
    })

    # Use file path as part of filename (replace / with _)
    safe_name = file_path.replace("/", "_").replace(".", "_")
    filepath = save_documentation(final_state["documentation"], safe_name)

    print(f"[Pipeline] Done. Score: {final_state.get('score', 'N/A')}/10")
    return filepath