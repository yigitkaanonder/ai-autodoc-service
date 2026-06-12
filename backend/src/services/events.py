import asyncio
from typing import Dict, Set


class EventHub:
    """
    Tiny in-memory pub/sub used to push live updates to connected
    browsers over Server-Sent Events (SSE).

    One asyncio.Queue is created per connected browser. When a GitHub
    push webhook is handled, the webhook router calls publish() with the
    affected repo, and every browser currently watching that repo gets a
    "refresh" message on its queue.

    This is in-process only (single backend instance), which is exactly
    what we have in development. If you later run multiple backend
    workers, this would need to move to Redis pub/sub, but the public
    interface (subscribe / unsubscribe / publish) would stay the same.
    """

    def __init__(self):
        # repo_full_name -> set of subscriber queues
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # the event loop the SSE endpoints run on; captured on first subscribe
        self._loop = None

    async def subscribe(self, repo_full_name: str) -> asyncio.Queue:
        # Called from inside an async endpoint, so we are on the main loop here.
        # We remember it so publish() (which may run in a worker thread) can
        # safely hand work back to this loop.
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(repo_full_name, set()).add(queue)
        return queue

    def unsubscribe(self, repo_full_name: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(repo_full_name)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(repo_full_name, None)

    def publish(self, repo_full_name: str, message: str = "refresh") -> None:
        """
        Notify every browser watching this repo.

        FastAPI runs plain `def` endpoints (like the webhook handler) in a
        threadpool, so this may be called from a worker thread. Pushing into
        an asyncio.Queue from another thread is unsafe, so we schedule the
        put on the main event loop with call_soon_threadsafe.
        """
        subscribers = self._subscribers.get(repo_full_name)
        if not subscribers:
            return
        for queue in list(subscribers):
            if self._loop is not None:
                self._loop.call_soon_threadsafe(queue.put_nowait, message)
            else:
                queue.put_nowait(message)


# Single shared instance, imported by both the SSE endpoint and the webhook.
event_hub = EventHub()