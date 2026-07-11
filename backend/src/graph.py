from typing import TypedDict
from langgraph.graph import StateGraph, END
from agents.generator import generate_documentation, validate_format
from agents.critic import critique_documentation, gate_documentation

MAX_ITERATIONS = 3

# State: shared data between all nodes
class DocumentationState(TypedDict):
    code: str
    function_name: str 
    mode: str
    existing_documentation: str
    deps: list
    documentation: str
    decision: str
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
    
    doc = generate_documentation(
        code=state["code"],
        deps=state.get("deps", []),
        function_name=state["function_name"],
        feedback=state["issues"] or None,
    )
 
    return {
        **state,
        "documentation": doc,
        "iteration": state["iteration"] + 1,
    }

# Node 2b: deterministic format check — no LLM call
def format_check_node(state: DocumentationState) -> DocumentationState:
    issues = validate_format(state["documentation"])
    if issues:
        print(f"[{state['function_name']}] Format check: FAILED — {issues}")
    else:
        print(f"[{state['function_name']}] Format check: OK")
    return {**state, "issues": issues}
 
 
def route_after_format_check(state: DocumentationState) -> str:
    if state["issues"]:
        if state["iteration"] >= MAX_ITERATIONS:
            print(f"[{state['function_name']}] Graph: max iterations reached (format), saving anyway")
            return "end"
        return "generator"
    return "critic"

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
        "score": result.get("score", 0),
    }

# Edge: should we loop back or finish?
def should_continue(state: DocumentationState) -> str:
    if state["approved"]:
        return "end"
    if state["iteration"] >= MAX_ITERATIONS: 
        print(f"[{state['function_name']}] Graph: max iterations reached, saving anyway")
        return "end"
    return "generate"

# Build the graph
def build_graph():
    graph = StateGraph(DocumentationState)
 
    graph.add_node("gate", gate_node)
    graph.add_node("generator", generator_node)
    graph.add_node("format_check", format_check_node)
    graph.add_node("critic", critic_node)
 
    graph.set_conditional_entry_point(route_entry, {"gate": "gate", "generator": "generator"})
    graph.add_conditional_edges("gate", after_gate, {"end": END, "generator": "generator"})
    graph.add_edge("generator", "format_check")
    graph.add_conditional_edges(
        "format_check", route_after_format_check, {"end": END, "generator": "generator", "critic": "critic"}
    )
    graph.add_conditional_edges("critic", should_continue, {"end": END, "generate": "generator"})
    return graph.compile()
