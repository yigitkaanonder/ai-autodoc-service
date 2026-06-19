from graph import build_graph
from services.doc_service import save_documentation_to_db

_graph = build_graph()


def process_function(db, repository_id, file_path, function_name, function_source, commit_sha=None, mode="added", existing_documentation=""):

    print(f"\n[Pipeline] Processing {file_path}::{function_name} (mode={mode})...")

    final_state = _graph.invoke({
        "code": function_source,
        "function_name": function_name,
        "mode": mode,
        "existing_documentation": existing_documentation or "",
        "documentation": "",
        "decision": "",
        "approved": False,
        "issues": [],
        "iteration": 0,
        "score": 0,
    })

    # kept old documentaiton
    if final_state.get("decision") == "keep":
        print(f"[Pipeline] {function_name}: doc still valid, kept. No new row.")
        return final_state["documentation"]

    documentation = final_state["documentation"]
    score = final_state.get("score", 0)

    save_documentation_to_db(
        db=db, 
        repository_id=repository_id, 
        file_path=file_path,
        content=documentation, 
        function_name=function_name,
        score=score, 
        commit_sha=commit_sha,
    )

    print(f"[Pipeline] Done {function_name}. Score: {score}/10. Saved.")
    return documentation