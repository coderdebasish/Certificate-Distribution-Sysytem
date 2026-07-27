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
import time

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
        queue_items: list[EmailQueueItem],
        provider: EmailProvider,
        on_sent_callback,          # Callable[[EmailQueueItem], None]
        on_failed_callback,        # Callable[[EmailQueueItem, str], None]
        delay_seconds: int = 5,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self._queue_items = queue_items
        self._provider = provider
        self._on_sent = on_sent_callback
        self._on_failed = on_failed_callback
        self._delay = delay_seconds
        self._max_retries = max_retries

    def _run(self) -> None:
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
            result = self._provider.send(message)
            if result.success:
                return True
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt, self._max_retries, item.to_email, result.error_message,
            )
            self._emit(Signal.log(
                f"  Retry {attempt}/{self._max_retries} for {item.to_email}", level="WARNING"
            ))
            if attempt < self._max_retries:
                time.sleep(5)   # Short pause before retry

        self._on_failed(item, result.error_message)
        return False
