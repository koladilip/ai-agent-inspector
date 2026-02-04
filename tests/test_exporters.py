"""
Tests for composite and extensible exporters.
"""

from unittest.mock import MagicMock

import pytest

from agent_inspector.core.exporters import CompositeExporter


class TestCompositeExporter:
    """Test CompositeExporter fan-out and error handling."""

    def test_requires_at_least_one_exporter(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeExporter([])

    def test_forwards_initialize_to_all(self):
        a = MagicMock()
        b = MagicMock()
        comp = CompositeExporter([a, b])
        comp.initialize()
        a.initialize.assert_called_once()
        b.initialize.assert_called_once()

    def test_forwards_export_batch_to_all(self):
        a = MagicMock()
        b = MagicMock()
        comp = CompositeExporter([a, b])
        comp.initialize()
        batch = [{"event_id": "e1", "type": "llm_call"}]
        comp.export_batch(batch)
        a.export_batch.assert_called_once_with(batch)
        b.export_batch.assert_called_once_with(batch)

    def test_export_batch_failure_in_one_continues_to_others(self):
        a = MagicMock()
        b = MagicMock()
        b.export_batch.side_effect = RuntimeError("boom")
        comp = CompositeExporter([a, b])
        comp.initialize()
        comp.export_batch([{"event_id": "e1"}])
        a.export_batch.assert_called_once()
        b.export_batch.assert_called_once()

    def test_shutdown_reverse_order(self):
        a = MagicMock()
        b = MagicMock()
        comp = CompositeExporter([a, b])
        comp.shutdown()
        b.shutdown.assert_called_once()
        a.shutdown.assert_called_once()
