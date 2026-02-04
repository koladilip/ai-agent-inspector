"""
Queue worker tests.
"""

import queue
import time
from unittest.mock import MagicMock

from agent_inspector.core.queue import EventQueue


def test_queue_flushes_batches():
    exporter = MagicMock()
    exporter_calls = []

    def _export(batch):
        exporter_calls.append(list(batch))

    q = EventQueue(maxsize=10, exporter=_export)
    q.start(batch_size=2, batch_timeout_ms=200)

    q.put_nowait({"id": 1})
    q.put_nowait({"id": 2})

    time.sleep(0.3)
    q.stop()

    assert exporter_calls
    assert len(exporter_calls[0]) == 2


def test_queue_timeout_flush():
    exporter_calls = []

    def _export(batch):
        exporter_calls.append(list(batch))

    q = EventQueue(maxsize=10, exporter=_export)
    q.start(batch_size=10, batch_timeout_ms=100)

    q.put_nowait({"id": 1})
    time.sleep(0.2)
    q.stop()

    assert exporter_calls
    assert exporter_calls[0][0]["id"] == 1


def test_queue_full_drops_event():
    exporter_calls = []

    def _export(batch):
        exporter_calls.append(list(batch))

    q = EventQueue(maxsize=1, exporter=_export)
    q.start(batch_size=10, batch_timeout_ms=100)

    assert q.put_nowait({"id": 1}) is True
    assert q.put_nowait({"id": 2}) is False

    q.stop()

    stats = q.get_stats()
    assert stats["events_dropped"] >= 1


def test_queue_stats_and_is_alive():
    q = EventQueue(maxsize=2, exporter=lambda _batch: None)
    q.start(batch_size=1, batch_timeout_ms=50)
    q.put_nowait({"id": 1})
    stats = q.get_stats()
    assert stats["events_queued"] >= 1
    assert stats["queue_maxsize"] == 2
    assert q.is_alive() is True
    q.stop()
    assert q.is_alive() is False


def test_queue_manager_lifecycle():
    from agent_inspector.core.queue import EventQueueManager
    from agent_inspector.core.config import TraceConfig

    manager = EventQueueManager(TraceConfig())
    assert manager.get_queue() is None

    def _export(_batch):
        return None

    manager.initialize(_export)
    assert manager.get_queue() is not None
    manager.shutdown()
    assert manager.get_queue() is None


def test_queue_start_twice_is_noop():
    q = EventQueue(maxsize=2, exporter=lambda _batch: None)
    q.start(batch_size=1, batch_timeout_ms=50)
    q.start(batch_size=1, batch_timeout_ms=50)
    assert q.is_alive() is True
    q.stop()


def test_queue_stop_without_start():
    q = EventQueue(maxsize=2, exporter=lambda _batch: None)
    q.stop()


def test_queue_stop_timeout_path():
    class DummyThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            return None

    q = EventQueue(maxsize=2, exporter=lambda _batch: None)
    q._started = True
    q._worker_thread = DummyThread()
    q.stop(timeout_ms=1)
    assert q._started is False


def test_queue_stop_normal_path():
    class DummyThread:
        def __init__(self):
            self._alive = True

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            self._alive = False

    q = EventQueue(maxsize=2, exporter=lambda _batch: None)
    q._started = True
    q._worker_thread = DummyThread()
    q.stop(timeout_ms=1)
    assert q.is_alive() is False


def test_worker_loop_flushes_remaining_batch(monkeypatch):
    exported = []

    def _export(batch):
        exported.append(list(batch))

    q = EventQueue(maxsize=2, exporter=_export)
    calls = {"count": 0}

    def _get(block=True, timeout=None):
        # get_nowait() calls get(block=False); main loop calls get(timeout=0.1)
        if not block:
            raise queue.Empty
        calls["count"] += 1
        if calls["count"] == 1:
            return {"id": 1}
        q._stop_event.set()
        raise RuntimeError("boom")

    monkeypatch.setattr(q._queue, "get", _get)
    q._worker_loop(batch_size=10, batch_timeout=1000)
    assert exported == [[{"id": 1}]]


def test_flush_batch_error_path():
    def _boom(_batch):
        raise RuntimeError("boom")

    q = EventQueue(maxsize=2, exporter=_boom)
    q._flush_batch([{"id": 1}])


def test_queue_manager_initialize_twice():
    from agent_inspector.core.queue import EventQueueManager
    from agent_inspector.core.config import TraceConfig

    manager = EventQueueManager(TraceConfig())

    def _export(_batch):
        return None

    manager.initialize(_export)
    manager.initialize(_export)
    manager.shutdown()


def test_put_blocking_success():
    """put(block=True) succeeds when queue has space."""
    exported = []

    def _export(batch):
        exported.append(list(batch))

    q = EventQueue(maxsize=5, exporter=_export)
    result = q.put({"id": 1, "type": "run_start"}, block=True, timeout=0.5)
    assert result is True
    assert q._events_queued == 1


def test_put_blocking_timeout_returns_false():
    """put(block=True, timeout=...) returns False when queue stays full."""
    q = EventQueue(maxsize=1, exporter=lambda _batch: None)
    q.put({"id": 1}, block=False)
    # Queue is full; blocking put with short timeout should fail
    result = q.put({"id": 2}, block=True, timeout=0.01)
    assert result is False
    assert q._events_dropped >= 1
