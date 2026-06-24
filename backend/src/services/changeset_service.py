import asyncio
from dataclasses import dataclass
from typing import Iterable, Optional
 
try:
    from services.call_graph import build_call_graph, condense, FuncKey
    from services.scheduler import run_scheduler, SchedulerResult
    from services.executor import (
        make_worker, make_pipeline_document_fn, FunctionTask, DocumentFn, FetchDocFn,
    )
except ImportError:
    from call_graph import build_call_graph, condense, FuncKey
    from scheduler import run_scheduler, SchedulerResult
    from executor import (
        make_worker, make_pipeline_document_fn, FunctionTask, DocumentFn, FetchDocFn,
    )
 
 
@dataclass
class ChangedFunction:
    func: dict
    mode: str = "added"                 # "added" | "modified"
    existing_documentation: str = ""
 
 
async def process_changeset(
    changeset: Iterable[ChangedFunction],
    *,
    document_fn: DocumentFn,
    repo_functions: Optional[Iterable[tuple]] = None,
    fetch_existing_doc: FetchDocFn = lambda k: None,
    concurrency: int = 4,
    max_retries: int = 2,
    base_backoff: float = 0.5,
) -> SchedulerResult:
    """
    Processes changed functions by building a call graph, resolving 
    dependencies, and scheduling asynchronous documentation generation.

    Args:
        changeset: Added or modified functions to document.
        document_fn: Async worker function to generate/save documentation.
        repo_functions: Unchanged repository functions used for context resolution.
        fetch_existing_doc: Function to retrieve existing docs from DB for context.
        concurrency/max_retries/base_backoff: Execution scheduler configurations.

    Returns:
        SchedulerResult containing execution states, orders, and results.
    """
    changeset = list(changeset)

    skipped_broken = [cf for cf in changeset if cf.func.get("has_error")]
    changeset = [cf for cf in changeset if not cf.func.get("has_error")]
    for cf in skipped_broken:
        print(f"[Changeset] SKIP {cf.func['file_path']}::{cf.func['name']} — syntax error, not documenting")

    functions = [cf.func for cf in changeset]

    if not functions:
        print("[Changeset] nothing to document (empty or all skipped)")
        return SchedulerResult()
 
    call_graph = build_call_graph(functions, repo_functions=repo_functions)
    cond = condense(call_graph)
 
    tasks = {
        FuncKey(cf.func["file_path"], cf.func["name"]): FunctionTask(
            source=cf.func["source"],
            mode=cf.mode,
            existing_documentation=cf.existing_documentation,
        )
        for cf in changeset
    }
 
    worker, _generated = make_worker(
        cond, call_graph, tasks, document_fn, fetch_existing_doc=fetch_existing_doc
    )
    
    print(f"[Changeset] {len(functions)} function(s) in {len(cond.components)} component(s); documenting...")
    result = await run_scheduler(
        cond, worker,
        concurrency=concurrency, max_retries=max_retries, base_backoff=base_backoff,
    )


    n_ok, n_fail = len(result.results), len(result.failures)
    print(f"[Changeset] done: {n_ok} documented, {n_fail} failed")
    for comp_id, exc in result.failures.items():
        members = ", ".join(n.name for n in cond.components[comp_id])
        print(f"[Changeset]   FAILED {{{members}}}: {type(exc).__name__}: {exc}")
 
    return result
 
 
def _repo_functions_excluding(db, repository_id, changeset_keys):
    """(file_path, name) of repo functions in the registry, minus the changeset."""
    from models import FunctionRegistry
    rows = (
        db.query(FunctionRegistry.file_path, FunctionRegistry.function_name)
        .filter(
            FunctionRegistry.repository_id == repository_id,
            FunctionRegistry.is_deleted == False,
        )
        .all()
    )
    return [(fp, nm) for (fp, nm) in rows if (fp, nm) not in changeset_keys]
 
 
def _make_fetch_existing_doc(db, repository_id):
    """FuncKey -> latest non-deleted Documentation.content for that function, or None."""
    from models import Documentation
 
    def fetch(key: FuncKey):
        row = (
            db.query(Documentation)
            .filter(
                Documentation.repository_id == repository_id,
                Documentation.file_path == key.file_path,
                Documentation.function_name == key.name,
                Documentation.is_deleted == False,
            )
            .order_by(Documentation.id.desc())
            .first()
        )
        return row.content if row else None
 
    return fetch
 
 
async def run_repo_changeset_async(
    db, session_factory, repository_id, commit_sha, changeset,
    concurrency=4, document_fn=None,
):
    """
    Asynchronous entry point for webhooks or background tasks. 
    Constructs DB-backed injectables and executes the changeset pipeline.

    Args:
        db: Request-scoped Session used ONLY for thread-safe reads on the main loop.
        session_factory: Session factory (SessionLocal) used by the worker threads 
                         to open/close short-lived sessions for parallel writes.
        document_fn: Optional override callable (primarily used to inject fakes in tests).
        
    Returns:
        SchedulerResult with the outcome of the orchestrated pipeline execution.
    """
    changeset = list(changeset)
    changeset_keys = {(cf.func["file_path"], cf.func["name"]) for cf in changeset}
    repo_functions = _repo_functions_excluding(db, repository_id, changeset_keys)
    fetch_existing_doc = _make_fetch_existing_doc(db, repository_id)
    doc_fn = document_fn or make_pipeline_document_fn(session_factory, repository_id, commit_sha)
 
    return await process_changeset(
        changeset,
        document_fn=doc_fn,
        repo_functions=repo_functions,
        fetch_existing_doc=fetch_existing_doc,
        concurrency=concurrency,
    )
 
 
def run_repo_changeset(
    db, session_factory, repository_id, commit_sha, changeset,
    concurrency=4, document_fn=None,
):
    """Sync entrypoint (backfill). Wraps the async one with asyncio.run."""
    return asyncio.run(run_repo_changeset_async(
        db, session_factory, repository_id, commit_sha, changeset,
        concurrency=concurrency, document_fn=document_fn,
    ))
 