from typing import TypedDict
from langgraph.graph import StateGraph, END
from agents.generator import generate_documentation
from agents.critic import critique_documentation, gate_documentation

# State: shared data between all nodes
class DocumentationState(TypedDict):
    code: str
    function_name: str 
    mode: str
    existing_documentation: str
    context: str
    documentation: str
    decision: str #kept decision as string to add patch as a future feature (only update the changed part)
                  #now we only have skip and redo.
    approved: bool
    issues: list
    iteration: int
    score: int

# Node 1: Critic #1
def gate_node(state: DocumentationState) -> DocumentationState:
    print(f"\n[{state['function_name']}] Gate: checking if existing doc still valid...")
    result = gate_documentation(state["code"], state["existing_documentation"])
    decision = result.get("decision", "regenerate")
    print(f"[{state['function_name']}] Gate decision: {decision} — {result.get('reason', '')}")
    out = {**state, "decision": decision}
    if decision == "keep":
        out["documentation"] = state["existing_documentation"]
    return out

def route_entry(state: DocumentationState) -> str:
    if state["mode"] == "modified" and state["existing_documentation"]:
        return "gate"
    return "generator"

def after_gate(state: DocumentationState) -> str:
    return "end" if state["decision"] == "keep" else "generator"

# Node 2: Generator
def generator_node(state: DocumentationState) -> DocumentationState:
    print(f"\n[{state['function_name']}] Generator: iteration {state['iteration'] + 1}")
    
    # If there are issues from critic, add them to the prompt
    extra = ""
    if state["issues"]:
        extra = f"\n\nPrevious documentation had these issues, fix them:\n" + "\n".join(state["issues"])
    
    doc = generate_documentation(state["code"] + extra, context=state.get("context", ""))
    
    return {
        **state,
        "documentation": doc,
        "iteration": state["iteration"] + 1
    }

# Node 3: Critic #2
def critic_node(state: DocumentationState) -> DocumentationState:
    print(f"[{state['function_name']}] Critic: reviewing...")
    
    result = critique_documentation(state["code"], state["documentation"])
    
    print(f"[{state['function_name']}] Critic: score {result.get('score', 'N/A')}/10")

    print(f"[{state['function_name']}] Critic: approved={result['approved']}")
    if not result["approved"]:
        print(f"[{state['function_name']}] Critic issues: {result['issues']}")
    
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
        print(f"[{state['function_name']}] Graph: max iterations reached, saving anyway")
        return "end"
    return "generate"

# Build the graph
def build_graph():
    graph = StateGraph(DocumentationState)
    
    graph.add_node("gate", gate_node)
    graph.add_node("generator", generator_node)
    graph.add_node("critic", critic_node)
    
    graph.set_conditional_entry_point(route_entry, {"gate": "gate", "generator": "generator"})
    graph.add_conditional_edges("gate", after_gate, {"end": END, "generator": "generator"})
    graph.add_edge("generator", "critic")
    graph.add_conditional_edges("critic", should_continue, {"end": END, "generate": "generator"})
    return graph.compile()
