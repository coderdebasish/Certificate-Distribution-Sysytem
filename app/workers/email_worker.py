"""
app.workers.email_worker
=========================
Background worker that sends emails from the email queue.

After every successful send:
  - Updates the queue item status in the database
  - Updates participant email_status
  - Saves the project state (crash-safe)

Supports pause, resume, and stop between emails.
"""

from __future__ import annotations

import logging
import queue
import time
from typing import Callable, Optional

from app.models.email_queue import EmailQueueItem, QueueItemStatus
from app.services.email.base import EmailProvider, EmailMessage
from app.workers.base_worker import BaseWorker
from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)


class EmailWorker(BaseWorker):
    """
    Sends emails sequentially from a pre-generated queue.

    The worker respects the configured delay between emails and supports
    configurable retry on failure.
    """

    def __init__(
        self,
        queue_items: list[EmailQueueItem] | None = None,
        provider: EmailProvider | None = None,
        email_provider: EmailProvider | None = None,
        on_sent_callback: Optional[Callable[[EmailQueueItem], None]] = None,
        on_failed_callback: Optional[Callable[[EmailQueueItem, str], None]] = None,
        signal_queue: Optional[queue.Queue[Signal]] = None,
        db_conn=None,
        project_id: int = 0,
        delay_seconds: int = 5,
        batch_size: int = 25,
        batch_pause_seconds: int = 60,
        max_retries: int = 3,
    ) -> None:
        super().__init__(signal_queue=signal_queue)
        self._queue_items = queue_items or []
        self._provider = email_provider or provider
        self._on_sent = on_sent_callback
        self._on_failed = on_failed_callback
        self._db_conn = db_conn
        self._project_id = project_id
        self._delay = delay_seconds
        self._batch_size = batch_size
        self._batch_pause_seconds = batch_pause_seconds
        self._max_retries = max_retries

    def _run(self) -> None:
        if not self._queue_items and self._db_conn and self._project_id:
            # Load queue from database if not explicitly passed
            from app.database.repositories.queue_repo import QueueRepository
            repo = QueueRepository(self._db_conn)
            self._queue_items = repo.get_all(self._project_id)

        total = len(self._queue_items)
        if total == 0:
            self._emit(Signal.error("Email queue is empty."))
            return

        sent = 0
        failed = 0
        self._emit(Signal.log(f"Starting email queue: {total} email(s) to send."))

        for idx, item in enumerate(self._queue_items, start=1):
            if self._should_stop():
                self._emit(Signal(type=SignalType.WORKER_STOPPED,
                                  payload={"sent": sent, "failed": failed}))
                return
            self._wait_if_paused()

            self._emit(Signal.progress(idx, total, f"Sending to {item.to_email}"))
            self._emit(Signal.log(f"Sending → {item.to_name} <{item.to_email}>"))

            success = self._send_with_retry(item)
            if success:
                sent += 1
                if self._on_sent:
                    self._on_sent(item)
                self._emit(Signal(
                    type=SignalType.EMAIL_SENT,
                    payload={"to": item.to_email, "name": item.to_name, "position": idx},
                ))
                self._emit(Signal.log(f"  ✓ Delivered to {item.to_email}"))
            else:
                failed += 1
                self._emit(Signal(
                    type=SignalType.EMAIL_FAILED,
                    payload={"to": item.to_email, "name": item.to_name, "position": idx},
                ))
                self._emit(Signal.log(f"  ✗ Failed: {item.to_email}", level="ERROR"))

            # Delay between emails (except after last)
            if idx < total and not self._should_stop():
                if self._batch_size > 0 and idx % self._batch_size == 0:
                    self._emit(Signal.log(f"⏸ Batch pause of {self._batch_pause_seconds}s after {idx} emails (Gmail quota safeguard)..."))
                    time.sleep(self._batch_pause_seconds)
                elif self._delay > 0:
                    time.sleep(self._delay)

        self._emit(Signal(
            type=SignalType.EMAIL_QUEUE_COMPLETE,
            payload={"sent": sent, "failed": failed, "total": total},
        ))
        self._emit(Signal.complete(
            f"Done. Sent: {sent} / Failed: {failed} / Total: {total}"
        ))

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _send_with_retry(self, item: EmailQueueItem) -> bool:
        """Attempt to send, retrying up to max_retries times."""
        message = EmailMessage(
            to_email=item.to_email,
            to_name=item.to_name,
            subject=item.subject,
            body_html=item.body_html,
            attachment_path=item.attachment_path,
        )

        for attempt in range(1, self._max_retries + 1):
            if self._should_stop():
                return False
            result = self._provider.send(message) if self._provider else None
            if result and result.success:
                return True
            err = result.error_message if result else "No email provider configured"
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt, self._max_retries, item.to_email, err,
            )
            self._emit(Signal.log(
                f"  Retry {attempt}/{self._max_retries} for {item.to_email}", level="WARNING"
            ))
            if attempt < self._max_retries:
                time.sleep(5)

        if self._on_failed:
            self._on_failed(item, err)
        return False
