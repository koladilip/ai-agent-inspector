"""
Storage exporter for Agent Inspector.

Implements the Exporter interface by processing events and
writing them to the database.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..core.events import EventType
from ..core.interfaces import Exporter
from ..processing.pipeline import ProcessingPipeline
from .database import Database

logger = logging.getLogger(__name__)


class StorageExporter(Exporter):
    """Exporter that writes events into SQLite storage."""

    def __init__(self, config):
        self.config = config
        self._database = Database(config)
        self._pipeline = ProcessingPipeline(config)
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self._database.initialize()
        self._initialized = True

    def export_batch(self, events: List[Dict[str, Any]]) -> None:
        """
        Process and store a batch of events.

        Handles run_start and run_end lifecycle updates and stores
        all other events as steps.
        """
        if not events:
            return

        steps_to_insert = []

        for event_dict in events:
            event_type = event_dict.get("type")

            if event_type == EventType.RUN_START.value:
                run_data = {
                    "id": event_dict.get("run_id"),
                    "name": event_dict.get("run_name", ""),
                    "status": "running",
                    "started_at": event_dict.get("timestamp_ms"),
                    "agent_type": event_dict.get("agent_type"),
                    "user_id": event_dict.get("user_id"),
                    "session_id": event_dict.get("session_id"),
                }
                self._database.insert_run(run_data)

            if event_type == EventType.RUN_END.value:
                if event_dict.get("delete_run"):
                    self._database.delete_run(event_dict.get("run_id", ""))
                else:
                    self._database.update_run(
                        run_id=event_dict.get("run_id", ""),
                        status=event_dict.get("run_status"),
                        completed_at=event_dict.get("completed_at"),
                        duration_ms=event_dict.get("duration_ms"),
                    )
                # Skip storing run_end as a step for now
                continue

            try:
                processed = self._pipeline.process(event_dict)
                steps_to_insert.append((event_dict, processed))
            except Exception as e:
                logger.error(
                    "Failed to process event %s: %s",
                    event_dict.get("event_id"),
                    e,
                )

        if steps_to_insert:
            self._database.insert_steps(steps_to_insert)

    def shutdown(self) -> None:
        self._database.close()
