from typing import TypedDict
from langgraph.graph import StateGraph, END
from agents.generator import generate_documentation
from agents.critic import critique_documentation

# State: shared data between all nodes
class DocumentationState(TypedDict):
    code: str
    documentation: str
    approved: bool
    issues: list
    iteration: int
    score: int

# Node 1: Generator
def generator_node(state: DocumentationState) -> DocumentationState:
    print(f"\n[Generator] Iteration {state['iteration'] + 1}...")
    
    # If there are issues from critic, add them to the prompt
    extra = ""
    if state["issues"]:
        extra = f"\n\nPrevious documentation had these issues, fix them:\n" + "\n".join(state["issues"])
    
    doc = generate_documentation(state["code"] + extra)
    
    return {
        **state,
        "documentation": doc,
        "iteration": state["iteration"] + 1
    }

# Node 2: Critic
def critic_node(state: DocumentationState) -> DocumentationState:
    print(f"[Critic] Reviewing documentation...")
    
    result = critique_documentation(state["code"], state["documentation"])
    
    print(f"[Critic] Score: {result.get('score', 'N/A')}/10")

    print(f"[Critic] Approved: {result['approved']}")
    if not result["approved"]:
        print(f"[Critic] Issues: {result['issues']}")
    
    return {
        **state,
        "approved": result["approved"],
        "issues": result.get("issues", []),
        "score": result.get("score", 0)
    }

# Edge: should we loop back or finish?
def should_continue(state: DocumentationState) -> str:
    if state["approved"]:
        return "end"
    if state["iteration"] >= 3: #max 3 iterations.
        print("[Graph] Max iterations reached, saving anyway.")
        return "end"
    return "generate"

# Build the graph
def build_graph():
    graph = StateGraph(DocumentationState)
    
    graph.add_node("generator", generator_node)
    graph.add_node("critic", critic_node)
    
    graph.set_entry_point("generator")
    graph.add_edge("generator", "critic")
    graph.add_conditional_edges(
        "critic",
        should_continue,
        {
            "end": END,
            "generate": "generator"
        }
    )
    
    return graph.compile()