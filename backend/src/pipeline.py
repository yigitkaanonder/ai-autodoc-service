from graph import build_graph
from services.doc_service import save_documentation_to_db

_graph = build_graph()


def process_function(db, repository_id, file_path, function_name, function_source, commit_sha=None):
    """Process a single function through the Generator-Critic pipeline."""
    print(f"\n[Pipeline] Processing {file_path}::{function_name}...")

    final_state = _graph.invoke({
        "code": function_source,
        "documentation": "",
        "approved": False,
        "issues": [],
        "iteration": 0,
        "score": 0
    })

    documentation = final_state["documentation"]
    score = final_state.get("score", 0)

    save_documentation_to_db(
        db=db,
        repository_id=repository_id,
        file_path=file_path,
        content=documentation,
        function_name=function_name,
        score=score,
        commit_sha=commit_sha
    )

    print(f"[Pipeline] Done {function_name}. Score: {score}/10. Saved to DB.")
    return documentation