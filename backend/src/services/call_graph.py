"""
This module finds the dependencies between functions and creates a graph with their dependencies.

For example, if function A calls function B, then the graph will have an edge B -> A. This means 
that B should be documented before A, and A's documentation generation prompt should include B's
documentation.

Design Choices:
- If the dependent function is not found in the repository, then the function will be considered 
as independent and will be documented without any dependencies. 

- Self-recursion doesn't generate any dependency.
"""

from __future__ import annotations
 
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, NamedTuple, Optional


class FuncKey(NamedTuple):
    file_path: str
    name: str

def _simple_name(name: str) -> str:
    return name.rsplit("::", 1)[-1].rsplit(".", 1)[-1]


@dataclass
class CallGraph:
    """
    Result of analysing one changeset.

    
    nodes: Every function in the change set (the units that will be documented).

    deps: The changeset functions that nodes depend on. These are the scheduling edges, every 
    key in deps[n] must finish before n runs.

    dependents: reverse of deps

    external_deps: node -> repo functions it depends on that are not in the changeset. Their 
    documentations will be retrieved from database.

    unresolved: Functions that did not resolve to any known function.

    broken: changeset functions whose source had a parse error. They still appear as graph nodes 
    so others can depend on them.
    """

    nodes: list[FuncKey]
    deps: dict[FuncKey, set[FuncKey]] = field(default_factory=dict)
    dependents: dict[FuncKey, set[FuncKey]] = field(default_factory=dict)
    external_deps: dict[FuncKey, set[FuncKey]] = field(default_factory=dict)
    unresolved: dict[FuncKey, set[str]] = field(default_factory=dict)
    broken: set[FuncKey] = field(default_factory=set)

    def in_degree(self, node: FuncKey) -> int:
        """Number of changeset dependencies that must complete before `node`."""
        return len(self.deps.get(node, ()))
 
    def roots(self) -> list[FuncKey]:
        """Nodes with no changeset dependencies (ready to start first)."""
        return [n for n in self.nodes if self.in_degree(n) == 0]
    

def _build_name_index(keys: Iterable[FuncKey]) -> dict[str, list[FuncKey]]:
    index: dict[str, list[FuncKey]] = {}
    for key in keys:
        index.setdefault(_simple_name(key.name), []).append(key)
    return index

def _resolve(simple: str, caller_file: str, index: dict[str, list[FuncKey]]) -> Optional[FuncKey]:
    """
    Resolve a simple callee name to a single FuncKey within `index`, or None.
    Prefers a unique same-file match; otherwise a unique repo-wide match;
    anything ambiguous returns None.
    """

    candidates = index.get(simple)
    if not candidates:
        return None
    same_file = [k for k in candidates if k.file_path == caller_file]
    if len(same_file) == 1:
        return same_file[0]
    if len(same_file) > 1:
        return None  # overloads in the same file — can't disambiguate
    if len(candidates) == 1:
        return candidates[0]
    return None  # same name across multiple other files — ambiguous


def build_call_graph(
    changeset_functions: Iterable[dict],
    repo_functions: Optional[Iterable[tuple[str, str]]] = None,
) -> CallGraph:
    """Build the call graph for given change set."""

    funcs = list(changeset_functions)
    nodes = [FuncKey(f["file_path"], f["name"]) for f in funcs]
 
    cs_index = _build_name_index(nodes)
    repo_keys = [FuncKey(fp, nm) for fp, nm in (repo_functions or [])]
    repo_index = _build_name_index(repo_keys) if repo_keys else {}
 
    graph = CallGraph(nodes=nodes)
    for node in nodes:
        graph.deps[node] = set()
        graph.dependents[node] = set()
        graph.external_deps[node] = set()
        graph.unresolved[node] = set()
 
    for func, node in zip(funcs, nodes):
        if func.get("has_error"):
            graph.broken.add(node)
 
        for raw_callee in func.get("callees", []):
            simple = _simple_name(raw_callee)
 
            # function in changeset
            if simple in cs_index:
                target = _resolve(simple, node.file_path, cs_index)
                if target is None:
                    graph.unresolved[node].add(raw_callee)
                elif target != node:               # ignore self-recursion
                    graph.deps[node].add(target)
                continue
 
            # function in repo
            if simple in repo_index:
                target = _resolve(simple, node.file_path, repo_index)
                if target is not None:
                    graph.external_deps[node].add(target)
                else:
                    graph.unresolved[node].add(raw_callee)
                continue
 
            # unknown function
            graph.unresolved[node].add(raw_callee)
 
    # Fill the reverse adjacency list.
    for node in nodes:
        for dep in graph.deps[node]:
            graph.dependents[dep].add(node)
 
    return graph


@dataclass
class Condensation:
    """Acyclic graph of SCC super-nodes over one changeset."""

    components: list[tuple[FuncKey, ...]] # index -> tuple of member FuncKeys (sorted)
    node_to_comp: dict[FuncKey, int] #FuncKey -> component index
    deps: dict[int, set[int]] = field(default_factory=dict) #component -> component indices it depends on (must finish first).
    dependents: dict[int, set[int]] = field(default_factory=dict) #reverse of deps.
 
    def is_cycle(self, comp_id: int) -> bool:
        return len(self.components[comp_id]) > 1
 
    def in_degree(self, comp_id: int) -> int:
        return len(self.deps.get(comp_id, ()))
 
    def roots(self) -> list[int]:
        """Components with no dependencies (ready to process)."""
        return [i for i in range(len(self.components)) if self.in_degree(i) == 0]
 
    def topological_order(self) -> list[int]:
        """Topological sort with Kahn's algorithm. (is deterministic)"""
        indeg = {i: self.in_degree(i) for i in range(len(self.components))}
        ready = deque(sorted(i for i, d in indeg.items() if d == 0))
        order = []
        while ready:
            i = ready.popleft()
            order.append(i)
            for dependent in sorted(self.dependents.get(i, ())):
                indeg[dependent] -= 1
                if indeg[dependent] == 0:
                    ready.append(dependent)
        if len(order) != len(self.components):
            raise ValueError("condensation is not acyclic — SCC bug")
        return order
 
 
def _tarjan_scc(nodes: list[FuncKey],
                adjacency: dict[FuncKey, set[FuncKey]]) -> list[list[FuncKey]]:
    """
    Strongly connected components via Tarjan's algorithm. 
    Deterministic: start nodes in `nodes` order, successors 
    in sorted order, every returned component sorted.
    """
    index_of: dict[FuncKey, int] = {}
    lowlink: dict[FuncKey, int] = {}
    on_stack: set[FuncKey] = set()
    scc_stack: list[FuncKey] = []
    sccs: list[list[FuncKey]] = []
    counter = 0
 
    succ = {n: sorted(adjacency.get(n, ())) for n in nodes}
 
    for start in nodes:
        if start in index_of:
            continue
        work = [(start, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index_of[node] = lowlink[node] = counter
                counter += 1
                scc_stack.append(node)
                on_stack.add(node)
            successors = succ[node]
            if pi < len(successors):
                work[-1] = (node, pi + 1)
                w = successors[pi]
                if w not in index_of:
                    work.append((w, 0))
                elif w in on_stack:
                    lowlink[node] = min(lowlink[node], index_of[w])  # back edge
            else:
                # node fully explored: if it's an SCC root, pop the component.
                if lowlink[node] == index_of[node]:
                    comp = []
                    while True:
                        w = scc_stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == node:
                            break
                    sccs.append(sorted(comp))
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
    return sccs
 
 
def condense(call_graph: CallGraph) -> Condensation:
    """Collapse the call graph's SCCs into an acyclic Condensation."""
    nodes = call_graph.nodes
    sccs = _tarjan_scc(nodes, call_graph.deps)
 
    # Order by each component's earliest member.
    pos = {n: i for i, n in enumerate(nodes)}
    sccs.sort(key=lambda comp: min(pos[n] for n in comp))
 
    components = [tuple(comp) for comp in sccs]
    node_to_comp: dict[FuncKey, int] = {}
    for cid, comp in enumerate(components):
        for n in comp:
            node_to_comp[n] = cid
 
    cond = Condensation(components=components, node_to_comp=node_to_comp)
    for cid in range(len(components)):
        cond.deps[cid] = set()
        cond.dependents[cid] = set()
 
    for n in nodes:
        cu = node_to_comp[n]
        for d in call_graph.deps[n]:
            cv = node_to_comp[d]
            if cu != cv:
                cond.deps[cu].add(cv)
    for cu in range(len(components)):
        for cv in cond.deps[cu]:
            cond.dependents[cv].add(cu)
 
    return cond