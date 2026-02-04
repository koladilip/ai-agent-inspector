"""
Tests for storage exporter.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_inspector.core.config import TraceConfig
from agent_inspector.core.events import EventType, create_run_end, create_run_start
from agent_inspector.storage.exporter import StorageExporter


@pytest.fixture
def config():
    return TraceConfig(
        compression_enabled=False,
        encryption_enabled=False,
    )


def test_exporter_run_start_inserts_run(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()

        event = create_run_start(run_id="run-1", run_name="test").to_dict()
        exporter.export_batch([event])

        assert db_instance.insert_run.called
        assert db_instance.insert_steps.called


def test_exporter_run_end_updates_run(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()

        event = create_run_end(
            run_id="run-1",
            status="completed",
            completed_at=123,
            duration_ms=10,
            delete_run=False,
        ).to_dict()
        exporter.export_batch([event])

        db_instance.update_run.assert_called_once()
        # run_end should not be stored as a step
        db_instance.insert_steps.assert_not_called()


def test_exporter_run_end_deletes_run(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()

        event = create_run_end(
            run_id="run-1",
            status="deleted",
            completed_at=123,
            duration_ms=10,
            delete_run=True,
        ).to_dict()
        exporter.export_batch([event])

        db_instance.delete_run.assert_called_once()
        db_instance.insert_steps.assert_not_called()


def test_exporter_skips_failed_processing(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.side_effect = Exception("boom")
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()

        event = {
            "event_id": "evt-1",
            "run_id": "run-1",
            "timestamp_ms": 1,
            "type": EventType.LLM_CALL.value,
        }
        exporter.export_batch([event])

    db_instance.insert_steps.assert_not_called()


def test_exporter_processes_non_run_events(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()

        event = {
            "event_id": "evt-1",
            "run_id": "run-1",
            "timestamp_ms": 1,
            "type": EventType.LLM_CALL.value,
        }
        exporter.export_batch([event])

        db_instance.insert_steps.assert_called_once()


def test_exporter_shutdown_closes_db(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()
        exporter.shutdown()

        db_instance.close.assert_called_once()


def test_exporter_empty_batch_noop(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()
        exporter.export_batch([])

        db_instance.insert_steps.assert_not_called()


def test_exporter_initialize_idempotent(config):
    with patch("agent_inspector.storage.exporter.Database") as db_mock, patch(
        "agent_inspector.storage.exporter.ProcessingPipeline"
    ) as pipeline_mock:
        db_instance = MagicMock()
        db_mock.return_value = db_instance
        pipeline_instance = MagicMock()
        pipeline_instance.process.return_value = b"data"
        pipeline_mock.return_value = pipeline_instance

        exporter = StorageExporter(config)
        exporter.initialize()
        exporter.initialize()

        db_instance.initialize.assert_called_once()
