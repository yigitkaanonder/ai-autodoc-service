import threading

_lock = threading.Lock()
_runs = {}


def register_run(repository_id):
    ev = threading.Event()
    with _lock:
        _runs.setdefault(repository_id, set()).add(ev)
    return ev


def unregister_run(repository_id, ev):
    with _lock:
        runs = _runs.get(repository_id)
        if runs is not None:
            runs.discard(ev)
            if not runs:
                _runs.pop(repository_id, None)


def cancel_repo(repository_id):
    with _lock:
        for ev in _runs.get(repository_id, ()):
            ev.set()
