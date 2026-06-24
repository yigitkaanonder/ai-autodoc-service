import asyncio
import heapq
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

try:
    from services.call_graph import Condensation
except ImportError:
    from call_graph import Condensation


@dataclass
class SchedulerResult:
    results: dict = field(default_factory=dict)
    failures: dict = field(default_factory=dict)
    completion_order: list = field(default_factory=list)
    attempts: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failures


def bottom_levels(cond: Condensation) -> dict:
    blevel: dict = {}
    for c in reversed(cond.topological_order()):
        downstream = cond.dependents.get(c, ())
        blevel[c] = 1 + max((blevel[d] for d in downstream), default=0)
    return blevel


async def run_scheduler(
    cond: Condensation,
    worker: Callable[[int], Awaitable[Any]],
    concurrency: int = 4,
    max_retries: int = 2,
    base_backoff: float = 0.5,
) -> SchedulerResult:

    n = len(cond.components)
    result = SchedulerResult()
    if n == 0:
        return result
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    blevel = bottom_levels(cond)
    remaining = {c: cond.in_degree(c) for c in range(n)}
    # Min-heap on (-blevel, comp_id): highest critical-path first, id breaks ties
    # so dispatch is deterministic.
    ready = [(-blevel[c], c) for c in range(n) if remaining[c] == 0]
    heapq.heapify(ready)

    running: dict = {}  # asyncio.Task -> component id

    async def attempt(comp: int):
        """Run worker(comp) with retry+backoff. Never raises; returns a tag."""
        result.attempts[comp] = 0
        last_exc = None
        for tryno in range(max_retries + 1):
            result.attempts[comp] += 1
            try:
                return ("ok", await worker(comp))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_exc = exc
                if tryno < max_retries:
                    await asyncio.sleep(base_backoff * (2 ** tryno))
        return ("err", last_exc)

    def unblock(comp: int):
        """Decrement dependents; push the ones whose deps are now all done."""
        for dep in cond.dependents.get(comp, ()):
            remaining[dep] -= 1
            if remaining[dep] == 0:
                heapq.heappush(ready, (-blevel[dep], dep))

    completed = 0
    while completed < n:
        # Fill free slots with the highest-priority ready components.
        while ready and len(running) < concurrency:
            _, comp = heapq.heappop(ready)
            running[asyncio.create_task(attempt(comp))] = comp

        if not running:
            raise RuntimeError(
                "scheduler stalled: components remain but none are ready"
            )

        done, _ = await asyncio.wait(list(running), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            comp = running.pop(task)
            status, payload = task.result()
            completed += 1
            result.completion_order.append(comp)
            if status == "ok":
                result.results[comp] = payload
            else:
                result.failures[comp] = payload
            # A failed component still unblocks its dependents: they proceed
            # without its documentation as context.
            unblock(comp)

    return result
