"""
app.workers.base_worker
========================
Abstract base class for all background workers.

Workers run in daemon threads and communicate progress back to the UI via
a thread-safe queue of Signal objects.  The UI polls this queue using the
CustomTkinter ``after()`` mechanism — never using direct widget access.
"""

from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod

from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """
    Abstract background worker.

    Subclasses implement ``_run()`` and call ``self._emit(signal)`` to send
    progress updates.  The UI retrieves signals via ``self.signal_queue``.
    """

    def __init__(self, signal_queue: queue.Queue[Signal] | None = None) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()   # Not paused by default
        self.signal_queue: queue.Queue[Signal] = signal_queue if signal_queue is not None else queue.Queue()

    # -----------------------------------------------------------------------
    # Control API (called from UI thread)
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker in a daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("%s already running.", self.__class__.__name__)
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(target=self._safe_run, daemon=True)
        self._thread.start()
        logger.debug("%s started.", self.__class__.__name__)

    def pause(self) -> None:
        """Pause processing after the current item finishes."""
        self._pause_event.clear()
        self._emit(Signal(type=SignalType.WORKER_PAUSED))

    def resume(self) -> None:
        """Resume a paused worker."""
        self._pause_event.set()

    def stop(self) -> None:
        """Request graceful stop.  Current item is finished before stopping."""
        self._stop_event.set()
        self._pause_event.set()   # Unblock if paused

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    # -----------------------------------------------------------------------
    # Abstract implementation
    # -----------------------------------------------------------------------

    @abstractmethod
    def _run(self) -> None:
        """Subclasses implement the actual work here."""

    # -----------------------------------------------------------------------
    # Protected helpers (used by subclasses)
    # -----------------------------------------------------------------------

    def _emit(self, signal: Signal) -> None:
        """Enqueue a signal for the UI thread to consume."""
        self.signal_queue.put_nowait(signal)

    def _should_stop(self) -> bool:
        return self._stop_event.is_set()

    def _wait_if_paused(self) -> None:
        """Block until resumed or stopped."""
        self._pause_event.wait()

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _safe_run(self) -> None:
        """Wrapper that catches unexpected exceptions."""
        self._emit(Signal(type=SignalType.WORKER_STARTED))
        try:
            self._run()
        except Exception as exc:
            logger.exception("Unhandled error in %s", self.__class__.__name__)
            self._emit(Signal.error(
                message=f"Unexpected error in {self.__class__.__name__}",
                details=str(exc),
            ))
        finally:
            logger.debug("%s finished.", self.__class__.__name__)
