"""
Non-blocking event queue and background worker for Agent Inspector.

Provides an in-memory queue that never blocks agent execution, with a
background thread that processes events in batches.
"""

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .config import TraceConfig

logger = logging.getLogger(__name__)


class EventQueue:
    """
    Non-blocking in-memory queue for trace events.

    This queue ensures that agent execution is never blocked by telemetry
    operations. Events are queued in memory and processed asynchronously by
    a background worker thread.
    """

    def __init__(
        self,
        maxsize: int = 1000,
        exporter: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ):
        """
        Initialize the event queue.

        Args:
            maxsize: Maximum number of events in the queue (default: 1000).
            exporter: Function to call with batched events for processing.
        """
        self.maxsize = maxsize
        self.exporter = exporter

        # Thread-safe queue
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)

        # Worker thread control
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

        # Statistics
        self._events_queued = 0
        self._events_dropped = 0
        self._events_processed = 0
        self._lock = threading.Lock()

    def start(
        self,
        batch_size: int = 50,
        batch_timeout_ms: int = 1000,
    ):
        """
        Start the background worker thread.

        Args:
            batch_size: Number of events to batch before processing (default: 50).
            batch_timeout_ms: Maximum time to wait before flushing batch (default: 1000ms).
        """
        if self._started:
            logger.warning("Worker thread already started")
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(batch_size, batch_timeout_ms / 1000.0),
            daemon=True,
            name="AgentInspectorWorker",
        )
        self._worker_thread.start()
        self._started = True
        logger.info("Background worker thread started")

    def stop(self, timeout_ms: int = 5000):
        """
        Stop the background worker thread and flush remaining events.

        Args:
            timeout_ms: Maximum time to wait for worker to finish (default: 5000ms).
        """
        if not self._started:
            return

        logger.info("Stopping background worker thread...")
        self._stop_event.set()

        # Wait for worker to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout_ms / 1000.0)
            if self._worker_thread.is_alive():
                logger.warning(
                    f"Worker thread did not stop within {timeout_ms}ms timeout"
                )
            else:
                logger.info("Background worker thread stopped")

        self._started = False

    def put_nowait(self, event: Dict[str, Any]) -> bool:
        """
        Add an event to the queue without blocking.

        If the queue is full, the event is dropped and logged.

        Args:
            event: Event dictionary to queue.

        Returns:
            True if event was queued, False if dropped.
        """
        return self.put(event, block=False)

    def put(
        self,
        event: Dict[str, Any],
        block: bool = False,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Add an event to the queue, optionally blocking until space is available.

        Args:
            event: Event dictionary to queue.
            block: If True, block until the event can be queued or timeout.
            timeout: Max seconds to block (used only when block=True).

        Returns:
            True if event was queued, False if dropped or timeout.
        """
        try:
            if block:
                self._queue.put(event, block=True, timeout=timeout or 5.0)
            else:
                self._queue.put_nowait(event)
            with self._lock:
                self._events_queued += 1
            return True
        except queue.Full:
            with self._lock:
                self._events_dropped += 1
            if block:
                logger.warning(
                    "Event queue full, block timeout reached (run_end may be dropped)"
                )
            else:
                logger.warning(
                    f"Event queue full ({self.maxsize} events), dropping event. "
                    f"Total dropped: {self._events_dropped}"
                )
            return False

    def _worker_loop(self, batch_size: int, batch_timeout: float):
        """
        Background worker thread main loop.

        Collects events in batches and passes them to the exporter.

        Args:
            batch_size: Number of events to batch before processing.
            batch_timeout: Maximum time to wait before flushing batch (seconds).
        """
        logger.info("Worker thread started")
        last_flush_time = time.time()
        batch: List[Dict[str, Any]] = []

        while not self._stop_event.is_set():
            try:
                # Wait for events or timeout
                try:
                    event = self._queue.get(timeout=0.1)
                    batch.append(event)
                except queue.Empty:
                    # No events, check if we should flush
                    pass

                # Check if we should flush the batch
                current_time = time.time()
                time_since_flush = current_time - last_flush_time

                should_flush = (
                    len(batch) >= batch_size
                    or time_since_flush >= batch_timeout
                    or self._stop_event.is_set()
                )

                if should_flush and batch:
                    self._flush_batch(batch)
                    batch = []
                    last_flush_time = current_time

            except Exception as e:
                logger.exception(f"Error in worker thread: {e}")
                # Continue processing despite errors

        # Drain queue and flush all remaining events before exiting
        try:
            while True:
                event = self._queue.get_nowait()
                batch.append(event)
        except queue.Empty:
            pass
        if batch:
            self._flush_batch(batch)

        logger.info("Worker thread exiting")

    def _flush_batch(self, batch: List[Dict[str, Any]]):
        """
        Process a batch of events through the exporter.

        Args:
            batch: List of events to process.
        """
        try:
            if self.exporter:
                self.exporter(batch)
            with self._lock:
                self._events_processed += len(batch)
            logger.debug(f"Flushed batch of {len(batch)} events")
        except Exception as e:
            logger.exception(f"Error processing batch: {e}")

    def get_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue statistics.
        """
        with self._lock:
            return {
                "events_queued": self._events_queued,
                "events_dropped": self._events_dropped,
                "events_processed": self._events_processed,
                "queue_size": self._queue.qsize(),
                "queue_maxsize": self.maxsize,
            }

    def is_alive(self) -> bool:
        """
        Check if the worker thread is running.

        Returns:
            True if worker thread is alive, False otherwise.
        """
        return self._worker_thread is not None and self._worker_thread.is_alive()


class EventQueueManager:
    """
    Manager for the event queue lifecycle.

    Handles initialization, configuration, and cleanup of the event queue.
    """

    def __init__(self, config: TraceConfig):
        """
        Initialize the event queue manager.

        Args:
            config: TraceConfig instance for queue configuration.
        """
        self.config = config
        self._queue: Optional[EventQueue] = None

    def initialize(self, exporter: Callable[[List[Dict[str, Any]]], None]):
        """
        Initialize the event queue with an exporter.

        Args:
            exporter: Function to process event batches.
        """
        if self._queue is not None:
            logger.warning("Event queue already initialized")
            return

        self._queue = EventQueue(
            maxsize=self.config.queue_size,
            exporter=exporter,
        )
        self._queue.start(
            batch_size=self.config.batch_size,
            batch_timeout_ms=self.config.batch_timeout_ms,
        )
        logger.info(f"Event queue initialized (maxsize={self.config.queue_size})")

    def shutdown(self):
        """Shutdown the event queue and flush remaining events."""
        if self._queue is None:
            return

        logger.info("Shutting down event queue...")
        self._queue.stop()
        self._queue = None
        logger.info("Event queue shut down")

    def get_queue(self) -> Optional[EventQueue]:
        """
        Get the event queue instance.

        Returns:
            EventQueue instance if initialized, None otherwise.
        """
        return self._queue
