import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
 
try:
    from services.call_graph import CallGraph, Condensation, FuncKey
except ImportError:
    from call_graph import CallGraph, Condensation, FuncKey


@dataclass
class FunctionTask:
    source: str
    mode: str = "added"
    existing_documentation: str = ""
 
 
# (func_key, code, context, task)
DocumentFn = Callable[[FuncKey, str, str, FunctionTask], Awaitable[str]]
# already documented
FetchDocFn = Callable[[FuncKey], Optional[str]]
 
 
def _format_context(items) -> str:
    """items: [(kind, FuncKey, text)], kind in {'doc','source'}."""
    if not items:
        return ""
    blocks = []
    for kind, key, text in items:
        label = "documentation" if kind == "doc" else "source"
        blocks.append(f"# {key.name} ({label}):\n{text}")
    return "\n\n".join(blocks)
 
 
def make_worker(
    cond: Condensation,
    call_graph: CallGraph,
    tasks: dict, # FuncKey -> FunctionTask
    document_fn: DocumentFn,
    fetch_existing_doc: FetchDocFn = lambda k: None,
):
    
    generated: dict = {}  # FuncKey -> the generated documentation
 
    async def worker(component_id: int):
        members = cond.components[component_id]
        is_cycle = cond.is_cycle(component_id)
        produced = {}
        for member in members:
            context_items = []
            resolved = []
 
            # dependencies inside change set
            for dep in sorted(call_graph.deps.get(member, ())):
                if cond.node_to_comp.get(dep) == component_id:
                    # same ssc, give code instead of document.
                    dep_task = tasks.get(dep)
                    if dep_task is not None:
                        context_items.append(("source", dep, dep_task.source))
                        resolved.append((dep.name, "CODE (cycle-mate)"))
                    else:
                        resolved.append((dep.name, "NOT FOUND"))
                else:
                    # previusly generated documentation
                    doc = generated.get(dep)
                    if doc is not None:
                        context_items.append(("doc", dep, doc))
                        resolved.append((dep.name, "DOCUMENTATION"))
                    else:
                        resolved.append((dep.name, "NOT FOUND (skipped/failed)"))
 

            for ext in sorted(call_graph.external_deps.get(member, ())):
                doc = fetch_existing_doc(ext)
                if doc:
                    context_items.append(("doc", ext, doc))
                    resolved.append((ext.name, "DOCUMENTATION (existing, from DB)"))
                else:
                    resolved.append((ext.name, "NOT FOUND (no doc in DB)"))
 
            unresolved = sorted(call_graph.unresolved.get(member, ()))
 
            where = f"{member.file_path}{', CYCLE' if is_cycle else ''}"
            deps_str = ", ".join(f"{n} -> {lbl}" for n, lbl in resolved) if resolved else "none"
            header = f"\n[Doc] {member.name}  ({where})\n      deps: {deps_str}"
            if unresolved:
                header += f"\n      unresolved calls (library/builtin, not a dependency): {', '.join(unresolved)}"
            print(header)
 
            task = tasks[member]
            context = _format_context(context_items)
            doc = await document_fn(member, task.source, context, task)
            generated[member] = doc
            produced[member] = doc
        return produced
 
    return worker, generated
 
 
def make_pipeline_document_fn(session_factory, repository_id, commit_sha=None):
    from pipeline import process_function
 
    async def document_fn(func_key: FuncKey, code: str, context: str,
                          task: FunctionTask) -> str:
        def _run():
            db = session_factory()
            try:
                result = process_function(
                    db=db,
                    repository_id=repository_id,
                    file_path=func_key.file_path,
                    function_name=func_key.name,
                    function_source=code,
                    commit_sha=commit_sha,
                    mode=task.mode,
                    existing_documentation=task.existing_documentation,
                    dependency_context=context,
                )

                db.commit()
                return result
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
 
        return await asyncio.to_thread(_run)
 
    return document_fn
