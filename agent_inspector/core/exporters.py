"""
Composite and extensible exporter implementations for Agent Inspector.

Provides CompositeExporter for fan-out to multiple backends (e.g., local DB
plus remote API) without changing Trace usage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .interfaces import Exporter

logger = logging.getLogger(__name__)


class CompositeExporter(Exporter):
    """
    Exporter that forwards batches to multiple exporters in sequence.

    Use this to send trace events to several backends (e.g., SQLite + HTTP).
    Each exporter is initialized, receives every batch, and is shut down in
    order. A failure in one exporter is logged and does not stop the others.
    """

    def __init__(self, exporters: List[Exporter]):
        """
        Initialize composite with a list of exporters.

        Args:
            exporters: Ordered list of exporters. Each will receive every batch.
        """
        if not exporters:
            raise ValueError("CompositeExporter requires at least one exporter")
        self._exporters = list(exporters)

    def initialize(self) -> None:
        """Initialize all child exporters."""
        for i, exporter in enumerate(self._exporters):
            try:
                exporter.initialize()
            except Exception as e:
                logger.exception(
                    "CompositeExporter: failed to initialize exporter %s: %s",
                    i,
                    e,
                )
                raise

    def export_batch(self, events: List[Dict[str, Any]]) -> None:
        """Forward batch to every exporter. Logs and continues on per-exporter failure."""
        for i, exporter in enumerate(self._exporters):
            try:
                exporter.export_batch(events)
            except Exception as e:
                logger.exception(
                    "CompositeExporter: exporter %s failed on batch of %s events: %s",
                    i,
                    len(events),
                    e,
                )
                # Continue to other exporters; do not swallow silently

    def shutdown(self) -> None:
        """Shutdown all exporters in reverse order (LIFO)."""
        for exporter in reversed(self._exporters):
            try:
                exporter.shutdown()
            except Exception as e:
                logger.exception("CompositeExporter: shutdown error: %s", e)
