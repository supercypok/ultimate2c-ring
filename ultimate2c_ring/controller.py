"""One background operation at a time, with an explicit pre-write handshake."""
from dataclasses import dataclass, field
from queue import SimpleQueue
from threading import Event, Lock, Thread
from . import reporting


@dataclass
class Confirmation:
    plan: dict
    ready: Event = field(default_factory=Event)
    approved: bool = False

    def resolve(self, approved):
        if not self.ready.is_set():
            self.approved = bool(approved)
            self.ready.set()

    def wait(self):
        self.ready.wait()
        return self.approved


class Operations:
    def __init__(self):
        self.events = SimpleQueue()
        self._lock = Lock()
        self._running = False
        self.pending = None
        self.thread = None

    @property
    def running(self):
        with self._lock:
            return self._running

    def confirm(self, plan):
        pending = Confirmation(plan)
        self.pending = pending
        self.events.put(('confirm', pending))
        try:
            return pending.wait()
        finally:
            self.pending = None

    def decline_pending(self):
        if self.pending is not None:
            self.pending.resolve(False)

    def start(self, name, action):
        with self._lock:
            if self._running:
                raise RuntimeError('An operation is already running.')
            self._running = True

        def run():
            try:
                with reporting.observe(lambda kind, values: self.events.put((kind, values))):
                    result = action()
                self.events.put(('result', {'name': name, 'value': result}))
            except Exception as error:
                self.events.put(('error', {'name': name, 'type': type(error).__name__, 'text': str(error)}))
            finally:
                with self._lock:
                    self._running = False
                self.events.put(('finished', {'name': name}))

        # The process must not silently exit halfway through a flash write.
        self.thread = Thread(target=run, name='ring-operation', daemon=False)
        try:
            self.thread.start()
        except BaseException:
            with self._lock:
                self._running = False
            raise
