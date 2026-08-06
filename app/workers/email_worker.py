"""
app.workers.email_worker
=========================
Background worker that sends emails from the email queue.

After every successful or failed send:
  - Updates the queue item status & attempt count in the database
  - Updates participant email_status in the database
  - Emits real-time thread signals for instant UI refresh
"""

from __future__ import annotations

import logging
import queue
import random
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

    The worker respects configured delay and updates the SQLite database
    immediately after each dispatch for crash resiliency and live UI updates.
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
        draft_mode: bool = False,
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
        self._draft_mode = draft_mode

    def _run(self) -> None:
        q_repo = None
        p_repo = None

        if self._db_conn:
            try:
                from app.database.repositories.queue_repo import QueueRepository
                from app.database.repositories.participant_repo import ParticipantRepository
                q_repo = QueueRepository(self._db_conn)
                p_repo = ParticipantRepository(self._db_conn)
            except Exception as exc:
                logger.error("Failed to initialize repositories in EmailWorker: %s", exc)

        if not self._queue_items and q_repo and self._project_id:
            self._queue_items = q_repo.get_all(self._project_id)

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
            self._emit(Signal.log(f"Sending [{idx}/{total}] → {item.to_name} <{item.to_email}>"))

            success, last_err = self._send_with_retry(item, q_repo)
            if success:
                sent += 1
                item.status = QueueItemStatus.SENT
                if q_repo and item.id:
                    try:
                        q_repo.mark_sent(item.id)
                    except Exception as exc:
                        logger.error("Failed to mark item %d sent in DB: %s", item.id, exc)

                if p_repo and item.participant_id:
                    try:
                        p_repo.mark_email_sent(item.participant_id)
                    except Exception as exc:
                        logger.error("Failed to mark participant %d sent in DB: %s", item.participant_id, exc)

                if self._on_sent:
                    self._on_sent(item)
                self._emit(Signal(
                    type=SignalType.EMAIL_SENT,
                    payload={"to": item.to_email, "name": item.to_name, "position": idx},
                ))
                if self._draft_mode:
                    self._emit(Signal.log(f"  📥 Saved as Gmail Draft for {item.to_email}"))
                else:
                    self._emit(Signal.log(f"  ✓ Delivered to {item.to_email}"))
            else:
                failed += 1
                item.status = QueueItemStatus.FAILED
                err_text = last_err or "Delivery failed"
                if q_repo and item.id:
                    try:
                        q_repo.mark_failed(item.id, err_text)
                    except Exception as exc:
                        logger.error("Failed to mark item %d failed in DB: %s", item.id, exc)

                if p_repo and item.participant_id:
                    try:
                        p_repo.mark_email_failed(item.participant_id, err_text)
                    except Exception as exc:
                        logger.error("Failed to mark participant %d failed in DB: %s", item.participant_id, exc)

                if self._on_failed:
                    self._on_failed(item, err_text)
                self._emit(Signal(
                    type=SignalType.EMAIL_FAILED,
                    payload={"to": item.to_email, "name": item.to_name, "position": idx, "error": err_text},
                ))
                self._emit(Signal.log(f"  ✗ Failed: {item.to_email} ({err_text})", level="ERROR"))

            # Delay between emails with anti-spam random jitter
            if idx < total and not self._should_stop():
                if self._batch_size > 0 and idx % self._batch_size == 0:
                    pause = self._batch_pause_seconds + random.uniform(5.0, 15.0)
                    self._emit(Signal.log(f"⏸ Anti-Spam Safeguard: Pausing {int(pause)}s after batch of {idx} emails..."))
                    time.sleep(pause)
                elif self._delay > 0:
                    jitter = random.uniform(1.5, 4.5)
                    total_delay = round(self._delay + jitter, 1)
                    time.sleep(total_delay)

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

    def _send_with_retry(self, item: EmailQueueItem, q_repo=None) -> tuple[bool, str]:
        """Attempt to send, retrying up to max_retries times. Return (success, error_message)."""
        message = EmailMessage(
            to_email=item.to_email,
            to_name=item.to_name,
            subject=item.subject,
            body_html=item.body_html,
            attachment_path=item.attachment_path,
        )

        last_err = ""
        for attempt in range(1, self._max_retries + 1):
            if self._should_stop():
                return False, "Stopped by user"

            item.attempts = attempt
            if q_repo and item.id:
                try:
                    q_repo.mark_failed(item.id, f"Attempt {attempt} in progress...")
                except Exception:
                    pass

            if self._draft_mode and hasattr(self._provider, "create_draft"):
                result = self._provider.create_draft(message)
            else:
                result = self._provider.send(message) if self._provider else None
            if result and result.success:
                return True, ""

            last_err = result.error_message if result else "No email provider configured"
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt, self._max_retries, item.to_email, last_err,
            )
            self._emit(Signal.log(
                f"  Retry {attempt}/{self._max_retries} for {item.to_email}: {last_err}", level="WARNING"
            ))
            if attempt < self._max_retries:
                time.sleep(2)

        return False, last_err
