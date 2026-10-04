"""Runs one pipeline action at a time on a background thread.

One at a time keeps e.g. "clear database" from racing a report run. A new
thread per job is fine for Playwright because the PDF actions close their
browser before they return.
"""

import logging
import threading
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class Busy(Exception):
    """Raised by submit() while another job is still running."""


class Cancelled(Exception):
    """Raised inside a job at its next progress() call after cancel()."""


@dataclass
class Job:
    id: str
    name: str
    state: str = "running"  # running | done | failed | cancelled
    done: int = 0
    total: int = 0
    message: str = ""
    result: object = None
    error: str | None = None
    cancel_requested: bool = False


class JobRunner:
    def __init__(self, inline: bool = False):
        self.inline = inline  # tests: run the job before submit() returns
        self.current: Job | None = None
        self._lock = threading.Lock()

    def submit(self, name: str, fn, *args, **kwargs) -> Job:
        with self._lock:
            if self.current and self.current.state == "running":
                raise Busy(self.current.name)
            job = self.current = Job(uuid.uuid4().hex[:8], name)

        def progress(done: int, total: int, message: str) -> None:
            # Long actions report between steps - the only safe place to stop.
            if job.cancel_requested:
                raise Cancelled
            job.done, job.total, job.message = done, total, message

        def run():
            try:
                job.result = fn(*args, progress=progress, **kwargs)
                job.state = "done"
            except Cancelled:
                job.state = "cancelled"
            except PermissionError as e:
                job.error = f"Can't write {e.filename or 'the file'} - is it open in another program?"
                job.state = "failed"
            except Exception as e:
                logger.exception(f"Job failed: {name}")
                job.error = str(e)
                job.state = "failed"

        if self.inline:
            run()
        else:
            threading.Thread(target=run, name=f"job-{job.id}", daemon=True).start()
        return job

    def cancel(self) -> None:
        if self.current and self.current.state == "running":
            self.current.cancel_requested = True
