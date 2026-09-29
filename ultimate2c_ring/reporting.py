"""Per-thread progress observers. Display failures must not interrupt recovery."""
from contextlib import contextmanager
from contextvars import ContextVar

_observer = ContextVar('ring_observer', default=None)


@contextmanager
def observe(callback):
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def emit(kind, **values):
    callback = _observer.get()
    if callback is None:
        return False
    try:
        callback(kind, values)
    except Exception:
        # USB verification and rollback must survive a broken display/logger.
        pass
    return True


def message(text):
    if not emit('message', text=str(text)):
        print(text, flush=True)


def progress(stage, percent):
    if not emit('progress', stage=stage, percent=percent):
        print(f'  {percent}%', flush=True)
